# Test- und Abnahmeplan

## Automatischer Testvertrag

| Vertrag | Erwartung | Testdatei |
|---|---|---|
| Einheiten | W/kW/MW und Wh/kWh/MWh werden korrekt umgerechnet | `tests/core/test_normalize.py` |
| Vorzeichen | Signed net, import positive, export positive, separate, import only | `tests/core/test_normalize.py` |
| Energiebilanz | plausible Bilanz, erkannte Abweichungen, keine Doppelzählung | `tests/core/test_normalize.py` |
| Fallback | unbekannt/veraltet/unglaubwürdig/unbestätigt blockiert Automatik | `tests/core/test_fallback.py` |
| Grenzen | Netz-, Phasen-, Geräte- und Energiebudget werden geklemmt oder blockiert | `tests/core/test_limits_planner.py` |
| Ausführung | Ausschalten ist sicherer Stopp, Einschalten braucht Freigabe und Freiraum | `tests/core/test_execution.py` |
| Ladeplan | Solar zuerst, Netz nur mit Freigabe, Abfahrt nie überschritten | `tests/core/test_limits_planner.py` |
| Erkennung | Rollen und Fähigkeiten; spezifische Geräte gewinnen gegen generische | `tests/core/test_discovery_modules.py` |
| Module | genau 15, Abhängigkeiten, zweisprachige Texte | `tests/core/test_discovery_modules.py` |
| Sicherheitsterminal | Stufen, Vertragsprüfung, Wiederholungen, Kern nie pausiert | `tests/core/test_security_privacy.py` |
| Datenschutz | lokal sendet keine Geräte; pseudonym sendet Alias, keine verbotenen Schlüssel | `tests/core/test_security_privacy.py` |
| KI | lokal ohne Netz, extern nur mit Modus + Bestätigung, niemals Steuerung | `tests/core/test_ai_calibration_forecast.py` |
| Kalibrierung | Zeit-, Leistungs-, Energie- und Netzgrenzen, Abbruch | `tests/core/test_ai_calibration_forecast.py` |
| Prognose | Cold Start, gelerntes Profil, Wetterfaktor, Vertrauensstufen | `tests/core/test_ai_calibration_forecast.py` |
| Oberfläche | alle Ansichten rendern, rote Datenschutzwarnung, Tutorial, kein Lovelace | `tests/frontend/render.test.mjs` |
| Sprache | Deutsch und Englisch haben identische Schlüssel; keine leeren Werte; keine deutschen Texte in der englischen Ansicht; jede Bestätigungsfrage läuft über die Übersetzungstabelle | `tests/frontend/render.test.mjs` |
| Grenzwerte | Grenzwerte erscheinen mit Zahlenwerten; unbestätigte Grenzen werden nie als bestätigt dargestellt | `tests/frontend/render.test.mjs` |
| Zahlenformat | Dezimaltrennzeichen folgt der gewählten Sprache | `tests/frontend/render.test.mjs` |
| Quelltext | kein nutzerseitiger deutscher Text ausserhalb der Übersetzungstabelle | `tests/frontend/render.test.mjs` |
| Laufzeit-Befehle | Einschalten braucht Bestätigung, Freigabe und frische Daten; Ausschalten bleibt sicherer Stopp; Not-Aus und unbekannte Geräte blockieren | `tests/ha/test_runtime.py` |
| Laufzeit-Snapshot | der Zustand enthält die Felder, die die Oberfläche liest; Grenzwerte und Warnungen stimmen | `tests/ha/test_runtime.py` |
| Laufzeit-Module | Kern nie abschaltbar, Abhängigkeiten werden mitaktiviert, genutzte Module nicht abschaltbar | `tests/ha/test_runtime.py` |
| Laufzeit-Persistenz | nur Konfiguration wird gespeichert; API-Schlüssel und Messwerte nie; Löschen entfernt nur eigene Daten | `tests/ha/test_runtime.py` |
| Benachrichtigungen | folgen der gewählten Sprache und enthalten keinen Schlüssel | `tests/ha/test_runtime.py` |
| Verträge | jedes von der Oberfläche gerufene Kommando existiert; Dienste in YAML und Code stimmen überein; Versionen und URLs konsistent | `tests/test_contracts.py` |
| KI-Übertragung | der echte HTTP-Aufruf enthält keine Namen, Entitäts-IDs, Kalenderinhalte, Koordinaten oder Schlüssel; der Schlüssel reist nur im Header; lokaler Modus erzeugt keinen Gerätekontext; Fehlerantworten werden gekürzt statt vollständig weitergegeben | `tests/ha/test_ai_client.py` |
| KI-Sprache | Systemprompt, Nutzerprompt, Nutzlast-Sprache und die lokale Regelantwort folgen der gewählten Sprache | `tests/ha/test_ai_client.py` |
| Anbieterkatalog | jeder Anbieter hat beide Namen und beide Datenschutzhinweise; Groq ist als extern und empfohlen markiert | `tests/ha/test_ai_client.py` |
| Stil | `ruff check` und `ruff format --check` laufen fehlerfrei | CI-Auftrag *Lint and format* |

Ausführen:

```bash
python -m unittest discover -s tests -t .
npm test
```

Aktueller Stand: **208 automatisierte Tests**
(119 Rechenkern, 54 Laufzeit und KI-Übertragung, 13 Verträge, 22 Oberfläche).

## Manuelle Hardware-Abnahme

Diese Prüfungen brauchen die konkrete Anlage des Nutzers:

- Stromzähler-Vorzeichen mit realen Tageswerten verifizieren.
- PV-Erzeugung gegen Wechselrichter-App vergleichen.
- Batterie-Lade-/Entladeleistung prüfen.
- Wallbox: gemeinsames und priorisiertes Laden, Abfahrt, manueller Modus.
- Wärmepumpe: Komfortgrenzen, Sperrzeiten, keine unerwarteten Abschaltungen.
- Kalender: Urlaub, Arbeit, verschobene Fahrt.
- Verbindungsabriss: Sensor ausstecken, Verhalten prüfen.
- Not-Aus: sofortige Sperre prüfen.
- Datenschutz: Vorschau ansehen, externe Übertragung blockieren.

Ergebnisse gehören in einen eigenen Abnahmebericht. Ohne diese Prüfungen wird
keine allgemeine Hardware-Garantie behauptet.
