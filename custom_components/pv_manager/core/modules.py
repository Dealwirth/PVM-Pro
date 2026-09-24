"""The internal PV Manager module store.

These are not Home Assistant add-ons and not Supervisor containers. They are
bundled, versioned feature packages of the PV Manager UI. A module can be
enabled or disabled individually without removing the base system.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModuleCategory(StrEnum):
    """Store categories shown in the UI."""

    BASE = "base"
    ENERGY = "energy"
    DEVICES = "devices"
    INTELLIGENCE = "intelligence"
    SAFETY = "safety"
    COMFORT = "comfort"


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    """One card in the internal store."""

    module_id: str
    name_de: str
    name_en: str
    summary_de: str
    summary_en: str
    category: ModuleCategory
    icon: str
    optional: bool = True
    default_enabled: bool = False
    safety_level: str = "standard"
    requires: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    reason_de: str = ""
    reason_en: str = ""

    def as_dict(self, *, enabled: bool) -> dict[str, object]:
        """Return a serializable store card."""
        return {
            "module_id": self.module_id,
            "name_de": self.name_de,
            "name_en": self.name_en,
            "summary_de": self.summary_de,
            "summary_en": self.summary_en,
            "category": self.category.value,
            "icon": self.icon,
            "optional": self.optional,
            "enabled": enabled,
            "default_enabled": self.default_enabled,
            "safety_level": self.safety_level,
            "requires": list(self.requires),
            "provides": list(self.provides),
            "reason_de": self.reason_de,
            "reason_en": self.reason_en,
        }


CORE_MODULE_ID = "core"

MODULE_SPECS: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        module_id=CORE_MODULE_ID,
        name_de="PV-Manager Grundsystem",
        name_en="PV Manager Core",
        summary_de=(
            "Immer aktiv. Zeigt PV-Erzeugung, Verbrauch, Netzbezug und Einspeisung. "
            "Erkennt Geräte, schützt Grenzen, prüft Daten und verhindert unsinnige Automatik."
        ),
        summary_en=(
            "Always active. Shows PV generation, consumption, grid import and export. "
            "Detects devices, protects limits, checks data and prevents unsafe automation."
        ),
        category=ModuleCategory.BASE,
        icon="mdi:solar-power-variant",
        optional=False,
        default_enabled=True,
        safety_level="mandatory",
        provides=(
            "energy_balance",
            "device_discovery",
            "fallback",
            "limits",
            "data_quality",
            "notifications",
            "privacy",
            "audit",
        ),
        reason_de="Die Grundlage für alle anderen Module.",
        reason_en="The foundation for every other module.",
    ),
    ModuleSpec(
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
        requires=(CORE_MODULE_ID,),
        provides=("price_windows", "cost_limit"),
        reason_de="Sparen, ohne Komfort zu opfern.",
        reason_en="Save money without sacrificing comfort.",
    ),
    ModuleSpec(
        module_id="storage_grid",
        name_de="Speicher & Netz",
        name_en="Storage & Grid",
        summary_de=(
            "Entscheidet, ob Solarstrom genutzt, gespeichert oder eingespeist wird. "
            "Überwacht Anschluss-, Phasen- und Leistungsgrenzen."
        ),
        summary_en=(
            "Decides whether solar power is used, stored or exported. Monitors service, "
            "phase and power limits."
        ),
        category=ModuleCategory.ENERGY,
        icon="mdi:battery-sync",
        requires=(CORE_MODULE_ID,),
        provides=("battery_strategy", "grid_guard", "export_management"),
        reason_de="Mehr Eigenverbrauch und sichere Netznutzung.",
        reason_en="More self-consumption and safe grid usage.",
    ),
    ModuleSpec(
        module_id="thermal",
        name_de="Thermische Flexibilität",
        name_en="Thermal Flexibility",
        summary_de=(
            "Heizung und Warmwasser dürfen flexibel geplant werden, aber nur innerhalb von "
            "Temperatur-, Hygiene- und Komfortgrenzen."
        ),
        summary_en=(
            "Heating and hot water may be scheduled flexibly, but only within temperature, "
            "hygiene and comfort limits."
        ),
        category=ModuleCategory.DEVICES,
        icon="mdi:heat-pump",
        requires=(CORE_MODULE_ID,),
        provides=("heat_pump_plan", "hot_water_plan", "pool_plan"),
        reason_de="Wärme dann erzeugen, wenn Strom günstig oder solar ist.",
        reason_en="Generate heat when power is cheap or solar.",
    ),
    ModuleSpec(
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
        requires=(CORE_MODULE_ID,),
        provides=("departure_planning", "recurring_trips"),
        reason_de="Ladeplanung passend zu echten Fahrten.",
        reason_en="Charging plans that match real trips.",
    ),
    ModuleSpec(
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
        requires=(CORE_MODULE_ID,),
        provides=("consumption_forecast", "solar_forecast", "calibration"),
        reason_de="Bessere Entscheidungen durch gelernte Muster.",
        reason_en="Better decisions from learned patterns.",
    ),
    ModuleSpec(
        module_id="what_if",
        name_de="Was wäre wenn?",
        name_en="What If?",
        summary_de=(
            "Zeigt vorab, was passieren würde, wenn das Auto später, eine Wallbox schneller "
            "oder die Wärmepumpe anders geplant würde."
        ),
        summary_en=(
            "Shows in advance what would happen if the car charged later, a wallbox charged "
            "faster or the heat pump was scheduled differently."
        ),
        category=ModuleCategory.INTELLIGENCE,
        icon="mdi:flask-outline",
        requires=(CORE_MODULE_ID, "forecast_learning"),
        provides=("simulation", "shadow_mode"),
        reason_de="Ausprobieren, bevor etwas geschaltet wird.",
        reason_en="Try before anything is switched.",
    ),
    ModuleSpec(
        module_id="flexible_loads",
        name_de="Flexible Geräte",
        name_en="Flexible Loads",
        summary_de=(
            "Plant Geräte wie Waschmaschine, Trockner, Geschirrspüler, Pumpen oder "
            "Bewässerung in sinnvollen Zeitfenstern."
        ),
        summary_en=(
            "Schedules washing machine, dryer, dishwasher, pumps or irrigation into sensible time windows."
        ),
        category=ModuleCategory.DEVICES,
        icon="mdi:washing-machine",
        requires=(CORE_MODULE_ID,),
        provides=("flexible_scheduling", "irrigation", "pool_pump"),
        reason_de="Haushaltsgeräte nutzen Strom, wenn er da ist.",
        reason_en="Household appliances use power when it is available.",
    ),
    ModuleSpec(
        module_id="goals_reports",
        name_de="Ziele, Berichte & Komfort",
        name_en="Goals, Reports & Comfort",
        summary_de=(
            "Zeigt Monatsziele, Berichte, Eigenstrom, CO₂-Schätzung und Komfortbereiche in einfacher Sprache."
        ),
        summary_en=(
            "Shows monthly goals, reports, self-consumption, CO2 estimate and comfort ranges "
            "in plain language."
        ),
        category=ModuleCategory.ENERGY,
        icon="mdi:target",
        requires=(CORE_MODULE_ID,),
        provides=("energy_budget", "reports", "export", "co2", "room_comfort"),
        reason_de="Verstehen, was man erreicht hat.",
        reason_en="Understand what has been achieved.",
    ),
    ModuleSpec(
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
        requires=(CORE_MODULE_ID,),
        provides=("presence", "holiday_mode", "guest_mode", "eco_mode"),
        reason_de="Automatik, die zum echten Alltag passt.",
        reason_en="Automation that matches real life.",
    ),
    ModuleSpec(
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
        requires=(CORE_MODULE_ID,),
        provides=("maintenance_reminders", "pv_health", "shading_check"),
        reason_de="Kleine Auffälligkeiten früh erkennen.",
        reason_en="Detect small anomalies early.",
    ),
    ModuleSpec(
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
        requires=(CORE_MODULE_ID,),
        provides=("ventilation_control",),
        reason_de="Frische Luft ohne unnötigen Energieverlust.",
        reason_en="Fresh air without unnecessary energy loss.",
    ),
    ModuleSpec(
        module_id="energy_habits",
        name_de="Energie-Gewohnheiten",
        name_en="Energy Habits",
        summary_de=(
            "Erkennt wiederkehrende Muster wie sonntägliches Laden. Es schlägt Muster vor, "
            "nutzt sie aber erst nach Bestätigung."
        ),
        summary_en=(
            "Detects recurring patterns such as Sunday charging. It proposes patterns but "
            "only uses them after confirmation."
        ),
        category=ModuleCategory.INTELLIGENCE,
        icon="mdi:repeat-variant",
        requires=(CORE_MODULE_ID, "forecast_learning"),
        provides=("habit_detection", "habit_confirmation"),
        reason_de="Wiederkehrendes automatisch erkennen, aber nicht heimlich übernehmen.",
        reason_en="Detect recurring behaviour, but never adopt it silently.",
    ),
    ModuleSpec(
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
        requires=(CORE_MODULE_ID, "mobility_calendar"),
        provides=("vehicle_link", "shared_charging", "priority_charging", "manual_assignment"),
        reason_de="Das richtige Auto an der richtigen Wallbox laden.",
        reason_en="Charge the right car at the right wallbox.",
    ),
    ModuleSpec(
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
        requires=(CORE_MODULE_ID,),
        provides=("module_monitor", "input_output_check", "ai_advice", "risk_reports"),
        reason_de="Extreme Sicherheit als freiwilliges Modul.",
        reason_en="High assurance as an optional module.",
        safety_level="high",
    ),
)

MODULES_BY_ID: dict[str, ModuleSpec] = {spec.module_id: spec for spec in MODULE_SPECS}
CORE_MODULE = MODULES_BY_ID[CORE_MODULE_ID]


def default_enabled_modules() -> set[str]:
    """Return the modules enabled on a fresh installation."""
    return {spec.module_id for spec in MODULE_SPECS if spec.default_enabled}


def resolve_dependencies(enabled: set[str], *, module_id: str) -> set[str]:
    """Return the set of modules that must be enabled together with module_id."""
    result = {module_id}
    changed = True
    while changed:
        changed = False
        for current in tuple(result):
            spec = MODULES_BY_ID.get(current)
            if spec is None:
                continue
            for dependency in spec.requires:
                if dependency not in result:
                    result.add(dependency)
                    changed = True
    return {item for item in result if item in MODULES_BY_ID or item == CORE_MODULE_ID}


def dependents_of(module_id: str, enabled: set[str]) -> set[str]:
    """Return enabled modules that depend on module_id."""
    return {
        spec.module_id for spec in MODULE_SPECS if module_id in spec.requires and spec.module_id in enabled
    }


def store_cards(enabled: set[str] | None = None) -> list[dict[str, object]]:
    """Return all store cards with their current state."""
    active = enabled or default_enabled_modules()
    return [spec.as_dict(enabled=spec.module_id in active) for spec in MODULE_SPECS]
