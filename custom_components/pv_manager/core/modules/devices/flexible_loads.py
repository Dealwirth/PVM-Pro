"""Addon: Flexible Geräte.

Plant Geräte wie Waschmaschine, Trockner, Geschirrspüler, Pumpen oder
Bewässerung in sinnvolle Zeitfenster ein – nur innerhalb der für das Gerät
bestätigten Grenzen.

Ort im Store: Kategorie "devices". Hängt an: core. Liefert flexible
Zeitfensterplanung, Bewässerung und Poolpumpe.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="flexible_loads",
    name_de="Flexible Geräte",
    name_en="Flexible Loads",
    summary_de=(
        "Plant Geräte wie Waschmaschine, Trockner, Geschirrspüler, Pumpen oder "
        "Bewässerung in sinnvollen Zeitfenstern."
    ),
    summary_en=(
        "Schedules washing machine, dryer, dishwasher, pumps or irrigation into sensible time windows."
    ),
    category=ModuleCategory.DEVICES,
    icon="mdi:washing-machine",
    requires=("core",),
    provides=("flexible_scheduling", "irrigation", "pool_pump"),
    reason_de="Haushaltsgeräte nutzen Strom, wenn er da ist.",
    reason_en="Household appliances use power when it is available.",
)
