"""Minimal Home Assistant stand-ins.

The project deliberately keeps every decision free of Home Assistant, and the
core tests import only ``custom_components.pv_manager.core``. That leaves the
glue in ``runtime.py`` - reading entity state, persisting settings, raising
notifications - uncovered, because Home Assistant is a very large dependency
that is not installed here.

``runtime.py`` touches only a handful of interfaces, and those are reproduced
below. The surface is intentionally tiny: a stand-in that reproduces more than
the integration uses would give false confidence.

Interfaces reproduced, and nothing else:

``hass.states.get`` / ``hass.states.async_all``
    Entity lookup by id and for discovery.
``hass.services.async_call``
    Service calls, so tests can prove a command was really issued.
``homeassistant.helpers.storage.Store``
    Settings persistence, in memory.
``homeassistant.util.dt.utcnow``
    The clock the runtime timestamps everything with.
``homeassistant.components.persistent_notification.async_create``
    User-facing notifications, so their wording can be asserted.
``homeassistant.config_entries.ConfigEntry``
    Carries ``options``, which point at the user's chosen entities.

Whenever the integration starts reaching for something new, the stub module
raises an explanatory error instead of silently returning ``None``.
"""

from __future__ import annotations

import sys
import types
from datetime import UTC, datetime
from typing import Any


class StubModule(types.ModuleType):
    """Module that explains itself when more than the tests reproduce is used."""

    def __getattr__(self, name: str) -> Any:
        """Report the missing stand-in instead of failing somewhere deep."""
        raise AttributeError(
            f"{self.__name__}.{name} is not reproduced by tests/ha/ha_stubs.py. "
            "Add it there before relying on it in the integration."
        )


def utcnow() -> datetime:
    """Return the current time, timezone aware, like Home Assistant does."""
    return datetime.now(UTC)


class State:
    """The subset of ``homeassistant.core.State`` that the runtime reads."""

    def __init__(
        self,
        entity_id: str,
        state: str,
        attributes: dict[str, Any] | None = None,
        last_updated: datetime | None = None,
    ) -> None:
        """Create one entity state."""
        self.entity_id = entity_id
        self.state = state
        self.attributes = dict(attributes or {})
        self.last_updated = last_updated or utcnow()
        self.last_changed = self.last_updated


class FakeStates:
    """Registry of entity states."""

    def __init__(self) -> None:
        """Start empty."""
        self._states: dict[str, State] = {}

    def set(
        self,
        entity_id: str,
        state: str,
        attributes: dict[str, Any] | None = None,
        last_updated: datetime | None = None,
    ) -> State:
        """Add or replace one entity state."""
        created = State(entity_id, state, attributes, last_updated)
        self._states[entity_id] = created
        return created

    def remove(self, entity_id: str) -> None:
        """Drop one entity state."""
        self._states.pop(entity_id, None)

    def get(self, entity_id: str | None) -> State | None:
        """Return one state or ``None``."""
        if entity_id is None:
            return None
        return self._states.get(entity_id)

    def async_all(self) -> list[State]:
        """Return all known states."""
        return list(self._states.values())


class FakeServices:
    """Records service calls instead of performing them."""

    def __init__(self) -> None:
        """Start with no calls."""
        self.calls: list[dict[str, Any]] = []

    async def async_call(
        self,
        domain: str,
        service: str,
        data: dict[str, Any] | None = None,
        blocking: bool = False,
        **kwargs: Any,
    ) -> None:
        """Record one service call."""
        self.calls.append(
            {"domain": domain, "service": service, "data": dict(data or {}), "blocking": blocking}
        )

    def called(self, domain: str, service: str) -> list[dict[str, Any]]:
        """Return the recorded calls matching a domain and service."""
        return [call for call in self.calls if call["domain"] == domain and call["service"] == service]


class FakePersistentNotification:
    """Records created persistent notifications."""

    def __init__(self) -> None:
        """Start with no notifications."""
        self.created: list[dict[str, Any]] = []

    def async_create(
        self,
        hass: Any,
        message: str,
        title: str | None = None,
        notification_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Record one notification."""
        self.created.append({"message": message, "title": title, "notification_id": notification_id})


class FakeHTTPResponse:
    """Minimal aiohttp response."""

    def __init__(self, status: int = 200, payload: Any = None, text: str = "") -> None:
        """Create a response with an OpenAI-compatible body by default."""
        self.status = status
        self._payload = payload if payload is not None else {"choices": [{"message": {"content": "ok"}}]}
        self._text = text

    async def json(self) -> Any:
        """Return the decoded body."""
        return self._payload

    async def text(self) -> str:
        """Return the raw body."""
        return self._text


class FakePostContext:
    """Async context manager returned by ``FakeHTTPSession.post``."""

    def __init__(self, response: FakeHTTPResponse) -> None:
        """Wrap one response."""
        self._response = response

    async def __aenter__(self) -> FakeHTTPResponse:
        """Enter the response."""
        return self._response

    async def __aexit__(self, *exc_info: Any) -> None:
        """Leave the response."""
        return None


class FakeHTTPSession:
    """Records outgoing HTTP requests instead of sending them.

    This is what makes the AI transport testable: the privacy promise is about
    what leaves the machine, and that can be asserted exactly.
    """

    def __init__(self, response: FakeHTTPResponse | None = None) -> None:
        """Create a session that answers with ``response``."""
        self.response = response or FakeHTTPResponse()
        self.requests: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        json: Any = None,
        headers: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> FakePostContext:
        """Record one POST request."""
        self.requests.append({"url": url, "json": json, "headers": dict(headers or {})})
        return FakePostContext(self.response)

    def sent_text(self) -> str:
        """Return everything ever sent, as one searchable string."""
        return str(self.requests)


class FakeHass:
    """Stand-in for ``HomeAssistant`` with the members the runtime uses."""

    def __init__(self) -> None:
        """Create empty state, services, storage and HTTP session."""
        self.states = FakeStates()
        self.services = FakeServices()
        self.data: dict[str, Any] = {}
        self.http_session = FakeHTTPSession()
        self.notifications = persistent_notification


class FakeConfigEntry:
    """Stand-in for ``ConfigEntry``: the runtime only reads ``options``."""

    def __init__(
        self,
        options: dict[str, Any] | None = None,
        entry_id: str = "test-entry",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Create one config entry."""
        self.entry_id = entry_id
        self.options = dict(options or {})
        self.data = dict(data or {})
        self.title = "PV Manager"


class FakeStore:
    """In-memory replacement for ``homeassistant.helpers.storage.Store``.

    ``async_load`` returns ``None`` when nothing was saved, exactly like the
    real implementation, so the runtime's first-run path is exercised.
    """

    def __init__(self, hass: FakeHass, version: int, key: str) -> None:
        """Remember where this store writes to."""
        self.hass = hass
        self.version = version
        self.key = key
        self.saved_payloads: list[Any] = []

    async def async_load(self) -> Any:
        """Return the previously saved payload, if any."""
        return self.hass.data.get(self.key)

    async def async_save(self, data: Any) -> None:
        """Persist a payload in memory."""
        self.saved_payloads.append(data)
        self.hass.data[self.key] = data

    async def async_remove(self) -> None:
        """Delete the persisted payload."""
        self.hass.data.pop(self.key, None)


persistent_notification = FakePersistentNotification()


def install() -> None:
    """Register the stand-in modules so the integration can be imported.

    Importing ``custom_components.pv_manager.runtime`` must happen *after* this
    call, which is why the test modules call it before their imports.
    """
    if getattr(sys.modules.get("homeassistant"), "_pvm_stub", False):
        return

    homeassistant = StubModule("homeassistant")
    homeassistant._pvm_stub = True

    config_entries = StubModule("homeassistant.config_entries")
    config_entries.ConfigEntry = FakeConfigEntry

    core = StubModule("homeassistant.core")
    core.HomeAssistant = FakeHass
    core.State = State
    core.callback = lambda func: func

    helpers = StubModule("homeassistant.helpers")
    storage = StubModule("homeassistant.helpers.storage")
    storage.Store = FakeStore
    helpers.storage = storage
    aiohttp_client = StubModule("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda hass, *args, **kwargs: hass.http_session
    helpers.aiohttp_client = aiohttp_client

    util = StubModule("homeassistant.util")
    dt = StubModule("homeassistant.util.dt")
    dt.utcnow = utcnow
    dt.now = utcnow
    dt.as_local = lambda value: value
    util.dt = dt

    components = StubModule("homeassistant.components")
    notification_module = StubModule("homeassistant.components.persistent_notification")
    notification_module.async_create = persistent_notification.async_create
    notification_module.async_dismiss = lambda *args, **kwargs: None
    components.persistent_notification = notification_module

    homeassistant.config_entries = config_entries
    homeassistant.core = core
    homeassistant.helpers = helpers
    homeassistant.util = util
    homeassistant.components = components

    sys.modules.update(
        {
            "homeassistant": homeassistant,
            "homeassistant.config_entries": config_entries,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.storage": storage,
            "homeassistant.helpers.aiohttp_client": aiohttp_client,
            "homeassistant.util": util,
            "homeassistant.util.dt": dt,
            "homeassistant.components": components,
            "homeassistant.components.persistent_notification": notification_module,
        }
    )
