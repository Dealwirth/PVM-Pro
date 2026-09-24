# Kalibrierung und Lernlauf

Der Lernlauf hilft, den tatsächlichen Verbrauch eines schaltbaren Geräts zu
messen. Er ist **keine elektrische Prüfung** und keine Eichung.

## Ablauf

1. Der Nutzer wählt ein Gerät und bestätigt den Lauf.
2. Der PV-Manager misst eine kurze Grundlast.
3. Ein Gerät wird eingeschaltet – nur eines gleichzeitig.
4. Leistung, Energie, Netzbezug und Dauer werden laufend geprüft.
5. Bei Grenzverletzung, Zeitüberschreitung, Energieüberschreitung, Not-Aus
   oder Verbindungsproblem wird sofort ausgeschaltet und abgebrochen.
6. Nach der eingestellten Anzahl Wiederholungen folgt eine verständliche
   Zusammenfassung.

## Grenzen

| Grenze | Standard | Zweck |
|---|---|---|
| Maximale Leistung | 2000 W | kleine, kontrollierte Testlast |
| Maximale Testenergie | 0,5 kWh | kein unnötiger Verbrauch |
| Maximale Einschaltdauer | 120 s | kurzer, absehbarer Test |
| Wiederholungen | 2 | genauere Messung |
| Netz-Freiraum | 500 W | eigener Anschluss bleibt belastbar |

Alle Werte sind vor dem Lauf einstellbar, aber nach oben begrenzt.

## Was der Lernlauf nicht tut

- Er ändert keine Spannung, Sicherung oder Anschlussleistung.
- Er umgeht keine Grenzen.
- Er schaltet nicht mehrere große Geräte gleichzeitig.
- Er ersetzt keine Elektrofachkraft.
- Er erzeugt keine Hersteller-Garantie.

## Ergebnis

Der PV-Manager speichert den gemessenen Wert als **Vorschlag**, nicht als
verifizierte Sicherheitsgrenze. Grenzen bestätigt immer der Nutzer.
