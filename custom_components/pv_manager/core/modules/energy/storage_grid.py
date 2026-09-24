"""Addon: Speicher & Netz.

Entscheidet, ob Solarstrom genutzt, gespeichert oder eingespeist wird, und
überwacht Anschluss-, Phasen- und Leistungsgrenzen.

Ort im Store: Kategorie "energy". Hängt an: core. Liefert Batteriestrategie,
Netzschutz und Einspeisemanagement.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="storage_grid",
    name_de="Speicher & Netz",
    name_en="Storage & Grid",
    summary_de=(
        "Entscheidet, ob Solarstrom genutzt, gespeichert oder eingespeist wird. "
        "Überwacht Anschluss-, Phasen- und Leistungsgrenzen."
    ),
    summary_en=(
        "Decides whether solar power is used, stored or exported. Monitors service, phase and power limits."
    ),
    category=ModuleCategory.ENERGY,
    icon="mdi:battery-sync",
    requires=("core",),
    provides=("battery_strategy", "grid_guard", "export_management"),
    reason_de="Mehr Eigenverbrauch und sichere Netznutzung.",
    reason_en="More self-consumption and safe grid usage.",
)
