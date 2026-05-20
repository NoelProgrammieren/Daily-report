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
TODAY_OVERVIEW_FILE = ROOT / "today_overview.json"
TODAY_DASHBOARD_FILE = ROOT / "today_dashboard.json"
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

# Chart-Farben für overview_chart-Series (Frontend Marktübersicht-Linien).
ETF_COLORS = {
    "SXR8.DE": "#3b82f6",   # S&P 500 – blue
    "EUNL.DE": "#e9edf3",   # MSCI World – off-white
    "XDWT.DE": "#a78bfa",   # World IT – purple
    "EMXC.DE": "#22c55e",   # EM ex China – green
    "ZPRR.DE": "#f59e0b",   # Russell 2000 – orange
}

# 5 SPDR-Sektor-ETFs als Proxy für Sektor-Tagesperformance.
SECTOR_PROXIES = [
    ("Technologie",      "XLK"),
    ("Kommunikation",    "XLC"),
    ("Industrie",        "XLI"),
    ("Gesundheitswesen", "XLV"),
    ("Energie",          "XLE"),
]

# Universum für Top-Mover-Berechnung: Portfolio + Watchlist (yfinance-Ticker).
TOP_MOVERS_UNIVERSE = [
    ("Apple",      "AAPL"),
    ("NVIDIA",     "NVDA"),
    ("Alphabet",   "GOOG"),
    ("Amazon",     "AMZN"),
    ("Walmart",    "WMT"),
    ("Tesla",      "TSLA"),
    ("Boeing",     "BA"),
    ("Bitcoin",    "BTC-USD"),
    ("Ethereum",   "ETH-USD"),
    ("S&P 500",    "SXR8.DE"),
    ("MSCI World", "EUNL.DE"),
    ("World IT",   "XDWT.DE"),
    ("EM ex China","EMXC.DE"),
    ("Russell 2000","ZPRR.DE"),
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
    # ETFs (Holdings) — Xetra-Ticker konsistent mit MARKET_INDICES
    "Core S&P 500": "SXR8.DE",
    "Core MSCI World": "EUNL.DE",
    "MSCI World Information Technology": "XDWT.DE",
    "MSCI Emerging Markets Ex China": "EMXC.DE",
    "Russell 2000 U.S. Small Cap": "ZPRR.DE",
    # App-Frontend-Schreibweisen (PORTFOLIO_COMPANIES in app.js) — case-sensitive Map!
    "S&P 500": "SXR8.DE",
    "MSCI World": "EUNL.DE",
    "MSCI Emerging Markets ex China": "EMXC.DE",
    "MSCI World Information Technology ": "XDWT.DE",  # mit/ohne trailing space sicherstellen
    # Watchlist-Schreibweisen App.js
    "Tesla": "TSLA",
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
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

**Übersetzungspflicht für News-Zitate:** Auch wenn deine Web-Suche englische Schlagzeilen oder Auszüge liefert, gibst du im Bericht NIE den englischen Originaltext wieder. Du formulierst den Inhalt zwingend auf Deutsch um. Das gilt für ALLE Felder: `macro.*`, `sectors.*.news.*` (title, summary, investor_relevance), `hot_takes.event_basis`, `hot_takes.thesis`, `hot_takes.risks`, `forecast.commentary`, `forecast.tickers.*.thesis`, `forecast.tickers.*.key_drivers`, `forecast.tickers.*.pros`, `forecast.tickers.*.cons`, `outlook.*`, `calendar_events.*`. Kein Feld darf englischen Fließtext oder ganze englische Sätze enthalten.

Beispiel falsch: "April CPI beat estimates, sending odds of rate hike higher."
Beispiel richtig: "Die April-Inflationsdaten (CPI) lagen über den Erwartungen, was die Wahrscheinlichkeit einer Zinserhöhung erhöht."

Beispiel falsch (News-Quote): "Apple hit all-time intraday high of $290.33"
Beispiel richtig: "Apple erreichte ein Allzeit-Intraday-Hoch bei 290,33 USD."

Beispiel falsch (Hot-Take-These): "CEO Huang's participation in US delegation summit with China suggests potential pathway for advanced chip exports."
Beispiel richtig: "Die Teilnahme von CEO Huang an der US-Delegation beim China-Gipfel deutet auf einen möglichen Weg für Exporte fortgeschrittener Chips hin."

## SPRACHNIVEAU — LAIENVERSTÄNDLICH

**Zielgruppe der Berichte:** Eine erwachsene Person ohne Finanzhintergrund. Sie soll auf Anhieb verstehen, was passiert ist, warum es passiert ist und welche Konsequenzen das hat.

**Regeln:**
- **Fachbegriffe erklären** beim ersten Auftauchen pro Bericht in Klammern, danach normal verwenden. Beispiele:
  - „Earnings (Quartalszahlen)"
  - „Bond-Yields (Anleiherenditen, also die Zinsen auf Staatsanleihen)"
  - „Hyperscaler (große Cloud-Anbieter wie AWS, Azure oder Google Cloud)"
  - „Guidance (Prognose, die ein Unternehmen für die kommenden Monate gibt)"
  - „Forward-PE (Bewertungs-Kennzahl, die Aktienkurs zu erwartetem Gewinn ins Verhältnis setzt)"
  - „Free Cash Flow (das Geld, das nach allen Ausgaben übrig bleibt)"
  - „Hedge (Absicherung gegen Verluste)"
- **Kausalketten ausschreiben.** Statt „Powell hawkish → yields up" lieber: „Notenbankchef Powell deutete höhere Zinsen an. Das treibt die Anleiherenditen nach oben, was wiederum auf Aktien drückt."
- **Vergleiche und Größenordnungen liefern.** Statt „Q1 EPS $2.14" lieber: „Der Gewinn pro Aktie lag im ersten Quartal bei 2,14 Dollar — etwa 8 % mehr als im Vorjahr."
- **Konsequenz benennen.** Bei jeder News kurz sagen, was das für den Kurs / die Branche bedeutet, nicht nur die Tatsache.

**SUBSTANZ-GARANTIE — NICHT verhandelbar:**
- Konkrete Zahlen (Kurse, Prozente, Termine, Ratings, Volumina) bleiben präzise und werden NICHT weichgespült.
- Tickersymbole, ISINs, Earnings-Daten, Indexstände, Inflationsraten — alles bleibt exakt.
- Fachbegriffe dürfen weiter verwendet werden, sie werden nur ergänzt um eine Klammer-Erklärung — nicht ersetzt durch vage Umschreibungen.

**Faustregel:** Nach dem Lesen einer Sektor-News oder eines Hot Takes muss ein Laie a) verstehen WAS passiert ist, b) verstehen WARUM es relevant ist, c) eine grobe Vorstellung der Größenordnung haben.

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
- **Jeder Hot Take MUSS `expected_move_pct` und `price_target` enthalten.** Beide Bandbreiten sind plausibel zur These zu wählen:
  - `expected_move_pct`: {`low`, `high`, `direction`}. `direction` ist `"up"` bei bullischen, `"down"` bei bearishen Takes. Beispiel: +6 bis +12 % in 2 Wochen → `{"low": 6.0, "high": 12.0, "direction": "up"}`.
  - `price_target`: {`low`, `high`, `currency`}. Konkrete Preisspanne in der Heimatwährung. Beispiel: 310–325 USD → `{"low": 310.0, "high": 325.0, "currency": "USD"}`.
  - Konsistenz: aktueller Kurs + `expected_move_pct` muss zur `price_target`-Range passen.

## PROGNOSE – PORTFOLIO & WATCHLIST (ZWINGEND VOLLSTÄNDIG!)

Liefere für die **gesamte folgende Liste** (13 Einträge) eine Prognose. KEINE Position darf fehlen — auch ETFs und Kryptos bekommen einen Forecast-Eintrag, weil das Frontend für jeden Eintrag eine Karte rendert. Lieber konservative Erwartungswerte als ausgelassene Karten:

1. **Portfolio (`category: "portfolio"`, 8 Einträge):**
   - Apple, NVIDIA, Alphabet (C), Amazon
   - S&P 500 (ETF), MSCI World (ETF), MSCI Emerging Markets ex China (ETF), MSCI World Information Technology (ETF)
2. **Watchlist (`category: "watchlist"`, 5 Einträge):**
   - Walmart, Tesla, Bitcoin, Ethereum, Boeing

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
- `thesis` (GENAU EIN deutscher, laienverständlicher Satz — die Kernaussage) PFLICHT
- `pros` (Liste 2–4 kurzer deutscher Stichpunkte: Argumente FÜR die Prognose / Chancen) PFLICHT
- `cons` (Liste 2–4 kurzer deutscher Stichpunkte: Argumente DAGEGEN / Risiken) PFLICHT
- `key_drivers` (Liste 2–4 neutrale Treiber-Stichworte für Tag-Anzeige, z.B. „Earnings", „China-Nachfrage") PFLICHT

`pros` und `cons` sind Stichpunkte, KEINE Sätze. Jeder Stichpunkt max. 8 Wörter. Beispiel-Pro: „Starke Cloud-Nachfrage, Margen wachsen". Beispiel-Con: „China-Restriktionen drücken Absatz".

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
      "expected_move_pct": { "low": 6.0, "high": 12.0, "direction": "up" },
      "price_target": { "low": 310.0, "high": 325.0, "currency": "USD" },
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
        "thesis": "Stabile Geschäfte, aber kurzfristig fehlt der große Kurstreiber.",
        "pros": [
          "WWDC im Juni mit neuen KI-Features",
          "Service-Sparte wächst zweistellig",
          "Hohe Cash-Reserven für Rückkäufe"
        ],
        "cons": [
          "iPhone-Absatz in China rückläufig",
          "Bewertung bereits ambitioniert",
          "Wachstum unter Tech-Schnitt"
        ]
      },
      {
        "company": "Walmart",
        "category": "watchlist",
        "scenario": "bullish",
        "expected_change_30d_pct": 3.0,
        "uncertainty_pct": 3.5,
        "potential_rating": 4,
        "key_drivers": ["Konsumdaten stabil", "Earnings Mitte Mai"],
        "thesis": "Starker Konsumtrend trifft auf solide Quartalszahlen — kurzfristig attraktiv.",
        "pros": [
          "Konsumdaten in den USA bleiben robust",
          "Quartalszahlen am 15. Mai erwartet stark",
          "E-Commerce-Sparte wächst zweistellig"
        ],
        "cons": [
          "Margendruck durch Lohnerhöhungen",
          "Zollthema belastet Lieferkette"
        ]
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
- `sectors` MUSS **mindestens 3 Einträge** enthalten — auch wenn ein Sektor heute keine harten News hat. In dem Fall: 1-Satz-Wochen-/Trend-Einordnung statt News (z.B. „Diese Woche keine spezifischen Treiber — Sektor folgt dem Gesamtmarkt im Rahmen der Rotation aus Tech in Defensives"). KEIN leerer Sektor-Eintrag, jedes `sectors[]` MUSS mindestens 1 `news`-Item haben.
- `hot_takes` darf leer sein wenn heute nichts überzeugendes da ist. NIEMALS spekulative Picks füllen.
- `forecast.tickers`: ZWINGEND alle 13 Einträge (8 Portfolio + 5 Watchlist) aus der oben gelisteten Pflicht-Liste. Jeder Eintrag bekommt `category`, `potential_rating` (1–5), `thesis` (1 Satz!), `pros` (2–4 Stichpunkte), `cons` (2–4 Stichpunkte) und `key_drivers` (2–4 Tags). `scenario` ist eines von: "bullish", "neutral", "bearish". Für ETFs und Kryptos: Treiber sind makro/breit (z.B. „Fed-Pfad", „Halbleiter-Capex", „Halving-Zyklus") — auch wenn dünn, KEIN Eintrag darf ausgelassen werden.
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


_CITE_RX = re.compile(r"<cite\b[^>]*>(.*?)</cite>", re.DOTALL)


def _strip_cite_tags(text: str) -> str:
    """Entfernt <cite index="..."> Tags aus dem web_search-Tool, behält den Inhalt."""
    return _CITE_RX.sub(r"\1", text)


def _strip_cite_deep(obj):
    """Wendet _strip_cite_tags rekursiv auf alle Strings in einer JSON-Struktur an."""
    if isinstance(obj, str):
        return _strip_cite_tags(obj)
    if isinstance(obj, list):
        return [_strip_cite_deep(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_cite_deep(v) for k, v in obj.items()}
    return obj


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
        extras = []
        mv = t.get("expected_move_pct") or {}
        if isinstance(mv, dict) and ("low" in mv or "high" in mv):
            direction = mv.get("direction", "up")
            sign = "+" if direction == "up" else "-"
            extras.append(f"Move {sign}{mv.get('low','?')}–{sign}{mv.get('high','?')} %")
        pt = t.get("price_target") or {}
        if isinstance(pt, dict) and ("low" in pt or "high" in pt):
            extras.append(f"Ziel {pt.get('low','?')}–{pt.get('high','?')} {pt.get('currency','')}".strip())
        extra_str = f" [{' · '.join(extras)}]" if extras else ""
        lines.append(
            f"- {t.get('company','?')} (Rating {t.get('rating','?')}, Event {t.get('event_date','?')}){extra_str}: {t.get('event_basis','')}"
        )
    return "\n".join(lines)


def merge_hot_takes(old: dict, new_takes: list, today: str) -> dict:
    today_date = datetime.strptime(today, "%Y-%m-%d").date()
    merged: dict = {}
    archive = list(old.get("archive", []))

    for t in old.get("takes", []):
        try:
            d = datetime.strptime(t.get("event_date", ""), "%Y-%m-%d").date()
            if d >= today_date:
                key = (t.get("company", ""), t.get("event_date", ""))
                merged[key] = t
            else:
                # Abgelaufener Take wandert ins Archiv (mit performance falls schon ausgewertet)
                archive.append(t)
        except (ValueError, KeyError):
            continue

    now_iso = datetime.now(BERLIN).isoformat()
    new_r5_alerts: list = []
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
            # r5-Alert nur wenn HEUTE neu hinzugekommen (existing == None) und rating == 5
            if existing is None and int(t_clean.get("rating") or 0) == 5:
                new_r5_alerts.append(t_clean)
        except (ValueError, KeyError):
            continue

    # Dedupliziere Archiv (gleicher Key = company + event_date)
    seen = set()
    archive_dedup = []
    for a in archive:
        k = (a.get("company", ""), a.get("event_date", ""))
        if k in seen:
            continue
        seen.add(k)
        archive_dedup.append(a)

    return {
        "takes": sorted(
            merged.values(),
            key=lambda e: (-int(e.get("rating", 0) or 0), e.get("event_date", "")),
        ),
        "archive": sorted(archive_dedup, key=lambda e: e.get("event_date", ""), reverse=True),
        "updated_at": now_iso,
        "_new_r5_alerts": new_r5_alerts,
    }


def evaluate_hot_takes_performance(state: dict, today: str) -> dict:
    """Wertet abgelaufene Hot Takes mit yfinance-Daten aus. Mutiert `state` in-place.

    Status-Werte: pending (event noch nicht +14T), hit (Kurs in target_range +14T), miss (außerhalb).
    Wenn kein price_target gesetzt war: status="no_target".
    """
    try:
        import yfinance as yf
    except ImportError:
        return state

    today_date = datetime.strptime(today, "%Y-%m-%d").date()
    archive = state.get("archive", [])
    evaluated_hit = 0
    evaluated_miss = 0
    evaluated_skip = 0
    for t in archive:
        perf = t.get("performance") or {}
        if perf.get("status") in ("hit", "miss", "no_target", "no_data"):
            continue
        try:
            event_date = datetime.strptime(t.get("event_date", ""), "%Y-%m-%d").date()
        except (ValueError, KeyError):
            continue
        if (today_date - event_date).days < 14:
            t["performance"] = {"status": "pending", "evaluated_at": None}
            continue

        company = t.get("company", "")
        symbol = TICKER_MAP.get(company)
        if not symbol:
            t["performance"] = {"status": "no_data", "reason": "ticker_unknown"}
            continue

        try:
            from datetime import timedelta
            hist = yf.Ticker(symbol).history(
                start=(event_date - timedelta(days=2)).isoformat(),
                end=(event_date + timedelta(days=20)).isoformat(),
                auto_adjust=True,
            )
            if hist.empty:
                t["performance"] = {"status": "no_data", "reason": "no_history"}
                continue
            closes = [(d.date(), float(c)) for d, c in zip(hist.index, hist["Close"]) if c == c]
            event_close = next((c for d, c in closes if d >= event_date), None)
            target_date = event_date + timedelta(days=14)
            after_close = next((c for d, c in closes if d >= target_date), None) or (closes[-1][1] if closes else None)
            if event_close is None or after_close is None:
                t["performance"] = {"status": "no_data", "reason": "incomplete"}
                continue
            pct_change = round((after_close / event_close - 1) * 100, 2)
            pt = t.get("price_target") or {}
            lo = pt.get("low")
            hi = pt.get("high")
            if lo is not None and hi is not None:
                in_range = lo <= after_close <= hi
                status = "hit" if in_range else "miss"
            else:
                status = "no_target"
                in_range = None
            t["performance"] = {
                "status": status,
                "price_at_event": round(event_close, 2),
                "price_14d_after": round(after_close, 2),
                "pct_change_14d": pct_change,
                "in_target_range": in_range,
                "evaluated_at": today,
            }
            if status == "hit":
                evaluated_hit += 1
            elif status == "miss":
                evaluated_miss += 1
            else:
                evaluated_skip += 1
        except Exception as e:
            t["performance"] = {"status": "no_data", "reason": str(e)[:80]}
            evaluated_skip += 1

    total = evaluated_hit + evaluated_miss + evaluated_skip
    if total:
        print(f"  Performance-Eval: {evaluated_hit} hit, {evaluated_miss} miss, {evaluated_skip} skip (gesamt {total})")
    return state


def _fetch_eurusd_rate(yf_module) -> float | None:
    """1× pro Run: aktueller EURUSD-Wechselkurs (USD pro 1 EUR)."""
    try:
        hist = yf_module.Ticker("EURUSD=X").history(period="2d", auto_adjust=False)
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 4)
    except Exception as e:
        print(f"  EURUSD=X Fehler: {e}")
    return None


def _ticker_currency(symbol: str) -> str:
    """Heuristik: Currency aus Ticker-Endung. .DE/.PA/.MI/.AS/.L → EUR/GBp, sonst USD."""
    if not symbol:
        return "USD"
    s = symbol.upper()
    if s.endswith((".DE", ".PA", ".MI", ".AS", ".MC", ".BR", ".VI", ".HE")):
        return "EUR"
    if s.endswith(".L"):
        return "GBp"
    if s.endswith(".SW"):
        return "CHF"
    if s.endswith(".TO"):
        return "CAD"
    return "USD"


def _fetch_analyst_insider(yf_module, symbol: str) -> dict:
    """Bestmöglich: Analystenkonsens + Insider-Käufe. Defensiv, alle Felder optional."""
    out: dict = {}
    try:
        ticker_obj = yf_module.Ticker(symbol)
        try:
            recs = ticker_obj.recommendations_summary
            if recs is not None and not recs.empty:
                row = recs.iloc[0]
                buy = int((row.get("strongBuy") or 0) + (row.get("buy") or 0))
                hold = int(row.get("hold") or 0)
                sell = int((row.get("sell") or 0) + (row.get("strongSell") or 0))
                total = buy + hold + sell
                if total > 0:
                    out["analyst_consensus"] = {"buy": buy, "hold": hold, "sell": sell}
        except Exception:
            pass
        try:
            info = ticker_obj.info or {}
            target_mean = info.get("targetMeanPrice")
            if target_mean is not None:
                out.setdefault("analyst_consensus", {})["target_mean"] = round(float(target_mean), 2)
                out["analyst_consensus"]["currency"] = info.get("currency", "USD")
        except Exception:
            pass
        try:
            insider = ticker_obj.insider_purchases
            if insider is not None and not insider.empty:
                purchases_row = insider[insider.iloc[:, 0].astype(str).str.contains("Purchase", case=False, na=False)]
                if not purchases_row.empty:
                    shares = int(purchases_row.iloc[0].get("Shares") or 0)
                    if shares > 0:
                        out["insider_purchases_90d"] = shares
        except Exception:
            pass
    except Exception:
        pass
    return out


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

    eurusd = _fetch_eurusd_rate(yf)
    print(f"  EURUSD=X: {eurusd}" if eurusd else "  EURUSD=X: nicht verfügbar")

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

        # Pros/Cons defensiv parsen: nur nicht-leere Strings übernehmen,
        # max. 4 Stichpunkte pro Seite, je max. 120 Zeichen.
        def _clean_bullets(raw):
            if not isinstance(raw, list):
                return []
            out = []
            for item in raw[:4]:
                if not isinstance(item, str):
                    continue
                s = item.strip()
                if s:
                    out.append(s[:120])
            return out

        pros = _clean_bullets(t.get("pros"))
        cons = _clean_bullets(t.get("cons"))

        currency = _ticker_currency(symbol) if symbol else "USD"
        last_close_eur = None
        if last_close is not None and currency == "USD" and eurusd:
            last_close_eur = round(last_close / eurusd, 2)

        analyst_insider = _fetch_analyst_insider(yf, symbol) if symbol else {}

        entry = {
            "company": company,
            "symbol": symbol,
            "category": category,
            "potential_rating": potential_rating,
            "history": history,
            "last_close": last_close,
            "last_date": last_date,
            "currency": currency,
            "scenario": t.get("scenario"),
            "thesis": t.get("thesis"),
            "pros": pros,
            "cons": cons,
            "key_drivers": t.get("key_drivers", []),
            "forecast": _build_forecast_projection(t, last_close, last_date),
        }
        if last_close_eur is not None:
            entry["last_close_eur"] = last_close_eur
            entry["fx_rate_eurusd"] = eurusd
        if analyst_insider:
            entry.update(analyst_insider)
        result.append(entry)

    payload = {
        "updated_at": datetime.now(BERLIN).isoformat(),
        "commentary": forecast.get("commentary", ""),
        "tickers": result,
    }
    if eurusd:
        payload["fx_rate_eurusd"] = eurusd
    return payload


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
            "projection": {"dates": [], "expected_path": [], "upper_band": [], "lower_band": []},
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

    # Beide Strukturen zurückgeben:
    # - `path` = Liste-of-Objects (alte Welle-4-Form, evtl. von anderen Konsumenten genutzt)
    # - `projection.*` = parallele Arrays (Form, die das Frontend in renderForecastChart liest)
    projection_block = {
        "dates":         [p["date"]    for p in points],
        "expected_path": [p["central"] for p in points],
        "upper_band":    [p["upper"]   for p in points],
        "lower_band":    [p["lower"]   for p in points],
    }
    return {
        "expected_change_30d_pct": exp_30,
        "expected_change_90d_pct": exp_90,
        "uncertainty_pct": unc,
        "path": points,
        "projection": projection_block,
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

    risk_indicators = _fetch_risk_indicators(yf)
    fear_greed = _fetch_fear_greed()

    payload: dict = {"updated_at": datetime.now(BERLIN).isoformat(), "indices": base_payload}
    if risk_indicators:
        payload["risk_indicators"] = risk_indicators
    if fear_greed:
        payload["fear_greed"] = fear_greed
    return payload


def _fetch_risk_indicators(yf_module) -> dict:
    """VIX (Volatilität) und 10Y-2Y-Yield-Spread (Rezessions-Indikator).

    yfinance Treasury-Tickers liefern den Yield × 10 (z.B. 4.32% als 43.2).
    """
    out: dict = {}
    try:
        vix_hist = yf_module.Ticker("^VIX").history(period="30d", auto_adjust=False)
        if not vix_hist.empty:
            closes = [float(c) for c in vix_hist["Close"].dropna()]
            if closes:
                last = round(closes[-1], 2)
                change_pct = None
                if len(closes) >= 2 and closes[-2]:
                    change_pct = round((closes[-1] / closes[-2] - 1) * 100, 2)
                out["vix"] = {
                    "value": last,
                    "change_pct": change_pct,
                    "sparkline": [round(c, 2) for c in closes[-30:]],
                }
                print(f"  yfinance VIX: {last} (Δ {change_pct}%)")
    except Exception as e:
        print(f"  VIX Fehler: {e}")

    try:
        tnx = yf_module.Ticker("^TNX").history(period="5d", auto_adjust=False)
        irx = yf_module.Ticker("^IRX").history(period="5d", auto_adjust=False)
        if not tnx.empty and not irx.empty:
            y10 = float(tnx["Close"].dropna().iloc[-1])
            y2 = float(irx["Close"].dropna().iloc[-1])
            spread_bps = int(round((y10 - y2) * 10))
            change_bps = None
            if len(tnx) >= 2 and len(irx) >= 2:
                y10_prev = float(tnx["Close"].dropna().iloc[-2])
                y2_prev = float(irx["Close"].dropna().iloc[-2])
                change_bps = int(round(((y10 - y2) - (y10_prev - y2_prev)) * 10))
            interpretation = "invertiert" if spread_bps < 0 else "normal"
            out["yield_spread_10y_2y"] = {
                "value_bps": spread_bps,
                "change_bps": change_bps,
                "interpretation": interpretation,
                "y10_pct": round(y10 / 10, 3),
                "y2_pct": round(y2 / 10, 3),
            }
            print(f"  yfinance Yield-Spread 10Y-2Y: {spread_bps} bps ({interpretation})")
    except Exception as e:
        print(f"  Yield-Curve Fehler: {e}")

    return out


def _fetch_fear_greed() -> dict:
    """CNN Fear & Greed Index via öffentlicher dataviz-API (kein Auth)."""
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        fg = data.get("fear_and_greed", {})
        score = fg.get("score")
        rating = fg.get("rating")
        if score is None:
            return {}
        result = {
            "score": int(round(float(score))),
            "rating": rating,
            "previous_close": fg.get("previous_close"),
            "previous_1_week": fg.get("previous_1_week"),
            "previous_1_month": fg.get("previous_1_month"),
        }
        print(f"  CNN Fear & Greed: {result['score']} ({result['rating']})")
        return result
    except Exception as e:
        print(f"  Fear & Greed Fehler: {e}")
        return {}


# ============================================================
# Today-Dashboard / Today-Overview (täglich neu)
# ============================================================

TODAY_PROSE_PROMPT = """Du bist Finanzredakteur für einen deutschsprachigen Tages-Marktbericht.
Schreibe für einen interessierten Laien — konkret, Zahlen-getrieben, ohne Floskeln.

INPUT: Du erhältst aggregierte Marktdaten (Top-Gainer + Top-Loser des Tages, 5 Sektor-Veränderungen, VIX, Yield-Spread, Fear&Greed-Score) plus ein 1-Satz-Macro-Kontext.

OUTPUT: Strikt nur dieses JSON-Objekt, kein Vor- oder Nachtext, keine Code-Fences:

{
  "summary": "8-12 Sätze, ca. 800-1100 Zeichen. Beschreibe den heutigen Handelstag KONKRET und BEGRÜNDET: (1) was haben die wichtigsten Indizes gemacht — Tages-%-Δ der 5 Portfolio-ETFs. (2) WARUM — welche Makro-Faktoren (Inflationsdaten, Zinsentscheidungen, Geopolitik, Earnings-Erwartungen), welche Branchen-News, welche Einzelaktien-Bewegungen haben den Markt getrieben? Nenne MINDESTENS 2-3 konkrete Ursachen mit Zahlen oder Eigennamen. (3) Sektor-Rotation: welche Sektoren liefen vorne, welche hinten, was steckt dahinter? (4) Wo war die Konzentration des Ab-/Aufwärtsschwungs (z.B. Tech-Mega-Caps, Energie, Defensives)?",
  "next_day_outlook": "7-10 Sätze, ca. 600-900 Zeichen. Erkläre, was morgen kommt und WARUM es relevant ist: (1) anstehende Daten/Events (CPI, FOMC, Earnings-Releases, Notenbank-Sprecher, ZEW, ISM etc.). (2) welche Sektoren könnten profitieren oder verlieren je nach Ausgang — mit konkreter Begründung („wenn X, dann Y, weil Z"). (3) konkrete Aktien/ETFs, die im Fokus stehen. (4) wesentliche Risiken: Inflation, Geopolitik, Konzentrations-Effekte. Sei spezifisch, nicht generisch.",
  "report_market_state": "5-7 Sätze über Marktbreite (Adv/Decline-Verhältnis), Tech-Beta zum Index, Sektor-Rotation, USD/EM-Effekt, Volumen-Indikatoren. Konkrete Zahlen wenn vorhanden, sonst plausible qualitative Bewertung.",
  "report_sentiment": "5-7 Sätze über VIX (mit Wert + Δ), Put/Call-Stimmung qualitativ ableiten, MOVE-Index falls ableitbar, Fear&Greed-Wert + Einordnung, Positionierung der Investoren vor anstehenden Events.",
  "sentiment_label": "1-3 Wörter passend zum F&G-Score (z.B. 'Neutral – Vorsichtig', 'Extreme Gier', 'Risiko-Aversion')."
}

REGELN:
- KEINE erfundenen Zahlen. Verwende ausschließlich die Werte aus dem Input. Wenn ein Wert fehlt, formuliere qualitativ („leicht erhöht", „nahe Normalniveau") statt zu erfinden.
- Begründe IMMER, warum etwas passiert ist — kein „der Markt fiel" ohne Ursache.
- Fachbegriffe (VIX, MOVE, Adv/Decline, Tech-Beta, KGV) kommen unkommentiert vor — das Frontend ergänzt Tooltips.
- Verwende deutsche Anführungszeichen „...".
- Keine Sterne, kein Markdown — Plain Text in den JSON-Strings.
- Beachte die ungefähren Längen-Vorgaben: lieber ausführlich-erklärend als knapp.
"""


def _fetch_overview_chart_series(yf_module) -> dict:
    """Lädt Zeitreihen für die 5 ETFs in 6 Zeiträumen, normalisiert auf %-Δ vom Baseline.

    Output-Struktur passt zu today_dashboard.json[overview_chart][ranges].
    Bei Fehler → leere Series-Listen (Frontend zeigt dann nichts an, statt zu crashen).
    """
    range_configs = [
        ("1D",  {"period": "1d",  "interval": "30m"}),
        ("5D",  {"period": "5d",  "interval": "1d"}),
        ("1M",  {"period": "1mo", "interval": "1d"}),
        ("6M",  {"period": "6mo", "interval": "1wk"}),
        ("YTD", {"period": "ytd", "interval": "1d"}),
        ("1Y",  {"period": "1y",  "interval": "1mo"}),
    ]
    ranges: dict = {}

    for range_key, params in range_configs:
        labels: list = []
        series: dict = {}

        for idx in MARKET_INDICES:
            ticker = idx["ticker"]
            key = ticker.split(".")[0].lower()
            series[key] = []
            try:
                hist = yf_module.Ticker(ticker).history(
                    period=params["period"], interval=params["interval"], auto_adjust=True
                )
                if hist.empty:
                    continue
                closes = [float(c) for c in hist["Close"].dropna()]
                if not closes or closes[0] == 0:
                    continue
                base = closes[0]
                pct_series = [round((c / base - 1) * 100, 3) for c in closes]
                series[key] = pct_series

                # Labels einmal pro Range setzen (vom ersten verfügbaren Ticker).
                if not labels:
                    idx_obj = hist.index
                    if range_key == "1D":
                        labels = [t.strftime("%H:%M") for t in idx_obj]
                    elif range_key == "5D":
                        wd = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
                        labels = [wd[t.weekday()] for t in idx_obj]
                    elif range_key == "1M":
                        labels = [f"KW{t.isocalendar().week}" for t in idx_obj]
                    elif range_key == "6M":
                        months_de = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                                     "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
                        labels = [months_de[t.month - 1] for t in idx_obj]
                    elif range_key == "YTD":
                        months_de = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                                     "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
                        # Nur jeden ~Monatswechsel labeln; Rest leer.
                        labels = []
                        last_month = None
                        for t in idx_obj:
                            if t.month != last_month:
                                labels.append(months_de[t.month - 1])
                                last_month = t.month
                            else:
                                labels.append("")
                    elif range_key == "1Y":
                        labels = [f"Q{(t.month-1)//3 + 1} {t.strftime('%y')}" for t in idx_obj]
            except Exception as e:
                print(f"  overview_chart {range_key}/{ticker} Fehler: {e}")
                continue

        ranges[range_key] = {"labels": labels, "series": series}
        print(f"  overview_chart {range_key}: {len(labels)} Labels, "
              f"{sum(1 for v in series.values() if v)} Series mit Daten")

    return ranges


def _fetch_sectors_changes(yf_module) -> list:
    """Lädt Tages-%-Δ für 5 SPDR-Sektor-ETFs als Sektor-Proxies."""
    result = []
    for sector_name, ticker in SECTOR_PROXIES:
        change_pct = None
        try:
            hist = yf_module.Ticker(ticker).history(period="5d", auto_adjust=True)
            closes = [float(c) for c in hist["Close"].dropna()] if not hist.empty else []
            if len(closes) >= 2 and closes[-2]:
                change_pct = round((closes[-1] / closes[-2] - 1) * 100, 2)
        except Exception as e:
            print(f"  Sektor {sector_name} ({ticker}) Fehler: {e}")
        result.append({"name": sector_name, "change_pct": change_pct})
    print(f"  sectors: {sum(1 for s in result if s['change_pct'] is not None)}/{len(result)} mit Daten")
    return result


def _fetch_top_movers(yf_module) -> dict:
    """Berechnet Top-5-Gainer + Top-5-Loser aus Portfolio + Watchlist."""
    movers = []
    for display_name, ticker in TOP_MOVERS_UNIVERSE:
        try:
            hist = yf_module.Ticker(ticker).history(period="5d", auto_adjust=True)
            closes = [float(c) for c in hist["Close"].dropna()] if not hist.empty else []
            if len(closes) >= 2 and closes[-2]:
                change_pct = round((closes[-1] / closes[-2] - 1) * 100, 2)
                movers.append({
                    "name": display_name,
                    "value": round(closes[-1], 2),
                    "change_pct": change_pct,
                })
        except Exception as e:
            print(f"  top_movers {display_name} ({ticker}) Fehler: {e}")

    movers_sorted = sorted(movers, key=lambda m: m["change_pct"], reverse=True)
    gainers = movers_sorted[:5]
    losers = list(reversed(movers_sorted[-5:]))
    print(f"  top_movers: {len(gainers)} Gainer, {len(losers)} Loser (Universum: {len(movers)})")
    return {"gainers": gainers, "losers": losers}


def _generate_today_prose(client, model_id: str, *,
                          macro_summary: str, indices: list, sectors: list,
                          top_movers: dict, fear_greed: dict, risk_indicators: dict) -> dict:
    """Eine zusätzliche Claude-Haiku-Call (kein web_search) für die Prose-Felder.

    Bei Parse-Fehler → repair_json_with_claude-Fallback. Bei totalem Fehler → leeres Dict.
    """
    # Kompakter Input-Context als Plain-Text-Block.
    vix = (risk_indicators or {}).get("vix", {})
    yld = (risk_indicators or {}).get("yield_spread_10y_2y", {})

    def _fmt_pct(v):
        return f"{v:+.2f}%" if isinstance(v, (int, float)) else "—"

    indices_lines = [
        f"  • {idx['short']}: {idx.get('last_close','—')} ({_fmt_pct(idx.get('change_pct'))})"
        for idx in indices
    ]
    sector_lines = [
        f"  • {s['name']}: {_fmt_pct(s.get('change_pct'))}" for s in sectors
    ]
    gainer_lines = [
        f"  • {m['name']}: {m['value']} ({_fmt_pct(m['change_pct'])})"
        for m in (top_movers.get("gainers") or [])
    ]
    loser_lines = [
        f"  • {m['name']}: {m['value']} ({_fmt_pct(m['change_pct'])})"
        for m in (top_movers.get("losers") or [])
    ]

    user_msg = "\n".join([
        f"DATUM: {datetime.now(BERLIN).strftime('%A, %d. %B %Y')}",
        "",
        "MARKTBREITE — Tages-%-Δ der 5 Portfolio-ETFs:",
        *indices_lines,
        "",
        "SEKTOREN (SPDR-Proxies):",
        *sector_lines,
        "",
        "TOP-GAINER (Portfolio + Watchlist):",
        *gainer_lines,
        "",
        "TOP-LOSER:",
        *loser_lines,
        "",
        f"VIX: {vix.get('value','—')} ({_fmt_pct(vix.get('change_pct'))})",
        f"Yield-Spread 10Y-2Y: {yld.get('value_bps','—')} bps ({yld.get('interpretation','—')})",
        f"Fear & Greed: {fear_greed.get('score','—')} ({fear_greed.get('rating','—')})",
        "",
        f"MACRO-KONTEXT (aus Tagesbericht): {macro_summary or '—'}",
        "",
        "Erzeuge das JSON exakt nach Schema.",
    ])

    try:
        response = client.messages.create(
            model=model_id,
            max_tokens=2500,
            system=TODAY_PROSE_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text_blocks = [b for b in response.content if b.type == "text"]
        if not text_blocks:
            raise RuntimeError("Kein Text-Block in der Prose-Antwort.")
        raw_text = text_blocks[-1].text
        try:
            return extract_json(raw_text)
        except json.JSONDecodeError as e:
            print(f"[today-prose] Parse-Fehler ({e}), versuche Claude-Repair…")
            try:
                return repair_json_with_claude(client, model_id, raw_text, str(e))
            except Exception as e2:
                print(f"[today-prose] Repair fehlgeschlagen: {e2}")
                return {}
    except Exception as e:
        print(f"[today-prose] API-Call fehlgeschlagen: {e}")
        return {}


def write_today_dashboard_and_overview(client, model_id: str, *,
                                       data: dict, indices_payload: dict) -> None:
    """Schreibt today_overview.json + today_dashboard.json (täglich frisch).

    Best-effort: einzelne Sub-Schritt-Fehler hinterlassen Defaults statt zu crashen.
    Vorhandene Dateien bleiben unangetastet, wenn der gesamte Block fehlschlägt.
    """
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance nicht installiert — today_dashboard/overview übersprungen.")
        return

    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] Baue today_dashboard.json + today_overview.json…")

    overview_ranges = _fetch_overview_chart_series(yf)
    sectors = _fetch_sectors_changes(yf)
    top_movers = _fetch_top_movers(yf)

    fear_greed = indices_payload.get("fear_greed") or {}
    risk_indicators = indices_payload.get("risk_indicators") or {}
    macro_summary = (data.get("macro", {}) or {}).get("summary", "")

    prose = _generate_today_prose(
        client, model_id,
        macro_summary=macro_summary,
        indices=indices_payload.get("indices", []),
        sectors=sectors,
        top_movers=top_movers,
        fear_greed=fear_greed,
        risk_indicators=risk_indicators,
    )

    today_overview = {
        "generated_at": datetime.now(BERLIN).isoformat(),
        "summary": prose.get("summary", ""),
        "next_day_outlook": prose.get("next_day_outlook", ""),
    }
    TODAY_OVERVIEW_FILE.write_text(
        json.dumps(today_overview, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  today_overview.json: summary={len(today_overview['summary'])} Zeichen, "
          f"outlook={len(today_overview['next_day_outlook'])} Zeichen")

    overview_indices_block = []
    for idx in indices_payload.get("indices", []):
        ticker = idx.get("ticker", "")
        overview_indices_block.append({
            "name": idx.get("short") or idx.get("name") or ticker,
            "key": ticker.split(".")[0].lower(),
            "value": idx.get("last_close"),
            "change_pct": idx.get("change_pct"),
            "color": ETF_COLORS.get(ticker, "#94a3b8"),
        })

    today_dashboard = {
        "report_market_state": prose.get("report_market_state", ""),
        "report_sentiment": prose.get("report_sentiment", ""),
        "overview_chart": {"ranges": overview_ranges},
        "overview_indices": overview_indices_block,
        "sentiment": {
            "score": fear_greed.get("score"),
            "label": prose.get("sentiment_label") or (fear_greed.get("rating") or "—"),
        },
        "sectors": sectors,
        "top_movers": top_movers,
    }
    TODAY_DASHBOARD_FILE.write_text(
        json.dumps(today_dashboard, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  today_dashboard.json: {len(overview_indices_block)} Indizes, "
          f"{len(sectors)} Sektoren, "
          f"{len(top_movers.get('gainers', []))}/{len(top_movers.get('losers', []))} Gainer/Loser")


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
    print(f"[{datetime.now(BERLIN).strftime('%H:%M:%S')}] Hot Takes geladen ({len(hot_takes_state.get('takes', []))} aktiv, {len(hot_takes_state.get('archive', []))} archiviert).")
    hot_takes_state = evaluate_hot_takes_performance(hot_takes_state, today)
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
        "Liefere `forecast.tickers` ZWINGEND für ALLE 13 Pflicht-Einträge (8 Portfolio inkl. ETFs + 5 Watchlist inkl. Kryptos) — KEINE Karte darf leer bleiben. "
        "Liefere `sectors` ZWINGEND mit mindestens 3 Branchen. "
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

    data = _strip_cite_deep(data)

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
    r5_alerts = new_hot_takes.pop("_new_r5_alerts", [])
    save_hot_takes(new_hot_takes)
    print(f"Hot Takes aktualisiert: {len(new_hot_takes['takes'])} aktive Einträge, {len(new_hot_takes.get('archive', []))} archiviert.")

    r5_alert_file = ROOT / "r5_alert.json"
    if r5_alerts:
        r5_alert_file.write_text(
            json.dumps({"alerts": r5_alerts, "generated_at": datetime.now(BERLIN).isoformat()}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[ALERT] {len(r5_alerts)} neue r5-Hot-Takes — r5_alert.json geschrieben.")
    else:
        # Wenn nichts da, sicherheitshalber alte Datei löschen damit Workflow nicht triggert
        if r5_alert_file.exists():
            r5_alert_file.unlink()

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

    # Today-Dashboard + Today-Overview (täglich frisch).
    # Hard-isoliert via try/except: ein Fehler hier darf den Rest des Runs nicht abbrechen,
    # alte JSONs bleiben in dem Fall stehen.
    try:
        write_today_dashboard_and_overview(
            client, model_id,
            data=data, indices_payload=indices_payload,
        )
    except Exception as e:
        print(f"[today-dashboard] Block fehlgeschlagen: {e} — vorhandene JSONs bleiben unverändert.")

    update_index()
    print("Index aktualisiert.")


if __name__ == "__main__":
    try:
        generate_report()
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)
