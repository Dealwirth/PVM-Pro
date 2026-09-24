"""Privacy engine for local and AI-assisted analysis.

Design rules:

* local-only is the default; nothing leaves the machine,
* aliases are one-time and derived with a local secret,
* a user nickname is never sent,
* a payload is validated before it may be sent,
* the user can always preview exactly what would leave the system.

Pseudonymization reduces risk but cannot make cloud processing anonymous.
The UI therefore shows an explicit warning for every external provider.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

FORBIDDEN_KEYS = {
    "entity_id",
    "device_id",
    "device_name",
    "name",
    "friendly_name",
    "nickname",
    "area",
    "area_name",
    "location",
    "latitude",
    "longitude",
    "address",
    "calendar",
    "calendar_title",
    "summary",
    "description",
    "api_key",
    "token",
    "access_token",
    "refresh_token",
    "ip",
    "ip_address",
    "mac",
    "mac_address",
    "vin",
    "license_plate",
    "user",
    "user_id",
    "person",
    "email",
    "phone",
}

FORBIDDEN_TEXT_HINTS = (
    "straße",
    "strasse",
    "street",
    "http://",
    "https://",
    "www.",
    "@",
)


class PrivacyMode(StrEnum):
    """How much data may leave the local system."""

    LOCAL_ONLY = "local_only"
    PSEUDONYMOUS = "pseudonymous"
    EXTENDED = "extended"


@dataclass(slots=True)
class PrivacySettings:
    """User-selected privacy options."""

    mode: PrivacyMode = PrivacyMode.LOCAL_ONLY
    include_numbers: bool = True
    include_error_codes: bool = True
    include_weather: bool = True
    include_energy_history: bool = False
    include_calendar_presence_only: bool = False
    include_module_versions: bool = True
    rotate_alias_every_report: bool = True
    allow_external_provider: bool = False
    preview_required: bool = True


@dataclass(slots=True)
class PayloadPreview:
    """Human-readable preview of an outgoing payload."""

    provider: str
    mode: PrivacyMode
    fields: list[str] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)
    warning_de: str = ""
    warning_en: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        """Return a serializable preview for the UI."""
        return {
            "provider": self.provider,
            "mode": self.mode.value,
            "fields": list(self.fields),
            "omitted": list(self.omitted),
            "warning_de": self.warning_de,
            "warning_en": self.warning_en,
            "payload": self.payload,
        }


class AliasVault:
    """Create short-lived, non-guessable aliases for local device ids."""

    def __init__(self, secret: bytes | None = None) -> None:
        """Create a vault with an optional fixed secret (tests only)."""
        self._secret = secret or secrets.token_bytes(32)
        self._local_mapping: dict[str, str] = {}

    def alias_for(self, device_id: str, *, report_id: str) -> str:
        """Return a one-time alias that is not linkable across reports."""
        digest = hmac.new(
            self._secret,
            f"{report_id}:{device_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        alias = f"device-{digest[:8]}"
        self._local_mapping[alias] = device_id
        return alias

    def resolve_local(self, alias: str) -> str | None:
        """Resolve an alias locally; never expose this mapping externally."""
        return self._local_mapping.get(alias)

    def clear(self) -> None:
        """Forget the local mapping, for example when the user deletes PV Manager."""
        self._local_mapping.clear()
        self._secret = secrets.token_bytes(32)


def contains_forbidden_key(payload: Any) -> list[str]:
    """Recursively find forbidden keys in a payload."""
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in FORBIDDEN_KEYS:
                found.append(key)
            found.extend(contains_forbidden_key(value))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            found.extend(contains_forbidden_key(item))
    return found


def looks_like_identifying_text(value: str) -> bool:
    """Return True when free text probably contains identifying information."""
    lowered = value.lower()
    return any(hint in lowered for hint in FORBIDDEN_TEXT_HINTS)


def sanitize_value(value: Any, *, max_text_length: int = 80) -> Any:
    """Sanitize one value for external analysis."""
    if isinstance(value, dict):
        # Drop forbidden keys entirely. Metrics come from devices and may use
        # arbitrary attribute names, so silently dropping is safer than raising
        # during a report. The top-level payload is still validated afterwards.
        return {key: sanitize_value(item) for key, item in value.items() if key.lower() not in FORBIDDEN_KEYS}
    if isinstance(value, (list, tuple)):
        return [sanitize_value(item) for item in value]
    if isinstance(value, str):
        if looks_like_identifying_text(value):
            return "[redacted]"
        return value[:max_text_length]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:max_text_length]


def build_device_context(
    *,
    vault: AliasVault,
    report_id: str,
    devices: list[dict[str, Any]],
    settings: PrivacySettings,
) -> list[dict[str, Any]]:
    """Build the pseudonymous device list for an AI request."""
    context: list[dict[str, Any]] = []
    for device in devices:
        alias = vault.alias_for(str(device.get("id", "unknown")), report_id=report_id)
        entry: dict[str, Any] = {
            "alias": alias,
            "category": str(device.get("kind", "unknown")),
            "capabilities": sorted(str(cap) for cap in device.get("capabilities", [])),
            "automation_allowed": bool(device.get("automation_allowed", False)),
        }
        if settings.include_numbers:
            entry.update(sanitize_value(device.get("metrics", {})))
        if settings.include_error_codes:
            entry["error_codes"] = [str(code)[:40] for code in device.get("error_codes", [])]
        if settings.include_module_versions:
            entry["module"] = str(device.get("module", "core"))
        context.append(sanitize_value(entry))
    return context


def build_payload(
    *,
    vault: AliasVault,
    provider: str,
    settings: PrivacySettings,
    devices: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    summary: dict[str, Any],
    report_id: str | None = None,
    locale: str = "de",
) -> PayloadPreview:
    """Build and validate a payload that may be sent to an AI provider."""
    report = report_id or secrets.token_hex(8)
    omitted: list[str] = []
    fields: list[str] = ["summary", "findings"]
    # "summary" is a forbidden key because calendar event titles use it in Home
    # Assistant. Our own neutral summary is therefore called "overview".
    payload: dict[str, Any] = {
        "schema": "pv_manager.security_report.v1",
        "locale": "en" if locale == "en" else "de",
        "report_id": report,
        "overview": sanitize_value(summary),
        "findings": [
            {
                "code": str(finding.get("code", "unknown"))[:40],
                "severity": str(finding.get("severity", "info"))[:20],
                "module": str(finding.get("module_id", "core"))[:40],
            }
            for finding in findings
        ],
    }
    if settings.mode is not PrivacyMode.LOCAL_ONLY:
        payload["devices"] = build_device_context(
            vault=vault,
            report_id=report,
            devices=devices,
            settings=settings,
        )
        fields.append("devices")
    else:
        omitted.append("devices")

    if settings.include_energy_history:
        payload["energy_history"] = sanitize_value(summary.get("energy_history", []))
        fields.append("energy_history")
    else:
        omitted.append("energy_history")

    if settings.include_weather:
        payload["weather"] = sanitize_value(summary.get("weather", {}))
        fields.append("weather")
    else:
        omitted.append("weather")

    if settings.include_calendar_presence_only:
        payload["presence"] = bool(summary.get("presence", False))
        fields.append("presence")
    else:
        omitted.append("calendar_presence")

    forbidden = contains_forbidden_key(payload)
    if forbidden:
        raise ValueError(f"Privacy violation: forbidden keys in payload: {sorted(set(forbidden))}")

    warning_de = ""
    warning_en = ""
    if settings.mode is PrivacyMode.LOCAL_ONLY:
        warning_de = "Lokalmodus: Es werden keine Daten an einen Anbieter gesendet."
        warning_en = "Local mode: no data is sent to any provider."
    elif settings.mode is PrivacyMode.PSEUDONYMOUS:
        warning_de = (
            "Warnung: Pseudonymisierte technische Daten werden an einen externen Anbieter "
            "gesendet. Eine völlige Anonymität kann nicht garantiert werden."
        )
        warning_en = (
            "Warning: pseudonymized technical data is sent to an external provider. Full "
            "anonymity cannot be guaranteed."
        )
    else:
        warning_de = (
            "Warnung: Erweiterte Datenübertragung aktiv. Nur verwenden, wenn du den Anbieter "
            "und seine Datenschutzregeln geprüft hast."
        )
        warning_en = (
            "Warning: extended data transfer is active. Only use this after reviewing the "
            "provider and its privacy rules."
        )

    return PayloadPreview(
        provider=provider,
        mode=settings.mode,
        fields=fields,
        omitted=omitted,
        warning_de=warning_de,
        warning_en=warning_en,
        payload=payload,
    )
