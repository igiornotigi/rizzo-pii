# -*- coding: utf-8 -*-
"""
Compone il modello + i recognizer regex/checksum in un analizzatore Presidio e
fornisce l'anonimizzazione REVERSIBILE (placeholder <-> valore) per usarlo come
guardrail (LiteLLM / Open WebUI).

Due modalita':
  1) build_recognizers()  -> lista di recognizer, usabili "a mano" (PoC leggero,
     solo presidio-analyzer + transformers). Vedi analyze()/reversible_anonymize().
  2) build_analyzer_engine() -> AnalyzerEngine completo (per il guardrail Presidio
     di LiteLLM). Richiede un nlp_engine spaCy 'it' per il context-enhancement.

La reversibilita' ricalca src/app/app.py: stesso (entita', valore-normalizzato) ->
stesso placeholder [ENTITY_N]; il dizionario {placeholder->valore} resta LOCALE.
"""
import re
from typing import Dict, List, Tuple

from presidio_analyzer import RecognizerResult

from .rizzo_recognizer import RizzoPiiRecognizer
from .it_legal_recognizers import build_it_recognizers


# --------------------------------------------------------------------------- #
# 1) PoC leggero: recognizer diretti + merge + anonimizzazione reversibile
# --------------------------------------------------------------------------- #
def build_recognizers(model_dir: str):
    rizzo = RizzoPiiRecognizer(model_dir)
    rizzo.load()
    return [rizzo] + build_it_recognizers()


def analyze(text: str, recognizers) -> List[RecognizerResult]:
    """Esegue tutti i recognizer e fonde i risultati senza sovrapposizioni.
    Priorita' (come nell'app): validato-da-checksum > score > lunghezza."""
    cands: List[RecognizerResult] = []
    for r in recognizers:
        # NB: i PatternRecognizer con entities=None non restituiscono nulla ->
        # passare a ogni recognizer le SUE entita' supportate.
        # Marchiamo NOI la fonte (regex vs modello): il recognition_metadata NON e'
        # popolato quando si chiama il recognizer direttamente (solo via AnalyzerEngine).
        regex_src = 0 if isinstance(r, RizzoPiiRecognizer) else 1
        for res in (r.analyze(text, entities=r.supported_entities, nlp_artifacts=None) or []):
            meta = res.recognition_metadata or {}
            meta["rizzo_is_regex"] = regex_src
            res.recognition_metadata = meta
            cands.append(res)

    def is_regex(res) -> int:
        # la rete regex/checksum e' piu' affidabile del modello sui PII a forma fissa
        # (CF/IBAN/carta) -> ha priorita' su score, come in app.py (evita la frammentazione).
        return (res.recognition_metadata or {}).get("rizzo_is_regex", 0)

    def validated(res) -> int:
        # "validato" = checksum passato: SOLO un match regex puo' esserlo (Presidio porta
        # lo score al max quando validate_result=True). Il modello, anche a score 1.0, NON
        # e' "validato" -> non deve battere il full-span della regex e frammentarlo.
        return 1 if (is_regex(res) and res.score >= 0.999) else 0

    order = sorted(cands,
                   key=lambda r: (validated(r), is_regex(r), r.score, r.end - r.start),
                   reverse=True)
    kept: List[RecognizerResult] = []
    for r in order:
        if all(r.end <= k.start or r.start >= k.end for k in kept):
            kept.append(r)
    kept.sort(key=lambda r: r.start)
    return kept


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).casefold()


def reversible_anonymize(text: str, results: List[RecognizerResult]
                         ) -> Tuple[str, Dict[str, str]]:
    """Ritorna (testo_anonimizzato, mapping placeholder->valore). Reversibile e locale."""
    counters, seen, mapping = {}, {}, {}
    out, pos = [], 0
    for r in sorted(results, key=lambda r: r.start):
        # trim spazi ai bordi dello span (il modello a volte ingloba lo spazio iniziale)
        start, end = r.start, r.end
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if end <= start or start < pos:   # vuoto o overlap residuo: salta
            continue
        r_start, r_end = start, end
        val = text[r_start:r_end]
        key = (r.entity_type, _norm(val))
        if key in seen:
            ph = seen[key]
        else:
            counters[r.entity_type] = counters.get(r.entity_type, 0) + 1
            ph = f"[{r.entity_type}_{counters[r.entity_type]}]"
            seen[key] = ph
            mapping[ph] = val
        out.append(text[pos:r_start])
        out.append(ph)
        pos = r_end
    out.append(text[pos:])
    return "".join(out), mapping


def deanonymize(anon_text: str, mapping: Dict[str, str]) -> str:
    """Rimette i valori veri. Placeholder piu' lunghi prima (evita _1 dentro _10)."""
    for ph in sorted(mapping, key=len, reverse=True):
        anon_text = anon_text.replace(ph, mapping[ph])
    return anon_text


# --------------------------------------------------------------------------- #
# 2) AnalyzerEngine completo (per il guardrail Presidio di LiteLLM)
# --------------------------------------------------------------------------- #
def build_analyzer_engine(model_dir: str):
    """AnalyzerEngine con i recognizer rizzo-pii. NB: serve un nlp_engine spaCy 'it'
    (blank e' sufficiente per la tokenizzazione/context). Senza spaCy usa build_recognizers()."""
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    nlp_engine = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "it", "model_name": "it_core_news_sm"}],
    }).create_engine()

    registry = RecognizerRegistry()
    rizzo = RizzoPiiRecognizer(model_dir)
    rizzo.load()
    registry.add_recognizer(rizzo)
    for r in build_it_recognizers():
        registry.add_recognizer(r)

    return AnalyzerEngine(registry=registry, nlp_engine=nlp_engine,
                          supported_languages=["it"])


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "models/rizzo-pii-0.3B"
    sample = ("Il sottoscritto Mario Rossi, C.F. RSSMRA85H12F205Z, residente in Via "
              "Garibaldi 24, Milano (MI), chiede il bonifico di € 12.500,00 sull'IBAN "
              "IT60X0542811101000000123456 intestato alla Edilnord S.r.l.")
    recs = build_recognizers(model)
    results = analyze(sample, recs)
    anon, mapping = reversible_anonymize(sample, results)
    print("ORIGINALE:  ", sample)
    print("ANONIMIZZATO:", anon)
    print("MAPPING:    ", mapping)
    print("RICOSTRUITO:", deanonymize(anon, mapping))
    assert deanonymize(anon, mapping) == sample, "round-trip non reversibile!"
    print("round-trip OK")
