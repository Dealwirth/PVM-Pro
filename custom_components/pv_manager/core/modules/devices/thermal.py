"""Addon: Thermische Flexibilität.

Heizung und Warmwasser dürfen flexibel geplant werden, aber nur innerhalb von
Temperatur-, Hygiene- und Komfortgrenzen. Poolpläne laufen über dasselbe Addon.

Ort im Store: Kategorie "devices". Hängt an: core. Liefert Wärmepumpen-,
Warmwasser- und Poolplanung.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="thermal",
    name_de="Thermische Flexibilität",
    name_en="Thermal Flexibility",
    summary_de=(
        "Heizung und Warmwasser dürfen flexibel geplant werden, aber nur innerhalb von "
        "Temperatur-, Hygiene- und Komfortgrenzen."
    ),
    summary_en=(
        "Heating and hot water may be scheduled flexibly, but only within temperature, "
        "hygiene and comfort limits."
    ),
    category=ModuleCategory.DEVICES,
    icon="mdi:heat-pump",
    requires=("core",),
    provides=("heat_pump_plan", "hot_water_plan", "pool_plan"),
    reason_de="Wärme dann erzeugen, wenn Strom günstig oder solar ist.",
    reason_en="Generate heat when power is cheap or solar.",
)
