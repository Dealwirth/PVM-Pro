"""Addon: Wartungsassistent & PV-Zustand.

Erinnert an sinnvolle Wartung und erkennt auffällige Änderungen bei
PV-Anlage, Wechselrichter und Verbrauchern. Nur Hinweise und Meldungen:
Dieses Addon greift nicht in Geräte ein.

Ort im Store: Kategorie "safety". Hängt an: core. Liefert
Wartungserinnerungen, PV-Zustand und Verschattungsprüfung.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="maintenance_pv_health",
    name_de="Wartungsassistent & PV-Zustand",
    name_en="Maintenance & PV Health",
    summary_de=(
        "Erinnert an sinnvolle Wartung und erkennt auffällige Änderungen bei PV-Anlage, "
        "Wechselrichter und Verbrauchern."
    ),
    summary_en=(
        "Reminds about useful maintenance and detects unusual changes in PV system, inverter and loads."
    ),
    category=ModuleCategory.SAFETY,
    icon="mdi:wrench-clock",
    requires=("core",),
    provides=("maintenance_reminders", "pv_health", "shading_check"),
    reason_de="Kleine Auffälligkeiten früh erkennen.",
    reason_en="Detect small anomalies early.",
)
