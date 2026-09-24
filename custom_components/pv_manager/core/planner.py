"""EV charging planner with calendar deadlines and hard limits.

The planner is deterministic and explainable. It never starts a charge when a
required input is unknown; it returns a plan with reasons instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .limits import ConstraintEngine


@dataclass(frozen=True, slots=True)
class ChargingRequest:
    """What the user or calendar wants."""

    vehicle_id: str
    wallbox_id: str
    required_energy_kwh: float
    departure: datetime | None
    target_soc: float = 80.0
    current_soc: float | None = None
    battery_capacity_kwh: float | None = None
    max_power_w: float = 11_000.0
    min_power_w: float = 1_400.0
    grid_charging_allowed: bool = False
    prefer_solar: bool = True
    manual: bool = False
    priority: int = 50


@dataclass(frozen=True, slots=True)
class SolarWindow:
    """Expected solar surplus in a time window."""

    start: datetime
    end: datetime
    surplus_power_w: float
    confidence: float = 0.5


@dataclass(frozen=True, slots=True)
class ChargeSlot:
    """One planned charging slot."""

    start: datetime
    end: datetime
    power_w: float
    energy_kwh: float
    source: str
    explanation_de: str
    explanation_en: str

    def as_dict(self) -> dict[str, object]:
        """Return a serializable representation."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "power_w": round(self.power_w),
            "energy_kwh": round(self.energy_kwh, 3),
            "source": self.source,
            "explanation_de": self.explanation_de,
            "explanation_en": self.explanation_en,
        }


@dataclass(slots=True)
class ChargingPlan:
    """Complete plan result."""

    vehicle_id: str
    wallbox_id: str
    feasible: bool
    planned_energy_kwh: float
    solar_energy_kwh: float
    grid_energy_kwh: float
    slots: list[ChargeSlot] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reasons_de: list[str] = field(default_factory=list)
    reasons_en: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Return a serializable representation for the UI."""
        return {
            "vehicle_id": self.vehicle_id,
            "wallbox_id": self.wallbox_id,
            "feasible": self.feasible,
            "planned_energy_kwh": round(self.planned_energy_kwh, 3),
            "solar_energy_kwh": round(self.solar_energy_kwh, 3),
            "grid_energy_kwh": round(self.grid_energy_kwh, 3),
            "slots": [slot.as_dict() for slot in self.slots],
            "warnings": list(self.warnings),
            "reasons_de": list(self.reasons_de),
            "reasons_en": list(self.reasons_en),
        }


def energy_from_soc(
    *,
    current_soc: float | None,
    target_soc: float,
    capacity_kwh: float | None,
) -> tuple[float | None, str | None]:
    """Calculate required energy from state of charge."""
    if current_soc is None or capacity_kwh is None or capacity_kwh <= 0:
        return None, "soc_or_capacity_unknown"
    delta = max(min(target_soc, 100.0) - max(current_soc, 0.0), 0.0)
    return capacity_kwh * delta / 100.0, None


def _overlap_seconds(start: datetime, end: datetime, window: SolarWindow) -> float:
    overlap_start = max(start, window.start)
    overlap_end = min(end, window.end)
    return max((overlap_end - overlap_start).total_seconds(), 0.0)


def plan_charging(
    request: ChargingRequest,
    *,
    now: datetime,
    solar_windows: list[SolarWindow] | None = None,
    engine: ConstraintEngine | None = None,
    grid_price_high: bool = False,
    reservation_minutes: int = 30,
) -> ChargingPlan:
    """Create a safe charging plan.

    Priority order:
    1. reach the deadline,
    2. use solar surplus,
    3. only use the grid if the user allowed it,
    4. never exceed the hard constraint engine.
    """
    plan = ChargingPlan(
        vehicle_id=request.vehicle_id,
        wallbox_id=request.wallbox_id,
        feasible=False,
        planned_energy_kwh=0.0,
        solar_energy_kwh=0.0,
        grid_energy_kwh=0.0,
    )
    if request.required_energy_kwh <= 0:
        plan.feasible = True
        plan.reasons_de.append("Keine Energie nötig.")
        plan.reasons_en.append("No energy required.")
        return plan
    if request.required_energy_kwh > 0 and request.departure is None:
        plan.warnings.append("departure_unknown")
        plan.reasons_de.append(
            "Abfahrtszeit unbekannt. Es wird nicht automatisch geladen; "
            "bitte Kalender oder Abfahrt eintragen."
        )
        plan.reasons_en.append(
            "Departure time unknown. No automatic charging; add a calendar event or departure time."
        )
        return plan
    if request.departure is not None and request.departure <= now:
        plan.warnings.append("departure_in_past")
        plan.reasons_de.append("Abfahrt liegt in der Vergangenheit. Plan nicht möglich.")
        plan.reasons_en.append("Departure is in the past. Plan is not possible.")
        return plan

    latest_end = request.departure - timedelta(minutes=reservation_minutes)
    if latest_end <= now:
        plan.warnings.append("deadline_too_close")
        plan.reasons_de.append("Zu wenig Zeit bis zur Abfahrt. Bitte Reserve verkleinern oder früher laden.")
        plan.reasons_en.append("Not enough time before departure. Reduce buffer or charge earlier.")
        return plan

    remaining = request.required_energy_kwh
    slots: list[ChargeSlot] = []
    solar_windows = sorted(solar_windows or [], key=lambda window: window.start)

    # 1. Use solar windows first, earliest deadline-relevant window first.
    for window in solar_windows:
        if remaining <= 1e-6:
            break
        start = max(window.start, now)
        end = min(window.end, latest_end)
        if end <= start:
            continue
        available_w = max(window.surplus_power_w, 0.0)
        # Prefer solar but leave a measurable minimum power.
        if 0 < available_w < request.min_power_w:
            continue
        power = min(available_w, request.max_power_w)
        hours = (end - start).total_seconds() / 3600.0
        if power <= 0 or hours <= 0:
            continue
        max_energy = power * hours / 1000.0
        energy = min(max_energy, remaining)
        if energy <= 0:
            continue
        duration_hours = energy / (power / 1000.0)
        slot_end = start + timedelta(hours=duration_hours)
        slots.append(
            ChargeSlot(
                start=start,
                end=slot_end,
                power_w=power,
                energy_kwh=energy,
                source="solar",
                explanation_de=f"Solarüberschuss mit {round(power)} W genutzt.",
                explanation_en=f"Charging from {round(power)} W solar surplus.",
            )
        )
        plan.solar_energy_kwh += energy
        remaining -= energy

    if remaining <= 1e-6:
        plan.feasible = True
        plan.planned_energy_kwh = plan.solar_energy_kwh
        plan.slots = list(slots)
        if engine is not None:
            clamped = engine.clamp(max(slot.power_w for slot in slots))
            if not clamped.allowed and slots:
                plan.feasible = False
                plan.warnings.append("hard_limit_blocked")
                plan.reasons_de.append(
                    f"Harte Grenze verhindert das Laden: {clamped.blocking_reason or 'unbekannt'}."
                )
                plan.reasons_en.append(f"Hard limit blocks charging: {clamped.blocking_reason or 'unknown'}.")
                plan.slots = []
        return plan

    # 2. Grid fallback, only when allowed.
    if not request.grid_charging_allowed:
        plan.warnings.append("grid_not_allowed")
        plan.reasons_de.append(
            "Solar reicht nicht aus. Netz laden ist nicht freigegeben, daher wird nicht geladen."
        )
        plan.reasons_en.append(
            "Solar is not sufficient. Grid charging is not allowed, so charging will not start."
        )
        plan.feasible = plan.planned_energy_kwh > 0
        plan.slots = list(slots)
        return plan

    if grid_price_high:
        plan.warnings.append("high_price")
        plan.reasons_de.append(
            "Strompreis ist aktuell hoch. Netz-Laden wird nur bei ausdrücklicher Freigabe geplant."
        )
        plan.reasons_en.append(
            "Electricity price is currently high. Grid charging is only planned with explicit consent."
        )
        return plan

    if engine is not None:
        clamped = engine.clamp(request.max_power_w)
        if not clamped.allowed:
            plan.warnings.append("hard_limit_blocked")
            plan.reasons_de.append(
                f"Netz-Laden würde eine harte Grenze verletzen: {clamped.blocking_reason or 'unbekannt'}."
            )
            plan.reasons_en.append(
                f"Grid charging would violate a hard limit: {clamped.blocking_reason or 'unknown'}."
            )
            return plan
        grid_power = clamped.allowed_w
    else:
        grid_power = request.max_power_w

    # Prefer the latest safe window so the car still has energy shortly before departure.
    grid_power = max(grid_power, 1.0)
    needed_hours = remaining / (grid_power / 1000.0)
    available_hours = (latest_end - now).total_seconds() / 3600.0
    if needed_hours > available_hours:
        # Never schedule beyond the departure deadline. Charge as much as
        # safely fits and explain the remaining deficit instead.
        possible_energy = grid_power * max(available_hours, 0.0) / 1000.0
        slots.append(
            ChargeSlot(
                start=now,
                end=latest_end,
                power_w=grid_power,
                energy_kwh=possible_energy,
                source="grid",
                explanation_de=(
                    "Netz-Laden mit maximal sicherer Leistung bis zur Abfahrt. "
                    "Die restliche Energie passt zeitlich nicht mehr."
                ),
                explanation_en=(
                    "Grid charging at maximum safe power until departure. The remaining "
                    "energy no longer fits in time."
                ),
            )
        )
        plan.grid_energy_kwh = possible_energy
        plan.planned_energy_kwh = plan.solar_energy_kwh + plan.grid_energy_kwh
        plan.feasible = False
        plan.warnings.append("insufficient_time")
        plan.reasons_de.append(
            f"Bis zur Abfahrt passen nur {possible_energy:.1f} kWh. Bitte früher starten, "
            "Abfahrt anpassen oder Ziel reduzieren."
        )
        plan.reasons_en.append(
            f"Only {possible_energy:.1f} kWh fit before departure. Start earlier, adjust "
            "departure or reduce the target."
        )
        plan.slots = list(slots)
        return plan

    grid_start = max(now, latest_end - timedelta(hours=needed_hours))
    slots.append(
        ChargeSlot(
            start=grid_start,
            end=grid_start + timedelta(hours=needed_hours),
            power_w=grid_power,
            energy_kwh=remaining,
            source="grid",
            explanation_de="Netz-Laden kurz vor der Abfahrt, damit Solarstrom am Tag genutzt werden kann.",
            explanation_en="Grid charging shortly before departure to preserve daytime solar usage.",
        )
    )
    plan.grid_energy_kwh = remaining
    plan.planned_energy_kwh = plan.solar_energy_kwh + plan.grid_energy_kwh
    plan.feasible = True
    plan.slots = list(slots)
    return plan
