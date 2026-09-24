"""Addon: Ziele, Berichte & Komfort.

Zeigt Monatsziele, Berichte, Eigenstromanteil, CO₂-Schätzung und
Komfortbereiche in einfacher Sprache. Reine Anzeige und Budgetierung:
Dieses Addon schaltet nichts.

Ort im Store: Kategorie "energy". Hängt an: core. Liefert Energiebudget,
Berichte, Export, CO₂ und Raumkomfort.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="goals_reports",
    name_de="Ziele, Berichte & Komfort",
    name_en="Goals, Reports & Comfort",
    summary_de=(
        "Zeigt Monatsziele, Berichte, Eigenstrom, CO₂-Schätzung und Komfortbereiche in einfacher Sprache."
    ),
    summary_en=(
        "Shows monthly goals, reports, self-consumption, CO2 estimate and comfort ranges in plain language."
    ),
    category=ModuleCategory.ENERGY,
    icon="mdi:target",
    requires=("core",),
    provides=("energy_budget", "reports", "export", "co2", "room_comfort"),
    reason_de="Verstehen, was man erreicht hat.",
    reason_en="Understand what has been achieved.",
)
