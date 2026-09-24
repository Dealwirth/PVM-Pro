# PV-Manager

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://github.com/Dealwirth/PVM-Pro/actions/workflows/tests.yml/badge.svg)](https://github.com/Dealwirth/PVM-Pro/actions/workflows/tests.yml)
[![Validate](https://github.com/Dealwirth/PVM-Pro/actions/workflows/validate.yml/badge.svg)](https://github.com/Dealwirth/PVM-Pro/actions/workflows/validate.yml)
[![Home Assistant 2025.6+](https://img.shields.io/badge/Home%20Assistant-2025.6%2B-41BDF5.svg)](https://www.home-assistant.io/)
[![HACS custom integration](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**Datenschutz zuerst. Eigene Oberfläche. Modulare Energieplanung für Home Assistant.**

Der PV-Manager ist eine HACS-Integration mit einer vollständig eigenen
Anwendung in der Home-Assistant-Seitenleiste. Er ist **kein Lovelace-Dashboard**
und **kein Home-Assistant-Add-on-Store-Eintrag**. Module werden in einem
eigenen Store innerhalb der PV-Manager-Oberfläche aktiviert.

> **Status 0.1.0:** Der Rechenkern, die Geräteerkennung, Fallbacks, Grenzen,
> Prognose, Ladeplanung, Kalibrierung, das Sicherheitsterminal, die
> Datenschutz-/KI-Schicht und die komplette Oberfläche sind implementiert und
> getestet. Die 15 Store-Karten sind vorhanden; einzelne Komfortmodule werden
> in kommenden Versionen weiter vertieft. Nichts wird als „todsicher“
> versprochen: Das System ist **fehlersicher** ausgelegt und blockiert
> Automatik bei unklaren Daten.

## Funktionen

- Eigene responsive Oberfläche mit deutscher und englischer Sprache.
- Einsteiger-Tutorial beim ersten Start.
- Automatische Geräteerkennung aus Home Assistant, mit manuellem Fallback und
  ausdrücklicher Freigabe vor jeder Automatik.
- Unterstützt kombinierte Zähler (+/−), getrennte Bezugs-/Einspeisewerte und
  reine Bezugszähler.
- Priorisierbare Geräteliste, Module, Ziele und Verbraucherverwaltung.
- Verbrauchs- und Solarprognose mit Vertrauenswert und einfacher Erklärung.
- Ladeplanung für Autos und Wallboxen mit Kalender, Solarpriorität, optionalem
  Netzbezug und harten Grenzen.
- Wärmepumpe, Warmwasser, Pool, Lüftung, flexible Geräte und mehr als
  Fähigkeitsprüfung statt Hersteller-Sonderlogik.
- Sicherheitsterminal mit Stufen *Beobachten*, *Unterstützen* und *Sicher
  eingreifen*, Eingabe-/Ausgabeprüfung und wiederholten Fehlermeldungen.
- Optionale KI-Beratung (Groq vorgeschlagen, lokale und andere
  OpenAI-kompatible Anbieter möglich). Die KI berät ausschließlich; sie kann
  keine Geräte steuern.
- Datenschutzmodus standardmäßig **lokal**. Externe KI wird dick und rot
  gekennzeichnet. Vor dem Senden zeigt der PV-Manager die exakte Vorschau.
- Sichere manuelle Gerätesteuerung: Ausschalten ist immer ein sicherer
  Stopp, Einschalten läuft durch dieselbe Grenz- und Freigabeprüfung.
- Protokoll mit Grund, Ergebnis und automatischer Redaktion sensibler Daten.
- Vollständiges Löschen der PV-Manager-eigenen Daten bei der Entfernung;
  fremde Home-Assistant-Geräte bleiben unangetastet.

## Installation über HACS

**Schnellster Weg – Download-Button:**

[![In Home Assistant laden](https://img.shields.io/badge/In%20Home%20Assistant%20laden-HACS%20Repo-41BDF5.svg)](https://my.home-assistant.io/redirect/repository/?owner=Dealwirth&repository=PVM-Pro&category=integration)
[![Download](https://img.shields.io/badge/Download-Repo%20als%20ZIP-2EA043.svg)](https://github.com/Dealwirth/PVM-Pro/archive/refs/heads/main.zip)

Der erste Button öffnet bei deiner Home-Assistant-Instanz direkt das
HACS-Dialogfenster „Benutzerdefiniertes Repository" mit bereits ausgefüllten
Feldern (erfordert einmalig den offiziellen Helfer
[my.home-assistant.io](https://my.home-assistant.io/), kostenlos und rein
lokal verbindend; ohne Helfer zeigt die Seite die manuellen Schritte).
Der zweite Button lädt das Repository als ZIP für die manuelle Installation.

Alternativ von Hand:
2. Drei-Punkte-Menü → **Benutzerdefinierte Repositories**.
3. Diese Repository-URL eintragen und als Kategorie **Integration** wählen.
4. **PV Manager** installieren.
5. Home Assistant neu starten.
6. **Einstellungen → Geräte & Dienste → Integration hinzufügen → PV Manager**.
7. Zähler und PV-Erzeugung auswählen. Alles Weitere ist optional.
8. In der Seitenleiste **PV-Manager** öffnen und das kurze Tutorial abschließen.

### Manuelle Installation

Den Ordner `custom_components/pv_manager` nach
`<config>/custom_components/pv_manager` kopieren, Home Assistant neu starten
und die Integration hinzufügen.

## Voraussetzungen

- Home Assistant 2025.6 oder neuer, mit HACS.
- Mindestens eine Leistungs- oder Energie-Entität für den Netzanschluss.
- Eine PV-Erzeugungsentität.
- Optional: Batterie, Ladestand, Wetter, Kalender, Strompreis und Wallboxen.
- Für die optionale Cloud-KI: ein eigener Groq-API-Schlüssel (oder ein anderer
  OpenAI-kompatibler Anbieter).

## Module

Alle 15 Karten sind im internen Modul-Store beschrieben und einzeln
aktivierbar. Die Grundfunktion ist immer aktiv.

### Ein Addon = eine Datei

Alle Addons leben als je eine eigene Python-Datei unter
`custom_components/pv_manager/core/modules/`, sortiert nach Kategorie
(`base/`, `energy/`, `devices/`, `intelligence/`, `safety/`, `comfort/`).
Jede Datei erklärt in ihrem Docstring, was das Addon tut, welche Grenzen es
respektiert und wo es einhängt – sie ist zugleich Beispiel und Spezifikation.
Registriert werden neue Addons mit zwei Zeilen in `core/modules/_registry.py`.

Die vollständige Anleitung – vom leeren Ordner bis zum Pull Request, mit
einem lauffähigen Beispiel-Addon, der ehrlichen Antwort zur Frage
„Home-Assistant-Addon-Menü“ und den Risiken externer Erweiterungen – steht
in [docs/ADDONS.md](docs/ADDONS.md).

| Modul | Zweck |
|---|---|
| PV-Manager Grundsystem | Energiebilanz, Geräteerkennung, Fallback, Grenzen, Datenqualität, Datenschutz, Protokoll |
| Preis & Kosten | Günstige Zeiten, Kostenlimits |
| Speicher & Netz | Batterie, Phasen-/Anschlusswächter, Einspeisung |
| Thermische Flexibilität | Wärmepumpe, Warmwasser, Speicherheizung, Pool |
| Mobilität & Kalender | Abfahrten, wiederkehrende Fahrten, Fahrpläne |
| Prognose & Lernen | Verbrauchs-/Solarprognose, Kalibrierläufe |
| Was wäre wenn? | Simulationen und Probeläufe |
| Flexible Geräte | Waschmaschine, Trockner, Geschirrspüler, Pumpen, Bewässerung |
| Ziele, Berichte & Komfort | Budgets, Eigenstrom, CO₂, Berichte, Raumkomfort |
| Anwesenheit & Sondermodi | Urlaub, Eco, Gast, Anwesenheit |
| Wartungsassistent & PV-Zustand | Wartung und auffällige Abweichungen |
| Lüftungssteuerung | Luftqualität, Anwesenheit, Wetter |
| Energie-Gewohnheiten | Muster erkennen, bestätigen, korrigieren |
| Auto–Wallbox-Verknüpfung | Zuordnung, gemeinsames und priorisiertes Laden |
| Sicherheitsterminal | Dauerüberwachung, Eingabe-/Ausgabeprüfung, optionale KI-Beratung |

## Sicherheit und Fallback

Jedes Gerät startet im sicheren Modus:

- unbekannte Geräte werden nur angezeigt;
- fehlende, veraltete oder widersprüchliche Daten pausieren die Automatik;
- Grenzen sind mit ihren Zahlenwerten sichtbar und müssen bestätigt werden;
- die KI darf niemals schalten;
- der Not-Aus sperrt alle Automatikaktionen;
- bei Kalibrierläufen werden Zeit, Leistung, Energie, Netzgrenze und Abbruch
  hart begrenzt;
- Software kann elektrische Sicherheit nicht ersetzen.

## Datenschutz

- Standard ist **lokal**. Keine Datenübertragung.
- Externe KI ist freiwillig, opt-in und wird rot markiert.
- Es werden nur die angezeigten, pseudonymisierten technischen Daten
  gesendet: Alias, Kategorie, Fähigkeiten, normalisierte Messwerte,
  Fehlercodes, Modulstatus.
- Nicht gesendet werden Gerätenamen, Raumnamen, Kalendertexte, Standort, IDs,
  IP-/MAC-Adressen, Fahrzeugkennungen, freie Texte und API-Schlüssel.
- Aliase rotieren pro Bericht und werden lokal aufgelöst.
- Pseudonymisierung ist kein Anonymisierungsversprechen. Details stehen in
  [PRIVACY.md](PRIVACY.md) und [SECURITY.md](SECURITY.md).

### Groq-Hinweis

Groq ist als empfohlener Cloud-Anbieter hinterlegt. Nach der aktuellen
Groq-Dokumentation werden Inferenzdaten standardmäßig nicht dauerhaft
gespeichert, können zur Stabilitäts-/Missbrauchsprüfung aber bis zu 30 Tage
temporär verbleiben. Zero Data Retention ist im Groq-Konto aktivierbar.
Nutzungsmetadaten werden weiterhin verarbeitet. Prüfe vor der Nutzung die
aktuellen Bedingungen und aktiviere nach Möglichkeit Zero Data Retention.

## Tests

```bash
# Rechenkern, Laufzeit und Verträge – ohne Home-Assistant-Installation
python -m unittest discover -s tests -t .

# Oberfläche: Rendering, Sprache, Datenschutz
npm test
```

Aktuell: **214 Tests** – 125 Rechenkern, 54 Laufzeit (Home-Assistant-Ebene und
KI-Übertragung), 13 Vertragstests und 22 Oberflächentests. Die Laufzeittests
führen den echten Code gegen schlanke Home-Assistant-Attrappen aus, ohne Home
Assistant zu installieren.

Besonders streng geprüft wird der einzige Pfad, der Daten aus dem Haus
schickt: die Tests der KI-Übertragung prüfen den **tatsächlich gesendeten
HTTP-Aufruf** darauf, dass keine Gerätenamen, Entitäts-IDs, Kalenderinhalte,
Koordinaten oder Schlüssel enthalten sind, dass der API-Schlüssel nur im
`Authorization`-Header reist und dass im lokalen Modus **kein Gerätekontext
überhaupt entsteht**.

Auf Windows kann `py` statt `python` verwendet werden.

## Mitwirken

Beiträge sind willkommen. Siehe [CONTRIBUTING.md](CONTRIBUTING.md) und
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Sicherheitslücken bitte gemäß
[SECURITY.md](SECURITY.md) melden.

## Lizenz

MIT – siehe [LICENSE](LICENSE).
