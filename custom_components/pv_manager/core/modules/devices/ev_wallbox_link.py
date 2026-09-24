"""Addon: Auto–Wallbox-Verknüpfung.

Ordnet Autos und Wallboxen eindeutig zu, wenn die technischen Daten eindeutig
sind. Bei mehreren Möglichkeiten zeigt es „Unbekanntes Fahrzeug" bzw.
„Unbekannte Fahrzeuge (Anzahl)" und erlaubt manuelle Zuordnung. Keine
künstliche Obergrenze für die Anzahl von Autos oder Wallboxen.

Ort im Store: Kategorie "devices". Hängt an: core und mobility_calendar.
Liefert Fahrzeugzuordnung, gemeinsames/priorisiertes Laden und manuelle
Zuweisung.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="ev_wallbox_link",
    name_de="Auto–Wallbox-Verknüpfung",
    name_en="Car–Wallbox Linking",
    summary_de=(
        "Ordnet Autos und Wallboxen eindeutig zu, wenn die technischen Daten eindeutig sind. "
        "Bei mehreren Möglichkeiten zeigt es Unbekannte-Gruppen und erlaubt manuelle Zuordnung."
    ),
    summary_en=(
        "Links cars and wallboxes when technical data is unambiguous. When several options "
        "match, it shows unknown groups and allows manual assignment."
    ),
    category=ModuleCategory.DEVICES,
    icon="mdi:car-electric",
    requires=("core", "mobility_calendar"),
    provides=("vehicle_link", "shared_charging", "priority_charging", "manual_assignment"),
    reason_de="Das richtige Auto an der richtigen Wallbox laden.",
    reason_en="Charge the right car at the right wallbox.",
)
