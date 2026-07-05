# -*- coding: utf-8 -*-
"""
Server HTTP compatibile con l'API REST di Presidio Analyzer, con dentro i
recognizer rizzo-pii (modello mmBERT + regex/checksum IT).

E' il pezzo che rende il modello un "drop-in" per l'ecosistema Presidio: qualsiasi
client che parla con `mcr.microsoft.com/presidio-analyzer` (LiteLLM guardrail
`presidio`, SDK, n8n, ...) puo' puntare qui e ottenere il rilevamento legale IT.

Endpoint (contratto Presidio Analyzer):
  POST /analyze            {"text", "language", ["entities"], ["score_threshold"]}
                           -> [ {entity_type, start, end, score, ...}, ... ]
  GET  /supportedentities  -> ["PERSON", "IT_FISCAL_CODE", ...]
  GET  /health             -> "Presidio Analyzer service (rizzo-pii)"

Endpoint extra (contratto del guardrail custom rizzo_pii_guardrail.py):
  POST /reversible         {"text"} -> {"anonymized_text", "mapping"}
  POST /deanonymize        {"text", "mapping"} -> {"text"}

Nota merge: NON usa l'AnalyzerEngine di Presidio ma il merge di engine.py
(checksum > modello): l'AnalyzerEngine risolve i conflitti solo per score e
frammenterebbe i CF quando il modello emette pezzi a score 1.0.

Avvio locale:   PII_MODEL_DIR=rizzoaiacademy/rizzo-pii-0.3B python -m rizzo_presidio.analyzer_app
Produzione:     gunicorn -w 1 -b 0.0.0.0:3000 "rizzo_presidio.analyzer_app:create_app()"
                (1 worker: la pipeline transformers non e' thread-safe)
"""
import os

from flask import Flask, jsonify, request

from . import DEFAULT_MODEL, __version__
from .engine import build_recognizers, analyze, reversible_anonymize, deanonymize


def _result_to_dict(r):
    """Serializzazione identica a quella del server Presidio ufficiale."""
    return {
        "entity_type": r.entity_type,
        "start": r.start,
        "end": r.end,
        "score": r.score,
        "analysis_explanation": None,
        "recognition_metadata": r.recognition_metadata or {},
    }


def create_app(model_dir: str = None) -> Flask:
    model_dir = model_dir or os.environ.get("PII_MODEL_DIR", DEFAULT_MODEL)
    app = Flask("rizzo-presidio-analyzer")

    print(f"[rizzo-presidio] carico il modello {model_dir} ...", flush=True)
    recognizers = build_recognizers(model_dir)
    supported = sorted({e for r in recognizers for e in r.supported_entities})
    print(f"[rizzo-presidio] pronto (v{__version__}, {len(recognizers)} recognizer, "
          f"{len(supported)} entita').", flush=True)

    # ---- contratto Presidio Analyzer -------------------------------------- #
    @app.post("/analyze")
    def analyze_route():
        data = request.get_json(silent=True) or {}
        text = data.get("text")
        if not isinstance(text, str):
            return jsonify({"error": "No text provided"}), 400
        results = analyze(text, recognizers)
        entities = data.get("entities")
        if entities:
            results = [r for r in results if r.entity_type in entities]
        threshold = data.get("score_threshold")
        if threshold is not None:
            results = [r for r in results if r.score >= float(threshold)]
        return jsonify([_result_to_dict(r) for r in results])

    @app.get("/supportedentities")
    def supported_entities():
        return jsonify(supported)

    @app.get("/health")
    def health():
        # stesso testo del server ufficiale (alcuni client lo controllano)
        return f"Presidio Analyzer service (rizzo-pii v{__version__}, model={model_dir})"

    # ---- contratto guardrail custom (reversibile) -------------------------- #
    @app.post("/reversible")
    def reversible_route():
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return jsonify({"anonymized_text": text or "", "mapping": {}})
        anon, mapping = reversible_anonymize(text, analyze(text, recognizers))
        return jsonify({"anonymized_text": anon, "mapping": mapping})

    @app.post("/deanonymize")
    def deanonymize_route():
        data = request.get_json(silent=True) or {}
        return jsonify({"text": deanonymize(data.get("text", ""),
                                            data.get("mapping", {}) or {})})

    return app


if __name__ == "__main__":
    host = os.environ.get("PII_HOST", "0.0.0.0")   # raggiungibile dai container
    port = int(os.environ.get("PII_PORT", os.environ.get("PORT", "3000")))
    create_app().run(host=host, port=port, threaded=False)
