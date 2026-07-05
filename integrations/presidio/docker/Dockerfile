# rizzo-pii-analyzer: Presidio Analyzer API + modello rizzo-pii-0.3B + regex/checksum IT.
#
# Il modello e' "COTTO" nell'immagine: il container parte OFFLINE (nessun download a
# runtime, HF_HUB_OFFLINE=1) -> adatto ad ambienti air-gapped / GDPR: nessun byte di
# testo o di rete esce dalla macchina. Il tag dell'immagine versiona codice+modello.
#
# Build (dalla cartella integrations/presidio/):
#   docker build -f docker/Dockerfile -t rizzo-pii-analyzer:0.1.0 .
# Run:
#   docker run -p 5002:3000 rizzo-pii-analyzer:0.1.0
# Test:
#   curl -X POST http://localhost:5002/analyze -H 'Content-Type: application/json' \
#        -d '{"text": "Mario Rossi, C.F. MRTPTR98B24B354B", "language": "it"}'

FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf

# torch CPU-only: su Linux il default pip e' la build CUDA (+~4GB inutili senza GPU)
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

# il pacchetto rizzo-presidio con gli extra modello+server
COPY pyproject.toml README.md /opt/rizzo-presidio/
COPY rizzo_presidio/ /opt/rizzo-presidio/rizzo_presidio/
RUN pip install "/opt/rizzo-presidio[model,server]"

# scarica il modello DENTRO l'immagine (unica fase che tocca la rete)
ARG MODEL_ID=rizzoaiacademy/rizzo-pii-0.3B
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('${MODEL_ID}')"

ENV PII_MODEL_DIR=${MODEL_ID} \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    PORT=3000

EXPOSE 3000
# 1 worker + preload: il modello si carica una volta; la pipeline non e' thread-safe.
# Timeout alto: il primo load su CPU puo' superare i 30s di default di gunicorn.
CMD gunicorn --workers 1 --threads 1 --timeout 300 --preload \
    --bind 0.0.0.0:${PORT} "rizzo_presidio.analyzer_app:create_app()"
