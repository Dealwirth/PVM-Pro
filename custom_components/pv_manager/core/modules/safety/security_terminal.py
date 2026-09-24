"""Addon: Sicherheitsterminal.

Überwacht alle PV-Manager-Addons, Geräte, Sensoren, Grenzen, Fehler und den
Datenschutzstatus dauerhaft. Meldet Risiken, kurze Berichte und genaue
Reparaturhinweise mit Stufen und einstellbarer Reaktionszeit. Eine KI ist
optional, berät ausschließlich und darf niemals allein steuern.

Ort im Store: Kategorie "safety", hohe Sicherheitsstufe. Hängt an: core.
Liefert Modulüberwachung, Eingabe-/Ausgabeprüfung, KI-Beratung und
Risikoberichte.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="security_terminal",
    name_de="Sicherheitsterminal",
    name_en="Security Terminal",
    summary_de=(
        "Überwacht alle PV-Manager-Module, Geräte, Sensoren, Grenzen, Fehler und den "
        "Datenschutzstatus dauerhaft. Meldet Risiken, kurze Berichte und genaue "
        "Reparaturhinweise. Eine KI ist optional und darf niemals allein steuern."
    ),
    summary_en=(
        "Continuously monitors all PV Manager modules, devices, sensors, limits, errors and "
        "privacy status. Reports risks, short summaries and exact repair guidance. An AI is "
        "optional and must never control devices on its own."
    ),
    category=ModuleCategory.SAFETY,
    icon="mdi:shield-check",
    requires=("core",),
    provides=("module_monitor", "input_output_check", "ai_advice", "risk_reports"),
    reason_de="Extreme Sicherheit als freiwilliges Modul.",
    reason_en="High assurance as an optional module.",
    safety_level="high",
)
