# -*- coding: utf-8 -*-
"""
Micro-servizio HTTP di anonimizzazione (modello + regex/checksum).

Espone POST /analyze {"text": "..."} -> {"anonymized_text": "...", "mapping": {...}}.
Carica il modello UNA volta all'avvio. Pensato per girare accanto a LiteLLM: il
guardrail (litellm_guardrail_http.py) lo chiama via HTTP, cosi' il container LiteLLM
NON deve avere torch/transformers ne' caricare il modello.

Avvio (nel venv con torch/transformers/presidio + flask):
    PII_MODEL_DIR=rizzoaiacademy/rizzo-pii-0.3B python -m src.integrations.presidio.service
Ascolta su 0.0.0.0:5005 (override con PII_HOST/PII_PORT) -> raggiungibile dai container.

NB: usa il dev server Flask (ok per test). In produzione: gunicorn + 1 worker
(il modello non e' thread-safe; tenere 1 worker o un lock).
"""
import os

from flask import Flask, jsonify, request

from .engine import build_recognizers, analyze, reversible_anonymize

MODEL = os.environ.get("PII_MODEL_DIR", "rizzoaiacademy/rizzo-pii-0.3B")

app = Flask(__name__)
print(f"[pii-service] carico il modello {MODEL} ...", flush=True)
RECS = build_recognizers(MODEL)
print("[pii-service] pronto.", flush=True)


@app.post("/analyze")
def analyze_route():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"anonymized_text": text or "", "mapping": {}})
    anon, mapping = reversible_anonymize(text, analyze(text, RECS))
    return jsonify({"anonymized_text": anon, "mapping": mapping})


@app.get("/health")
def health():
    return jsonify({"ok": True, "model": MODEL})


if __name__ == "__main__":
    host = os.environ.get("PII_HOST", "0.0.0.0")   # 0.0.0.0 -> raggiungibile dai container
    port = int(os.environ.get("PII_PORT", "5005"))
    app.run(host=host, port=port, threaded=False)
