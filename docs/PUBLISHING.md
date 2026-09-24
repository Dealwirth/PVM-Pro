# Veröffentlichung auf GitHub

Diese Anleitung enthält die exakten Befehle für den ersten Upload. Sie ist so
geschrieben, dass sie auf Windows in **Git Bash** funktioniert (dort stehen
`sed`, `grep` und `git` zur Verfügung).

Das Repository ist bereits lokal vorbereitet: `git init -b main` wurde
ausgeführt, die Dateien liegen bereit, es gibt noch **keinen Commit und kein
Remote**.

> **Status:** Schritt 1–3 sind bereits erledigt. Der Besitzer ist
> **Dealwirth**, das Repository `Dealwirth/PVM-Pro` existiert (öffentlich,
> leer, Standardbranch `main`) und alle Platzhalter im Manifest sind ersetzt.
> Der Ablauf beginnt bei **Schritt 4**.

---

## Schritt 1 – Besitzer und Repo-Name eintragen *(erledigt: `@Dealwirth`)*

Name des Repositorys: **PVM-Pro** (der Repo-Name muss nicht mit der Domain
`pv_manager` übereinstimmen, das ist für HACS nicht erforderlich).

`OWNER` ist dein GitHub-Benutzername (oder der Name der Organisation). Er darf
nur Buchstaben, Ziffern und Bindestriche enthalten.

```bash
OWNER=Dealwirth

sed -i "s|@pv-manager|@$OWNER|; s|github\.com/pv-manager/pv-manager|github.com/$OWNER/PVM-Pro|g" \
  custom_components/pv_manager/manifest.json
```

Kontrolle – es darf **kein** Treffer mehr erscheinen:

```bash
grep -n "pv-manager/pv-manager\|@pv-manager" custom_components/pv_manager/manifest.json
cat custom_components/pv_manager/manifest.json
```

Erwartetes Ergebnis: `codeowners` zeigt auf `@Dealwirth`,
`documentation` auf `https://github.com/Dealwirth/PVM-Pro` und
`issue_tracker` auf dieselbe URL mit `/issues`.

> **Hinweis:** Ein nicht existierendes Konto in `codeowners` kann die
> hassfest-Prüfung im Workflow `validate.yml` scheitern lassen. Verwende
> deshalb wirklich deinen eigenen Benutzernamen.

---

## Schritt 2 – Git-Identität setzen

Aktuell ist weder `user.name` noch `user.email` konfiguriert, ein Commit würde
also fehlschlagen. Die Identität wird hier **nur für dieses Repository**
gesetzt:

```bash
git config user.name "Dealwirth"
git config user.email "171386277+Dealwirth@users.noreply.github.com"
```

Die hier angegebene Identität ist die GitHub-NoReply-Adresse des Benutzers
`Dealwirth` (Benutzer-ID `171386277`): Commits werden so dem Konto zugeordnet,
ohne dass eine private E-Mail öffentlich wird.

---

## Schritt 3 – Repository auf GitHub anlegen *(erledigt: `Dealwirth/PVM-Pro` existiert)*

Das Repository existiert bereits und ist leer – dieser Schritt ist damit
abgeschlossen. Der Abschnitt bleibt als Referenz, falls das Repository neu
angelegt werden muss.

`gh` (GitHub CLI) ist auf diesem System nicht installiert, deshalb ist der Weg
über die Weboberfläche der einfachste.

1. <https://github.com/new> öffnen.
2. **Repository name:** `PVM-Pro`
3. **Description:** `Privacy-first Home Assistant PV and large-load manager with its own custom UI.`
4. **Public** auswählen.
5. **Kein** README, **keine** `.gitignore` und **keine** Lizenz hinzufügen – das
   Repository muss leer bleiben, sonst kollidiert der erste Push.
6. **Create repository**.

### Optional: mit installierter GitHub CLI

```bash
winget install --id GitHub.cli -e
gh auth login
gh repo create PVM-Pro --public \
  --description "Privacy-first Home Assistant PV and large-load manager with its own custom UI."
```

---

## Schritt 4 – Committen und hochladen

Alle Dateien werden bewusst explizit aufgezählt. `preview/` und `.freebuff/`
sind über `.gitignore` ausgeschlossen und werden nicht hochgeladen.

```bash
git add .github .gitignore CHANGELOG.md CODE_OF_CONDUCT.md CONTRIBUTING.md \
  LICENSE PRIVACY.md README.md SECURITY.md brand custom_components docs \
  hacs.json package.json pyproject.toml scripts tests

git status --short
git commit -m "Initial public release of PV Manager 0.1.0"

git remote add origin https://github.com/Dealwirth/PVM-Pro.git
git push -u origin main
```

`git status --short` sollte vor dem Commit ausschließlich mit `A` markierte
Dateien zeigen. Erscheint dort etwas Unerwartetes, nicht committen, sondern
zuerst prüfen.

---

## Schritt 5 – Repository-Metadaten setzen (HACS-Pflicht)

HACS verlangt eine Beschreibung, aktivierte Issues und die Topics `hacs` und
`integration`. Diese Angaben lassen sich nicht per Workflow setzen.

Im Repository unter **Settings**:

- **Description** eintragen (falls in Schritt 3 leer geblieben).
- **Issues** aktivieren.
- Unter **Topics** hinzufügen: `hacs`, `integration`, `home-assistant`,
  `photovoltaics`, `energy-management`, `privacy`.

---

## Schritt 6 – Erstes Release erstellen (empfohlen)

Ohne Release lädt HACS die Dateien des Standard-Branches. Mit einem Release
erhält der Nutzer eine Versionsauswahl und spätere Updates funktionieren
sauber.

1. **Releases → Draft a new release**
2. **Choose a tag:** `v0.1.0` → *Create new tag on publish*
3. **Release title:** `PV Manager 0.1.0`
4. Beschreibung aus dem Abschnitt `0.1.0` in [CHANGELOG.md](../CHANGELOG.md)
   übernehmen.
5. **Publish release**

Wichtig: Die Version im Release-Tag muss zu `"version": "0.1.0"` in
`manifest.json` passen.

---

## Schritt 7 – Workflow-Prüfung scharf stellen

`.github/workflows/validate.yml` ignoriert zurzeit `issues` und `topics`, weil
diese Metadaten vor der Veröffentlichung nicht existieren konnten. Sobald
Schritt 5 erledigt ist, diese Zeile entfernen:

```yaml
          ignore: "issues topics"
```

Danach muss der Workflow **Validate** ohne Ignorierungen grün durchlaufen.

---

## Schritt 8 – CI-Abzeichen einsetzen

Nach dem ersten Push lässt sich der Testzustand direkt im README anzeigen.
Die Abzeichen sind bereits eingetragen und zeigen auf `Dealwirth/PVM-Pro`;
dieser Abschnitt dient nur noch als Referenz:

```markdown
[![Tests](https://github.com/Dealwirth/PVM-Pro/actions/workflows/tests.yml/badge.svg)](https://github.com/Dealwirth/PVM-Pro/actions/workflows/tests.yml)
[![Validate](https://github.com/Dealwirth/PVM-Pro/actions/workflows/validate.yml/badge.svg)](https://github.com/Dealwirth/PVM-Pro/actions/workflows/validate.yml)
```

Sie sind bereits im README eingetragen und werden nach dem ersten Push
automatisch grün, sobald beide Workflows einmal gelaufen sind.

## Prüfliste nach dem Upload

- [ ] `manifest.json` enthält keinen Platzhalter mehr (Schritt 1).
- [ ] Der Workflow **Tests** ist grün (Python 3.12/3.13 und Node 22).
- [ ] Der Workflow **Validate** ist grün (HACS-Action und hassfest).
- [ ] Release `v0.1.0` ist veröffentlicht.
- [ ] Beschreibung, Topics und Issues sind gesetzt.
- [ ] In HACS als benutzerdefiniertes Repository mit Kategorie *Integration*
      hinzufügbar.
- [ ] Nach der Installation erscheint **PV-Manager** in der Seitenleiste und
      das Tutorial startet beim ersten Öffnen.

---

## Vor dem ersten Push erneut prüfen

```bash
py -m compileall -q custom_components scripts tests
py -m unittest discover -s tests -t .
node --test tests/frontend/render.test.mjs
```

Erwartet: **208 Tests grün** (186 Python, 22 Frontend) und ein fehlerfreier
Lauf von `ruff check` sowie `ruff format --check`.

Zusätzlich empfehlenswert: eine Suche nach versehentlich eingecheckten
Geheimnissen.

```bash
grep -rniE "(api[_-]?key|token|secret|password)" \
  custom_components docs scripts .github README.md || echo "keine Treffer"
```

Diese Anleitung kann nach der Veröffentlichung gelöscht werden; sie ist nicht
Teil der Integration.
