# KI-Beratung

Die KI ist **optional**, **beratend** und **ohne Werkzeuge**. Sie kann keine
Geräte schalten, keine Dienste aufrufen und keine Grenzen ändern.

## Anbieter

| Anbieter | Lokal | Empfohlen | Hinweis |
|---|---|---|---|
| Lokale Regeln | ja | ja | funktioniert immer, kein Netzwerk |
| Lokales OpenAI-kompatibles Modell | ja | – | z. B. Ollama im eigenen Netz |
| Groq | nein | ja | empfohlener Cloud-Anbieter |
| Anderer OpenAI-kompatibler Anbieter | nein | – | Nutzer prüft Datenschutzregeln |

## Einrichtung

1. **KI & Datenschutz** in der PV-Manager-Oberfläche öffnen.
2. Datenschutzmodus wählen: lokal, pseudonymisiert oder erweitert.
3. Anbieter wählen; Groq ist vorgeschlagen.
4. API-Schlüssel eingeben. Er wird lokal im Home-Assistant-Eintrag gespeichert
   und nie an die Oberfläche zurückgegeben.
5. **Vorschau** drücken und prüfen, welche Daten gesendet würden.
6. **Bericht erstellen** und die externe Übertragung bestätigen.

## Berichtsrhythmus

- aus,
- stündlich,
- täglich,
- wöchentlich,
- nur bei schwerwiegenden Fehlern,
- nur manuell.

Kritische Fehler werden unabhängig vom Rhythmus gemeldet, aber entdoppelt und
begrenzt.

## Groq und Aufbewahrung

Nach der aktuellen Groq-Dokumentation:

- Inferenzdaten werden standardmäßig nicht dauerhaft gespeichert.
- Zur Stabilitäts- und Missbrauchsprüfung können Eingaben/Ausgaben bis zu
  30 Tage temporär gespeichert werden.
- Zero Data Retention kann im Groq-Konto aktiviert werden; dadurch entfallen
  speicherbasierte Zusatzfunktionen.
- Nutzungsmetadaten werden weiterhin verarbeitet.
- Daten können in den USA verarbeitet werden.

Prüfe die aktuellen Bedingungen selbst und aktiviere nach Möglichkeit Zero
Data Retention. Der lokale Modus bleibt immer die strengste Option.
