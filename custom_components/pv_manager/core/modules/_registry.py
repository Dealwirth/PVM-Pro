"""Zusammensetzung des Stores.

Die Reihenfolge in ``MODULE_SPECS`` ist zugleich die Anzeigereihenfolge im
Store. Ein eigenes Addon wird hier mit zwei Zeilen registriert:

1. ``from .<kategorie>.<module_id> import SPEC as <NAME>_SPEC``
2. die Variable in das Tupel ``MODULE_SPECS`` einreihen

Ein Addon = eine Datei unter ``core/modules/<kategorie>/<module_id>.py``.
Details und ein vollständiges Beispiel stehen in ``docs/ADDONS.md``.
"""

from __future__ import annotations

from ._spec import ModuleSpec
from .base.core import SPEC as _CORE
from .comfort.presence_modes import SPEC as _PRESENCE_MODES
from .comfort.ventilation import SPEC as _VENTILATION
from .devices.ev_wallbox_link import SPEC as _EV_WALLBOX_LINK
from .devices.flexible_loads import SPEC as _FLEXIBLE_LOADS
from .devices.mobility_calendar import SPEC as _MOBILITY_CALENDAR
from .devices.thermal import SPEC as _THERMAL
from .energy.goals_reports import SPEC as _GOALS_REPORTS
from .energy.price_cost import SPEC as _PRICE_COST
from .energy.storage_grid import SPEC as _STORAGE_GRID
from .intelligence.energy_habits import SPEC as _ENERGY_HABITS
from .intelligence.forecast_learning import SPEC as _FORECAST_LEARNING
from .intelligence.what_if import SPEC as _WHAT_IF
from .safety.maintenance_pv_health import SPEC as _MAINTENANCE_PV_HEALTH
from .safety.security_terminal import SPEC as _SECURITY_TERMINAL

#: Alle Karten in Store-Reihenfolge (erst Basis, dann Kategorien).
MODULE_SPECS: tuple[ModuleSpec, ...] = (
    _CORE,
    _PRICE_COST,
    _STORAGE_GRID,
    _THERMAL,
    _MOBILITY_CALENDAR,
    _FORECAST_LEARNING,
    _WHAT_IF,
    _FLEXIBLE_LOADS,
    _GOALS_REPORTS,
    _PRESENCE_MODES,
    _MAINTENANCE_PV_HEALTH,
    _VENTILATION,
    _ENERGY_HABITS,
    _EV_WALLBOX_LINK,
    _SECURITY_TERMINAL,
)

MODULES_BY_ID: dict[str, ModuleSpec] = {spec.module_id: spec for spec in MODULE_SPECS}
CORE_MODULE = MODULES_BY_ID["core"]
CORE_MODULE_ID = CORE_MODULE.module_id


def default_enabled_modules() -> set[str]:
    """Return the modules enabled on a fresh installation."""
    return {spec.module_id for spec in MODULE_SPECS if spec.default_enabled}


def resolve_dependencies(enabled: set[str], *, module_id: str) -> set[str]:
    """Return the set of modules that must be enabled together with module_id."""
    result = {module_id}
    changed = True
    while changed:
        changed = False
        for current in tuple(result):
            spec = MODULES_BY_ID.get(current)
            if spec is None:
                continue
            for dependency in spec.requires:
                if dependency not in result:
                    result.add(dependency)
                    changed = True
    return {item for item in result if item in MODULES_BY_ID or item == CORE_MODULE_ID}


def dependents_of(module_id: str, enabled: set[str]) -> set[str]:
    """Return enabled modules that depend on module_id."""
    return {
        spec.module_id for spec in MODULE_SPECS if module_id in spec.requires and spec.module_id in enabled
    }


def store_cards(enabled: set[str] | None = None) -> list[dict[str, object]]:
    """Return all store cards with their current state."""
    active = enabled or default_enabled_modules()
    return [spec.as_dict(enabled=spec.module_id in active) for spec in MODULE_SPECS]
