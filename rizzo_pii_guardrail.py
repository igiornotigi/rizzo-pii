# -*- coding: utf-8 -*-
"""
Guardrail LiteLLM (versione FLAT, autonoma) — da montare accanto al config.yaml.

Perche' flat: LiteLLM importa i guardrail custom come `<modulo>.<Classe>` (un solo
punto), risolvendo il modulo dalla working dir del proxy (/app, dove sta config.yaml).
Un path profondo (src.integrations.presidio...) non si risolveva e il nome conteneva
"presidio" -> rischio di collisione col guardrail built-in di LiteLLM. Questo file
elimina entrambi i problemi: nome piatto, nessun "presidio", zero dipendenze oltre httpx.

Chiama il PII service (service.py) via HTTP: anonimizza pre-call, ricostruisce post-call.

Config (litellm config.yaml):
  guardrails:
    - guardrail_name: "rizzo-pii"
      litellm_params:
        guardrail: rizzo_pii_guardrail.RizzoPiiHttpGuardrail
        mode: [pre_call, post_call]
        default_on: true
        service_url: "http://192.168.178.55:5005/analyze"

Mount (compose, container LiteLLM):
  - /home/igi/rizzo-pii/rizzo_pii_guardrail.py:/app/rizzo_pii_guardrail.py:ro
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


_log("modulo importato")   # compare nei log all'avvio se LiteLLM carica la classe


class RizzoPiiHttpGuardrail(CustomGuardrail):
    def __init__(self, service_url="http://192.168.178.55:5005/analyze",
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
        for ph in sorted(mapping, key=len, reverse=True):
            text = text.replace(ph, mapping[ph])
        return text

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
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
        mapping = (data or {}).get("metadata", {}).get(_MAP_KEY) or {}
        _log(f"post_call: mapping da ricostruire = {len(mapping)}")
        if not mapping:
            return response
        try:
            for ch in response.choices:
                m = getattr(ch, "message", None)
                if m and isinstance(getattr(m, "content", None), str):
                    m.content = self._deanon(m.content, mapping)
        except Exception as e:
            _log(f"post_call errore: {e}")
        return response
