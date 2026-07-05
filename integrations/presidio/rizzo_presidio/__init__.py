# -*- coding: utf-8 -*-
"""
rizzo-presidio: recognizer Presidio per PII legali/anagrafici italiani.

Due famiglie di recognizer, pensate per lavorare INSIEME:
  - `RizzoPiiRecognizer` (model_recognizer): il modello mmBERT `rizzoaiacademy/rizzo-pii-0.3B`
    come NER contestuale (nomi, org, indirizzi, date in prosa).
  - `build_it_recognizers()` (checksum_recognizers): regex + checksum per i PII a forma
    fissa (CF, P.IVA, IBAN, carta, targa, importi) — deterministici, zero falsi positivi
    sui tipi validabili.

`engine.py` li compone (merge con priorita' checksum > modello) e aggiunge
l'anonimizzazione REVERSIBILE (placeholder <-> valore, dizionario locale).
`analyzer_app.py` espone il tutto dietro l'API REST standard di Presidio Analyzer.
"""
from .taxonomy import TAG_TO_PRESIDIO, CUSTOM_ENTITIES, ALL_ENTITIES, to_presidio
from .validators import iban_ok, piva_ok, cf_ok, luhn_ok

__version__ = "0.1.0"
DEFAULT_MODEL = "rizzoaiacademy/rizzo-pii-0.3B"

__all__ = [
    "TAG_TO_PRESIDIO", "CUSTOM_ENTITIES", "ALL_ENTITIES", "to_presidio",
    "iban_ok", "piva_ok", "cf_ok", "luhn_ok",
    "DEFAULT_MODEL", "__version__",
]
