"""Addon: Preis & Kosten.

Nutzt Strompreise, um günstige Zeiten für Wärmepumpe, Auto und andere große
Verbraucher zu finden. Ein Kostenlimit verhindert teure Überraschungen.

Ort im Store: Kategorie "energy". Hängt an: core. Liefert Preisfenster und
Kostenlimit; ohne aktives Addon werden keine Preisdaten gelesen.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="price_cost",
    name_de="Preis & Kosten",
    name_en="Price & Cost",
    summary_de=(
        "Nutzt Strompreise, um günstige Zeiten für Wärmepumpe, Auto und andere große "
        "Verbraucher zu finden. Ein Kostenlimit verhindert teure Überraschungen."
    ),
    summary_en=(
        "Uses electricity prices to find cheap windows for heat pump, car and other large "
        "loads. A cost limit prevents expensive surprises."
    ),
    category=ModuleCategory.ENERGY,
    icon="mdi:cash-clock",
    requires=("core",),
    provides=("price_windows", "cost_limit"),
    reason_de="Sparen, ohne Komfort zu opfern.",
    reason_en="Save money without sacrificing comfort.",
)
