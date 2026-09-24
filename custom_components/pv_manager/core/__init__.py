"""Framework-independent PV Manager core.

This package must not import Home Assistant. It contains all logic that can be
unit-tested without a running Home Assistant instance and that must remain
available even when optional modules are disabled.
"""

from .types import (
    Capability,
    DeviceKind,
    DeviceLimits,
    DeviceProfile,
    EntityDescriptor,
    FallbackMode,
    SensorReading,
    SignConvention,
)

__all__ = [
    "Capability",
    "DeviceKind",
    "DeviceLimits",
    "DeviceProfile",
    "EntityDescriptor",
    "FallbackMode",
    "SensorReading",
    "SignConvention",
]
