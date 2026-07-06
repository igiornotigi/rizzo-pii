# rizzo-presidio — il modello rizzo-pii nell'ecosistema Microsoft Presidio

Espone il modello **`rizzoaiacademy/rizzo-pii-0.3B`** (mmBERT, 22 tag PII legali IT)
come **recognizer Microsoft Presidio**, insieme ai **recognizer regex+checksum
italiani** (CF, P.IVA, IBAN, carta, targa, importi) che Presidio — tarato sugli
USA — non ha. Il tutto è impacchettato in un **container drop-in** che parla l'API
REST standard di Presidio Analyzer: qualsiasi client Presidio (guardrail LiteLLM,
SDK Python, n8n, …) può puntare qui e ottenere il rilevamento legale italiano.

```
                       ┌──────────────────────────────────────┐
  POST /analyze  ───►  │  rizzo-pii-analyzer (questo pacchetto)│
  (API Presidio)       │  • mmBERT 0.3B  (NER contestuale)     │
                       │  • regex+checksum (CF/PIVA/IBAN/…)    │
                       │  • merge: checksum > modello          │
                       │  • modello COTTO nell'immagine        │
                       │    → avvio OFFLINE (GDPR/air-gapped)  │
                       └──────────────────────────────────────┘
```

## Perché modello + checksum insieme

Il principio del progetto: *in produzione affiancare sempre la rete regex+checksum
al modello*. Qui i due sono fusi con una regola di merge precisa: **un match regex
validato dal checksum vince sempre sui frammenti del modello** (l'AnalyzerEngine
standard di Presidio risolve i conflitti solo per score e spezzerebbe i CF).
Il checksum (mod-97 IBAN, tabella CF, Luhn, controllo P.IVA) porta anche i falsi
positivi a ~zero sui tipi validabili.

## Struttura

| Percorso | Cosa |
|---|---|
| `rizzo_presidio/taxonomy.py` | 22 tag rizzo-pii → entità Presidio (custom `IT_*` per i tag legali) |
| `rizzo_presidio/validators.py` | checksum puri (zero dipendenze): CF, IBAN, P.IVA, Luhn |
| `rizzo_presidio/checksum_recognizers.py` | `PatternRecognizer` con `validate_result()` = checksum |
| `rizzo_presidio/model_recognizer.py` | il modello mmBERT come `EntityRecognizer` (chunking incluso) |
| `rizzo_presidio/engine.py` | merge modello+regex, anonimizzazione **reversibile** |
| `rizzo_presidio/analyzer_app.py` | server HTTP **compatibile Presidio Analyzer** |
| `docker/` | immagine (modello incluso) + compose con l'anonymizer MS ufficiale |
| `tests/` | checksum, tassonomia, merge, round-trip (senza modello: veloci) |
| `examples/` | config LiteLLM (provider `presidio` e guardrail custom), round-trip demo |

## Installazione

```bash
pip install .                 # solo recognizer regex+checksum (leggero)
pip install ".[model]"        # + modello mmBERT (transformers, torch)
pip install ".[model,server]" # + server HTTP
pip install ".[test]" && pytest tests/
```

## Docker (consigliato)

```bash
cd integrations/presidio
docker compose -f docker/docker-compose.yml up -d --build
```

Avvia due servizi:
- **`rizzo-analyzer`** su `:5002` — rilevamento (questo pacchetto, modello incluso
  nell'immagine: il container gira **offline**, `HF_HUB_OFFLINE=1`);
- **`presidio-anonymizer`** su `:5001` — sostituzione (immagine Microsoft ufficiale).

Prova:
```bash
curl -X POST http://localhost:5002/analyze -H 'Content-Type: application/json' \
     -d '{"text": "Il Sig. Mario Rossi, C.F. MRTPTR98B24B354B", "language": "it"}'
```

## Uso con LiteLLM (via UI admin o config)

Il guardrail **`presidio` nativo** di LiteLLM funziona senza codice aggiuntivo:
UI admin → *Guardrails → Add Guardrail → Presidio PII*, oppure config
([examples/litellm_config_presidio.yaml](examples/litellm_config_presidio.yaml)):

```yaml
guardrails:
  - guardrail_name: "rizzo-pii-presidio"
    litellm_params:
      guardrail: presidio
      mode: "pre_call"
      presidio_analyzer_api_base: "http://<HOST>:5002"
      presidio_anonymizer_api_base: "http://<HOST>:5001"
      presidio_language: "it"
      output_parse_pii: true      # ripristina i valori veri nella risposta
```

In alternativa, per il controllo totale del round-trip (placeholder numerati
`[PERSON_1]`, dizionario locale), c'è il guardrail custom
[examples/litellm_guardrail_http.py](examples/litellm_guardrail_http.py) che usa
l'endpoint extra `/reversible` dello stesso container.

## Endpoint del container

| Endpoint | Contratto | Uso |
|---|---|---|
| `POST /analyze` | **Presidio Analyzer standard** | LiteLLM `presidio`, SDK, qualsiasi client Presidio |
| `GET /supportedentities` | Presidio standard | discovery delle entità (incluse `IT_*`) |
| `GET /health` | Presidio standard | healthcheck |
| `POST /reversible` | extra: `{"text"}` → `{"anonymized_text","mapping"}` | guardrail custom reversibile |
| `POST /deanonymize` | extra: `{"text","mapping"}` → `{"text"}` | ricostruzione lato client |

## Limiti noti (onesti)

- **Il recall del modello determina i leak.** Un'entità mancata esce verso l'LLM
  esterno. I recognizer checksum coprono deterministicamente i PII strutturati, ma
  su nomi/indirizzi il recall va **misurato su documenti reali** prima di fidarsi.
- **Inferenza CPU nell'immagine di default**: il 0.3B su CPU è adeguato a testi di
  chat/documenti; per throughput alto servono batch/GPU (immagine da estendere).
- **Streaming**: nel guardrail custom il post_call su stream è solo-audit → restore
  lato client o streaming OFF. Con `output_parse_pii` di LiteLLM vale il comportamento
  del provider nativo.
- **Multi-turno**: il mapping reversibile è per-richiesta; una chat coerente richiede
  stato per-conversazione (stessa entità → stesso placeholder tra i turni).
- **Tassonomia**: i tag `IT_*` sono entità custom (i client che filtrano per entità
  devono includerle; `GET /supportedentities` le elenca).
- L'immagine ridistribuisce i pesi di `rizzoaiacademy/rizzo-pii-0.3B` (© Simone Rizzo
  / Rizzo AI Academy, **MIT** — ridistribuzione consentita mantenendo l'attribuzione;
  vedi [`NOTICE`](NOTICE)). Modello e dataset a monte sono entrambi MIT.
