"""Unit, sign and energy balance normalization.

Wrong signs or mixed units are the most common source of bogus PV manager
decisions. Everything enters this module first and leaves it in one canonical
form:

* power: watts
* energy: kilowatt hours
* grid: positive = import, negative = export
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite

from .types import SignConvention

_POWER_TO_W: dict[str, float] = {
    "w": 1.0,
    "watt": 1.0,
    "watts": 1.0,
    "kw": 1000.0,
    "kilowatt": 1000.0,
    "mw": 1_000_000.0,
    "va": 1.0,
    "kva": 1000.0,
}

_ENERGY_TO_KWH: dict[str, float] = {
    "wh": 0.001,
    "kwh": 1.0,
    "mwh": 1000.0,
    "gwh": 1_000_000.0,
    "j": 1 / 3_600_000,
    "kj": 1 / 3600,
    "mj": 1 / 3.6,
}

_GRID_MODES = {
    "signed_net": SignConvention.SIGNED_NET,
    "signed": SignConvention.SIGNED_NET,
    "net": SignConvention.SIGNED_NET,
    "import_positive": SignConvention.IMPORT_POSITIVE,
    "import_positiv": SignConvention.IMPORT_POSITIVE,
    "export_positive": SignConvention.EXPORT_POSITIVE,
    "export_positiv": SignConvention.EXPORT_POSITIVE,
    "separate": SignConvention.SEPARATE,
    "import_export": SignConvention.SEPARATE,
    "import_only": SignConvention.IMPORT_ONLY,
    "nur_bezug": SignConvention.IMPORT_ONLY,
}


def safe_float(value: object) -> float | None:
    """Convert a state value to float, ignoring unusable values."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        return result if isfinite(result) else None
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        if not text or text.lower() in {"unknown", "unavailable", "none", "nan"}:
            return None
        try:
            result = float(text)
        except ValueError:
            return None
        return result if isfinite(result) else None
    return None


def parse_grid_mode(mode: str | SignConvention | None) -> SignConvention:
    """Parse a user-facing meter mode into a sign convention."""
    if isinstance(mode, SignConvention):
        return mode
    if mode is None:
        return SignConvention.UNKNOWN
    return _GRID_MODES.get(mode.strip().lower(), SignConvention.UNKNOWN)


def normalize_power(value: float | None, unit: str | None) -> float | None:
    """Convert a power value to watts."""
    if value is None or not isfinite(value):
        return None
    factor = _POWER_TO_W.get((unit or "w").strip().lower())
    if factor is None:
        return None
    return value * factor


def normalize_energy(value: float | None, unit: str | None) -> float | None:
    """Convert an energy value to kilowatt hours."""
    if value is None or not isfinite(value):
        return None
    factor = _ENERGY_TO_KWH.get((unit or "kwh").strip().lower())
    if factor is None:
        return None
    return value * factor


def is_stale(
    timestamp: datetime | None,
    now: datetime,
    max_age: timedelta,
) -> bool:
    """Return True when a timestamp is missing or older than max_age."""
    if timestamp is None:
        return True
    return (now - timestamp) > max_age


@dataclass(frozen=True, slots=True)
class GridSample:
    """Canonical grid power sample in watts."""

    import_power_w: float | None
    export_power_w: float | None
    net_power_w: float
    convention: SignConvention
    confidence: float
    warning: str | None = None

    @property
    def has_import(self) -> bool:
        """Return True when grid import is present."""
        return self.net_power_w > 0

    @property
    def has_export(self) -> bool:
        """Return True when grid export is present."""
        return self.net_power_w < 0


def normalize_grid_sample(
    *,
    import_value: float | None = None,
    export_value: float | None = None,
    combined_value: float | None = None,
    unit: str | None = "W",
    convention: SignConvention | str | None = None,
) -> GridSample:
    """Normalize the many ways a grid meter can report power.

    The result always uses the canonical convention ``positive = import`` and
    ``negative = export``. When data is missing the function degrades safely
    instead of guessing an inversion that could later cause a wrong decision.
    """
    mode = convention if isinstance(convention, SignConvention) else parse_grid_mode(convention)
    imp = normalize_power(import_value, unit)
    exp = normalize_power(export_value, unit)
    net = normalize_power(combined_value, unit)

    if mode is SignConvention.SEPARATE or (imp is not None and exp is not None):
        if imp is None and exp is None:
            return GridSample(None, None, 0.0, SignConvention.UNKNOWN, 0.0, "no_grid_data")
        if imp is not None and imp < 0:
            return GridSample(
                None,
                None,
                0.0,
                SignConvention.SEPARATE,
                0.2,
                "separate_import_negative",
            )
        if exp is not None and exp < 0:
            return GridSample(
                None,
                None,
                0.0,
                SignConvention.SEPARATE,
                0.2,
                "separate_export_negative",
            )
        import_w = imp or 0.0
        export_w = exp or 0.0
        if import_w > 0 and export_w > 0:
            return GridSample(
                import_w,
                export_w,
                import_w - export_w,
                SignConvention.SEPARATE,
                0.5,
                "import_and_export_at_once",
            )
        return GridSample(import_w, export_w, import_w - export_w, SignConvention.SEPARATE, 1.0)

    if mode is SignConvention.IMPORT_ONLY:
        if imp is None:
            return GridSample(None, None, 0.0, mode, 0.0, "import_only_without_value")
        if imp < 0:
            return GridSample(None, None, 0.0, mode, 0.2, "import_only_negative")
        return GridSample(
            imp,
            0.0,
            imp,
            mode,
            0.6,
            "export_unknown_import_only",
        )

    if net is None:
        return GridSample(None, None, 0.0, SignConvention.UNKNOWN, 0.0, "no_grid_data")

    signed = -net if mode is SignConvention.EXPORT_POSITIVE else net

    import_w = signed if signed > 0 else 0.0
    export_w = -signed if signed < 0 else 0.0
    confidence = 1.0 if mode is not SignConvention.UNKNOWN else 0.5
    warning = None if mode is not SignConvention.UNKNOWN else "unknown_sign_convention"
    return GridSample(import_w, export_w, signed, mode, confidence, warning)


@dataclass(frozen=True, slots=True)
class EnergyBalance:
    """Household power balance in watts."""

    pv_w: float
    grid_import_w: float
    grid_export_w: float
    battery_charge_w: float
    battery_discharge_w: float
    measured_load_w: float | None
    computed_load_w: float
    deviation_pct: float | None
    balanced: bool
    warnings: tuple[str, ...] = ()

    @property
    def net_grid_w(self) -> float:
        """Grid power with positive import and negative export."""
        return self.grid_import_w - self.grid_export_w

    @property
    def battery_net_w(self) -> float:
        """Positive means charging, negative means discharging."""
        return self.battery_charge_w - self.battery_discharge_w


def _clean(value: float | None) -> float:
    return value if value is not None and isfinite(value) else 0.0


def compute_balance(
    *,
    pv_w: float | None = None,
    grid_import_w: float | None = None,
    grid_export_w: float | None = None,
    battery_charge_w: float | None = None,
    battery_discharge_w: float | None = None,
    measured_load_w: float | None = None,
    tolerance_pct: float = 15.0,
) -> EnergyBalance:
    """Compute the residual household load.

    ``load = pv + grid_import + battery_discharge - grid_export - battery_charge``
    """
    pv = max(_clean(pv_w), 0.0)
    grid_in = max(_clean(grid_import_w), 0.0)
    grid_out = max(_clean(grid_export_w), 0.0)
    charge = max(_clean(battery_charge_w), 0.0)
    discharge = max(_clean(battery_discharge_w), 0.0)
    computed = pv + grid_in + discharge - grid_out - charge

    warnings: list[str] = []
    deviation: float | None = None
    balanced = True
    if measured_load_w is not None and measured_load_w >= 0:
        reference = max(abs(measured_load_w), 100.0)
        deviation = (computed - measured_load_w) / reference * 100.0
        if abs(deviation) > tolerance_pct:
            balanced = False
            warnings.append("load_balance_deviation")
    if grid_in > 0 and grid_out > 0:
        warnings.append("simultaneous_import_export")
        balanced = False

    return EnergyBalance(
        pv_w=pv,
        grid_import_w=grid_in,
        grid_export_w=grid_out,
        battery_charge_w=charge,
        battery_discharge_w=discharge,
        measured_load_w=measured_load_w,
        computed_load_w=max(computed, 0.0),
        deviation_pct=deviation,
        balanced=balanced,
        warnings=tuple(warnings),
    )


def integrate_energy_kwh(
    samples: Iterable[tuple[datetime, float | None]],
    *,
    unit: str = "W",
) -> float:
    """Integrate a power series into kWh using the trapezoid rule."""
    points = [(ts, watts) for ts, raw in samples if (watts := normalize_power(raw, unit)) is not None]
    if len(points) < 2:
        return 0.0
    total_ws = 0.0
    for (t0, p0), (t1, p1) in zip(points, points[1:], strict=False):
        seconds = (t1 - t0).total_seconds()
        if seconds <= 0:
            continue
        total_ws += (p0 + p1) / 2.0 * seconds
    return total_ws / 3_600_000.0


def values_from_mapping(
    mapping: Mapping[str, object],
    key: str,
    *,
    unit_key: str | None = None,
    default_unit: str = "W",
) -> tuple[float | None, str | None]:
    """Extract a value and unit from a mapping of attributes."""
    value = safe_float(mapping.get(key))
    unit = mapping.get(unit_key) if unit_key else mapping.get("unit_of_measurement")
    return value, str(unit) if unit else default_unit
