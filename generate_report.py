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
HOT_TAKES_FILE = ROOT / "hot_takes.json"
FORECAST_FILE = ROOT / "forecast_data.json"
MARKET_INDICES_FILE = ROOT / "market_indices.json"
REPORTS_DIR.mkdir(exist_ok=True)

BERLIN = ZoneInfo("Europe/Berlin")

# Hero-Chips: User-spezifische ETFs auf Xetra (entsprechen Portfolio-Holdings).
MARKET_INDICES = [
    {"name": "Core S&P 500", "short": "S&P 500", "ticker": "SXR8.DE"},
    {"name": "MSCI World", "short": "MSCI World", "ticker": "EUNL.DE"},
    {"name": "MSCI World IT", "short": "World IT", "ticker": "XDWT.DE"},
    {"name": "MSCI EM ex China", "short": "EM ex China", "ticker": "EMXC.DE"},
    {"name": "Russell 2000 US Small Cap", "short": "Russell 2000", "ticker": "ZPRR.DE"},
]

# Mapping deutsche/Anzeige-Namen → yfinance-Ticker (Portfolio + Watchlist).
TICKER_MAP = {
    "Apple": "AAPL",
    "NVIDIA": "NVDA",
    "Alphabet": "GOOG",
    "Alphabet C": "GOOG",
    "Microsoft": "MSFT",
    "Intel": "INTC",
    "Amazon": "AMZN",
    "MasterCard": "MA",
    "Mastercard": "MA",
    "Berkshire Hathaway": "BRK-B",
    "Berkshire Hathaway B": "BRK-B",
    "BRK.B": "BRK-B",
    "LVMH": "MC.PA",
    "Hermès": "RMS.PA",
    "Hermes": "RMS.PA",
    "AMD": "AMD",
    "Broadcom": "AVGO",
    "Meta": "META",
    "Visa": "V",
    "JPMorgan": "JPM",
    "Coca-Cola": "KO",
    "Walmart": "WMT",
    "Eli Lilly": "LLY",
    "Moderna": "MRNA",
    "Caterpillar": "CAT",
    "Siemens": "SIE.DE",
    "Lockheed Martin": "LMT",
    "Rheinmetall": "RHM.DE",
    # Watchlist (rein beobachtend, keine Holdings)
    "Oracle": "ORCL",
    "Boeing": "BA",
    "Airbus": "AIR.PA",
    "MSCI World Health Care": "WHEA.DE",
    # ETFs (Holdings)
    "Core S&P 500": "CSPX.L",
    "Core MSCI World": "IWDA.L",
    "MSCI World Information Technology": "WITS.L",
    "MSCI Emerging Markets Ex China": "EMXC",
    "Russell 2000 U.S. Small Cap": "IWM",
}

# Reine Watchlist-Werte (keine Holdings). Erscheinen im
# Portfolio-&-Watchlist-Tab in einer separaten Sektion.
WATCHLIST_COMPANIES = [
    "Walmart",
    "Oracle",
    "MSCI World Health Care",
    "Boeing",
    "Airbus",
]

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
Watch: Lockheed Martin, Rheinmetall, Boeing, Airbus (keine eigenen Positionen – bei relevanten geopolitischen Entwicklungen oder Großaufträgen berichten)

### 🔭 Erweiterte Watchlist (rein beobachtend, keine Holdings)
Watch: Walmart, Oracle, MSCI World Health Care ETF (WHEA.DE), Boeing, Airbus.
Diese Werte erscheinen in der Watchlist-Sektion mit eigener 4-Wochen-Prognose und Potential-Rating. Berichte über sie in den Tagesnachrichten nur, wenn etwas wirklich Relevantes passiert ist (gleiche Schwelle wie Holdings).

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

## SPRACHE — ZWINGEND DEUTSCH

**ALLE Textfelder müssen auf Deutsch verfasst sein.** Auch wenn deine Quellen englisch sind (Reuters, Bloomberg, CNBC etc.), übersetze die Inhalte sinngemäß ins Deutsche.

**Verboten:**
- Direkte englische Zitate oder Phrasen im Berichtstext (z.B. "April CPI beat estimates", "rate hike odds", "earnings beat", "guidance lifted")
- Englische Fachwörter, wenn ein deutsches Äquivalent existiert (statt "rate cut" → "Zinssenkung"; statt "guidance" → "Ausblick"; statt "beat" → "übertroffen").
- Mischtexte mit englischen Satzfetzen.

**Erlaubt:** Eigennamen (Unternehmen, Indizes), gängige Tickersymbole, etablierte Finanz-Akronyme (CPI, FOMC, EPS, M&A) — diese sollten aber sparsam und mit deutscher Erläuterung im Kontext stehen.

Beispiel falsch: "April CPI beat estimates, sending odds of rate hike higher."
Beispiel richtig: "Die April-Inflationsdaten (CPI) lagen über den Erwartungen, was die Wahrscheinlichkeit einer Zinserhöhung erhöht."

## ZEITLICHER KONTEXT
Bericht wird um 19:00 MEZ/MESZ (= 13:00 ET) erstellt. Erfasst After-Hours-News vom Vortag sowie Pre-Market- und Intraday-Entwicklungen bis Mittag ET. Late-Session-Überraschungen sind noch nicht enthalten.

## HOT TAKES – VIELVERSPRECHENDE PROGNOSEN

Zusätzlich zu den Tagesnachrichten lieferst du eine Liste „Hot Takes": Unternehmen aus dem Portfolio oder dem Watch-Universum mit **besonders vielversprechender Aussicht**, fundiert auf **konkreten, seriösen Ereignissen** (anstehende Earnings, bestätigte Produkt-Launches, regulatorische Genehmigungen, M&A-Deals, Analyst-Days mit klarer Guidance).

**Strikte Regeln für Hot Takes:**
- Niemals geratene Spekulation. Jeder Hot Take MUSS an ein nachweisbares Ereignis gekoppelt sein.
- 0–5 Einträge pro Tag — nur wenn es wirklich etwas gibt. Lieber leer als schwach.
- Rating 1–5 nach Stärke der Prognose (5 = sehr hohe Konviktion, 1 = nur leichter Vorteil).
- Bevorzugt Unternehmen, die ins Portfolio passen (siehe Universum-Liste oben).
- Hot Takes werden rollierend persistiert. Ein Eintrag verfällt, wenn sein `event_date` vorbei ist.

## PROGNOSE – PORTFOLIO & WATCHLIST

Liefere einen kurzen Markt-/Portfolio-Ausblick und eine quantitative Erwartung für **zwei Gruppen**:

1. **Portfolio (`category: "portfolio"`):** 3–5 Kern-Holdings (z.B. Apple, NVIDIA, Microsoft, Amazon, Alphabet C).
2. **Watchlist (`category: "watchlist"`):** ALLE 5 Watchlist-Werte zwingend — Walmart, Oracle, MSCI World Health Care, Boeing, Airbus.

Für jeden Eintrag:
- `expected_change_30d_pct` (≈ 4 Wochen) PFLICHT
- `expected_change_90d_pct` (3 Monate) optional
- `uncertainty_pct` (halbe Bandbreite) PFLICHT
- `potential_rating` (1–5, PFLICHT): Wie attraktiv ist das Chance-Risiko-Profil auf 4-Wochen-Sicht?
  - 5 = sehr starkes Setup, klarer Katalysator, gutes Risk/Reward
  - 4 = überdurchschnittlich attraktiv
  - 3 = neutral / im Erwartungsbereich
  - 2 = eher abwartend, Gegenwind
  - 1 = strukturelle Probleme, kein Setup
- `thesis` (1–2 deutsche Sätze) PFLICHT
- `key_drivers` (Liste deutscher Stichworte) PFLICHT

Der Erwartungsbereich darf eine begründete Einschätzung sein (nicht reine Mathematik), MUSS aber an konkrete Ereignisse/Trends gekoppelt werden. Klar als „Erwartung", nicht als „Vorhersage" kennzeichnen.

## AUSGABE-SCHEMA

Gib AUSSCHLIESSLICH gültiges JSON aus – keine einleitenden Sätze, kein Markdown-Code-Fence. Genau dieses Schema:

```
{
  "macro": {
    "market_state": "2 Sätze: aktueller Stand der Märkte (Indizes, Tagesbewegung, Stimmung)",
    "macro_drivers": "2-3 Sätze: Zinsen, Inflation, Notenbanken, Geopolitik, Rohstoffe — was bewegt den Markt strukturell heute",
    "sentiment": "1 Satz: Investorenstimmung (Risk-on / Risk-off / abwartend) und ein bis drei Stichworte",
    "sp500": "z.B. 5.842 (+0,3 %)",
    "nasdaq": "z.B. 18.920 (-0,1 %)",
    "dax": "z.B. 19.350 (+0,4 %)"
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
  "hot_takes": [
    {
      "company": "NVIDIA",
      "rating": 5,
      "event_basis": "Q1 FY27 Earnings am 2026-05-22 — Konsens erwartet Beat dank Hyperscaler-Capex",
      "event_date": "2026-05-22",
      "time_horizon": "1-2 Wochen",
      "thesis": "2-3 Sätze: Warum die Prognose vielversprechend ist. Verweis auf konkrete Daten / Aussagen / Quellen.",
      "risks": "1 Satz: was diese Prognose entgleisen könnte"
    }
  ],
  "forecast": {
    "commentary": "3-5 deutsche Sätze: Wie sich Portfolio + Watchlist in den nächsten 4-8 Wochen voraussichtlich entwickeln. Welche Treiber? Welche Risiken?",
    "tickers": [
      {
        "company": "Apple",
        "category": "portfolio",
        "scenario": "neutral",
        "expected_change_30d_pct": 2.5,
        "expected_change_90d_pct": 5.0,
        "uncertainty_pct": 4.0,
        "potential_rating": 3,
        "key_drivers": ["WWDC im Juni", "China-Nachfrage", "iPhone-17-Zyklus"],
        "thesis": "1-2 deutsche Sätze begründende Einschätzung"
      },
      {
        "company": "Walmart",
        "category": "watchlist",
        "scenario": "bullish",
        "expected_change_30d_pct": 3.0,
        "uncertainty_pct": 3.5,
        "potential_rating": 4,
        "key_drivers": ["Konsumdaten stabil", "Earnings Mitte Mai"],
        "thesis": "1-2 deutsche Sätze begründende Einschätzung"
      }
    ]
  },
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
- `hot_takes` darf leer sein wenn heute nichts überzeugendes da ist. NIEMALS spekulative Picks füllen.
- `forecast.tickers`: 3–5 Portfolio-Holdings (`category: "portfolio"`) **PLUS** alle 5 Watchlist-Werte (`category: "watchlist"`) — also typischerweise 8–10 Einträge gesamt. Jeder Eintrag bekommt `category` und `potential_rating` (1–5). `scenario` ist eines von: "bullish", "neutral", "bearish".
- `expected_change_*_pct` und `uncertainty_pct`: Zahlen in Prozent (z.B. `2.5` für +2,5 %). `uncertainty_pct` ist die halbe Bandbreite um die Erwartung (Bandbreite = expected ± uncertainty).
- `price_change` in news weglassen wenn nicht relevant
- `outlook` = Ausblick nächste Tage / diese Woche (3-7 Punkte)
- `calendar_events` = wichtige Termine für die nächsten Wochen/Monate
- `category` ist eines von: "earnings", "fed", "economic", "product", "political", "other"
- `company`-Namen in hot_takes/forecast.tickers: nutze die Schreibweise aus dem Universum oben (z.B. "Apple", "NVIDIA", "Berkshire Hathaway B", "LVMH").
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


def _normalize_json_text(text: str) -> str:
    """Strippe Code-Fence/BOM und beschränke auf das äußerste {..}-Objekt."""
    text = text.lstrip("﻿").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        text = text[first:last + 1]
    return text


def _auto_repair_json(text: str) -> str:
    """Heuristische Reparaturen für häufige LLM-JSON-Fehler.

    Best-effort: bei nicht greifender Reparatur wird der Originaltext zurückgegeben.
    """
    repaired = text
    # Typografische Anführungszeichen → ASCII
    repaired = repaired.replace("“", '"').replace("”", '"')
    repaired = repaired.replace("‘", "'").replace("’", "'")
    # Trailing Commas vor } oder ]
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    # Single-Quote-Keys → Double Quotes (nur wenn unproblematisch)
    repaired = re.sub(r"(?P<pre>[{,]\s*)'([A-Za-z_][\w\- ]*)'(\s*:)", r'\g<pre>"\2"\3', repaired)
    return repaired


def extract_json(text: str) -> dict:
    """Parst JSON mit Auto-Repair-Fallback. Wirft `json.JSONDecodeError` wenn alles scheitert."""
    cleaned = _normalize_json_text(text)
    try:
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError as first_err:
        repaired = _auto_repair_json(cleaned)
        if repaired != cleaned:
            try:
                result = json.loads(repaired, strict=False)
                print(f"[parser] Auto-Repair erfolgreich (Original-Fehler: {first_err}).")
                return result
            except json.JSONDecodeError:
                pass
        raise first_err


def repair_json_with_claude(client, model_id: str, raw_text: str, original_error: str) -> dict:
    """Letzte Reparatur-Stufe: bittet Claude, das JSON zu reparieren.

    Schlanker Call ohne Web-Search, niedriges Token-Budget. Gibt das geparste Objekt zurück.
    """
    repair_system = (
        "Du erhältst kaputtes JSON, das ein anderes LLM erzeugt hat. "
        "Deine einzige Aufgabe: gib das valide JSON zurück. "
        "Behalte alle Werte inhaltlich bei, behebe nur Syntaxfehler "
        "(unescapte Anführungszeichen in Strings, fehlende Kommas, falsche Escapes, etc.). "
        "Antworte AUSSCHLIESSLICH mit dem reparierten JSON-Objekt — kein Markdown, kein Code-Fence, kein Kommentar."
    )
    user_msg = (
        f"Folgendes JSON ist beim Parsen fehlgeschlagen: {original_error}\n\n"
        "Hier der Rohtext (zwischen den Markern). Repariere ihn und gib NUR das valide JSON aus.\n\n"
        f"---BEGIN---\n{raw_text}\n---END---"
    )
    print(f"[parser] Versuche Claude-Retry für JSON-Reparatur ({len(raw_text)} chars)...")
    response = client.messages.create(
        model=model_id,
        max_tokens=12000,
        system=repair_system,
        messages=[{"role": "user", "content": user_msg}],
    )
    text_blocks = [b for b in response.content if getattr(b, "type", "") == "text"]
    if not text_blocks:
        raise RuntimeError("Repair-Call lieferte keinen Text-Block.")
    repaired_raw = text_blocks[-1].text
    return extract_json(repaired_raw)


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


def load_hot_takes() -> dict:
    if HOT_TAKES_FILE.exists():
        return json.loads(HOT_TAKES_FILE.read_text(encoding="utf-8"))
    return {"takes": [], "updated_at": None}


def save_hot_takes(data: dict) -> None:
    HOT_TAKES_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def build_hot_takes_context(hot_takes: dict, today: str) -> str:
    today_date = datetime.strptime(today, "%Y-%m-%d").date()
    active = []
    for t in hot_takes.get("takes", []):
        try:
            d = datetime.strptime(t.get("event_date", ""), "%Y-%m-%d").date()
            if d >= today_date:
                active.append(t)
        except (ValueError, KeyError):
            continue
    if not active:
        return "Aktuell keine offenen Hot Takes."
    lines = ["Aktuell offene Hot Takes (bitte aktualisieren oder bestätigen, nicht doppelt aufnehmen):"]
    for t in sorted(active, key=lambda e: e.get("event_date", ""))[:15]:
        lines.append(
            f"- {t.get('company','?')} (Rating {t.get('rating','?')}, Event {t.get('event_date','?')}): {t.get('event_basis','')}"
        )
    return "\n".join(lines)


def merge_hot_takes(old: dict, new_takes: list, today: str) -> dict:
    today_date = datetime.strptime(today, "%Y-%m-%d").date()
    merged: dict = {}

    for t in old.get("takes", []):
        try:
            d = datetime.strptime(t.get("event_date", ""), "%Y-%m-%d").date()
            if d >= today_date:
                key = (t.get("company", ""), t.get("event_date", ""))
                merged[key] = t
        except (ValueError, KeyError):
            continue

    now_iso = datetime.now(BERLIN).isoformat()
    for t in new_takes:
        try:
            d = datetime.strptime(t.get("event_date", ""), "%Y-%m-%d").date()
            if d < today_date:
                continue
            key = (t.get("company", ""), t.get("event_date", ""))
            existing = merged.get(key)
            t_clean = dict(t)
            t_clean["first_seen"] = existing.get("first_seen", today) if existing else today
            t_clean["last_updated"] = now_iso
            merged[key] = t_clean
        except (ValueError, KeyError):
            continue

    return {
        "takes": sorted(
            merged.values(),
            key=lambda e: (-int(e.get("rating", 0) or 0), e.get("event_date", "")),
        ),
        "updated_at": now_iso,
    }


def fetch_forecast_data(forecast: dict) -> dict:
    """Holt historische Kursdaten für alle Forecast-Ticker via yfinance.

    Best-effort: bei Fehlern wird der Ticker einfach ohne Historie ausgeliefert.
    """
    tickers = forecast.get("tickers", [])
    if not tickers:
        return {"updated_at": datetime.now(BERLIN).isoformat(), "tickers": []}

    try:
        import yfinance as yf
    except ImportError:
        print("yfinance nicht installiert — überspringe historische Daten.")
        return {
            "updated_at": datetime.now(BERLIN).isoformat(),
            "tickers": [{"company": t.get("company"), "symbol": None, "history": [], "forecast": _build_forecast_projection(t, None, None)} for t in tickers],
        }

    result = []
    for t in tickers:
        company = t.get("company", "")
        symbol = TICKER_MAP.get(company)
        history = []
        last_close = None
        last_date = None
        if symbol:
            try:
                hist = yf.Ticker(symbol).history(period="90d", auto_adjust=True)
                if not hist.empty:
                    for ts, close in zip(hist.index, hist["Close"]):
                        if close is None or (isinstance(close, float) and (close != close)):
                            continue
                        history.append({"date": ts.strftime("%Y-%m-%d"), "close": round(float(close), 2)})
                    if history:
                        last_close = history[-1]["close"]
                        last_date = history[-1]["date"]
                print(f"  yfinance {company} ({symbol}): {len(history)} Tage")
            except Exception as e:
                print(f"  yfinance Fehler für {company} ({symbol}): {e}")
        else:
            print(f"  Kein Ticker-Mapping für '{company}' — Forecast nur ohne Historie.")

        # Fallback-Kategorie: Claude vergibt "portfolio"/"watchlist", aber
        # falls vergessen, identifizieren wir Watchlist-Werte über die Liste.
        category = t.get("category")
        if category not in ("portfolio", "watchlist"):
            category = "watchlist" if company in WATCHLIST_COMPANIES else "portfolio"

        rating_raw = t.get("potential_rating")
        try:
            potential_rating = int(rating_raw) if rating_raw is not None else None
            if potential_rating is not None:
                potential_rating = max(1, min(5, potential_rating))
        except (TypeError, ValueError):
            potential_rating = None

        result.append({
            "company": company,
            "symbol": symbol,
            "category": category,
            "potential_rating": potential_rating,
            "history": history,
            "last_close": last_close,
            "last_date": last_date,
            "scenario": t.get("scenario"),
            "thesis": t.get("thesis"),
            "key_drivers": t.get("key_drivers", []),
            "forecast": _build_forecast_projection(t, last_close, last_date),
        })

    return {
        "updated_at": datetime.now(BERLIN).isoformat(),
        "commentary": forecast.get("commentary", ""),
        "tickers": result,
    }


def _build_forecast_projection(ticker: dict, last_close, last_date) -> dict:
    """Berechnet Erwartungspfad + Band aus Claude-Schätzungen."""
    exp_30 = _safe_float(ticker.get("expected_change_30d_pct"))
    exp_90 = _safe_float(ticker.get("expected_change_90d_pct"))
    unc = _safe_float(ticker.get("uncertainty_pct"))
    if exp_30 is None or unc is None:
        return None

    if last_close is None:
        return {
            "expected_change_30d_pct": exp_30,
            "expected_change_90d_pct": exp_90,
            "uncertainty_pct": unc,
            "path": [],
        }

    try:
        anchor = datetime.strptime(last_date, "%Y-%m-%d").date() if last_date else datetime.now(BERLIN).date()
    except ValueError:
        anchor = datetime.now(BERLIN).date()

    points = []
    horizon_days = 90 if exp_90 is not None else 30
    for d in (7, 14, 30, 60, 90):
        if d > horizon_days:
            continue
        if d <= 30 or exp_90 is None:
            expected_pct = exp_30 * (d / 30.0)
        else:
            expected_pct = exp_30 + (exp_90 - exp_30) * ((d - 30) / 60.0)
        band_pct = unc * (d / 30.0) ** 0.5  # leicht wachsendes Unsicherheitsband
        central = last_close * (1 + expected_pct / 100.0)
        lower = last_close * (1 + (expected_pct - band_pct) / 100.0)
        upper = last_close * (1 + (expected_pct + band_pct) / 100.0)
        points.append({
            "date": (anchor + timedelta(days=d)).strftime("%Y-%m-%d"),
            "central": round(central, 2),
            "lower": round(lower, 2),
            "upper": round(upper, 2),
        })
    return {
        "expected_change_30d_pct": exp_30,
        "expected_change_90d_pct": exp_90,
        "uncertainty_pct": unc,
        "path": points,
    }


def _safe_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_market_indices() -> dict:
    """Holt Tagesschluss + 30-Tage-Sparkline für die Hero-Chips via yfinance.

    Best-effort: einzelne Ticker-Fehler hinterlassen leere Felder, brechen den
    Lauf aber nicht ab — das Frontend zeigt dann '—' statt Wert.
    """
    base_payload = [
        {
            "name": idx["name"],
            "short": idx["short"],
            "ticker": idx["ticker"],
            "last_close": None,
            "prev_close": None,
            "change_pct": None,
            "currency": None,
            "last_date": None,
            "sparkline": [],
        }
        for idx in MARKET_INDICES
    ]

    try:
        import yfinance as yf
    except ImportError:
        print("yfinance nicht installiert — Indizes-Chips bleiben leer.")
        return {"updated_at": datetime.now(BERLIN).isoformat(), "indices": base_payload}

    for entry, idx in zip(base_payload, MARKET_INDICES):
        ticker = idx["ticker"]
        try:
            yt = yf.Ticker(ticker)
            hist = yt.history(period="30d", auto_adjust=True)
            if hist.empty:
                print(f"  yfinance leer für {idx['name']} ({ticker})")
                continue

            closes = [float(c) for c in hist["Close"].dropna()]
            dates = [d.strftime("%Y-%m-%d") for d in hist.index]
            if not closes:
                continue

            entry["last_close"] = round(closes[-1], 2)
            entry["last_date"] = dates[-1]
            entry["sparkline"] = [round(c, 2) for c in closes[-30:]]
            if len(closes) >= 2 and closes[-2]:
                entry["prev_close"] = round(closes[-2], 2)
                entry["change_pct"] = round((closes[-1] / closes[-2] - 1) * 100, 2)
            try:
                entry["currency"] = getattr(yt.fast_info, "currency", None)
            except Exception:
                pass

            print(
                f"  yfinance {idx['name']} ({ticker}): "
                f"last={entry['last_close']} {entry['currency'] or ''}, "
                f"Δ={entry['change_pct']}%, sparkline={len(entry['sparkline'])} Punkte"
            )
        except Exception as e:
            print(f"  yfinance Fehler für {idx['name']} ({ticker}): {e}")

    return {"updated_at": datetime.now(BERLIN).isoformat(), "indices": base_payload}


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

    hot_takes_state = load_hot_takes()
    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] Hot Takes geladen ({len(hot_takes_state.get('takes', []))} aktiv).")
    hot_takes_context = build_hot_takes_context(hot_takes_state, today)

    client = anthropic.Anthropic(timeout=600.0)
    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] Client initialisiert, starte API-Call mit Web-Search...")

    user_message = (
        f"Erstelle den Tagesbericht für heute, {today} (Datum entspricht Europe/Berlin).\n\n"
        f"{calendar_context}\n\n"
        f"{hot_takes_context}\n\n"
        "Recherchiere aktuelle Nachrichten zu den im Universum gelisteten Unternehmen und Sektoren "
        "(After-Hours von gestern + Pre-Market & Intraday bis ca. 13:00 ET heute). "
        "Halte dich strikt an die Reporting-Prinzipien (Qualität vor Quantität). "
        "Aktualisiere den Kalender mit neu entdeckten wichtigen Terminen. "
        "Aktualisiere oder ergänze Hot Takes (rollierend) — nur an konkrete Events gekoppelt, niemals geraten. "
        "Liefere `forecast.tickers` für 3–6 Kern-Portfolio-Positionen. "
        "Gib NUR das JSON aus, kein anderer Text."
    )

    model_id = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
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
        print(f"[parser] Erster Parse-Versuch fehlgeschlagen: {e}")
        debug_path = REPORTS_DIR / f"{today}.raw.txt"
        debug_path.write_text(raw_text, encoding="utf-8")
        print(f"[parser] Rohtext gesichert: {debug_path}")
        try:
            data = repair_json_with_claude(client, model_id, raw_text, str(e))
            print(f"[parser] Claude-Retry erfolgreich.")
        except Exception as e2:
            raise RuntimeError(
                f"JSON-Parsing fehlgeschlagen (auch nach Retry): {e2}. Rohtext: {debug_path}"
            ) from e2

    report_data = {
        "date": today,
        "generated_at": datetime.now(BERLIN).isoformat(),
        "macro": data.get("macro", {}),
        "sectors": data.get("sectors", []),
        "hot_takes": data.get("hot_takes", []),
        "forecast": data.get("forecast", {}),
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

    new_hot_takes = merge_hot_takes(hot_takes_state, data.get("hot_takes", []), today)
    save_hot_takes(new_hot_takes)
    print(f"Hot Takes aktualisiert: {len(new_hot_takes['takes'])} aktive Einträge.")

    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] Hole Kursdaten für Forecast via yfinance...")
    forecast_payload = fetch_forecast_data(data.get("forecast", {}))
    FORECAST_FILE.write_text(
        json.dumps(forecast_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Forecast-Daten gespeichert: {len(forecast_payload.get('tickers', []))} Ticker.")

    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] Hole Markt-Indizes für Hero-Chips...")
    indices_payload = fetch_market_indices()
    MARKET_INDICES_FILE.write_text(
        json.dumps(indices_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    filled = sum(1 for x in indices_payload.get("indices", []) if x.get("last_close") is not None)
    print(f"Markt-Indizes gespeichert: {filled}/{len(indices_payload.get('indices', []))} mit Daten.")

    update_index()
    print("Index aktualisiert.")


if __name__ == "__main__":
    try:
        generate_report()
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)
