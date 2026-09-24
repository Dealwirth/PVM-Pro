"""Automatic device and capability discovery.

Home Assistant already knows which devices exist. PV Manager therefore does
not scan the network. It reads the entity and device registries, classifies
candidates and always asks the user before a device is used for control.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .types import Capability, DeviceKind, EntityDescriptor

ACTUATOR_DOMAINS: dict[str, Capability] = {
    "switch": Capability.SWITCH,
    "input_boolean": Capability.SWITCH,
    "light": Capability.SWITCH,
    "fan": Capability.SET_MODE,
    "climate": Capability.SET_TEMPERATURE,
    "water_heater": Capability.SET_TEMPERATURE,
    "number": Capability.SET_POWER,
    "input_number": Capability.SET_POWER,
    "select": Capability.SET_MODE,
    "input_select": Capability.SET_MODE,
    "cover": Capability.SET_MODE,
}

_DOMAIN_CAPABILITIES: dict[str, set[Capability]] = {
    "sensor": set(),
    "binary_sensor": set(),
    "weather": {Capability.READ_WEATHER},
    "calendar": {Capability.READ_CALENDAR},
    "device_tracker": {Capability.MEASURE_PRESENCE},
    "person": {Capability.MEASURE_PRESENCE},
}

_MEASUREMENT_CAPABILITIES: dict[str, Capability] = {
    "power": Capability.MEASURE_POWER,
    "energy": Capability.MEASURE_ENERGY,
    "temperature": Capability.MEASURE_TEMPERATURE,
    "humidity": Capability.MEASURE_HUMIDITY,
    "battery": Capability.MEASURE_SOC,
    "current": Capability.MEASURE_PHASE_CURRENT,
    "monetary": Capability.MEASURE_PRICE,
}

_KIND_HINTS: dict[DeviceKind, tuple[str, ...]] = {
    DeviceKind.GRID_METER: (
        "grid",
        "netz",
        "meter",
        "zähler",
        "zaehler",
        "import",
        "export",
        "einspeis",
        "bezug",
    ),
    DeviceKind.PV: (
        "pv",
        "solar",
        "photovoltaik",
        "string",
        "mppt",
        "inverter",
        "wechselrichter",
        "erzeugung",
        "generation",
    ),
    DeviceKind.BATTERY: (
        "battery",
        "batterie",
        "speicher",
        "akku",
        "soc",
        "state of charge",
    ),
    DeviceKind.EV_CHARGER: (
        "wallbox",
        "wall box",
        "charger",
        "ladepunkt",
        "ladestation",
        "evse",
        "charge point",
        "go-e",
        "zappi",
        "easee",
        "openwb",
    ),
    DeviceKind.EV: (
        "car",
        "auto",
        "vehicle",
        "fahrzeug",
        "tesla",
        "leaf",
        "ioniq",
        "id.3",
        "id.4",
    ),
    DeviceKind.HEAT_PUMP: ("heat pump", "wärmepumpe", "waermepumpe", "wp ", "cop"),
    DeviceKind.HOT_WATER: ("water heater", "warmwasser", "boiler", "heizstab", "ww "),
    DeviceKind.POOL: ("pool", "whirlpool", "spa"),
    DeviceKind.VENTILATION: (
        "lüftung",
        "lueftung",
        "ventilation",
        "luftqualität",
        "co2",
        "voc",
        "abluft",
        "zuft",
    ),
    DeviceKind.FLEXIBLE_LOAD: (
        "washer",
        "waschmaschine",
        "dryer",
        "trockner",
        "dishwasher",
        "geschirrspüler",
        "geschirrspueler",
        "irrigation",
        "bewässerung",
        "pumpe",
        "pump",
    ),
}

NAME_HINTS: dict[DeviceKind, tuple[str, ...]] = _KIND_HINTS


@dataclass(slots=True)
class EntityCapabilities:
    """Capabilities derived from one entity."""

    entity_id: str
    capabilities: set[Capability] = field(default_factory=set)
    reasons: dict[Capability, str] = field(default_factory=dict)


@dataclass(slots=True)
class DeviceCandidate:
    """A proposed assignment that the user still has to confirm."""

    entity_id: str
    name: str
    kind: DeviceKind
    score: float
    capabilities: set[Capability] = field(default_factory=set)
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    requires_confirmation: bool = True
    manual: bool = False


def capabilities_for(entity: EntityDescriptor) -> EntityCapabilities:
    """Derive capabilities from an entity descriptor."""
    result = EntityCapabilities(entity.entity_id)
    domain = entity.domain.lower()

    for capability in _DOMAIN_CAPABILITIES.get(domain, set()):
        result.capabilities.add(capability)
        result.reasons[capability] = f"domain:{domain}"

    actuator = ACTUATOR_DOMAINS.get(domain)
    if actuator is not None:
        result.capabilities.add(actuator)
        result.reasons[actuator] = f"domain:{domain}"
        if domain in {"number", "input_number"}:
            units = (entity.unit or "").lower()
            if units in {"w", "kw"}:
                result.capabilities.add(Capability.SET_POWER)
            elif units in {"°c", "c", "f"}:
                result.capabilities.add(Capability.SET_TEMPERATURE)
        if domain == "light":
            result.capabilities.add(Capability.SET_MODE)
        if domain == "fan":
            result.capabilities.add(Capability.SET_FAN_SPEED)

    device_class = (entity.device_class or "").lower()
    measurement = _MEASUREMENT_CAPABILITIES.get(device_class)
    if measurement is not None:
        result.capabilities.add(measurement)
        result.reasons[measurement] = f"device_class:{device_class}"

    units = (entity.unit or "").lower()
    if units in {"w", "kw", "mw"}:
        result.capabilities.add(Capability.MEASURE_POWER)
        result.reasons.setdefault(Capability.MEASURE_POWER, f"unit:{units}")
    elif units in {"wh", "kwh", "mwh"}:
        result.capabilities.add(Capability.MEASURE_ENERGY)
        result.reasons.setdefault(Capability.MEASURE_ENERGY, f"unit:{units}")
    elif units in {"a", "ma"}:
        result.capabilities.add(Capability.MEASURE_PHASE_CURRENT)
        result.reasons.setdefault(Capability.MEASURE_PHASE_CURRENT, f"unit:{units}")
    elif units in {"°c", "c"}:
        result.capabilities.add(Capability.MEASURE_TEMPERATURE)
        result.reasons.setdefault(Capability.MEASURE_TEMPERATURE, f"unit:{units}")
    elif units in {"%"} and device_class == "battery":
        result.capabilities.add(Capability.MEASURE_SOC)
        result.reasons.setdefault(Capability.MEASURE_SOC, f"unit:{units}")
    elif units in {"€/kwh", "ct/kwh", "eur/kwh", "currency"}:
        result.capabilities.add(Capability.MEASURE_PRICE)
        result.reasons.setdefault(Capability.MEASURE_PRICE, f"unit:{units}")

    if entity.state_class in {"measurement"} and result.capabilities:
        result.capabilities.add(Capability.MEASURE_POWER) if (
            Capability.MEASURE_POWER in result.capabilities
        ) else None
    return result


# More specific roles win over generic ones such as "flexible load". This
# prevents a heat pump containing the word "pump" from being classified as a
# generic appliance.
_KIND_SPECIFICITY: tuple[DeviceKind, ...] = (
    DeviceKind.HEAT_PUMP,
    DeviceKind.EV_CHARGER,
    DeviceKind.EV,
    DeviceKind.BATTERY,
    DeviceKind.PV,
    DeviceKind.GRID_METER,
    DeviceKind.VENTILATION,
    DeviceKind.POOL,
    DeviceKind.HOT_WATER,
    DeviceKind.FLEXIBLE_LOAD,
)


def guess_kind(entity: EntityDescriptor) -> tuple[DeviceKind, float, tuple[str, ...]]:
    """Guess the logical device kind and return a confidence score."""
    text = " ".join(
        part.lower()
        for part in (
            entity.entity_id,
            entity.name,
            entity.device_id or "",
            entity.area_name or "",
        )
    )
    scores: dict[DeviceKind, float] = {}
    reasons_by_kind: dict[DeviceKind, list[str]] = {}
    for kind, hints in _KIND_HINTS.items():
        hits = [hint for hint in hints if hint in text]
        if not hits:
            continue
        score = min(0.35 + 0.22 * len(hits), 0.95)
        if entity.device_class == "energy" and kind in {
            DeviceKind.GRID_METER,
            DeviceKind.PV,
            DeviceKind.BATTERY,
        }:
            score += 0.1
        scores[kind] = score
        reasons_by_kind[kind] = [f"hint:{hit}" for hit in hits]

    if not scores:
        if entity.device_class == "power":
            return DeviceKind.LOAD, 0.2, ("device_class:power",)
        return DeviceKind.UNKNOWN, 0.0, ()

    best_kind = max(scores, key=lambda kind: scores[kind])
    best_score = scores[best_kind]
    # Prefer a specific device role when it is reasonably close to the generic
    # candidate. A heat pump stays a heat pump even though "pump" also matches.
    for kind in _KIND_SPECIFICITY:
        if kind in scores and scores[kind] >= best_score - 0.3 and scores[kind] >= 0.4:
            best_kind = kind
            best_score = scores[kind]
            break
    return best_kind, min(best_score, 1.0), tuple(reasons_by_kind.get(best_kind, []))


def discover_candidates(
    entities: Iterable[EntityDescriptor],
    *,
    known_entities: Iterable[str] = (),
    min_score: float = 0.2,
) -> list[DeviceCandidate]:
    """Return ranked candidates for the user to confirm."""
    known = set(known_entities)
    candidates: list[DeviceCandidate] = []
    for entity in entities:
        if entity.entity_id in known:
            continue
        caps = capabilities_for(entity)
        if not caps.capabilities:
            continue
        if not entity.available and not caps.capabilities & {
            Capability.READ_CALENDAR,
            Capability.READ_WEATHER,
        }:
            candidates.append(
                DeviceCandidate(
                    entity_id=entity.entity_id,
                    name=entity.name,
                    kind=DeviceKind.UNKNOWN,
                    score=0.1,
                    capabilities=caps.capabilities,
                    reasons=("entity_unavailable",),
                    warnings=("offline",),
                    manual=True,
                )
            )
            continue
        kind, kind_score, reasons = guess_kind(entity)
        score = min(kind_score + 0.25 * min(len(caps.capabilities), 3) / 3, 1.0)
        if kind_score < min_score and score < min_score:
            continue
        warnings: list[str] = []
        if cap_control_without_measure(caps.capabilities):
            warnings.append("control_without_measurement")
        if kind is DeviceKind.UNKNOWN:
            warnings.append("manual_assignment_required")
        candidates.append(
            DeviceCandidate(
                entity_id=entity.entity_id,
                name=entity.name,
                kind=kind,
                score=round(score, 3),
                capabilities=set(caps.capabilities),
                reasons=tuple(reasons),
                warnings=tuple(warnings),
                requires_confirmation=True,
                manual=kind is DeviceKind.UNKNOWN,
            )
        )
    candidates.sort(key=lambda candidate: (candidate.score, candidate.name), reverse=True)
    return candidates


def cap_control_without_measure(capabilities: set[Capability]) -> bool:
    """Return True when a device can be switched but not measured."""
    actuators = {
        Capability.SWITCH,
        Capability.SET_POWER,
        Capability.SET_TEMPERATURE,
        Capability.SET_MODE,
    }
    measurements = {
        Capability.MEASURE_POWER,
        Capability.MEASURE_ENERGY,
        Capability.MEASURE_TEMPERATURE,
        Capability.MEASURE_SOC,
        Capability.MEASURE_PHASE_CURRENT,
    }
    return bool(capabilities & actuators) and not bool(capabilities & measurements)


def best_matches(
    entities: Iterable[EntityDescriptor], kind: DeviceKind, limit: int = 3
) -> list[DeviceCandidate]:
    """Return the best candidates for one logical role."""
    return [c for c in discover_candidates(entities) if c.kind is kind][:limit]
