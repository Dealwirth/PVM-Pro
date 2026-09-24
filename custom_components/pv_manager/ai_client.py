"""AI transports for optional providers.

The API key is read from the config entry options, is never returned through
the websocket API and is never written to logs. All external traffic uses TLS
and a strict timeout.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_AI_API_KEY
from .core.ai import PROVIDER_CATALOG, OpenAICompatibleProvider

_LOGGER = logging.getLogger(__name__)

CATALOG_BY_ID = {info.provider_id: info for info in PROVIDER_CATALOG}


def provider_info(provider_id: str) -> dict[str, Any]:
    """Return public provider metadata for the UI."""
    info = CATALOG_BY_ID.get(provider_id)
    if info is None:
        return {}
    return {
        "provider_id": info.provider_id,
        "name_de": info.name_de,
        "name_en": info.name_en,
        "local": info.local,
        "suggested": info.suggested,
        "endpoint_default": info.endpoint_default,
        "model_default": info.model_default,
        "privacy_note_de": info.privacy_note_de,
        "privacy_note_en": info.privacy_note_en,
    }


def build_provider_factory(hass: HomeAssistant, runtime: Any):
    """Return a factory that builds providers with an injected transport."""

    def factory(provider_id: str) -> OpenAICompatibleProvider:
        config = runtime.ai
        info = CATALOG_BY_ID.get(provider_id)
        is_local = bool(info.local) if info else False
        endpoint = str(config.get("endpoint") or (info.endpoint_default if info else ""))
        model = str(config.get("model") or (info.model_default if info else ""))
        api_key = runtime.entry.options.get(CONF_AI_API_KEY, "")
        # The user's language belongs to the request, but the transport keeps a
        # default for the injected payload label below.
        language = str(runtime.settings.get("language", "de"))

        async def transport(request: dict[str, Any]) -> str:
            session = async_get_clientsession(hass)
            url = f"{str(request['endpoint']).rstrip('/')}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if api_key and not is_local:
                headers["Authorization"] = f"Bearer {api_key}"
            body = {
                "model": request["model"],
                "messages": request["messages"],
                "temperature": request.get("temperature", 0.1),
                "max_tokens": request.get("max_tokens", 700),
            }
            if request.get("payload") is not None:
                label = "Data" if language == "en" else "Daten"
                body["messages"] = [
                    *body["messages"],
                    {
                        "role": "user",
                        "content": f"{label}: {request['payload']}",
                    },
                ]
            timeout = asyncio.timeout(30)
            async with timeout, session.post(url, json=body, headers=headers) as response:
                if response.status >= 400:
                    text = await response.text()
                    # Never log response bodies that could contain user data.
                    raise RuntimeError(f"provider_http_{response.status}: {text[:200]}")
                data = await response.json()
            try:
                return str(data["choices"][0]["message"]["content"])
            except (KeyError, IndexError, TypeError) as err:
                raise RuntimeError("provider_unexpected_response") from err

        return OpenAICompatibleProvider(
            provider_id=provider_id,
            endpoint=endpoint,
            model=model,
            transport=transport,
            language=language,
        )

    return factory
