"""Privacy-aware audit log.

Every automatic action, manual override, module change and security finding is
recorded with its reason. Tokens, API keys and personal free text are removed
before anything is stored or exported.
"""

from __future__ import annotations

import csv
import io
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "authorization",
    "cookie",
    "email",
    "phone",
    "latitude",
    "longitude",
    "address",
    "vin",
    "license_plate",
}


class AuditKind(StrEnum):
    """Categories of audit entries."""

    ACTION = "action"
    DECISION = "decision"
    MODULE = "module"
    SETTING = "setting"
    SECURITY = "security"
    PRIVACY = "privacy"
    CALIBRATION = "calibration"
    AI = "ai"
    SYSTEM = "system"


@dataclass(slots=True)
class AuditEntry:
    """One redacted audit record."""

    timestamp: datetime
    kind: AuditKind
    message_de: str
    message_en: str
    actor: str = "system"
    module_id: str = "core"
    reason: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "kind": self.kind.value,
            "message_de": self.message_de,
            "message_en": self.message_en,
            "actor": self.actor,
            "module_id": self.module_id,
            "reason": self.reason,
            "context": self.context,
        }


def redact(value: Any) -> Any:
    """Recursively remove sensitive values."""
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        for key in SENSITIVE_KEYS:
            if lowered.startswith(f"{key}=") or lowered.startswith(f"{key}:"):
                return "[redacted]"
        return value
    return value


class AuditLog:
    """Bounded in-memory audit log with optional persistence callback."""

    def __init__(self, limit: int = 400) -> None:
        """Create a log with a maximum number of entries."""
        self.limit = max(limit, 1)
        self._entries: deque[AuditEntry] = deque(maxlen=self.limit)

    def add(self, entry: AuditEntry) -> None:
        """Add a redacted entry."""
        entry.context = redact(entry.context)
        self._entries.appendleft(entry)

    def record(
        self,
        *,
        kind: AuditKind,
        message_de: str,
        message_en: str,
        now: datetime,
        actor: str = "system",
        module_id: str = "core",
        reason: str = "",
        context: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Create and store one entry."""
        entry = AuditEntry(
            timestamp=now,
            kind=kind,
            message_de=message_de,
            message_en=message_en,
            actor=actor,
            module_id=module_id,
            reason=reason,
            context=context or {},
        )
        self.add(entry)
        return entry

    def entries(self) -> list[AuditEntry]:
        """Return entries, newest first."""
        return list(self._entries)

    def clear(self) -> None:
        """Delete all entries; used when the integration is removed."""
        self._entries.clear()

    def to_json(self) -> str:
        """Export entries as JSON."""
        return json.dumps([entry.as_dict() for entry in self.entries()], ensure_ascii=False, indent=2)

    def to_csv(self) -> str:
        """Export entries as CSV."""
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=["timestamp", "kind", "module_id", "actor", "message_de", "reason"],
        )
        writer.writeheader()
        for entry in self.entries():
            writer.writerow(
                {
                    "timestamp": entry.timestamp.isoformat(),
                    "kind": entry.kind.value,
                    "module_id": entry.module_id,
                    "actor": entry.actor,
                    "message_de": entry.message_de,
                    "reason": entry.reason,
                }
            )
        return buffer.getvalue()

    def as_dicts(self) -> list[dict[str, Any]]:
        """Return serializable entries."""
        return [entry.as_dict() for entry in self.entries()]
