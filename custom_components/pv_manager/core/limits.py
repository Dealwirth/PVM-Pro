"""Central hard-limit engine.

Every actuator request must pass this engine. It is deliberately simple and
deterministic so that no optional module, user interface or AI can bypass it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite


class LimitKind(StrEnum):
    """Categories of enforced limits."""

    GRID_IMPORT = "grid_import"
    GRID_EXPORT = "grid_export"
    PHASE = "phase"
    DEVICE_POWER = "device_power"
    DEVICE_ENERGY = "device_energy"
    COMFORT = "comfort"
    STATE_OF_CHARGE = "state_of_charge"
    USER = "user"


@dataclass(frozen=True, slots=True)
class Constraint:
    """A single limit that must not be exceeded."""

    kind: LimitKind
    label: str
    limit: float
    current: float
    unit: str = "W"
    hard: bool = True
    source: str = "config"

    @property
    def headroom(self) -> float:
        """Remaining room before the limit is reached."""
        return max(self.limit - self.current, 0.0)

    @property
    def exceeded(self) -> bool:
        """Return True when the current value already violates the limit."""
        return self.current > self.limit


@dataclass(frozen=True, slots=True)
class ClampResult:
    """Result of clamping a requested power."""

    requested_w: float
    allowed_w: float
    reduced: bool
    blocking_reason: str | None
    constraints: tuple[Constraint, ...] = ()

    @property
    def allowed(self) -> bool:
        """Return True when a non-zero action may be executed."""
        return self.allowed_w > 0


@dataclass(slots=True)
class ConstraintEngine:
    """Collects constraints and clamps actuator requests."""

    constraints: list[Constraint] = field(default_factory=list)

    def add(self, constraint: Constraint) -> None:
        """Add or replace a constraint of the same kind and label."""
        self.constraints = [
            existing
            for existing in self.constraints
            if not (existing.kind == constraint.kind and existing.label == constraint.label)
        ]
        self.constraints.append(constraint)

    def add_grid_limits(
        self,
        *,
        net_power_w: float,
        import_limit_w: float,
        export_limit_w: float,
    ) -> None:
        """Add grid import/export constraints for the current net power."""
        if import_limit_w > 0:
            self.add(
                Constraint(
                    kind=LimitKind.GRID_IMPORT,
                    label="grid_import",
                    limit=import_limit_w,
                    current=max(net_power_w, 0.0),
                    source="grid",
                )
            )
        if export_limit_w > 0:
            self.add(
                Constraint(
                    kind=LimitKind.GRID_EXPORT,
                    label="grid_export",
                    limit=export_limit_w,
                    current=max(-net_power_w, 0.0),
                    source="grid",
                )
            )

    def add_phase_limit(
        self,
        *,
        phase_current_a: float,
        phase_limit_a: float,
        voltage_v: float = 230.0,
        phases: int = 1,
    ) -> None:
        """Translate a phase current limit into available watts."""
        if phase_limit_a <= 0 or phases <= 0:
            return
        available_w = max(phase_limit_a - phase_current_a, 0.0) * voltage_v * phases
        self.add(
            Constraint(
                kind=LimitKind.PHASE,
                label="phase_current",
                limit=available_w,
                current=0.0,
                source="phase",
            )
        )

    def add_device_power(self, *, label: str, max_power_w: float) -> None:
        """Add a device maximum power."""
        if max_power_w > 0:
            self.add(
                Constraint(
                    kind=LimitKind.DEVICE_POWER,
                    label=label,
                    limit=max_power_w,
                    current=0.0,
                    source="device",
                )
            )

    def add_daily_energy(self, *, label: str, used_kwh: float, limit_kwh: float) -> None:
        """Add a daily energy budget."""
        if limit_kwh > 0:
            self.add(
                Constraint(
                    kind=LimitKind.DEVICE_ENERGY,
                    label=label,
                    limit=limit_kwh,
                    current=used_kwh,
                    unit="kWh",
                    source="device",
                )
            )

    def add_comfort_range(self, *, label: str, current_c: float, minimum_c: float, maximum_c: float) -> None:
        """Add a comfort temperature band."""
        if maximum_c > minimum_c:
            self.add(
                Constraint(
                    kind=LimitKind.COMFORT,
                    label=label,
                    limit=maximum_c,
                    current=current_c,
                    unit="°C",
                    source="comfort",
                )
            )

    def add_soc_range(
        self, *, label: str, current_soc: float, minimum_soc: float, maximum_soc: float
    ) -> None:
        """Add a state-of-charge band."""
        if maximum_soc > minimum_soc:
            self.add(
                Constraint(
                    kind=LimitKind.STATE_OF_CHARGE,
                    label=label,
                    limit=maximum_soc,
                    current=current_soc,
                    unit="%",
                    source="battery",
                )
            )

    def hard_violations(self) -> tuple[Constraint, ...]:
        """Return already violated hard constraints."""
        return tuple(c for c in self.constraints if c.hard and c.exceeded)

    def clamp(self, requested_w: float) -> ClampResult:
        """Limit a requested power so that no hard constraint is exceeded."""
        if not isfinite(requested_w):
            return ClampResult(0.0, 0.0, True, "invalid_request")
        requested = max(requested_w, 0.0)
        blocking = self.hard_violations()
        if blocking:
            return ClampResult(
                requested_w=requested,
                allowed_w=0.0,
                reduced=requested > 0,
                blocking_reason=blocking[0].label,
                constraints=tuple(self.constraints),
            )
        power_limits = [
            constraint
            for constraint in self.constraints
            if constraint.hard
            and constraint.unit == "W"
            and constraint.kind in {LimitKind.GRID_IMPORT, LimitKind.PHASE, LimitKind.DEVICE_POWER}
        ]
        allowed = requested
        reason: str | None = None
        for constraint in power_limits:
            if constraint.headroom < allowed:
                allowed = constraint.headroom
                reason = constraint.label
        allowed = max(allowed, 0.0)
        return ClampResult(
            requested_w=requested,
            allowed_w=allowed,
            reduced=allowed < requested,
            blocking_reason=reason,
            constraints=tuple(self.constraints),
        )

    def snapshot(self) -> list[dict[str, object]]:
        """Return a serializable snapshot for the UI."""
        return [
            {
                "kind": constraint.kind.value,
                "label": constraint.label,
                "limit": constraint.limit,
                "current": constraint.current,
                "unit": constraint.unit,
                "hard": constraint.hard,
                "source": constraint.source,
                "headroom": constraint.headroom,
                "exceeded": constraint.exceeded,
            }
            for constraint in self.constraints
        ]


def amps_to_watts(amps: float, *, voltage_v: float = 230.0, phases: int = 1) -> float:
    """Convert a phase current to power."""
    return max(amps, 0.0) * voltage_v * max(phases, 1)


def watts_to_amps(watts: float, *, voltage_v: float = 230.0, phases: int = 1) -> float:
    """Convert power to current per phase."""
    denominator = voltage_v * max(phases, 1)
    return max(watts, 0.0) / denominator if denominator else 0.0
