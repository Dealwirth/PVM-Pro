"""Bounded device calibration state machine.

A learning run may switch one supported device on and off a few times to
compare its measured power with the grid and household balance. It is strictly
bounded and always abortable. It never changes voltage, fuses or tariffs and is
not an electrical certificate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum


class CalibrationState(StrEnum):
    """Lifecycle of a learning run."""

    IDLE = "idle"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    BASELINE = "baseline"
    DEVICE_ON = "device_on"
    DEVICE_OFF = "device_off"
    FINISHED = "finished"
    ABORTED = "aborted"


@dataclass(slots=True)
class CalibrationLimits:
    """Hard boundaries of a run."""

    max_power_w: float = 2000.0
    max_energy_kwh: float = 0.5
    max_seconds_on: float = 120.0
    baseline_seconds: float = 60.0
    off_seconds: float = 60.0
    repetitions: int = 2
    minimum_grid_headroom_w: float = 500.0


@dataclass(slots=True)
class CalibrationRun:
    """State and measurements of one run."""

    device_id: str
    entity_id: str
    limits: CalibrationLimits
    state: CalibrationState = CalibrationState.IDLE
    started_at: datetime | None = None
    step: int = 0
    used_energy_kwh: float = 0.0
    baseline_power_w: float | None = None
    device_power_w: float | None = None
    measured_delta_w: float | None = None
    aborted_reason: str | None = None
    log: list[str] = field(default_factory=list)

    def can_start(self) -> tuple[bool, str]:
        """Return whether the run may start."""
        if self.state is not CalibrationState.IDLE:
            return False, "already_running"
        if self.limits.repetitions < 1:
            return False, "no_repetitions"
        if self.limits.max_power_w <= 0 or self.limits.max_energy_kwh <= 0:
            return False, "invalid_limits"
        return True, "ok"

    def start(self, now: datetime) -> None:
        """Start the baseline phase."""
        self.state = CalibrationState.BASELINE
        self.started_at = now
        self.log.append("baseline_started")

    def baseline_done(self, baseline_power_w: float, now: datetime) -> bool:
        """Record the baseline and switch to the device-on phase."""
        if self.state is not CalibrationState.BASELINE:
            return False
        if self.started_at is None or (now - self.started_at).total_seconds() < self.limits.baseline_seconds:
            return False
        self.baseline_power_w = baseline_power_w
        self.state = CalibrationState.DEVICE_ON
        self.started_at = now
        self.step += 1
        self.log.append(f"device_on_step_{self.step}")
        return True

    def device_on_allowed(self, *, grid_headroom_w: float, device_power_w: float) -> tuple[bool, str]:
        """Check whether the device may stay on."""
        if self.state is not CalibrationState.DEVICE_ON:
            return False, "not_in_device_on_state"
        if device_power_w > self.limits.max_power_w:
            return False, "device_power_limit"
        if grid_headroom_w < self.limits.minimum_grid_headroom_w:
            return False, "grid_headroom_too_low"
        if self.used_energy_kwh >= self.limits.max_energy_kwh:
            return False, "energy_budget_reached"
        elapsed_seconds = (
            (datetime.now(self.started_at.tzinfo) - self.started_at).total_seconds()
            if self.started_at is not None
            else 0.0
        )
        if elapsed_seconds > self.limits.max_seconds_on:
            return False, "time_limit_reached"
        return True, "ok"

    def record_measurement(self, device_power_w: float, seconds: float) -> None:
        """Accumulate measured energy."""
        self.device_power_w = device_power_w
        self.used_energy_kwh += max(device_power_w, 0.0) * max(seconds, 0.0) / 3_600_000.0
        if self.baseline_power_w is not None:
            self.measured_delta_w = device_power_w - self.baseline_power_w

    def device_off(self, now: datetime) -> bool:
        """Finish the current on-phase; return True when all repeats are done."""
        if self.state is not CalibrationState.DEVICE_ON:
            return False
        self.state = CalibrationState.DEVICE_OFF
        self.started_at = now
        self.log.append(f"device_off_step_{self.step}")
        return self.step >= self.limits.repetitions

    def finish(self) -> None:
        """Mark the run as finished."""
        self.state = CalibrationState.FINISHED
        self.log.append("finished")

    def abort(self, reason: str) -> None:
        """Abort the run for a safety reason."""
        self.aborted_reason = reason
        self.state = CalibrationState.ABORTED
        self.log.append(f"aborted:{reason}")

    def summary_de(self) -> str:
        """Return a plain-language summary."""
        if self.state is CalibrationState.ABORTED:
            return f"Lernlauf abgebrochen: {self.aborted_reason}. Das Gerät wurde ausgeschaltet."
        if self.measured_delta_w is None:
            return "Noch keine brauchbare Messung vorhanden."
        watts = round(self.measured_delta_w)
        confidence = "hoch" if self.step >= 2 else "niedrig"
        return (
            f"Gemessener zusätzlicher Verbrauch: etwa {watts} W. "
            f"Verbrauchte Testenergie: {self.used_energy_kwh:.3f} kWh. "
            f"Verlässlichkeit: {confidence}."
        )

    def summary_en(self) -> str:
        """Return the English summary."""
        if self.state is CalibrationState.ABORTED:
            return f"Learning run aborted: {self.aborted_reason}. The device was switched off."
        if self.measured_delta_w is None:
            return "No usable measurement yet."
        watts = round(self.measured_delta_w)
        confidence = "high" if self.step >= 2 else "low"
        return (
            f"Measured additional consumption: about {watts} W. "
            f"Test energy used: {self.used_energy_kwh:.3f} kWh. "
            f"Reliability: {confidence}."
        )

    def next_deadline(self, now: datetime) -> datetime | None:
        """Return the next time the run should advance."""
        if self.started_at is None:
            return None
        if self.state is CalibrationState.BASELINE:
            return self.started_at + timedelta(seconds=self.limits.baseline_seconds)
        if self.state is CalibrationState.DEVICE_ON:
            return self.started_at + timedelta(seconds=self.limits.max_seconds_on)
        if self.state is CalibrationState.DEVICE_OFF:
            return self.started_at + timedelta(seconds=self.limits.off_seconds)
        return None
