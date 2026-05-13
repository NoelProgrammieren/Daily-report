"""Erzeugt den täglichen Börsen-Bericht und aktualisiert den Kalender.

Wird täglich Mo–Fr um 19:00 Europe/Berlin via GitHub Actions ausgeführt.
Verwendet Claude Opus 4.7 mit Web-Search für tagesaktuelle News.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

ROOT = Path(__file__).parent
REPORTS_DIR = ROOT / "reports"
CALENDAR_FILE = ROOT / "calendar.json"
REPORTS_DIR.mkdir(exist_ok=True)

BERLIN = ZoneInfo("Europe/Berlin")

PORTFOLIO_PROMPT = """# 📊 BRANCHEN-TRACKER – Daily News & Updates

Du bist der persönliche Finanz-Dashboard-Manager für tägliches Portfolio-Monitoring.

## PORTFOLIO (Stand: 11. Mai 2026)

**Einzelaktien:**
- Informationstechnologie: Apple (9,94 %), NVIDIA (5,09 %), Alphabet C (2,43 %), Microsoft (1,97 %), Intel ⚠️ (1,53 %), Amazon (1,33 %)
- Finanzdienstleistungen: MasterCard (2,04 %), Berkshire Hathaway B (0,67 %)
- Luxusgüter: LVMH (0,53 %), Hermès (0,39 %)

⚠️ Intel ist gesondert zu beobachten – strukturell volatile Position (Foundry-Strategie, Apple-Deal, KI-Shift).

**ETFs:**
- Core S&P 500 USD (Acc) — 23,84 %
- Core MSCI World USD (Acc) — 21,56 %
- MSCI World Information Technology — 17,91 %
- MSCI Emerging Markets Ex China — 7,46 %
- Russell 2000 U.S. Small Cap — 3,33 %

## UNIVERSUM – ZU BEOBACHTENDE UNTERNEHMEN

### 🖥️ Informationstechnologie
Eigene Positionen: Apple, NVIDIA, Alphabet (C), Microsoft, Intel ⚠️, Amazon
Watch: AMD (Konkurrent zu NVIDIA & Intel), Broadcom (Halbleiter-Bellwether), Meta

### 💳 Finanzdienstleistungen
Eigene Positionen: MasterCard, Berkshire Hathaway (B)
Watch: Visa (direkter MasterCard-Konkurrent), JPMorgan (Bankensektor-Bellwether)

### 👜 Luxusgüter
Eigene Positionen: LVMH, Hermès

### 🛒 Consumer Staples & Defensiv
Watch: Coca-Cola, Walmart (Konjunktur- und Konsumbarometer – keine eigenen Positionen)

### 🏥 Gesundheitswesen & Pharma
Watch: Eli Lilly (GLP-1, KI-Medizin), Moderna (mRNA-Pipeline)

### 🏗️ Infrastruktur & Industrie
Watch: Caterpillar (Infrastruktur-Bellwether), Siemens (europäische Perspektive)

### 🛡️ Rüstung & Luft-/Raumfahrt
Watch: Lockheed Martin, Rheinmetall (keine eigenen Positionen – bei relevanten geopolitischen Entwicklungen berichten)

## REPORTING-PRINZIP: QUALITÄT VOR QUANTITÄT

**Grundregel:** Berichte NUR über eine Aktie oder einen Sektor, wenn es heute etwas Berichtenswertes gibt. Gibt es nichts Relevantes, wird der Sektor vollständig übersprungen.

**Berichtenswert:**
- Earnings-Überraschungen (positiv oder negativ)
- Kursrelevante Nachrichten: Deals, M&A, Produktankündigungen, Partnerschaften
- Regulatorische Entscheidungen mit direktem Unternehmenseinfluss
- Management-Wechsel oder strategische Neuausrichtungen
- Makro-Ereignisse, die Sektoren spürbar beeinflussen

**Nicht berichten:**
- Routinemäßige Kursbewegungen ohne News-Hintergrund
- Analysten-Ratings ohne neue fundamentale Begründung
- Nachrichten ohne Relevanz für einen Langfristinvestor (5+ Jahre Horizont)

Ein guter Tagesbericht hat **3–6 News-Items gesamt**, nicht 20.

## PRIORITÄTS-MARKIERUNGEN
- "fire" 🔥 Sehr wichtig – direkte Auswirkung auf Positionen oder Gesamtmarkt
- "lightning" ⚡ Interessant – relevante Entwicklung, kein unmittelbarer Handlungsbedarf
- "pin" 📌 Beobachten – mittelfristig relevant, noch kein klares Signal

## RELEVANZ-RATING (1–5)
- 5: Earnings, CEO-Wechsel, M&A, regulatorische Entscheidungen mit direktem Kurseinfluss
- 4: Wichtige Produktankündigungen, Makro-Schocks (Zinsentscheide, Geopolitik)
- 3: Strategische Entwicklungen, Branchentrends mit mittelfristiger Kursrelevanz
- 2: Hintergrundrauschen, indirekt relevant
- 1: Beobachtungswürdig, kurzfristig kaum Kursrelevanz

## QUELLEN
Ausschließlich seriöse Quellen: Reuters, Bloomberg, CNBC, Financial Times, Wall Street Journal, SEC Filings, offizielle Unternehmens-Pressemitteilungen. Bei Unsicherheit: lieber weglassen statt spekulieren. Keine Kaufempfehlungen.

## ZEITLICHER KONTEXT
Bericht wird um 19:00 MEZ/MESZ (= 13:00 ET) erstellt. Erfasst After-Hours-News vom Vortag sowie Pre-Market- und Intraday-Entwicklungen bis Mittag ET. Late-Session-Überraschungen sind noch nicht enthalten.

## AUSGABE-SCHEMA

Gib AUSSCHLIESSLICH gültiges JSON aus – keine einleitenden Sätze, kein Markdown-Code-Fence. Genau dieses Schema:

```
{
  "macro": {
    "summary": "2-3 Sätze: S&P 500, Nasdaq + wichtigstes geopolitisches/makroökonomisches Hintergrundrauschen",
    "sp500": "z.B. 5.842 (+0,3 %)",
    "nasdaq": "z.B. 18.920 (-0,1 %)"
  },
  "sectors": [
    {
      "name": "Informationstechnologie",
      "emoji": "🖥️",
      "positions_mentioned": ["Apple", "NVIDIA"],
      "news": [
        {
          "priority": "fire",
          "title": "Kurzer prägnanter Titel",
          "rating": 5,
          "summary": "2-4 Sätze Zusammenfassung",
          "price_change": "+2,3 %",
          "investor_relevance": "1 Satz: warum für mich relevant"
        }
      ]
    }
  ],
  "outlook": [
    {
      "date": "2026-05-15",
      "event": "NVIDIA Q1 Earnings",
      "relevant_for": "NVIDIA",
      "rating": 5
    }
  ],
  "calendar_events": [
    {
      "date": "2026-05-28",
      "event": "FOMC Sitzung – Zinsentscheid",
      "relevant_for": "Gesamtmarkt, MasterCard, JPMorgan",
      "rating": 5,
      "category": "fed"
    }
  ]
}
```

**Wichtige Regeln:**
- Sektoren NUR aufnehmen wenn berichtenswert (keine leeren Einträge!)
- `price_change` weglassen wenn nicht relevant
- `outlook` = Ausblick nächste Tage / diese Woche (3-7 Punkte)
- `calendar_events` = wichtige Termine für die nächsten Wochen/Monate, die in den persistenten Kalender aufgenommen werden sollen
- `category` ist eines von: "earnings", "fed", "economic", "product", "political", "other"
- Daten im Format YYYY-MM-DD
- Antworte AUSSCHLIESSLICH mit dem JSON-Objekt
"""


def load_calendar() -> dict:
    if CALENDAR_FILE.exists():
        return json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
    return {"events": [], "updated_at": None}


def save_calendar(cal: dict) -> None:
    CALENDAR_FILE.write_text(
        json.dumps(cal, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def extract_json(text: str) -> dict:
    text = text.lstrip("﻿").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        text = text[first:last + 1]
    return json.loads(text, strict=False)


def build_calendar_context(calendar: dict, today: str) -> str:
    today_date = datetime.strptime(today, "%Y-%m-%d").date()
    future_events = []
    for ev in calendar.get("events", []):
        try:
            d = datetime.strptime(ev["date"], "%Y-%m-%d").date()
            if d >= today_date:
                future_events.append(ev)
        except (ValueError, KeyError):
            continue
    if not future_events:
        return "Kalender ist aktuell leer."
    lines = ["Aktuell im Kalender (zukünftige Ereignisse, bitte nicht doppelt aufnehmen):"]
    for ev in sorted(future_events, key=lambda e: e["date"])[:30]:
        lines.append(f"- {ev['date']}: {ev.get('event','')} (Rating {ev.get('rating','?')})")
    return "\n".join(lines)


def merge_calendar(old: dict, new_events: list, today: str) -> dict:
    today_date = datetime.strptime(today, "%Y-%m-%d").date()
    merged: dict = {}

    for ev in old.get("events", []):
        try:
            d = datetime.strptime(ev["date"], "%Y-%m-%d").date()
            if d >= today_date:
                merged[(ev["date"], ev.get("event", ""))] = ev
        except (ValueError, KeyError):
            continue

    for ev in new_events:
        try:
            d = datetime.strptime(ev.get("date", ""), "%Y-%m-%d").date()
            if d >= today_date:
                merged[(ev["date"], ev.get("event", ""))] = ev
        except (ValueError, KeyError):
            continue

    return {
        "events": sorted(merged.values(), key=lambda e: e["date"]),
        "updated_at": datetime.now(BERLIN).isoformat(),
    }


def update_index() -> None:
    reports = []
    for f in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        if f.name == "index.json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            reports.append({
                "date": data.get("date", f.stem),
                "filename": f.name,
                "generated_at": data.get("generated_at"),
            })
        except (json.JSONDecodeError, OSError):
            continue
    (REPORTS_DIR / "index.json").write_text(
        json.dumps({"reports": reports}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def generate_report() -> None:
    now_berlin = datetime.now(BERLIN)
    today = now_berlin.strftime("%Y-%m-%d")

    # Guard against running outside the intended 19:00 Berlin window.
    # GitHub Actions cron uses UTC; we schedule at both 17:00 and 18:00 UTC
    # to cover DST. Only run if Berlin local time is roughly 19:00.
    if os.getenv("FORCE_RUN") != "1" and not (18 <= now_berlin.hour <= 20):
        print(f"Berlin time {now_berlin.strftime('%H:%M')} — not the 19:00 window, skipping.")
        return

    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] Start: Datum={today}, FORCE_RUN={os.getenv('FORCE_RUN')}")
    calendar = load_calendar()
    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] Kalender geladen ({len(calendar.get('events', []))} Ereignisse).")
    calendar_context = build_calendar_context(calendar, today)

    client = anthropic.Anthropic(timeout=600.0)
    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] Client initialisiert, starte API-Call mit Web-Search...")

    user_message = (
        f"Erstelle den Tagesbericht für heute, {today} (Datum entspricht Europe/Berlin).\n\n"
        f"{calendar_context}\n\n"
        "Recherchiere aktuelle Nachrichten zu den im Universum gelisteten Unternehmen und Sektoren "
        "(After-Hours von gestern + Pre-Market & Intraday bis ca. 13:00 ET heute). "
        "Halte dich strikt an die Reporting-Prinzipien (Qualität vor Quantität). "
        "Aktualisiere den Kalender mit neu entdeckten wichtigen Terminen. "
        "Gib NUR das JSON aus, kein anderer Text."
    )

    model_id = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] Modell: {model_id}")

    search_count = 0
    with client.messages.stream(
        model=model_id,
        max_tokens=12000,
        system=PORTFOLIO_PROMPT,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }],
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for event in stream:
            etype = getattr(event, "type", "")
            if etype == "content_block_start":
                block = getattr(event, "content_block", None)
                btype = getattr(block, "type", "")
                if btype == "server_tool_use":
                    search_count += 1
                    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] Web-Suche #{search_count} gestartet...")
                elif btype == "text":
                    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] Claude beginnt mit Textausgabe...")
        response = stream.get_final_message()

    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] API-Call fertig ({search_count} Web-Suchen, "
          f"input={response.usage.input_tokens}, output={response.usage.output_tokens} Tokens).")

    text_blocks = [b for b in response.content if b.type == "text"]
    if not text_blocks:
        raise RuntimeError("Kein Text-Block in der Antwort.")

    raw_text = text_blocks[-1].text
    try:
        data = extract_json(raw_text)
    except json.JSONDecodeError as e:
        debug_path = REPORTS_DIR / f"{today}.raw.txt"
        debug_path.write_text(raw_text, encoding="utf-8")
        raise RuntimeError(f"JSON-Parsing fehlgeschlagen: {e}. Rohtext: {debug_path}") from e

    report_data = {
        "date": today,
        "generated_at": datetime.now(BERLIN).isoformat(),
        "macro": data.get("macro", {}),
        "sectors": data.get("sectors", []),
        "outlook": data.get("outlook", []),
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }
    report_path = REPORTS_DIR / f"{today}.json"
    report_path.write_text(
        json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Bericht gespeichert: {report_path}")

    new_calendar = merge_calendar(calendar, data.get("calendar_events", []), today)
    save_calendar(new_calendar)
    print(f"Kalender aktualisiert: {len(new_calendar['events'])} Ereignisse.")

    update_index()
    print("Index aktualisiert.")


if __name__ == "__main__":
    try:
        generate_report()
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)
