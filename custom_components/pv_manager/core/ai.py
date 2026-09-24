"""AI advisory layer.

Rules enforced here:

* an AI provider is optional,
* local rules always exist and never need a network,
* Groq is the suggested external provider, other OpenAI-compatible providers
  can be selected as well,
* the provider receives only the previewed, pseudonymized payload,
* the result is advice and a repair description, never a device command,
* the AI has no tools and no service access.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

from .privacy import PayloadPreview, PrivacyMode, PrivacySettings, build_payload
from .security import SecurityReport

Transport = Callable[[dict[str, Any]], Awaitable[str]]


class ReportInterval(StrEnum):
    """How often AI feedback is generated."""

    OFF = "off"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    ON_ERROR = "on_error"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class ProviderInfo:
    """Static description of a provider."""

    provider_id: str
    name_de: str
    name_en: str
    local: bool
    suggested: bool
    endpoint_default: str
    model_default: str
    privacy_note_de: str
    privacy_note_en: str


PROVIDER_CATALOG: tuple[ProviderInfo, ...] = (
    ProviderInfo(
        provider_id="local_rules",
        name_de="Lokale Regeln (keine Cloud)",
        name_en="Local rules (no cloud)",
        local=True,
        suggested=True,
        endpoint_default="",
        model_default="deterministic",
        privacy_note_de="Es verlassen keine Daten das System.",
        privacy_note_en="No data leaves the system.",
    ),
    ProviderInfo(
        provider_id="local_model",
        name_de="Lokales Modell (OpenAI-kompatibel)",
        name_en="Local model (OpenAI compatible)",
        local=True,
        suggested=False,
        endpoint_default="http://homeassistant.local:11434/v1",
        model_default="llama3.1",
        privacy_note_de="Daten bleiben im eigenen Netzwerk, sofern das Modell lokal läuft.",
        privacy_note_en="Data stays in your own network as long as the model runs locally.",
    ),
    ProviderInfo(
        provider_id="groq",
        name_de="Groq (empfohlen für Cloud)",
        name_en="Groq (recommended for cloud)",
        local=False,
        suggested=True,
        endpoint_default="https://api.groq.com/openai/v1",
        model_default="llama-3.3-70b-versatile",
        privacy_note_de=(
            "Daten werden an Groq übertragen. Standardmäßig keine dauerhafte Speicherung, "
            "temporär bis zu 30 Tage möglich; Zero Data Retention im Groq-Konto aktivierbar. "
            "Nutzungsmetadaten werden weiterhin verarbeitet."
        ),
        privacy_note_en=(
            "Data is transmitted to Groq. No permanent storage by default, temporary retention "
            "up to 30 days is possible; Zero Data Retention can be enabled in the Groq account. "
            "Usage metadata is still processed."
        ),
    ),
    ProviderInfo(
        provider_id="openai_compatible",
        name_de="Anderer OpenAI-kompatibler Anbieter",
        name_en="Other OpenAI-compatible provider",
        local=False,
        suggested=False,
        endpoint_default="",
        model_default="",
        privacy_note_de=(
            "Der Nutzer ist verantwortlich, die Datenschutzregeln des Anbieters zu prüfen. "
            "PV Manager sendet nur die angezeigte, pseudonymisierte Nutzlast."
        ),
        privacy_note_en=(
            "The user is responsible for reviewing the provider's privacy rules. PV Manager "
            "sends only the previewed, pseudonymized payload."
        ),
    ),
)


@dataclass(slots=True)
class ProviderConfig:
    """Configured provider instance."""

    provider_id: str = "local_rules"
    endpoint: str = ""
    model: str = ""
    enabled: bool = False
    api_key_set: bool = False


@dataclass(slots=True)
class AIRequest:
    """Prepared advisory request."""

    preview: PayloadPreview
    prompt_de: str
    prompt_en: str
    locale: str = "de"

    @property
    def prompt(self) -> str:
        """Return the prompt in the language the user selected."""
        return self.prompt_en if self.locale == "en" else self.prompt_de


@dataclass(slots=True)
class AIReport:
    """Advisory result shown to the user."""

    provider_id: str
    created_at: datetime
    title_de: str
    title_en: str
    summary_de: str
    summary_en: str
    repair_de: list[str] = field(default_factory=list)
    repair_en: list[str] = field(default_factory=list)
    external_data_sent: bool = False
    warning_de: str = ""
    warning_en: str = ""
    raw_answer: str = ""
    ai_can_control: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        return {
            "provider_id": self.provider_id,
            "created_at": self.created_at.isoformat(),
            "title_de": self.title_de,
            "title_en": self.title_en,
            "summary_de": self.summary_de,
            "summary_en": self.summary_en,
            "repair_de": list(self.repair_de),
            "repair_en": list(self.repair_en),
            "external_data_sent": self.external_data_sent,
            "warning_de": self.warning_de,
            "warning_en": self.warning_en,
            "ai_can_control": False,
        }


class AIProvider(Protocol):
    """Minimal provider interface."""

    provider_id: str
    local: bool

    async def complete(self, request: AIRequest) -> str:
        """Return a textual advisory answer."""
        ...


class LocalRulesProvider:
    """Deterministic local provider that needs no network."""

    provider_id = "local_rules"
    local = True

    def __init__(self, locale: str = "de") -> None:
        """Store the fallback locale used when a request carries none."""
        self.locale = locale

    async def complete(self, request: AIRequest) -> str:
        """Return a structured local report in the language of the request."""
        # The request wins over the constructor, because the user can change
        # the language at any time while the provider is long lived.
        german = (request.locale or self.locale) == "de"
        payload = request.preview.payload
        findings = payload.get("findings", [])
        lines: list[str] = []
        if not findings:
            lines.append("Keine Auffälligkeiten gefunden." if german else "No findings.")
            return "\n".join(lines)
        for finding in findings:
            severity = finding.get("severity", "info")
            module = finding.get("module", "core")
            code = finding.get("code", "unknown")
            if severity == "critical":
                lines.append(
                    f"KRITISCH in {module}: {code}. Bitte zuerst dieses Modul prüfen."
                    if german
                    else f"CRITICAL in {module}: {code}. Check this module first."
                )
            elif severity == "warning":
                lines.append(
                    f"Warnung in {module}: {code}. Sensor und Einstellungen prüfen."
                    if german
                    else f"Warning in {module}: {code}. Check sensor and settings."
                )
            else:
                lines.append(f"Hinweis in {module}: {code}." if german else f"Note in {module}: {code}.")
        return "\n".join(lines)


class OpenAICompatibleProvider:
    """Provider that sends an OpenAI-compatible chat request."""

    local = False

    def __init__(
        self,
        *,
        provider_id: str,
        endpoint: str,
        model: str,
        transport: Transport,
        language: str = "de",
    ) -> None:
        """Create a provider around an injected transport function."""
        self.provider_id = provider_id
        self.endpoint = endpoint
        self.model = model
        self.transport = transport
        self.language = language

    def build_request(self, request: AIRequest) -> dict[str, Any]:
        """Build the provider request without any local identifiers.

        The user's language is taken from the request, so an English user is not
        answered in German. The system prompt must say the same thing either
        way: the AI advises and never controls anything.
        """
        english = (request.locale or self.language) == "en"
        system = (
            "You are a safety-oriented PV and energy system adviser. You must not "
            "control devices or execute commands. Answer with analysis, risk, a "
            "short summary and concrete repair steps only. Use only the data given."
            if english
            else (
                "Du bist ein sicherheitsorientierter PV- und Energiesystem-Berater. "
                "Du darfst keine Geräte steuern und keine Befehle ausführen. Antworte "
                "nur mit Analyse, Risiko, kurzer Zusammenfassung und konkreten "
                "Reparaturschritten. Nutze ausschließlich die übergebenen Daten."
            )
        )
        return {
            "endpoint": self.endpoint,
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 700,
        }

    async def complete(self, request: AIRequest) -> str:
        """Send the request through the injected transport."""
        provider_request = self.build_request(request)
        provider_request["payload"] = request.preview.payload
        return await self.transport(provider_request)


class GroqProvider(OpenAICompatibleProvider):
    """Suggested external provider."""

    def __init__(
        self,
        *,
        model: str,
        transport: Transport,
        endpoint: str | None = None,
        language: str = "de",
    ) -> None:
        """Create a Groq provider around an injected transport."""
        super().__init__(
            provider_id="groq",
            endpoint=endpoint or "https://api.groq.com/openai/v1",
            model=model,
            transport=transport,
            language=language,
        )


class AIAdvisor:
    """Prepare, validate and execute advisory requests."""

    def __init__(
        self,
        *,
        providers: dict[str, AIProvider] | None = None,
        settings: PrivacySettings | None = None,
    ) -> None:
        """Create an advisor with providers and privacy settings."""
        self.providers = providers or {"local_rules": LocalRulesProvider()}
        self.settings = settings or PrivacySettings()

    def prepare(
        self,
        *,
        vault: Any,
        provider_id: str,
        modules: list[dict[str, Any]],
        report: SecurityReport,
        summary: dict[str, Any] | None = None,
        report_id: str | None = None,
        locale: str = "de",
    ) -> AIRequest:
        """Build the privacy preview that the user must confirm."""
        preview = build_payload(
            vault=vault,
            provider=provider_id,
            settings=self.settings,
            devices=modules,
            findings=[finding.as_dict() for finding in report.findings],
            summary=summary or {},
            report_id=report_id,
            locale=locale,
        )
        prompt = (
            "Analysiere diesen pseudonymisierten PV-Manager-Bericht. Nenne die wichtigsten "
            "Risiken, eine kurze Zusammenfassung und genaue Reparaturschritte. Du darfst "
            "keine Geräte steuern.\n\n"
            f"{preview.payload}"
        )
        prompt_en = (
            "Analyse this pseudonymized PV Manager report. Name the main risks, a short "
            "summary and exact repair steps. You must not control any devices.\n\n"
            f"{preview.payload}"
        )
        return AIRequest(
            preview=preview,
            prompt_de=prompt,
            prompt_en=prompt_en,
            locale="en" if locale == "en" else "de",
        )

    async def analyse(
        self,
        request: AIRequest,
        *,
        now: datetime,
        provider_id: str,
        user_confirmed: bool = False,
    ) -> AIReport:
        """Execute a prepared request.

        External providers require an explicit confirmation and a
        non-local privacy mode. The local provider always works.
        """
        provider = self.providers.get(provider_id)
        if provider is None:
            return self._error_report(provider_id, now, "unknown_provider")

        if not provider.local:
            if self.settings.mode is PrivacyMode.LOCAL_ONLY:
                return self._error_report(provider_id, now, "local_mode_blocks_external_ai")
            if not user_confirmed:
                return self._error_report(provider_id, now, "preview_not_confirmed")
            if not self.settings.allow_external_provider:
                return self._error_report(provider_id, now, "external_provider_not_allowed")

        answer = await provider.complete(request)
        return self._report_from_answer(provider, answer, request, now)

    def _report_from_answer(
        self,
        provider: AIProvider,
        answer: str,
        request: AIRequest,
        now: datetime,
    ) -> AIReport:
        external = not provider.local
        lines = [line.strip("-• \t") for line in answer.splitlines() if line.strip()]
        repair_markers = ("prüf", "check", "repair", "sensor", "reset")
        repairs = [line for line in lines if any(key in line.lower() for key in repair_markers)]
        return AIReport(
            provider_id=provider.provider_id,
            created_at=now,
            title_de="Sicherheitsbericht",
            title_en="Security report",
            summary_de=answer,
            summary_en=answer,
            repair_de=repairs[:5],
            repair_en=repairs[:5],
            external_data_sent=external,
            warning_de=request.preview.warning_de,
            warning_en=request.preview.warning_en,
            raw_answer=answer,
        )

    def _error_report(self, provider_id: str, now: datetime, code: str) -> AIReport:
        return AIReport(
            provider_id=provider_id,
            created_at=now,
            title_de="Bericht nicht möglich",
            title_en="Report not possible",
            summary_de=f"Der Bericht wurde aus Sicherheitsgründen nicht erstellt: {code}.",
            summary_en=f"The report was not created for safety reasons: {code}.",
            warning_de="Lokaler Modus oder fehlende Bestätigung.",
            warning_en="Local mode or missing confirmation.",
        )


@dataclass(slots=True)
class ReportSchedule:
    """Track when the next report is due."""

    interval: ReportInterval = ReportInterval.DAILY
    last_run: datetime | None = None
    force_on_critical: bool = True

    def next_due(self, now: datetime) -> datetime | None:
        """Return the next due time, or None when disabled/manual."""
        if self.interval in {ReportInterval.OFF, ReportInterval.MANUAL}:
            return None
        if self.last_run is None:
            return now
        delta = {
            ReportInterval.HOURLY: timedelta(hours=1),
            ReportInterval.DAILY: timedelta(days=1),
            ReportInterval.WEEKLY: timedelta(weeks=1),
        }.get(self.interval)
        return None if delta is None else self.last_run + delta

    def is_due(self, now: datetime, *, critical: bool = False) -> bool:
        """Return True when a report should be generated now."""
        if self.interval is ReportInterval.ON_ERROR:
            return critical
        if self.force_on_critical and critical:
            return True
        due = self.next_due(now)
        return due is not None and now >= due

    def mark_run(self, now: datetime) -> None:
        """Record a successful or attempted run."""
        self.last_run = now
