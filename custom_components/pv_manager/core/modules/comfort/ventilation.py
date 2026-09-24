"""Addon: Lüftungssteuerung.

Steuert eine unterstützte Lüftung anhand von Luftqualität, Anwesenheit,
Wetter und gewählten Zeiten – niemals ohne gültige Sensoren oder manuelle
Freigabe.

Ort im Store: Kategorie "comfort". Hängt an: core. Liefert die
Lüftungssteuerung.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="ventilation",
    name_de="Lüftungssteuerung",
    name_en="Ventilation Control",
    summary_de=(
        "Steuert eine unterstützte Lüftung anhand von Luftqualität, Anwesenheit, Wetter "
        "und gewählten Zeiten; niemals ohne gültige Sensoren oder manuelle Freigabe."
    ),
    summary_en=(
        "Controls supported ventilation based on air quality, presence, weather and chosen "
        "times; never without valid sensors or manual approval."
    ),
    category=ModuleCategory.COMFORT,
    icon="mdi:air-filter",
    requires=("core",),
    provides=("ventilation_control",),
    reason_de="Frische Luft ohne unnötigen Energieverlust.",
    reason_en="Fresh air without unnecessary energy loss.",
)
