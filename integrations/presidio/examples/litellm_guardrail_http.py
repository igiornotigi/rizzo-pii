# -*- coding: utf-8 -*-
"""
Guardrail LiteLLM CUSTOM "sottile": chiama l'endpoint /reversible del container
rizzo-pii-analyzer. Alternativa al provider `presidio` nativo quando si vuole il
controllo totale del round-trip (placeholder numerati [PERSON_1], mapping locale).

  utente -> [pre_call: POST /reversible -> anonimizza] -> LLM -> [post_call: ricostruisce] -> utente

Config (litellm config.yaml; il file va messo ACCANTO al config, LiteLLM lo risolve
come path relativo alla dir del config, NON dal PYTHONPATH):
  guardrails:
    - guardrail_name: "rizzo-pii"
      litellm_params:
        guardrail: litellm_guardrail_http.RizzoPiiHttpGuardrail
        mode: [pre_call, post_call]
        default_on: true
        service_url: "http://<HOST>:5002/reversible"

NB (onesto):
 - Il RECALL del modello decide i leak: valuta prima su documenti reali.
 - Streaming: il post_call su stream in LiteLLM e' solo-audit -> ricostruzione lato
   client (es. outlet di Open WebUI) o streaming OFF.
 - Multi-turno: il mapping e' per-richiesta; per una chat coerente serve stato
   per-conversazione (stessa entita' -> stesso placeholder tra i turni).
"""
import httpx

try:
    from litellm.integrations.custom_guardrail import CustomGuardrail
except Exception:                       # import possibile anche senza litellm
    class CustomGuardrail:              # pragma: no cover
        def __init__(self, *a, **k): pass

_MAP_KEY = "rizzo_pii_map"


class RizzoPiiHttpGuardrail(CustomGuardrail):
    def __init__(self, service_url="http://127.0.0.1:5002/reversible",
                 timeout=60, **kwargs):
        super().__init__(**kwargs)
        self._url = service_url
        self._timeout = timeout

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
        merged = {}
        for msg in data.get("messages", []):
            c = msg.get("content")
            if isinstance(c, str) and c.strip():
                anon, mp = await self._anon(c)
                msg["content"] = anon
                merged.update(mp)
        data.setdefault("metadata", {})[_MAP_KEY] = merged
        return data

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        """Ricostruisce i valori veri nella risposta."""
        mapping = (data or {}).get("metadata", {}).get(_MAP_KEY) or {}
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
