#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Valida e fonde nel banco template i lotti generati dai modelli (Codex/Gemini/...).

Ogni lotto e' un file JSON: lista di {"doc_type": ..., "text": ...}. Per ciascun
template controlla, con le STESSE regole del repo:
  - i segnaposto usati sono tutti in generate_synthetic_pii.SLOTS (iniettabili);
  - nessun nome/citta' scritto inline (llm_template_bank.find_stray_names) ->
    altrimenti le label BIO sarebbero sbagliate e finirebbe PII non taggata.
I template validi (e non gia' presenti) vengono aggiunti a
dataset/synthetic/legal_templates.json con id riassegnati. Stampa solo il conteggio
e la lista degli SCARTATI (l'operatore guarda solo le eccezioni).

Uso:  python src/data_pipeline/validate_and_merge.py <batch1.json> [<batch2.json> ...]
"""
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "data_pipeline"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import generate_synthetic_pii as gen   # noqa: E402
import llm_template_bank as tb          # noqa: E402

BANK = ROOT / "dataset" / "synthetic" / "legal_templates.json"
VALID_SLOTS = set(gen.SLOTS)


def load(p):
    return json.load(open(p, encoding="utf-8"))


def check(text):
    """None se valido, altrimenti stringa col motivo dello scarto."""
    if not text or not text.strip():
        return "vuoto"
    slots = set(gen.SLOT_RE.findall(text))
    if not slots:
        return "nessun segnaposto"
    bad = slots - VALID_SLOTS
    if bad:
        return f"slot non validi {sorted(bad)}"
    stray = tb.find_stray_names(text)
    if stray:
        return f"nomi inline {sorted(set(stray))[:5]}"
    return None


def main(paths):
    bank = load(BANK) if BANK.exists() else []
    seen = {t["text"].strip() for t in bank}
    added = dup = 0
    rejects = []
    for path in paths:
        try:
            batch = load(path)
        except Exception as e:
            print(f"ERRORE lettura {path}: {e}")
            continue
        for t in batch:
            text = (t.get("text") or "")
            dt = t.get("doc_type", "?")
            err = check(text)
            if err:
                rejects.append((dt, err))
                continue
            if text.strip() in seen:
                dup += 1
                continue
            seen.add(text.strip())
            bank.append({"id": 0, "doc_type": dt, "text": text})
            added += 1
    for i, t in enumerate(bank):     # id sequenziali
        t["id"] = i
    BANK.parent.mkdir(parents=True, exist_ok=True)
    json.dump(bank, open(BANK, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"aggiunti {added} | duplicati saltati {dup} | scartati {len(rejects)} "
          f"| banco totale {len(bank)}")
    for dt, why in rejects:
        print(f"  SCARTATO: {dt} -> {why}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("uso: validate_and_merge.py <batch1.json> [<batch2.json> ...]")
    main(sys.argv[1:])
