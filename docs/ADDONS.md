# Eigene Addons schreiben

Der PV-Manager hat einen **internen Modul-Store**. Alles, was dort als Karte
erscheint, nennen wir hier **Addon**. Wichtig zur Abgrenzung:

> **PV-Manager-Addons sind KEINE Home-Assistant-Add-ons.** Ein
> Home-Assistant-Add-on ist ein Docker-Container im Supervisor. Ein
> PV-Manager-Addon ist eine Python-Datei innerhalb dieser Integration, die
> eine Karte im internen Store beschreibt. Es gibt keinen Supervisor, keine
> Container und keinen Add-on-Store von Home Assistant. Die Abschaltung
> erfolgt jederzeit über den internen Store in der PV-Manager-Oberfläche.

Diese Anleitung zeigt, wie du in wenigen Minuten ein eigenes Addon anlegst,
registrierst, testest und veröffentlichst.

---

## Ordnerstruktur: ein Addon = eine Datei

Alle Addons liegen in der Integration unter
`custom_components/pv_manager/core/modules/`, sortiert nach Kategorie –
jede Datei ist in sich vollständig lesbar und versteht sich ohne den Rest
des Codes:

```
core/modules/
├── __init__.py        Stabile öffentliche Schnittstelle des Stores
├── _spec.py           Datenklassen ModuleSpec / ModuleCategory
├── _registry.py       Registrierung: hier neue Addons einreihen
├── base/
│   └── core.py        Grundsystem (immer aktiv, nicht abschaltbar)
├── energy/
│   ├── price_cost.py
│   ├── storage_grid.py
│   └── goals_reports.py
├── devices/
│   ├── thermal.py
│   ├── mobility_calendar.py
│   ├── flexible_loads.py
│   └── ev_wallbox_link.py
├── intelligence/
│   ├── forecast_learning.py
│   ├── what_if.py
│   └── energy_habits.py
├── safety/
│   ├── maintenance_pv_health.py
│   └── security_terminal.py
└── comfort/
    ├── presence_modes.py
    └── ventilation.py
```

Jede Addon-Datei folgt demselben Muster: oben ein Docstring, der in einfachen
Sätzen erklärt, was das Addon tut, welche Grenzen es respektiert und wo es
einhängt – danach die `SPEC`. Öffne zum Vergleich eine der bestehenden
Dateien; jede ist gleichzeitig Beispiel und Spezifikation.

---

## Die Schnittstelle: ModuleSpec

``_spec.py`` definiert die Datenklasse; die Felder sind im Docstring dort
ausführlich erklärt. Die wichtigsten:

| Feld | Bedeutung |
|---|---|
| `module_id` | Stabile Kennung, klein und mit Unterstrichen; ändert sich nach der ersten Veröffentlichung nie wieder |
| `name_de` / `name_en` | Anzeigename in beiden Sprachen (beide sind Pflicht – es gibt kein „nur Deutsch") |
| `summary_de` / `summary_en` | Kurze Beschreibung für die Store-Karte |
| `category` | Eine der sechs Kategorien; bestimmt auch den Ordner der Datei |
| `icon` | Material-Design-Icon (`mdi:...`) |
| `optional` | Nur das Grundsystem ist `False`; eigene Addons sind immer `True` |
| `default_enabled` | Aktiv bei frischer Installation – nur für das Grundsystem `True` |
| `safety_level` | `"standard"`, `"high"` oder `"mandatory"` |
| `requires` | Addons, die zusammen mit diesem aktiviert werden müssen (mindestens `("core",)`) |
| `provides` | Fähigkeiten, die dieses Addon wirklich liefert – ehrlich aufführen |
| `reason_de` / `reason_en` | Ein Satz „Warum es sich lohnt" |

---

## Eigenes Addon in fünf Schritten

### 1. Datei anlegen

Kategorie wählen (siehe Ordnerliste oben) und dort eine neue Datei mit dem
Namen der `module_id` anlegen, zum Beispiel
`core/modules/comfort/electricity_tariff.py`:

```python
"""Addon: Stromtarif-Fenster.

Zeigt, zu welchen Zeiten der eigene Tarif günstig ist, und markiert diese
Fenster im Ladeplan. Es liest nur einen von dir angegebenen Sensor und
schaltet nichts.

Ort im Store: Kategorie "comfort". Hängt an: core. Liefert Tariffenster
für Plan und Dashboard.
"""

from __future__ import annotations

from .._spec import ModuleCategory, ModuleSpec

SPEC = ModuleSpec(
    module_id="electricity_tariff",
    name_de="Stromtarif-Fenster",
    name_en="Tariff Windows",
    summary_de=(
        "Zeigt die günstigen Zeiten deines Stromtarifs und markiert sie im "
        "Ladeplan. Reine Anzeige, ohne Schaltfunktion."
    ),
    summary_en=(
        "Shows the cheap windows of your electricity tariff and highlights them "
        "in the charging plan. Display only, no switching."
    ),
    category=ModuleCategory.COMFORT,
    icon="mdi:clock-time-eight",
    requires=("core",),
    provides=("tariff_windows",),
    reason_de="Günstige Stunden auf einen Blick.",
    reason_en="Cheap hours at a glance.",
)
```

### 2. Registrieren

In `core/modules/_registry.py` zwei Zeilen ergänzen – den Import oben und
die Position im `MODULE_SPECS`-Tupel (die Reihenfolge im Tupel ist die
Reihenfolge im Store):

```python
from .comfort.electricity_tariff import SPEC as _ELECTRICITY_TARIFF

MODULE_SPECS: tuple[ModuleSpec, ...] = (
    _CORE,
    ...,
    _ELECTRICITY_TARIFF,  # neuer Eintrag
)
```

### 3. Prüfen

```bash
py -m compileall -q custom_components tests
py -m unittest discover -s tests -t .
py -m ruff check .
```

Struktur-Tests achten darauf, dass jede Datei eine `SPEC` exportiert, die
`module_id` dem Dateinamen entspricht, und dass der Eintrag in der Registry
existiert. Danach die neue Karte im Store sichten:

```bash
node scripts/build_preview.mjs
```

und die Vorschau im Browser öffnen (Kategorie „comfort", Karte
„Stromtarif-Fenster").

### 4. Verhalten implementieren

Die `SPEC` ist die Karte im Store; das tatsächliche Verhalten hängst du je
nach Art des Addons an unterschiedlichen Stellen ein:

- **Reine Anzeige** (wie das Beispiel): Werte im `snapshot()` der Laufzeit
  ergänzen und in der Oberfläche rendern (`frontend/render.js`,
  Texte in `frontend/i18n.js` in **beiden** Sprachen).
- **Berechnung** (Prognose, Planung, Grenzen): Logik als reine Funktion im
  HA-freien Kern (`core/`) implementieren und dort unit-testen – genau wie
  die bestehenden Module `core/forecast.py` oder `core/planner.py`.
- **Schaltendes Verhalten**: immer über das Sicherheitsgate
  (`core/execution.py`, `evaluate_manual_action`) führen. Ein Addon, das
  Geräte schaltet, ohne dieses Gate zu durchlaufen, wird im Review
  abgelehnt.

Grenzen, die jedes Addon respektieren muss:

- Keine Automatik ohne ausdrückliche Freigabe des Nutzers.
- Unklare oder alte Daten → sicherer Fallback statt Annahme.
- Alle Nutzertexte in Deutsch **und** Englisch (über `frontend/i18n.js`).
- Kein Netzwerkzugriff ohne opt-in; externe Dienste nur über
  `ai_client.py`-Muster mit Pseudonymisierung.
- Löschen der Integration entfernt auch die Daten des Addons.

### 5. Dokumentieren

Einen Eintrag in der Tabelle in `docs/MODULES.md` ergänzen und das Addon im
`CHANGELOG.md` unter „Unreleased" nennen.

---

## Geht das auch im Home-Assistant-Addon-Menü?

Kurz gesagt: **nein – und das ist gewollt.**

Das Add-on-Menü von Home Assistant gehört zum Supervisor und verwaltet
Docker-Container. PV-Manager-Addons sind Bestandteile der Integration und
bewusst dort integriert, wo ihre Sicherheit und ihr Datenschutz am besten
kontrollierbar sind: im internen Store der PV-Manager-Oberfläche (Modul
„Store" in der Seitenleiste). Nutzer aktivieren und deaktivieren sie mit
einem Klick; die Aktivierung wird sofort wirksam und ist jederzeit
rückholbar.

Ein echtes Home-Assistant-Add-on wäre für diese Funktionalität der falsche
Weg: mehr Angriffsfläche (eigener Container mit potenziell weitreichenden
Rechten), kein gemeinsames Sicherheitsgate, keine geteilte
Datenschutzschicht und ein zweites Update-System neben der Integration.

### Risiken, wenn du es trotzdem separat auslieferst

Solltest du eigene Erweiterungen **außerhalb** dieser Integration als
Home-Assistant-Add-on, custom component oder Skript ausliefern, gilt
unabhängig vom PV-Manager:

- **Verlust der Garantien.** Die Zusagen in `PRIVACY.md` (keine
  Datenweitergabe, lokale Verarbeitung, Pseudonymisierung) gelten nur für
  Code in diesem Repository. Externer Code umgeht Pseudonymisierung,
  Audit-Log und Sicherheitsgate vollständig.
- **Schreibrechte auf deine gesamte Instanz.** Ein Add-on-Container läuft
  standardmäßig mit weitreichenden Rechten; ein fehlerhafter oder
  bösartiger Container kann Geräte schalten, Daten lesen und Systemeinstellungen
  ändern.
- **Keine gemeinsame Abschaltbarkeit.** Der Not-Aus des PV-Managers stoppt
  nur PV-Manager-Aktionen. Externe Automatiken laufen weiter.
- **Verwirrung über Verantwortlichkeit.** Der PV-Manager kann Fehler
  externer Erweiterungen nicht erkennen oder erklären.

**Empfehlung:** Eigene Erweiterungen als PV-Manager-Addon nach dieser
Anleitung bauen. Dann bleiben Überwachung (Sicherheitsterminal), Audit-Log,
Datenschutzmodus und Not-Aus vollständig wirksam.

---

## Veröffentlichen (eigener Fork oder Pull Request)

1. Addon-Datei, Registry-Eintrag, `docs/MODULES.md` und `CHANGELOG.md`
   ändern – nichts anderes.
2. `py -m unittest discover -s tests -t .` und `py -m ruff check .` grün.
3. Pull Request mit kurzem Bezug auf die Store-Karte öffnen. Erwartet im
   Review: ehrliche `provides`-Angaben, beide Sprachen, Sicherheitsgate bei
   Schaltfunktionen, keine neuen Netzwerkaufrufe ohne opt-in.

Häufige Ablehnungsgründe im Review:

| Befund | Warum |
|---|---|
| `name_en`/`summary_en` fehlen oder sind Kopien des Deutschen | Die vollständige Zweisprachigkeit ist eine Kernvorgabe |
| `provides` verspricht Fähigkeiten, die der Code nicht hat | Nutzer treffen Entscheidung anhand der Karte |
| Schalten ohne `evaluate_manual_action` | Umgeht Not-Aus und Audit |
| Neuer Netzwerkzugriff ohne Zustimmungsdialog | Verstoß gegen die Datenschutzvorgabe |
| `module_id` nach Veröffentlichung geändert | Aktivierungen und Tests würden still brechen |
