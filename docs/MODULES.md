# Module

15 Karten im internen Store. Nur die Grundfunktion ist Pflicht. Alle anderen
Module sind freiwillig und einzeln aktivierbar.

| # | Modul | ID | Standard | Abhängigkeiten | Sicherheit |
|---|---|---|---|---|---|
| 1 | PV-Manager Grundsystem | `core` | aktiv | – | immer aktiv |
| 2 | Preis & Kosten | `price_cost` | aus | core | Kostenlimit |
| 3 | Speicher & Netz | `storage_grid` | aus | core | Netzgrenzen |
| 4 | Thermische Flexibilität | `thermal` | aus | core | Komfort-/Hygienegrenzen |
| 5 | Mobilität & Kalender | `mobility_calendar` | aus | core | sichere Ersatzplanung |
| 6 | Prognose & Lernen | `forecast_learning` | aus | core | begrenzte Lernläufe |
| 7 | Was wäre wenn? | `what_if` | aus | core, forecast_learning | nur Simulation |
| 8 | Flexible Geräte | `flexible_loads` | aus | core | Zeit-/Leistungsgrenzen |
| 9 | Ziele, Berichte & Komfort | `goals_reports` | aus | core | nur Anzeige/Budget |
| 10 | Anwesenheit & Sondermodi | `presence_modes` | aus | core | reduziert Automatik |
| 11 | Wartungsassistent & PV-Zustand | `maintenance_pv_health` | aus | core | nur Hinweise |
| 12 | Lüftungssteuerung | `ventilation` | aus | core | Sensor- und Komfortgrenzen |
| 13 | Energie-Gewohnheiten | `energy_habits` | aus | core, forecast_learning | nur nach Bestätigung |
| 14 | Auto–Wallbox-Verknüpfung | `ev_wallbox_link` | aus | core, mobility_calendar | eindeutige Zuordnung, sonst unbekannt |
| 15 | Sicherheitsterminal | `security_terminal` | aus | core | hohe Sicherheitsstufe |

## Grundfunktion

- Energiebilanz und Vorzeichenprüfung.
- Geräteerkennung aus Home Assistant.
- Fallback, Grenzen und Datenqualität.
- Benachrichtigungen, Datenschutz, Audit.
- Funktioniert ohne jedes andere Modul.

## Auto–Wallbox-Verknüpfung

- Keine künstliche Obergrenze für Autos/Wallboxen; die Oberfläche bleibt durch
  Paginierung und gestufte Aktualisierung performant.
- Automatische Zuordnung nur bei eindeutigen technischen Merkmalen.
- Sonst: „Unbekanntes Fahrzeug“ oder „Unbekannte Fahrzeuge (Anzahl)“.
- Manuelle Zuordnung jederzeit möglich.
- Gemeinsames oder priorisiertes Laden, Start/Stopp/Leistungsanpassung nur
  innerhalb aller harten Grenzen.

## Sicherheitsterminal

- Stufen: Beobachten, Unterstützen, Sicher eingreifen.
- Reaktionszeit einstellbar: sofort, 30 s, 5 min, nächste Prüfung.
- Prüft Modulstatus, Herzschläge, Eingabe-/Ausgabeverträge, Grenzen,
  Datenalter, Energiebilanz und Datenschutzmodus.
- Wiederholte Meldungen werden entdoppelt und begrenzt.
- KI ist optional und ausschließlich beratend.
