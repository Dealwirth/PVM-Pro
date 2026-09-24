# Datenschutz / Privacy

Der PV-Manager wurde mit der Regel entworfen: **So viel Funktion wie nötig,
so wenig Datenübertragung wie möglich, und niemals eine Übertragung ohne
sichtbare Zustimmung.**

## Standardverhalten

- Alle Berechnungen laufen lokal auf dem Home-Assistant-System.
- Es gibt keine Telemetrie, kein Analytics, kein Tracking und keine
  automatische Cloud-Verbindung.
- Die lokale KI-Beratung (Regeln) funktioniert vollständig ohne Netzwerk.
- Externe Wetter-, Preis- oder KI-Daten sind optionale Funktionen und
  standardmäßig deaktiviert.

## Privatmodus für KI

Der PV-Manager erzeugt vor jeder externen Beratung eine **Vorschau**. Erst
diese Vorschau darf gesendet werden. Der Nutzer sieht:

- welche Felder gesendet werden,
- welche Felder bewusst weggelassen werden,
- den vollständigen Inhalt der Nutzlast,
- eine Warnung für den aktiven Modus.

### Was niemals gesendet wird

- Home-Assistant-Entity-IDs und Geräte-IDs,
- Geräte-, Raum- und Spitznamen,
- Kalenderinhalte und -titel,
- Standort, Adresse, Koordinaten,
- IP-, MAC- und Netzwerkadressen,
- Fahrzeugkennungen und VIN,
- freie Texte und Nutzereingaben,
- API-Schlüssel, Tokens, Passwörter und Cookies.

### Was im pseudonymisierten Modus gesendet werden kann

- ein pro Bericht neu erzeugter Alias wie `device-3f9a1c22`,
- eine grobe Gerätekategorie,
- erkannte Fähigkeiten,
- normalisierte Zahlenwerte wie Leistung, Alter und Fehleranzahl,
- Fehlercodes,
- der Status eines Moduls,
- optional aggregierte Wetterwerte.

### Grenze der Pseudonymisierung

Ein Alias schützt vor direktem Namensabgleich, aber Verbrauchsmuster,
Zeitpunkte und Kombinationen können in Einzelfällen Rückschlüsse erlauben.
Deshalb gilt: Der lokale Modus ist der datenschutzfreundlichste Modus. Wer den
Cloud-Modus nutzt, sollte den Anbieter, seine Aufbewahrungsregeln und
gegebenenfalls Zero Data Retention prüfen.

## Sichtbarkeit in der Oberfläche

| Status | Bedeutung |
|---|---|
| **GRÜN** | Lokal. Keine externe KI-Datenübertragung. |
| **ROT, dick und hervorgehoben** | Externe KI aktiv. Pseudonymisierte Daten können gesendet werden. |

## Protokoll

Das Audit-Protokoll entfernt automatisch:

- API-Schlüssel, Tokens, Passwörter und Cookies,
- E-Mail-Adressen und Telefonnummern,
- Koordinaten und Adressen,
- Fahrzeugkennungen.

Das Protokoll ist begrenzt, lokal exportierbar und vollständig löschbar.

## Löschen

Beim Entfernen der Integration löscht der PV-Manager:

- alle eigenen Einstellungen,
- alle Modulzustände und Pläne,
- das eigene Protokoll und die Laufzeitdaten,
- die generierten Entitäten.

Nicht gelöscht werden:

- die originale Home-Assistant-Recorder-Historie,
- fremde Entitäten, Geräte und Kalender.

Diese Trennung verhindert, dass das Löschen des PV-Managers unerwartet andere
Dashboards, Automationen oder Langzeitstatistiken zerstört.
