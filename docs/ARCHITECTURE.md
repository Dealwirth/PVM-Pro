# Architektur

## Schichten

```
custom_components/pv_manager/
├── frontend/            Eigene Oberfläche (kein Lovelace)
│   ├── pv-manager-panel.js   Webcomponent + Interaktion
│   ├── render.js             reine Renderfunktionen (testbar)
│   ├── styles.js             eigenes Designsystem
│   └── i18n.js               Deutsch/Englisch
├── core/                HA-freier, testbarer Rechenkern
│   ├── types.py              Datentypen und Fähigkeiten
│   ├── normalize.py          Einheiten, Vorzeichen, Energiebilanz
│   ├── discovery.py          Geräte- und Fähigkeitserkennung
│   ├── fallback.py           fehlersichere Freigabe
│   ├── limits.py             harte Grenzen
│   ├── forecast.py           Verbrauchs- und Solarprognose
│   ├── planner.py            Ladeplanung
│   ├── calibration.py        begrenzter Lernlauf
│   ├── modules.py            Modul-Store
│   ├── security.py           Sicherheitsterminal
│   ├── privacy.py            Pseudonymisierung und Nutzlastprüfung
│   ├── ai.py                 KI-Anbieter und Beratung
│   └── audit.py              redigiertes Protokoll
├── runtime.py           Zustand eines Config-Eintrags
├── coordinator.py       Aktualisierung im Hintergrund
├── config_flow.py       Einrichtung und Optionen
├── panel.py             Seitenleiste und statische Dateien
├── websocket_api.py     Oberflächen-API
├── services.py          HA-Dienste inkl. Lernlauf
├── ai_client.py         HTTP-Anbindung der KI-Anbieter
├── sensor.py            Energiesensoren
├── binary_sensor.py     Sicherheits-/Datenschutzsensoren
└── switch.py            Modulschalter
```

## Zentrale Regel

Es gibt **eine** Entscheidungskette:

1. Rohdaten aus Home Assistant
2. Einheiten- und Vorzeichennormalisierung
3. Fähigkeits- und Grenzprüfung
4. Fallback-Entscheidung
5. Planung/Empfehlung
6. zentrale Grenzprüfung
7. Ausführung oder sichere Blockade
8. Protokoll mit Grund und Ergebnis

Kein Modul, keine Oberfläche und keine KI darf Schritt 6 umgehen.

## Module

Module sind mitgelieferte, versionierte Funktionspakete. „Aktivieren“ ist ein
lokaler Zustand, kein Nachladen von fremdem Code. Es gibt:

- eine zentrale Laufzeit (`PVManagerRuntime`),
- einen Websocket-Zustand für die Oberfläche,
- Modulschalter als Home-Assistant-Entitäten,
- abhängigkeitssichere Aktivierung.

## Datenfluss der Oberfläche

`hass.callWS` → `websocket_api.py` → `runtime.snapshot()` → `render.js`.
Die Oberfläche erhält nur den Zustand, den sie anzeigen darf. API-Schlüssel
werden nie Teil des Zustands.

## Löschen

`async_remove_entry` löscht den eigenen `Store`, das Audit-Protokoll, die
Alias-Zuordnung und entfernt bei Bedarf Seitenleiste sowie Dienste. Fremde
Home-Assistant-Entitäten und die Recorder-Historie bleiben unberührt.

## Tests

Die Testebenen sind bewusst getrennt, damit kein Testlauf eine
Home-Assistant-Installation braucht.

| Ebene | Ordner | Was geprüft wird |
|---|---|---|
| Rechenkern | `tests/core/` | Entscheidungen, ohne Home Assistant zu importieren |
| Laufzeit | `tests/ha/` | `runtime.py` gegen die HA-Attrappen aus `ha_stubs.py` |
| Verträge | `tests/test_contracts.py` | Kommando- und Dienstnamen, Versionen, URLs |
| Oberfläche | `tests/frontend/` | Rendering, Sprache, Datenschutz |

`tests/ha/ha_stubs.py` reproduziert bewusst nur die fünf Schnittstellen, die
`runtime.py` tatsächlich benutzt: `hass.states`, `hass.services`, `Store`,
`util.dt` und `persistent_notification`. Fehlt etwas, meldet die Attrappe das
mit einer klaren Fehlermeldung, statt still `None` zurückzugeben. So kann der
Testlauf eine fehlende Schnittstelle nicht übersehen.
