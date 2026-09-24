"""Addon: Mobilität & Kalender.

Liest Abfahrtszeiten und wiederkehrende Kalenderereignisse, damit das Auto
nicht zu spät geladen wird. Fehlende Kalenderdaten führen zu sicherem
Fallback statt zu riskanten Annahmen.

Ort im Store: Kategorie "devices". Hängt an: core. Liefert Abfahrtsplanung
und wiederkehrende Fahrten; ist Voraussetzung für die Auto–Wallbox-Verknüpfung.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="mobility_calendar",
    name_de="Mobilität & Kalender",
    name_en="Mobility & Calendar",
    summary_de=(
        "Liest Abfahrtszeiten und wiederkehrende Kalenderereignisse, damit das Auto "
        "nicht zu spät geladen wird. Fehlende Kalenderdaten führen zu sicherem Fallback."
    ),
    summary_en=(
        "Reads departures and recurring calendar events so the car is not charged too late. "
        "Missing calendar data results in a safe fallback."
    ),
    category=ModuleCategory.DEVICES,
    icon="mdi:calendar-clock",
    requires=("core",),
    provides=("departure_planning", "recurring_trips"),
    reason_de="Ladeplanung passend zu echten Fahrten.",
    reason_en="Charging plans that match real trips.",
)
