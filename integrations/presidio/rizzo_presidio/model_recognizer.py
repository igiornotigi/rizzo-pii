# -*- coding: utf-8 -*-
"""
Recognizer Presidio che usa il modello mmBERT di rizzo-pii come NER esterno.

Wrappa la stessa `transformers.pipeline("token-classification", aggregation_strategy="simple")`
dell'app e converte le entita' del modello in `RecognizerResult` Presidio, mappando i
22 tag -> entita' Presidio (taxonomy.py). Fa il chunking word-safe per i testi lunghi
(gli offset restano globali).

Il modello copre i tag CONTESTUALI (nomi, org, indirizzi, date in prosa): la sua forza
sono i PII che nessuna regex prende. Va affiancato ai recognizer regex+checksum
(checksum_recognizers.py) per i PII strutturati -> modello + rete = recall alto.

Dipendenze: presidio-analyzer + extra [model] (transformers, torch).
"""
import re
from typing import List

from presidio_analyzer import EntityRecognizer, RecognizerResult

from .taxonomy import to_presidio, ALL_ENTITIES

MAX_WORDS = 120   # come nell'app: ~180 subword, sotto i 512 del training
OVERLAP = 20


def _chunks(text, max_words=MAX_WORDS, overlap=OVERLAP):
    words = list(re.finditer(r"\S+", text))
    if not words:
        return []
    out, i, step = [], 0, max(1, max_words - overlap)
    while i < len(words):
        block = words[i:i + max_words]
        s, e = block[0].start(), block[-1].end()
        out.append((text[s:e], s))
        if i + max_words >= len(words):
            break
        i += step
    return out


class RizzoPiiRecognizer(EntityRecognizer):
    """NER contestuale di rizzo-pii come recognizer Presidio."""

    def __init__(self, model_dir: str, supported_language: str = "it",
                 score_threshold: float = 0.0):
        # NB: Presidio EntityRecognizer.__init__ chiama self.load() -> gli attributi
        # devono esistere PRIMA della super().__init__().
        self._model_dir = model_dir
        self._threshold = score_threshold
        self._nlp = None
        # dichiara a Presidio quali entita' puo' produrre (i tipi mappati dai 22 tag)
        super().__init__(
            supported_entities=ALL_ENTITIES + [f"RIZZO_{t}" for t in
                                               ("STREET", "ZIPCODE", "BUILDINGNUM")],
            supported_language=supported_language,
            name="RizzoPiiRecognizer",
        )

    def load(self) -> None:
        if self._nlp is not None:        # idempotente (super().__init__ la chiama gia')
            return
        # import pesanti solo al load
        import torch
        from transformers import pipeline
        device = 0 if torch.cuda.is_available() else -1
        self._nlp = pipeline(
            "token-classification",
            model=self._model_dir,
            tokenizer=self._model_dir,
            aggregation_strategy="simple",
            device=device,
        )

    def analyze(self, text: str, entities: List[str],
                nlp_artifacts=None) -> List[RecognizerResult]:
        if self._nlp is None:
            self.load()
        chunks = _chunks(text)
        if not chunks:
            return []
        results = self._nlp([c for c, _ in chunks])
        if isinstance(results, dict):
            results = [results]

        out: List[RecognizerResult] = []
        for (_, off), res in zip(chunks, results):
            for e in res:
                ent = to_presidio(e["entity_group"])
                if entities and ent not in entities:
                    continue
                score = float(e["score"])
                if score < self._threshold:
                    continue
                out.append(RecognizerResult(
                    entity_type=ent,
                    start=int(e["start"]) + off,
                    end=int(e["end"]) + off,
                    score=score,
                    analysis_explanation=None,
                    recognition_metadata={
                        RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                        "rizzo_tag": e["entity_group"],
                    },
                ))
        return out
