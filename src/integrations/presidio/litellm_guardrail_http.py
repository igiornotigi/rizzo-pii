# -*- coding: utf-8 -*-
"""
Guardrail LiteLLM "sottile": chiama il PII service via HTTP (service.py).

Da usare quando LiteLLM gira in un container: NON serve torch/transformers/modello
nel container, solo `httpx` (che LiteLLM ha gia'). Il modello vive nel PII service.

  utente -> [pre_call: POST /analyze -> anonimizza] -> LLM -> [post_call: ricostruisci] -> utente

Config (litellm config.yaml):
  guardrails:
    - guardrail_name: "rizzo-pii"
      litellm_params:
        guardrail: src.integrations.presidio.litellm_guardrail_http.RizzoPiiHttpGuardrail
        mode: [pre_call, post_call]
        default_on: true
        service_url: "http://host.docker.internal:5005/analyze"

NB (onesto):
 - Il RECALL del modello decide i leak: valuta prima su documenti reali.
 - Streaming: il post_call su stream in LiteLLM e' solo-audit -> ricostruzione lato
   Open WebUI (outlet) o streaming OFF.
 - Multi-turno: il mapping e' per-richiesta; per una chat coerente serve stato
   per-conversazione (stessa entita' -> stesso placeholder tra i turni).
"""
import sys

import httpx

try:
    from litellm.integrations.custom_guardrail import CustomGuardrail
except Exception:                       # import possibile anche senza litellm
    class CustomGuardrail:              # pragma: no cover
        def __init__(self, *a, **k): pass

_MAP_KEY = "rizzo_pii_map"


def _log(msg: str) -> None:
    print(f"[rizzo-guardrail] {msg}", file=sys.stderr, flush=True)


# segnale di avvenuto IMPORT del modulo (compare nei log all'avvio se LiteLLM lo carica)
_log("modulo importato")


class RizzoPiiHttpGuardrail(CustomGuardrail):
    def __init__(self, service_url="http://host.docker.internal:5005/analyze",
                 timeout=60, **kwargs):
        super().__init__(**kwargs)
        self._url = service_url
        self._timeout = timeout
        _log(f"init OK (service_url={service_url}, kwargs={list(kwargs.keys())})")

    async def _anon(self, text: str):
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(self._url, json={"text": text})
            r.raise_for_status()
            d = r.json()
        return d.get("anonymized_text", text), d.get("mapping", {}) or {}

    @staticmethod
    def _deanon(text: str, mapping: dict) -> str:
        for ph in sorted(mapping, key=len, reverse=True):   # piu' lunghi prima (_1 in _10)
            text = text.replace(ph, mapping[ph])
        return text

    # --- LiteLLM hooks -----------------------------------------------------
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        """Anonimizza ogni messaggio PRIMA di uscire verso l'LLM."""
        _log(f"pre_call: {len(data.get('messages', []))} messaggi")
        merged = {}
        for msg in data.get("messages", []):
            c = msg.get("content")
            if isinstance(c, str) and c.strip():
                anon, mp = await self._anon(c)
                msg["content"] = anon
                merged.update(mp)
        data.setdefault("metadata", {})[_MAP_KEY] = merged
        _log(f"pre_call: mascherate {len(merged)} entita'")
        return data

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        """Ricostruisce i valori veri nella risposta."""
        mapping = (data or {}).get("metadata", {}).get(_MAP_KEY) or {}
        _log(f"post_call: mapping da ricostruire = {len(mapping)}")
        if not mapping:
            return response
        try:
            for ch in response.choices:
                m = getattr(ch, "message", None)
                if m and isinstance(getattr(m, "content", None), str):
                    m.content = self._deanon(m.content, mapping)
        except Exception:
            pass
        return response
