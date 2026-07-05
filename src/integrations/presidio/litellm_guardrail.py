# -*- coding: utf-8 -*-
"""
Guardrail LiteLLM che usa rizzo-pii per anonimizzare l'input verso l'LLM esterno
e ripristinare i placeholder nella risposta (round-trip REVERSIBILE).

  utente -> [pre_call: anonimizza] -> LLM esterno -> [post_call: ripristina] -> utente

Il dizionario {placeholder->valore} NON lascia la macchina: viaggia solo tra i due hook
della STESSA richiesta (stash in data["metadata"]).

Config (litellm proxy config.yaml):
  guardrails:
    - guardrail_name: "rizzo-pii"
      litellm_params:
        guardrail: src.integrations.presidio.litellm_guardrail.RizzoPiiGuardrail
        mode: [pre_call, post_call]
        model_dir: "models/rizzo-pii-0.3B"

NB (onesto):
 - Il RECALL del modello decide i leak: valuta prima su documenti reali.
 - Streaming: in LiteLLM il post_call su stream e' solo-audit -> per ripristinare i
   placeholder disattiva lo streaming o fai il restore nell'outlet di Open WebUI.
 - Multi-turno: qui il mapping e' per-richiesta; per una chat coerente serve stato
   per-conversazione (stessa entita' -> stesso placeholder tra i turni).
"""
from typing import Optional

try:
    from litellm.integrations.custom_guardrail import CustomGuardrail
except Exception:                       # permette l'import anche senza litellm installato
    class CustomGuardrail:              # pragma: no cover
        def __init__(self, *a, **k): pass

from .engine import build_recognizers, analyze, reversible_anonymize, deanonymize

_MAP_KEY = "rizzo_pii_map"


class RizzoPiiGuardrail(CustomGuardrail):
    def __init__(self, model_dir: str = "models/rizzo-pii-0.3B", **kwargs):
        super().__init__(**kwargs)
        self._recs = build_recognizers(model_dir)   # carica il modello una volta

    def _anonymize_messages(self, data: dict) -> dict:
        merged = {}
        for msg in data.get("messages", []):
            content = msg.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            anon, mapping = reversible_anonymize(content, analyze(content, self._recs))
            msg["content"] = anon
            merged.update(mapping)       # placeholder univoci tra i messaggi
        data.setdefault("metadata", {})[_MAP_KEY] = merged
        return data

    # --- LiteLLM hooks -----------------------------------------------------
    async def async_pre_call_hook(self, user_api_key_dict, cache, data: dict,
                                  call_type) -> Optional[dict]:
        """Anonimizza le PII PRIMA di inviare la richiesta all'LLM esterno."""
        return self._anonymize_messages(data)

    async def async_post_call_success_hook(self, data: dict, user_api_key_dict,
                                           response):
        """Ripristina i valori veri nella risposta (i placeholder tornano PII)."""
        mapping = (data or {}).get("metadata", {}).get(_MAP_KEY) or {}
        if not mapping:
            return response
        try:
            for choice in response.choices:
                msg = getattr(choice, "message", None)
                if msg and isinstance(getattr(msg, "content", None), str):
                    msg.content = deanonymize(msg.content, mapping)
        except Exception:
            pass                         # in caso di formati risposta non standard
        return response
