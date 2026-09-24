"""Shared value objects for the PV Manager core."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any


class DeviceKind(StrEnum):
    """Logical role a device can play in the energy system."""

    GRID_METER = "grid_meter"
    PV = "pv"
    LOAD = "load"
    BATTERY = "battery"
    EV_CHARGER = "ev_charger"
    EV = "ev"
    HEAT_PUMP = "heat_pump"
    HOT_WATER = "hot_water"
    POOL = "pool"
    VENTILATION = "ventilation"
    FLEXIBLE_LOAD = "flexible_load"
    UNKNOWN = "unknown"


class Capability(StrEnum):
    """Capabilities are discovered, never blindly assumed."""

    MEASURE_POWER = "measure_power"
    MEASURE_ENERGY = "measure_energy"
    MEASURE_TEMPERATURE = "measure_temperature"
    MEASURE_HUMIDITY = "measure_humidity"
    MEASURE_SOC = "measure_soc"
    MEASURE_PHASE_CURRENT = "measure_phase_current"
    MEASURE_PRESENCE = "measure_presence"
    MEASURE_PRICE = "measure_price"
    READ_CALENDAR = "read_calendar"
    READ_WEATHER = "read_weather"
    SWITCH = "switch"
    SET_POWER = "set_power"
    SET_TEMPERATURE = "set_temperature"
    SET_MODE = "set_mode"
    SET_FAN_SPEED = "set_fan_speed"


class SignConvention(StrEnum):
    """How a grid meter reports import and export."""

    UNKNOWN = "unknown"
    SIGNED_NET = "signed_net"
    IMPORT_POSITIVE = "import_positive"
    EXPORT_POSITIVE = "export_positive"
    SEPARATE = "separate"
    IMPORT_ONLY = "import_only"


class FallbackMode(StrEnum):
    """User-selectable fallback behaviour."""

    SAFE_HOLD = "safe_hold"
    NO_AUTOMATION = "no_automation"
    MANUAL = "manual"
    LAST_KNOWN = "last_known"


class ProviderKind(StrEnum):
    """Supported AI provider categories."""

    DISABLED = "disabled"
    LOCAL_RULES = "local_rules"
    LOCAL_MODEL = "local_model"
    GROQ = "groq"
    OPENAI_COMPATIBLE = "openai_compatible"


@dataclass(frozen=True, slots=True)
class SensorReading:
    """A single normalized reading."""

    value: float | None
    unit: str | None
    timestamp: datetime | None
    available: bool = True
    source: str | None = None
    quality: float = 1.0

    @property
    def valid(self) -> bool:
        """Return True when the reading is usable for calculations."""
        return (
            self.available and self.value is not None and isfinite(self.value) and 0.0 <= self.quality <= 1.0
        )


@dataclass(slots=True)
class DeviceLimits:
    """Hard and soft boundaries for one device."""

    min_power_w: float = 0.0
    max_power_w: float = 0.0
    max_energy_kwh_per_day: float = 0.0
    battery_capacity_kwh: float = 0.0
    min_soc: float = 0.0
    max_soc: float = 100.0
    min_temperature_c: float = 0.0
    max_temperature_c: float = 0.0
    phase_count: int = 1
    phase_limit_a: float = 0.0
    grid_import_limit_w: float = 0.0
    grid_export_limit_w: float = 0.0
    verified: bool = False

    def known(self) -> bool:
        """Return True when at least one meaningful limit was verified."""
        return self.verified and (
            self.max_power_w > 0
            or self.max_energy_kwh_per_day > 0
            or self.phase_limit_a > 0
            or self.max_temperature_c > self.min_temperature_c
        )


@dataclass(slots=True)
class DeviceProfile:
    """A device as understood by PV Manager."""

    device_id: str
    name: str
    kind: DeviceKind = DeviceKind.UNKNOWN
    capabilities: set[Capability] = field(default_factory=set)
    sign_convention: SignConvention = SignConvention.UNKNOWN
    limits: DeviceLimits = field(default_factory=DeviceLimits)
    fallback: FallbackMode = FallbackMode.NO_AUTOMATION
    confidence: float = 0.0
    manually_configured: bool = False
    source_entities: tuple[str, ...] = ()
    area_name: str | None = None
    nickname: str | None = None
    priority: int = 50
    automations_allowed: bool = False

    def supports(self, capability: Capability) -> bool:
        """Return True when the capability was detected or confirmed."""
        return capability in self.capabilities

    @property
    def controllable(self) -> bool:
        """Return True only when at least one actuator was detected."""
        return bool(
            self.capabilities
            & {
                Capability.SWITCH,
                Capability.SET_POWER,
                Capability.SET_TEMPERATURE,
                Capability.SET_MODE,
                Capability.SET_FAN_SPEED,
            }
        )


@dataclass(frozen=True, slots=True)
class EntityDescriptor:
    """HA-independent description of an entity used for discovery."""

    entity_id: str
    domain: str
    name: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    state: Any = None
    available: bool = True
    device_id: str | None = None
    area_name: str | None = None
    integration: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    last_changed: datetime | None = None
