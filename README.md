# 📊 Börsen-Tracker

Automatischer Tagesbericht zur Börse, jeden Werktag um 19:00 Europe/Berlin.
Hosted auf GitHub Pages, generiert via GitHub Actions + Claude Opus 4.7 (mit Web-Search).

## Wie es funktioniert

```
                 GitHub Actions (Cron, Mo–Fr 19:00 Berlin)
                                │
                                ▼
                   generate_report.py (Claude API + Web-Search)
                                │
                                ▼
            reports/YYYY-MM-DD.json + calendar.json + reports/index.json
                                │
                                ▼  git push
                                ▼
                   GitHub Pages serviert statische Website
```

- `generate_report.py` ruft Claude Opus 4.7 mit Web-Search, generiert den Bericht als JSON, aktualisiert `calendar.json`, schreibt `reports/YYYY-MM-DD.json`.
- Der Workflow committed die neuen Dateien und deployed automatisch nach GitHub Pages.
- Das Frontend (statisches HTML/JS) lädt die JSON-Dateien direkt aus dem Repo.

## Einmalige Einrichtung

### 1. Anthropic API-Key (neu — der alte wurde geleakt!)

1. Den geleakten Key (`sk-ant-api03-yAxAib0Zqa5...`) auf https://console.anthropic.com/settings/keys **sofort revoken**.
2. Neuen Key erstellen.
3. **Nicht** in Code einfügen — er kommt gleich als GitHub Secret.

### 2. GitHub-Repo anlegen

```bash
cd "/Users/juliusfischer/Claude Code Projekte/Daily Stock Report"
git init
git add .
git commit -m "Initial commit: Börsen-Tracker"
```

Dann auf https://github.com/new ein neues (privates) Repo `daily-stock-report` anlegen, **ohne** README/.gitignore/License (sonst Merge-Konflikt). Dann lokal:

```bash
git remote add origin git@github.com:<dein-username>/daily-stock-report.git
git branch -M main
git push -u origin main
```

### 3. API-Key als GitHub Secret hinterlegen

Im neuen Repo auf GitHub:

**Settings → Secrets and variables → Actions → New repository secret**

- Name: `ANTHROPIC_API_KEY`
- Value: (dein neuer Anthropic-Key)

### 4. GitHub Pages aktivieren

**Settings → Pages**

- Source: **GitHub Actions** auswählen (nicht "Deploy from branch")

Der erste Deploy passiert automatisch beim ersten Run des Workflows.

### 5. Erste Test-Generierung manuell triggern

**Actions → Daily Stock Report → Run workflow → force = true → Run workflow**

Das erzwingt einen Lauf außerhalb des 19-Uhr-Fensters. Nach ~1 Minute ist der Bericht erstellt, commited und gepushed; nach weiteren ~1 Minute ist die Pages-Seite live unter:

```
https://<dein-username>.github.io/daily-stock-report/
```

Diese URL kannst du dir als Lesezeichen speichern, mobil aufrufen, etc.

## Täglicher Ablauf

- **Cron**: Mo–Fr 17:00 UTC **und** 18:00 UTC (deckt MEZ/MESZ ab).
- Das Skript prüft die lokale Berlin-Zeit (`Europe/Berlin` Zeitzone) und überspringt den Lauf, wenn nicht ~19:00.
- Bei Bedarf jederzeit manuell triggern via **Actions → Run workflow** (Option `force=true`).

## Lokal testen

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sk-ant-..."   # dein NEUER Key
FORCE_RUN=1 python generate_report.py
```

Danach öffnet ein lokaler Webserver die Seite:

```bash
python -m http.server 8000
# → http://localhost:8000
```

## Kosten

Pro Lauf ein API-Call mit Claude Opus 4.7 + bis zu 10 Web-Searches:
- ~5.000–15.000 Input-Tokens (Prompt + Suchergebnisse)
- ~2.000–4.000 Output-Tokens (JSON-Report)
- Web-Search: $10 / 1.000 Suchen → ca. $0,05–0,10 pro Lauf
- Tokens: ca. $0,10–0,25 pro Lauf

→ **Mo–Fr ≈ $1–2 pro Woche, $5–8 pro Monat.**

## Dateistruktur

```
.
├── .github/workflows/daily-report.yml   # Cron + Deploy
├── generate_report.py                   # Bericht-Generator
├── requirements.txt
├── calendar.json                        # Persistenter Kalender
├── reports/
│   ├── index.json                       # Auto-generiert: Liste aller Berichte
│   └── YYYY-MM-DD.json                  # Tagesberichte
├── index.html                           # Frontend
├── styles.css
├── app.js
└── README.md
```

## Anpassungen

- **Portfolio ändern**: Im `PORTFOLIO_PROMPT` in `generate_report.py` anpassen, committen, pushen.
- **Andere Uhrzeit**: Cron in `.github/workflows/daily-report.yml` anpassen + den Stunden-Guard in `generate_report.py` (Zeile mit `18 <= now_berlin.hour <= 20`).
- **Mehr/weniger Berichte im Archiv**: In `app.js`, Variable `isOpen = i < 3` ändern.
