"""Consumption and solar forecasting.

The forecast is intentionally explainable and conservative:

* the household baseline learns day-of-week/hour profiles from history,
* a cold-start profile is used until enough data exists,
* solar forecast is an explicit input (Forecast.Solar or another HA entity),
* weather only scales a forecast, it never invents production,
* every result carries a confidence value and the number of samples used.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import isfinite
from statistics import fmean

from .normalize import safe_float

DEFAULT_COLD_START_KWH = 0.35
MIN_SAMPLES_FOR_CONFIDENCE = 8


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    """One forecast interval."""

    start: datetime
    end: datetime
    expected_kwh: float
    confidence: float
    source: str
    samples: int = 0
    lower_kwh: float = 0.0
    upper_kwh: float = 0.0

    def as_dict(self) -> dict[str, object]:
        """Return a serializable representation for the API/UI."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "expected_kwh": round(self.expected_kwh, 4),
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "samples": self.samples,
            "lower_kwh": round(self.lower_kwh, 4),
            "upper_kwh": round(self.upper_kwh, 4),
        }


@dataclass(frozen=True, slots=True)
class SolarForecastInput:
    """Normalized solar forecast input."""

    start: datetime
    end: datetime
    expected_kwh: float
    confidence: float = 0.6
    source: str = "solar_entity"


@dataclass(slots=True)
class BaselineProfile:
    """Learned household baseline."""

    weekday_hour_kwh: dict[tuple[int, int], list[float]] = field(default_factory=dict)

    def add(self, timestamp: datetime, kwh: float) -> None:
        """Add one historical sample."""
        value = safe_float(kwh)
        if value is None or value < 0:
            return
        self.weekday_hour_kwh.setdefault((timestamp.weekday(), timestamp.hour), []).append(value)

    def expected(self, timestamp: datetime) -> tuple[float, float, int]:
        """Return (kWh, confidence, sample count) for a point in time."""
        key = (timestamp.weekday(), timestamp.hour)
        samples = self.weekday_hour_kwh.get(key)
        if not samples:
            # Fall back to the same hour on any weekday.
            samples = [
                value
                for (weekday, hour), values in self.weekday_hour_kwh.items()
                if hour == timestamp.hour
                for value in values
            ]
        if not samples:
            return DEFAULT_COLD_START_KWH, 0.15, 0
        average = fmean(samples)
        # More samples increase confidence, but never above 0.9 for a forecast.
        confidence = min(0.9, 0.35 + 0.05 * min(len(samples), 11))
        return average, confidence, len(samples)


def build_baseline(
    history: Iterable[tuple[datetime, float]],
) -> BaselineProfile:
    """Build a weekday/hour profile from historical hourly values."""
    profile = BaselineProfile()
    for timestamp, kwh in history:
        profile.add(timestamp, kwh)
    if not profile.weekday_hour_kwh:
        return _cold_start_profile()
    return profile


def _cold_start_profile() -> BaselineProfile:
    """Return an empty profile; expected() supplies the neutral default.

    Keeping this empty is intentional: a default value must never look like a
    learned measurement, otherwise the UI would show false confidence.
    """
    return BaselineProfile()


def consumption_forecast(
    profile: BaselineProfile,
    *,
    start: datetime,
    end: datetime,
    step_minutes: int = 60,
) -> list[ForecastPoint]:
    """Create a consumption forecast between two points in time."""
    if end <= start:
        return []
    points: list[ForecastPoint] = []
    cursor = start
    while cursor < end:
        slot_end = min(cursor + timedelta(minutes=step_minutes), end)
        hours = (slot_end - cursor).total_seconds() / 3600.0
        expected, confidence, samples = profile.expected(cursor)
        value = max(expected, 0.0) * hours
        points.append(
            ForecastPoint(
                start=cursor,
                end=slot_end,
                expected_kwh=value,
                confidence=confidence,
                source="consumption_baseline",
                samples=samples,
                lower_kwh=max(value * 0.7, 0.0),
                upper_kwh=value * 1.3,
            )
        )
        cursor = slot_end
    return points


def weather_efficiency(
    *,
    cloud_coverage_pct: float | None = None,
    temperature_c: float | None = None,
    rain_mm: float | None = None,
    snow: bool = False,
) -> tuple[float, str]:
    """Return a solar efficiency factor and an explanation key."""
    factor = 1.0
    reasons: list[str] = []
    if cloud_coverage_pct is not None:
        cloud = min(max(cloud_coverage_pct, 0.0), 100.0)
        cloud_factor = 1.0 - 0.65 * (cloud / 100.0)
        factor *= cloud_factor
        reasons.append("cloud")
    if temperature_c is not None and temperature_c > 25.0:
        heat_derate = min((temperature_c - 25.0) * 0.004, 0.2)
        factor *= 1.0 - heat_derate
        reasons.append("heat")
    if rain_mm is not None and rain_mm > 1.0:
        factor *= 0.9
        reasons.append("rain")
    if snow:
        factor *= 0.2
        reasons.append("snow")
    return max(min(factor, 1.0), 0.0), ",".join(reasons) or "clear"


def solar_forecast(
    raw: Sequence[SolarForecastInput],
    *,
    efficiency: float = 1.0,
) -> list[ForecastPoint]:
    """Apply a weather efficiency factor to a solar forecast."""
    points: list[ForecastPoint] = []
    for item in raw:
        kwh = max(item.expected_kwh, 0.0) * max(min(efficiency, 1.0), 0.0)
        points.append(
            ForecastPoint(
                start=item.start,
                end=item.end,
                expected_kwh=kwh,
                confidence=item.confidence,
                source=item.source,
                lower_kwh=kwh * 0.6,
                upper_kwh=kwh * 1.1,
            )
        )
    return points


def merge_intervals(
    primary: Sequence[ForecastPoint],
    secondary: Sequence[ForecastPoint],
) -> list[ForecastPoint]:
    """Merge two forecasts by interval start, preferring existing values."""
    merged: dict[datetime, ForecastPoint] = {point.start: point for point in primary}
    for point in secondary:
        if point.start not in merged:
            merged[point.start] = point
    return [merged[key] for key in sorted(merged)]


def total_kwh(points: Iterable[ForecastPoint]) -> float:
    """Sum the expected energy of forecast points."""
    return round(sum(point.expected_kwh for point in points), 4)


def solar_surplus(
    *,
    solar_kwh: float,
    consumption_kwh: float,
    battery_room_kwh: float = 0.0,
    efficiency: float = 1.0,
) -> float:
    """Return the usable surplus after consumption and battery reserve."""
    usable = max(solar_kwh * max(min(efficiency, 1.0), 0.0) - consumption_kwh - battery_room_kwh, 0.0)
    return round(usable, 4)


def confidence_label(confidence: float) -> str:
    """Translate a confidence value into a plain-language label."""
    if not isfinite(confidence):
        return "unknown"
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.5:
        return "medium"
    if confidence >= 0.25:
        return "low"
    return "very_low"
