"""Optional high-assurance security terminal.

The core already performs deterministic safety checks. The security terminal
adds continuous monitoring of modules, their input/output contracts, repeated
error notifications and optional AI advice. It can never bypass hard limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum


class SecurityLevel(StrEnum):
    """How strongly the security terminal may react."""

    OBSERVE = "observe"
    ASSIST = "assist"
    INTERVENE = "intervene"


class ReactionSpeed(StrEnum):
    """How quickly the terminal reacts to a finding."""

    IMMEDIATE = "immediate"
    THIRTY_SECONDS = "30s"
    FIVE_MINUTES = "5m"
    NEXT_CHECK = "next_check"


class HealthStatus(StrEnum):
    """Health of one module."""

    READY = "ready"
    DEGRADED = "degraded"
    ERROR = "error"
    STOPPED = "stopped"
    DISABLED = "disabled"


class FindingSeverity(StrEnum):
    """Severity of one finding."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(slots=True)
class ModuleContract:
    """Declared inputs and outputs of a module."""

    inputs: set[str] = field(default_factory=set)
    outputs: set[str] = field(default_factory=set)
    produces_units: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ModuleHealth:
    """Runtime health of one module."""

    module_id: str
    status: HealthStatus = HealthStatus.READY
    last_heartbeat: datetime | None = None
    last_error_code: str | None = None
    last_error_de: str | None = None
    last_error_en: str | None = None
    contract: ModuleContract = field(default_factory=ModuleContract)
    observed_inputs: set[str] = field(default_factory=set)
    observed_outputs: set[str] = field(default_factory=set)
    enabled: bool = True
    error_count: int = 0
    consecutive_failures: int = 0


@dataclass(frozen=True, slots=True)
class RiskFinding:
    """One concrete finding with a user-facing explanation."""

    code: str
    severity: FindingSeverity
    module_id: str
    title_de: str
    title_en: str
    detail_de: str
    detail_en: str
    repair_de: str
    repair_en: str
    timestamp: datetime
    intervention_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        """Return a serializable representation."""
        return {
            "code": self.code,
            "severity": self.severity.value,
            "module_id": self.module_id,
            "title_de": self.title_de,
            "title_en": self.title_en,
            "detail_de": self.detail_de,
            "detail_en": self.detail_en,
            "repair_de": self.repair_de,
            "repair_en": self.repair_en,
            "timestamp": self.timestamp.isoformat(),
            "intervention_allowed": self.intervention_allowed,
        }


@dataclass(slots=True)
class TerminalConfig:
    """User-selectable behaviour of the security terminal."""

    level: SecurityLevel = SecurityLevel.OBSERVE
    reaction: ReactionSpeed = ReactionSpeed.THIRTY_SECONDS
    repeat_minutes: int = 15
    repeat_until_resolved: bool = True
    max_repeats: int = 6
    allow_module_pause: bool = False
    allow_safe_stop: bool = False
    allow_emergency_stop: bool = False
    heartbeat_timeout_seconds: int = 300
    stale_data_seconds: int = 300


@dataclass(slots=True)
class SecurityReport:
    """Result of one evaluation cycle."""

    overall: FindingSeverity
    score: int
    findings: list[RiskFinding] = field(default_factory=list)
    paused_modules: list[str] = field(default_factory=list)
    summary_de: str = ""
    summary_en: str = ""

    def as_dict(self) -> dict[str, object]:
        """Return a serializable representation for the UI."""
        return {
            "overall": self.overall.value,
            "score": self.score,
            "findings": [finding.as_dict() for finding in self.findings],
            "paused_modules": list(self.paused_modules),
            "summary_de": self.summary_de,
            "summary_en": self.summary_en,
        }


class SecurityTerminal:
    """Deterministic monitoring; AI advice is added elsewhere."""

    def __init__(self, config: TerminalConfig | None = None) -> None:
        """Create a terminal with an optional custom configuration."""
        self.config = config or TerminalConfig()
        self._last_sent: dict[str, datetime] = {}
        self._repeat_count: dict[str, int] = {}

    def evaluate(
        self,
        *,
        modules: dict[str, ModuleHealth],
        now: datetime,
        emergency_stop: bool = False,
        reading_ages: dict[str, float] | None = None,
        hard_violations: list[str] | None = None,
        balance_ok: bool = True,
        privacy_mode: str = "local_only",
        ai_enabled: bool = False,
    ) -> SecurityReport:
        """Evaluate all modules and produce findings."""
        findings: list[RiskFinding] = []
        if emergency_stop:
            findings.append(
                RiskFinding(
                    code="emergency_stop",
                    severity=FindingSeverity.CRITICAL,
                    module_id="core",
                    title_de="Not-Aus aktiv",
                    title_en="Emergency stop active",
                    detail_de="Alle automatischen Aktionen sind gesperrt.",
                    detail_en="All automatic actions are blocked.",
                    repair_de="Not-Aus im PV-Manager prüfen und bewusst zurücksetzen.",
                    repair_en="Check and consciously reset the emergency stop.",
                    timestamp=now,
                    intervention_allowed=False,
                )
            )

        for module_id, health in modules.items():
            findings.extend(self._check_module(module_id, health, now))
            findings.extend(self._check_contract(module_id, health, now))

        if reading_ages:
            for source, age in reading_ages.items():
                if age > self.config.stale_data_seconds:
                    findings.append(
                        RiskFinding(
                            code="stale_reading",
                            severity=FindingSeverity.WARNING
                            if age < self.config.stale_data_seconds * 3
                            else FindingSeverity.CRITICAL,
                            module_id="core",
                            title_de=f"Daten von {source} sind veraltet",
                            title_en=f"Data from {source} is stale",
                            detail_de=(
                                f"Der Wert ist {round(age)} Sekunden alt. Automatik für betroffene "
                                "Geräte ist pausiert."
                            ),
                            detail_en=(
                                f"The value is {round(age)} seconds old. Automation for affected "
                                "devices is paused."
                            ),
                            repair_de="Sensor, Verbindung oder Energiezähler prüfen.",
                            repair_en="Check sensor, connection or energy meter.",
                            timestamp=now,
                            intervention_allowed=self.config.allow_module_pause,
                        )
                    )

        for violation in hard_violations or []:
            findings.append(
                RiskFinding(
                    code="hard_limit",
                    severity=FindingSeverity.CRITICAL,
                    module_id="core",
                    title_de="Harte Grenze verletzt",
                    title_en="Hard limit violated",
                    detail_de=f"Grenze betroffen: {violation}. Es werden keine neuen Aktionen gestartet.",
                    detail_en=f"Affected limit: {violation}. No new actions are started.",
                    repair_de="Werte und Grenzen im Sicherheitsbereich prüfen, dann bewusst freigeben.",
                    repair_en="Review values and limits in the safety area, then release consciously.",
                    timestamp=now,
                    intervention_allowed=self.config.allow_safe_stop,
                )
            )

        if not balance_ok:
            findings.append(
                RiskFinding(
                    code="energy_balance_unconfirmed",
                    severity=FindingSeverity.WARNING,
                    module_id="core",
                    title_de="Energiebilanz nicht plausibel",
                    title_en="Energy balance not plausible",
                    detail_de="Messwerte passen rechnerisch nicht zusammen. Automatik ist vorsichtig.",
                    detail_en="Readings do not add up. Automation is cautious.",
                    repair_de="Zähler, Vorzeichen und Einheiten in der Geräteprüfung kontrollieren.",
                    repair_en="Check meter, sign conventions and units in device verification.",
                    timestamp=now,
                    intervention_allowed=False,
                )
            )

        if ai_enabled and privacy_mode != "local_only":
            findings.append(
                RiskFinding(
                    code="external_ai_active",
                    severity=FindingSeverity.INFO,
                    module_id="security_terminal",
                    title_de="Externe KI aktiv",
                    title_en="External AI active",
                    detail_de=(
                        "Pseudonymisierte technische Daten können an einen externen KI-Anbieter "
                        "gesendet werden. Keine Gerätenamen, keine Kalenderinhalte."
                    ),
                    detail_en=(
                        "Pseudonymized technical data may be sent to an external AI provider. "
                        "No device names, no calendar contents."
                    ),
                    repair_de=(
                        "Nur einschalten lassen, wenn du das bewusst möchtest. "
                        "Der lokale Modus bleibt immer verfügbar."
                    ),
                    repair_en=("Only keep this on deliberately. Local mode always remains available."),
                    timestamp=now,
                    intervention_allowed=False,
                )
            )

        overall = FindingSeverity.INFO
        if any(finding.severity is FindingSeverity.CRITICAL for finding in findings):
            overall = FindingSeverity.CRITICAL
        elif any(finding.severity is FindingSeverity.WARNING for finding in findings):
            overall = FindingSeverity.WARNING
        score = self._score(findings)
        paused = self._decide_interventions(findings)
        summary_de, summary_en = self._summary(overall, findings)
        return SecurityReport(
            overall=overall,
            score=score,
            findings=findings,
            paused_modules=paused,
            summary_de=summary_de,
            summary_en=summary_en,
        )

    def _check_module(self, module_id: str, health: ModuleHealth, now: datetime) -> list[RiskFinding]:
        findings: list[RiskFinding] = []
        if not health.enabled:
            return findings
        if health.status is HealthStatus.ERROR or health.consecutive_failures >= 3:
            findings.append(
                RiskFinding(
                    code="module_error",
                    severity=FindingSeverity.CRITICAL,
                    module_id=module_id,
                    title_de=f"Modul {module_id} hat einen Fehler",
                    title_en=f"Module {module_id} has an error",
                    detail_de=health.last_error_de or "Das Modul meldet wiederholt einen Fehler.",
                    detail_en=health.last_error_en or "The module reports a repeated error.",
                    repair_de="Modul kurz pausieren, Einstellungen prüfen und Protokoll ansehen.",
                    repair_en="Pause the module briefly, review settings and inspect the log.",
                    timestamp=now,
                    intervention_allowed=self.config.allow_module_pause,
                )
            )
        if health.last_heartbeat is None or (
            (now - health.last_heartbeat).total_seconds() > self.config.heartbeat_timeout_seconds
        ):
            findings.append(
                RiskFinding(
                    code="module_heartbeat",
                    severity=FindingSeverity.WARNING,
                    module_id=module_id,
                    title_de=f"Modul {module_id} meldet sich nicht",
                    title_en=f"Module {module_id} is not reporting",
                    detail_de=(
                        "Der letzte Lebenszeichen ist zu alt. Das Modul wird als eingeschränkt behandelt."
                    ),
                    detail_en="Last heartbeat is too old. The module is treated as degraded.",
                    repair_de=(
                        "Home Assistant neu laden; wenn das nicht hilft, "
                        "Modul deaktivieren und Fehler melden."
                    ),
                    repair_en=(
                        "Reload Home Assistant; if that does not help, "
                        "disable the module and report the issue."
                    ),
                    timestamp=now,
                    intervention_allowed=False,
                )
            )
        elif health.status is HealthStatus.DEGRADED:
            findings.append(
                RiskFinding(
                    code="module_degraded",
                    severity=FindingSeverity.WARNING,
                    module_id=module_id,
                    title_de=f"Modul {module_id} ist eingeschränkt",
                    title_en=f"Module {module_id} is degraded",
                    detail_de=health.last_error_de or "Ein Teil der Funktionen arbeitet nicht vollständig.",
                    detail_en=health.last_error_en or "Part of the functionality is not fully available.",
                    repair_de="Prüfen, ob benötigte Sensoren verfügbar sind.",
                    repair_en="Check whether required sensors are available.",
                    timestamp=now,
                    intervention_allowed=False,
                )
            )
        return findings

    def _check_contract(self, module_id: str, health: ModuleHealth, now: datetime) -> list[RiskFinding]:
        if not health.enabled or health.status in {HealthStatus.DISABLED, HealthStatus.STOPPED}:
            return []
        missing_inputs = health.contract.inputs - health.observed_inputs
        missing_outputs = health.contract.outputs - health.observed_outputs
        if not missing_inputs and not missing_outputs:
            return []
        return [
            RiskFinding(
                code="module_io_contract",
                severity=FindingSeverity.WARNING,
                module_id=module_id,
                title_de=f"Ein-/Ausgaben von {module_id} passen nicht",
                title_en=f"Inputs/outputs of {module_id} do not match",
                detail_de=(
                    "Fehlende Eingaben: "
                    + (", ".join(sorted(missing_inputs)) or "keine")
                    + ". Fehlende Ausgaben: "
                    + (", ".join(sorted(missing_outputs)) or "keine")
                    + "."
                ),
                detail_en=(
                    "Missing inputs: "
                    + (", ".join(sorted(missing_inputs)) or "none")
                    + ". Missing outputs: "
                    + (", ".join(sorted(missing_outputs)) or "none")
                    + "."
                ),
                repair_de="Gerätezuordnung und Modul-Einstellungen prüfen.",
                repair_en="Check device assignment and module settings.",
                timestamp=now,
                intervention_allowed=False,
            )
        ]

    def _score(self, findings: list[RiskFinding]) -> int:
        score = 100
        for finding in findings:
            if finding.severity is FindingSeverity.CRITICAL:
                score -= 25
            elif finding.severity is FindingSeverity.WARNING:
                score -= 8
        return max(score, 0)

    def _decide_interventions(self, findings: list[RiskFinding]) -> list[str]:
        if self.config.level is not SecurityLevel.INTERVENE:
            return []
        paused: list[str] = []
        for finding in findings:
            if not finding.intervention_allowed:
                continue
            if (
                self.config.allow_module_pause
                and finding.module_id not in {"core", *paused}
                and finding.severity is FindingSeverity.CRITICAL
            ):
                paused.append(finding.module_id)
        return paused

    def _summary(self, overall: FindingSeverity, findings: list[RiskFinding]) -> tuple[str, str]:
        critical = sum(1 for finding in findings if finding.severity is FindingSeverity.CRITICAL)
        warning = sum(1 for finding in findings if finding.severity is FindingSeverity.WARNING)
        if overall is FindingSeverity.CRITICAL:
            return (
                f"{critical} kritische und {warning} warnende Hinweise. Automatik ist eingeschränkt.",
                f"{critical} critical and {warning} warning findings. Automation is limited.",
            )
        if overall is FindingSeverity.WARNING:
            return (
                f"{warning} Hinweise. Das System läuft, benötigt aber Aufmerksamkeit.",
                f"{warning} findings. The system runs but needs attention.",
            )
        return ("Alles in Ordnung.", "Everything is fine.")

    def due_notifications(
        self,
        findings: list[RiskFinding],
        *,
        now: datetime,
    ) -> list[RiskFinding]:
        """Return findings that should be notified again right now."""
        due: list[RiskFinding] = []
        for finding in findings:
            if finding.severity is FindingSeverity.INFO:
                continue
            last = self._last_sent.get(finding.code)
            repeats = self._repeat_count.get(finding.code, 0)
            if repeats >= self.config.max_repeats:
                continue
            if last is None:
                self._last_sent[finding.code] = now
                self._repeat_count[finding.code] = 1
                due.append(finding)
                continue
            if now - last >= timedelta(minutes=self.config.repeat_minutes):
                self._last_sent[finding.code] = now
                self._repeat_count[finding.code] = repeats + 1
                due.append(finding)
        return due
