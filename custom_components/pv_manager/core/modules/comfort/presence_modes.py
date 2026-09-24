"""Addon: Anwesenheit & Sondermodi.

Erkennt, ob jemand da ist, und passt Verbrauch und Automatik an. Urlaub,
Eco- und Gastmodus sind bewusste Entscheidungen des Nutzers – nie versteckte
Automatik.

Ort im Store: Kategorie "comfort". Hängt an: core. Liefert Anwesenheit,
Urlaubs-, Gast- und Eco-Modus.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="presence_modes",
    name_de="Anwesenheit & Sondermodi",
    name_en="Presence & Special Modes",
    summary_de=(
        "Erkennt, ob jemand da ist, und passt Verbrauch und Automatik an. Urlaub, Eco- "
        "und Gastmodus sind bewusst auswählbar."
    ),
    summary_en=(
        "Detects whether someone is home and adapts consumption and automation. Holiday, "
        "eco and guest mode are explicit choices."
    ),
    category=ModuleCategory.COMFORT,
    icon="mdi:home-account",
    requires=("core",),
    provides=("presence", "holiday_mode", "guest_mode", "eco_mode"),
    reason_de="Automatik, die zum echten Alltag passt.",
    reason_en="Automation that matches real life.",
)
