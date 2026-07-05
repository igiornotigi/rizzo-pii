# rizzo-pii ⇄ Presidio — integrazione (PoC)

Espone il modello mmBERT di rizzo-pii **come recognizer Microsoft Presidio**, così il
detector diventa **drop-in** nell'ecosistema Presidio (LiteLLM, LangChain, ecc.) e non
solo nell'app Flask del repo. Aggiunge inoltre i **recognizer legali italiani**
(CF, P.IVA, IBAN, catasto, targa…) che Presidio, tarato sugli USA, non ha.

## Perché
Obiettivo di produzione del progetto: *anonimizzare in locale prima di mandare a un LLM
esterno*. Presidio dà gratis la **tubatura** (registry di recognizer, anonymizer /
deanonymizer reversibile) e LiteLLM ha già un **guardrail Presidio**. Serve solo portare
il modello + la rete checksum dentro Presidio → è ciò che fa questo modulo.

## File
| File | Cosa |
|---|---|
| `taxonomy.py` | mappa i 22 tag rizzo-pii → entità Presidio (custom `IT_*` per i tag legali) |
| `it_legal_recognizers.py` | `PatternRecognizer` con **checksum** (mod-97 IBAN, CF, Luhn, P.IVA) |
| `rizzo_recognizer.py` | il modello mmBERT come `EntityRecognizer` Presidio (chunking incluso) |
| `engine.py` | compone modello+regex, anonimizzazione **reversibile**, `AnalyzerEngine` |
| `litellm_guardrail.py` | guardrail LiteLLM: anonimizza pre-call, ripristina post-call |

## Dipendenze
```
pip install presidio-analyzer presidio-anonymizer transformers torch
# per AnalyzerEngine completo (context-enhancement): spaCy 'it'
python -m spacy download it_core_news_sm
```

## Prova rapida (PoC, senza spaCy)
```
python -m src.integrations.presidio.engine models/rizzo-pii-0.3B
```
Stampa testo originale → anonimizzato → mapping → ricostruito, con assert sul round-trip.

## Uso come guardrail LiteLLM
`config.yaml` del proxy:
```yaml
guardrails:
  - guardrail_name: "rizzo-pii"
    litellm_params:
      guardrail: src.integrations.presidio.litellm_guardrail.RizzoPiiGuardrail
      mode: [pre_call, post_call]
      model_dir: "models/rizzo-pii-0.3B"
```
Open WebUI → LiteLLM (con questo guardrail) → LLM esterno. L'input viene anonimizzato
prima di uscire; la risposta viene ricostruita coi valori veri.

## Limiti noti (onesti)
- **Il recall del modello determina i leak.** Un'entità mancata esce verso l'LLM esterno.
  Tenere sempre i recognizer checksum (catturano i PII strutturati in modo deterministico)
  e **misurare il recall** su documenti reali prima di fidarsi.
- **Streaming**: in LiteLLM il post_call su stream è solo-audit → per ripristinare i
  placeholder, disattivare lo streaming o fare il restore nell'`outlet` di Open WebUI.
- **Multi-turno**: il mapping qui è per-richiesta; una chat coerente richiede stato
  per-conversazione (stessa entità → stesso placeholder tra i turni + history anonimizzata).
- **Tassonomia**: i tag `IT_*` sono entità custom Presidio (vanno dichiarate agli operatori
  a valle).
