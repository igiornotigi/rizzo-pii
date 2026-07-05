# -*- coding: utf-8 -*-
"""
Simula il flusso completo del guardrail SENZA LiteLLM/OWUI:
  utente -> [anonimizza] -> "LLM" -> [ricostruisci] -> utente

L'"LLM" finto vede SOLO il testo anonimizzato e risponde citando i placeholder,
come farebbe un LLM vero. Serve a verificare che il testo in input venga
anonimizzato e la risposta venga ricostruita correttamente.

Uso (con rizzo-presidio[model] installato):
    python examples/roundtrip_test.py [model_dir_o_hf_id]
"""
import re
import sys

from rizzo_presidio.engine import (build_recognizers, analyze,
                                   reversible_anonymize, deanonymize)

PH_RE = re.compile(r"\[[A-Z_]+_\d+\]")


def fake_llm(anon_text: str) -> str:
    """LLM finto: vede il testo anonimizzato e risponde riferendosi ai placeholder."""
    phs = list(dict.fromkeys(PH_RE.findall(anon_text)))
    return ("Ho preso in carico la richiesta relativa a " + ", ".join(phs) +
            ". Confermo che procederemo come indicato.")


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "rizzoaiacademy/rizzo-pii-0.3B"
    recs = build_recognizers(model)

    user_text = ("Il Sig. Mario Rossi, C.F. MRTPTR98B24B354B, chiede il bonifico di "
                 "€ 12.500,00 sull'IBAN IT08H8381014592811856239313 in favore della "
                 "Edilnord S.r.l., con recapito mario.rossi@studio.it.")

    print("1. UTENTE                 ->", user_text)
    anon, mapping = reversible_anonymize(user_text, analyze(user_text, recs))
    print("2. VERSO L'LLM (anonimo)  ->", anon)
    reply = fake_llm(anon)
    print("3. RISPOSTA LLM (placehl) ->", reply)
    restored = deanonymize(reply, mapping)
    print("4. ALL'UTENTE (ricostr.)  ->", restored)

    # verifiche: niente PII verso l'LLM, niente placeholder verso l'utente
    assert "Mario Rossi" not in anon and "MRTPTR98B24B354B" not in anon, \
        "PII trapelata verso l'LLM!"
    assert not PH_RE.search(restored), "placeholder non ricostruiti nella risposta!"
    print("\nOK: input anonimizzato verso l'LLM, risposta ricostruita per l'utente.")
    print(f"    ({len(mapping)} entita' mascherate e rimappate)")


if __name__ == "__main__":
    main()
