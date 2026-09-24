"""Addon: Energie-Gewohnheiten.

Erkennt wiederkehrende Muster wie sonntägliches Laden und schlägt sie vor.
Muster werden erst nach ausdrücklicher Bestätigung verwendet – nie heimlich
übernommen.

Ort im Store: Kategorie "intelligence". Hängt an: core und
forecast_learning. Liefert Mustererkennung und Musterbestätigung.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="energy_habits",
    name_de="Energie-Gewohnheiten",
    name_en="Energy Habits",
    summary_de=(
        "Erkennt wiederkehrende Muster wie sonntägliches Laden. Es schlägt Muster vor, "
        "nutzt sie aber erst nach Bestätigung."
    ),
    summary_en=(
        "Detects recurring patterns such as Sunday charging. It proposes patterns but "
        "only uses them after confirmation."
    ),
    category=ModuleCategory.INTELLIGENCE,
    icon="mdi:repeat-variant",
    requires=("core", "forecast_learning"),
    provides=("habit_detection", "habit_confirmation"),
    reason_de="Wiederkehrendes automatisch erkennen, aber nicht heimlich übernehmen.",
    reason_en="Detect recurring behaviour, but never adopt it silently.",
)
