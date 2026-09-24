"""Addon: Prognose & Lernen.

Berechnet voraussichtlichen Verbrauch und Solarproduktion. Geräte können in
begrenzten Lernläufen geprüft und kalibriert werden; das Addon liefert die
Grundlage für Simulation ("Was wäre wenn?") und Gewohnheitserkennung.

Ort im Store: Kategorie "intelligence". Hängt an: core. Liefert
Verbrauchs- und Solarprognose sowie Kalibrierung.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="forecast_learning",
    name_de="Prognose & Lernen",
    name_en="Forecast & Learning",
    summary_de=(
        "Berechnet voraussichtlichen Verbrauch und Solarproduktion. Geräte können in "
        "begrenzten Lernläufen geprüft und kalibriert werden."
    ),
    summary_en=(
        "Predicts consumption and solar production. Devices can be verified and calibrated "
        "in bounded learning runs."
    ),
    category=ModuleCategory.INTELLIGENCE,
    icon="mdi:chart-timeline-variant-shimmer",
    requires=("core",),
    provides=("consumption_forecast", "solar_forecast", "calibration"),
    reason_de="Bessere Entscheidungen durch gelernte Muster.",
    reason_en="Better decisions from learned patterns.",
)
