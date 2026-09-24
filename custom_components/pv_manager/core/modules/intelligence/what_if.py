"""Addon: Was wäre wenn?

Zeigt vorab, was passieren würde, wenn das Auto später, eine Wallbox
schneller oder die Wärmepumpe anders geplant würde. Rein simulativ:
Es schaltet nichts und verändert keine Einstellungen.

Ort im Store: Kategorie "intelligence". Hängt an: core und
forecast_learning. Liefert Simulation und Schattenmodus.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="what_if",
    name_de="Was wäre wenn?",
    name_en="What If?",
    summary_de=(
        "Zeigt vorab, was passieren würde, wenn das Auto später, eine Wallbox schneller "
        "oder die Wärmepumpe anders geplant würde."
    ),
    summary_en=(
        "Shows in advance what would happen if the car charged later, a wallbox charged "
        "faster or the heat pump was scheduled differently."
    ),
    category=ModuleCategory.INTELLIGENCE,
    icon="mdi:flask-outline",
    requires=("core", "forecast_learning"),
    provides=("simulation", "shadow_mode"),
    reason_de="Ausprobieren, bevor etwas geschaltet wird.",
    reason_en="Try before anything is switched.",
)
