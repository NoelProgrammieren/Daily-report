// ============================================================
// DAILY STOCK REPORT — Frontend (Redesign 2.0, Mai 2026)
// ============================================================

const MONTH_DE = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"];
const MONTH_DE_FULL = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"];
const WEEKDAY_DE = ["Sonntag","Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag"];
const WEEKDAY_SHORT = ["So","Mo","Di","Mi","Do","Fr","Sa"];

const SCENARIO_LABEL = { bullish: "Bullisch", bearish: "Bärisch", neutral: "Neutral" };

// Portfolio-Universum (8 Hauptforecasts)
const PORTFOLIO_COMPANIES = [
  "Apple", "NVIDIA", "Alphabet", "Amazon",
  "S&P 500", "MSCI World", "MSCI Emerging Markets ex China", "MSCI World Information Technology",
];

// Watchlist-Universum (5 Werte)
const WATCHLIST_COMPANIES = ["Walmart", "Tesla", "Bitcoin", "Ethereum", "Boeing"];

// ============================================================
// HELPERS
// ============================================================

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDateLong(isoDate) {
  if (!isoDate) return "";
  const d = new Date(isoDate + "T00:00:00");
  if (isNaN(d.getTime())) return isoDate;
  return `${WEEKDAY_DE[d.getDay()]}, ${d.getDate()}. ${MONTH_DE_FULL[d.getMonth()]} ${d.getFullYear()}`;
}

async function fetchJSON(path) {
  const r = await fetch(path + "?t=" + Date.now());
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

// ============================================================
// GLOSSAR — Tooltips für Fachbegriffe
// ============================================================

let GLOSSARY = { terms: [], _sortedMatches: [] };

async function loadGlossary() {
  try {
    const data = await fetchJSON("glossary.json");
    const terms = data.terms || [];
    // Sortiere ALLE match-strings nach Länge DESC (z.B. "MOVE-Index" vor "MOVE")
    const allMatches = [];
    terms.forEach((entry, idx) => {
      (entry.match || []).forEach((m) => {
        allMatches.push({ phrase: m, entryIdx: idx });
      });
    });
    allMatches.sort((a, b) => b.phrase.length - a.phrase.length);
    GLOSSARY = { terms, _sortedMatches: allMatches };
  } catch (e) {
    console.warn("Glossar konnte nicht geladen werden:", e);
  }
}

// HTML-escapen (für rohe Werte)
function escapeHtmlBasic(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Spezielle Regex-Escape-Funktion
function regexEscape(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// linkifyTerms: ersetzt Glossar-Wörter durch Tooltip-Spans.
// Strategie: Token-basiert, damit Match nicht innerhalb eines bereits eingefügten Span landet.
function linkifyTerms(text) {
  if (!text) return "";
  const safeText = escapeHtmlBasic(text);
  if (!GLOSSARY._sortedMatches || GLOSSARY._sortedMatches.length === 0) return safeText;

  // Wir nutzen einen Marker-Ansatz: Treffer werden durch Platzhalter ersetzt, am Ende durch echte Spans ausgetauscht.
  // So vermeiden wir Mehrfach-Matches innerhalb bereits markierter Bereiche.
  let working = safeText;
  const placeholders = []; // {placeholder, replacement}
  const used = new Set(); // entryIdx, jeweils nur einmal pro Text

  for (const { phrase, entryIdx } of GLOSSARY._sortedMatches) {
    if (used.has(entryIdx)) continue;
    const entry = GLOSSARY.terms[entryIdx];
    if (!entry) continue;
    const escapedPhrase = regexEscape(phrase);
    // Word-Boundary-Regex; für nicht-ASCII Phrasen verwenden wir Lookaround.
    // \b funktioniert nicht zuverlässig vor/nach Sonderzeichen wie & oder -.
    // Wir nutzen: (?<![A-Za-z0-9äöüß])phrase(?![A-Za-z0-9äöüß])
    const re = new RegExp(`(?<![A-Za-z0-9äöüß])(${escapedPhrase})(?![A-Za-z0-9äöüß])`, "i");
    const match = working.match(re);
    if (!match) continue;
    used.add(entryIdx);
    const placeholder = `__TERM_PLACEHOLDER_${placeholders.length}__`;
    const tipText = escapeHtmlBasic(`${entry.label}: ${entry.explanation}`).replace(/"/g, "&quot;");
    const replacement = `<span class="term" data-tip="${tipText}" tabindex="0" role="button" aria-label="Erklärung zu ${escapeHtmlBasic(entry.label)}">${match[1]}</span>`;
    placeholders.push({ placeholder, replacement });
    working = working.replace(re, placeholder);
  }

  // Tausche Platzhalter aus
  for (const { placeholder, replacement } of placeholders) {
    working = working.replace(placeholder, replacement);
  }
  return working;
}

// Convenience: escape+linkify in einem Schritt
function escapeAndLinkify(text) {
  return linkifyTerms(text);
}

// Tap/Click-Handler für Mobile + zum manuellen Toggle
document.addEventListener("click", (e) => {
  const term = e.target.closest(".term");
  if (term) {
    e.preventDefault();
    e.stopPropagation();
    const wasOpen = term.classList.contains("is-open");
    document.querySelectorAll(".term.is-open").forEach((t) => t.classList.remove("is-open"));
    if (!wasOpen) term.classList.add("is-open");
    return;
  }
  // Klick außerhalb: alle schließen
  document.querySelectorAll(".term.is-open").forEach((t) => t.classList.remove("is-open"));
});

// ESC schließt alle offenen Tooltips
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.querySelectorAll(".term.is-open").forEach((t) => t.classList.remove("is-open"));
  }
});

function fmtNum(v, digits = 2) {
  if (v == null) return "—";
  return Number(v).toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtPct(v, digits = 2) {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${Number(v).toFixed(digits)} %`;
}

// ============================================================
// TABS
// ============================================================

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    const panel = document.getElementById(`tab-${btn.dataset.tab}`);
    if (panel) panel.classList.add("active");
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
});

// Brand-Click → Tab "Überblick"
const brandBtn = document.getElementById("brand-home");
if (brandBtn) {
  brandBtn.addEventListener("click", () => {
    document.querySelector('.tab[data-tab="overview"]')?.click();
  });
}

// ============================================================
// TAB 1: ÜBERBLICK
// ============================================================

async function loadOverview() {
  const todayEl = document.getElementById("overview-today");
  const tomorrowEl = document.getElementById("overview-tomorrow");
  const dateEl = document.getElementById("overview-date");
  try {
    const data = await fetchJSON("today_overview.json");
    if (todayEl) todayEl.innerHTML = escapeAndLinkify(data.summary || "—");
    if (tomorrowEl) tomorrowEl.innerHTML = escapeAndLinkify(data.next_day_outlook || "—");
    if (dateEl && data.generated_at) {
      const g = new Date(data.generated_at);
      dateEl.textContent = `Stand: ${g.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}`;
    }
  } catch (e) {
    if (todayEl) todayEl.textContent = "Noch keine Tageszusammenfassung vorhanden.";
    if (tomorrowEl) tomorrowEl.textContent = "Noch kein Ausblick vorhanden.";
  }
}

// ============================================================
// TAB 2: REPORT
// ============================================================

// --- ETF-Grid: 5 große Kacheln mit Sparkline ---

function renderSparklineSvg(values, polarity) {
  if (!Array.isArray(values) || values.length < 2) return "";
  const w = 100, h = 40;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = w / (values.length - 1);
  const points = values
    .map((v, i) => `${(i * step).toFixed(2)},${(h - ((v - min) / range) * h).toFixed(2)}`)
    .join(" ");
  const stroke = polarity === "down" ? "var(--negative)" : "var(--positive)";
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
    <polyline points="${points}" fill="none" stroke="${stroke}" stroke-width="2"
              stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
  </svg>`;
}

async function loadEtfGrid() {
  const grid = document.getElementById("etf-grid");
  if (!grid) return;
  try {
    const data = await fetchJSON("market_indices.json");
    const indices = data.indices || [];
    if (indices.length === 0) {
      grid.innerHTML = `<p class="loading">Keine Indizes-Daten verfügbar.</p>`;
      return;
    }
    grid.innerHTML = indices.map((idx, i) => {
      const polarity = idx.change_pct == null ? null : (idx.change_pct >= 0 ? "up" : "down");
      // Absolut-Änderung aus sparkline (letzte zwei Werte)
      let absChange = "";
      if (Array.isArray(idx.sparkline) && idx.sparkline.length >= 2) {
        const d = idx.sparkline[idx.sparkline.length - 1] - idx.sparkline[idx.sparkline.length - 2];
        absChange = (d >= 0 ? "+" : "") + d.toLocaleString("de-DE", { maximumFractionDigits: 2 });
      }
      const labelName = idx.short || idx.name || "—";
      return `<article class="etf-card ${polarity || ""}">
        <div class="etf-card-info">
          <span class="etf-card-name">${escapeHtml(labelName)}</span>
          <span class="etf-card-value">${fmtNum(idx.last_close)}</span>
          <span class="etf-card-change ${polarity || ""}">${absChange || "—"}</span>
        </div>
        <div class="etf-card-right">
          <span class="etf-card-pct ${polarity || ""}">${fmtPct(idx.change_pct)}</span>
          <span class="etf-card-spark">${renderSparklineSvg(idx.sparkline, polarity)}</span>
        </div>
      </article>`;
    }).join("");
  } catch (e) {
    grid.innerHTML = `<p class="loading">Indizes gerade nicht verfügbar.</p>`;
  }
}

// --- Marktbericht: 4 Sektionen ---

const REPORT_SECTION_ICONS = {
  context: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>`,
  market_state: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="3" y1="3" x2="3" y2="21"></line><line x1="3" y1="21" x2="21" y2="21"></line><rect x="7" y="13" width="3" height="6"></rect><rect x="12" y="9" width="3" height="10"></rect><rect x="17" y="5" width="3" height="14"></rect></svg>`,
  drivers: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><polyline points="12 7 12 13 16 15"></polyline></svg>`,
  sentiment: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>`,
};

let todayDashboard = null;

function renderReportSections(report, dashboard) {
  const container = document.getElementById("today-report");
  if (!container) return;
  if (!report || !report.macro) {
    container.innerHTML = `<div class="empty-state"><span class="em">📭</span>Kein Bericht für diesen Tag.</div>`;
    return;
  }
  const macro = report.macro || {};
  // Dashboard-Override hat Vorrang, Report-Felder sind Fallback.
  // "Makro-Kontext" und "Makro-Treiber" sind bewusst entfernt (Überschneidung mit Überblick-Tab bzw. Relevanz zu gering).
  const marketState = (dashboard?.report_market_state) || macro.market_state || macro.summary || "";
  const sentiment = (dashboard?.report_sentiment) || macro.sentiment || "";

  const sections = [
    { key: "market_state", title: "Marktlage", text: marketState },
    { key: "sentiment", title: "Sentiment", text: sentiment },
  ].filter((s) => s.text);

  if (sections.length === 0) {
    container.innerHTML = `<div class="empty-state"><span class="em">🤫</span>Heute nichts Berichtenswertes – Markt unaufgeregt.</div>`;
    return;
  }
  let html = "";
  for (const s of sections) {
    const bulletsHtml = (s.bullets && s.bullets.length)
      ? `<ul class="report-section-bullets">${s.bullets.map((b) => `<li>${escapeAndLinkify(b)}</li>`).join("")}</ul>`
      : "";
    html += `<article class="report-section">
      <div class="report-section-icon">${REPORT_SECTION_ICONS[s.key]}</div>
      <div class="report-section-body">
        <h3 class="report-section-title">${escapeHtml(s.title)}</h3>
        ${s.text ? `<p class="report-section-text">${escapeAndLinkify(s.text)}</p>` : ""}
        ${bulletsHtml}
      </div>
    </article>`;
  }
  container.innerHTML = html;
}

function renderReportSectorsBlock(report) {
  const container = document.getElementById("today-sectors");
  if (!container) return;
  const sectors = report?.sectors || [];
  if (sectors.length === 0) {
    container.innerHTML = "";
    return;
  }
  let html = `<h2 class="section-head" style="margin-top:16px">Branchen-Aufschlüsselung</h2>
    <p class="section-sub">Aktuelle Bewegungen in den Branchen, in denen ich investiert bin.</p>`;
  for (const s of sectors) {
    html += `<article class="report-sector">
      <div class="report-sector-head">
        <span aria-hidden="true">${escapeHtml(s.emoji || "📌")}</span>
        <h3>${escapeHtml(s.name || "")}</h3>
      </div>`;
    if (s.positions_mentioned?.length) {
      html += `<p class="report-sector-positions">Positionen: ${s.positions_mentioned.map(escapeHtml).join(" · ")}</p>`;
    }
    for (const n of s.news || []) {
      const r = Number(n.rating || 0);
      html += `<div class="report-news-item">
        <div class="report-news-head">
          <span class="report-news-title">${escapeAndLinkify(n.title || "")}</span>
          <span class="report-news-rating r${r}">${r}/5</span>
        </div>
        <p class="report-news-summary">${escapeAndLinkify(n.summary || "")}</p>
      </div>`;
    }
    html += `</article>`;
  }
  container.innerHTML = html;
}

async function loadReport() {
  const container = document.getElementById("today-report");
  const dateEl = document.getElementById("today-date");
  const genEl = document.getElementById("today-generated");
  if (!container) return;
  try {
    try { todayDashboard = await fetchJSON("today_dashboard.json"); } catch (_) { todayDashboard = null; }
    const index = await fetchJSON("reports/index.json");
    if (!index.reports || index.reports.length === 0) {
      if (dateEl) dateEl.textContent = formatDateLong(new Date().toISOString().slice(0, 10));
      container.innerHTML = `<div class="empty-state"><span class="em">⏳</span>Noch kein Bericht erstellt.</div>`;
      return;
    }
    const latest = index.reports[0];
    const report = await fetchJSON(`reports/${latest.filename}`);
    if (dateEl) dateEl.textContent = formatDateLong(report.date);
    if (genEl && report.generated_at) {
      const g = new Date(report.generated_at);
      genEl.textContent = g.toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
    }
    renderReportSections(report, todayDashboard);
    renderReportSectorsBlock(report);

    const footerInfo = document.getElementById("footer-info");
    if (footerInfo && report.generated_at) {
      const g = new Date(report.generated_at);
      footerInfo.textContent = `Daten per ${g.toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" })} MEZ`;
    }
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><span class="em">⚠️</span>Bericht konnte nicht geladen werden.</div>`;
  }
}

// --- Widget: Marktüberblick (Intraday-Chart + Indices) ---

let dashboardOverviewChart = null;
let dashboardCurrentRange = "1D";

function renderMarketOverview() {
  const data = todayDashboard;
  if (!data) return;
  const indicesList = document.getElementById("overview-indices-list");
  if (!indicesList) return;

  const indices = data.overview_indices || [];
  indicesList.innerHTML = indices.map((idx) => {
    const polarity = idx.change_pct >= 0 ? "up" : "down";
    const sign = idx.change_pct >= 0 ? "+" : "";
    return `<div class="widget-index-row">
      <span class="widget-index-dot" style="background:${idx.color || "var(--text-dim)"}"></span>
      <span class="widget-index-name">${escapeHtml(idx.name || "")}</span>
      <span class="widget-index-value">${fmtNum(idx.value)}</span>
      <span class="widget-index-pct ${polarity}">${sign}${idx.change_pct.toFixed(2)}%</span>
    </div>`;
  }).join("");

  renderOverviewChart(data, dashboardCurrentRange);

  document.querySelectorAll("#overview-time-tabs .time-tab").forEach((t) => {
    if (t.dataset.bound) return;
    t.dataset.bound = "1";
    t.addEventListener("click", () => {
      document.querySelectorAll("#overview-time-tabs .time-tab").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      dashboardCurrentRange = t.dataset.range;
      renderOverviewChart(data, dashboardCurrentRange);
    });
  });
}

function renderOverviewChart(data, range) {
  const canvas = document.getElementById("overview-chart");
  if (!canvas || !window.Chart) return;
  const ranges = data.overview_chart?.ranges || {};
  const r = ranges[range] || ranges["1D"];
  if (!r) return;
  if (dashboardOverviewChart) { dashboardOverviewChart.destroy(); dashboardOverviewChart = null; }
  const datasets = (data.overview_indices || []).map((idx) => ({
    label: idx.name,
    data: (r.series && r.series[idx.key]) || [],
    borderColor: idx.color,
    backgroundColor: idx.color,
    borderWidth: 1.8,
    pointRadius: 0,
    tension: 0.3,
  }));
  dashboardOverviewChart = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: { labels: r.labels || [], datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(10, 22, 37, 0.97)",
          borderColor: "rgba(148, 163, 184, 0.2)",
          borderWidth: 1,
          titleColor: "#f1f5f9",
          bodyColor: "#cbd5e1",
          padding: 10,
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${(ctx.raw >= 0 ? "+" : "")}${ctx.raw.toFixed(2)} %`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "rgba(100, 116, 139, 0.8)", font: { size: 10 }, maxRotation: 0 },
          grid: { color: "rgba(148, 163, 184, 0.08)", display: true },
        },
        y: {
          ticks: {
            color: "rgba(100, 116, 139, 0.8)",
            font: { size: 10 },
            callback: (v) => (v >= 0 ? "+" : "") + v.toFixed(1) + "%",
          },
          grid: { color: "rgba(148, 163, 184, 0.08)" },
        },
      },
    },
  });
}

// --- Widget: Marktstimmung (Halbkreis-Gauge) ---

function renderSentimentGauge() {
  const data = todayDashboard;
  const svg = document.getElementById("sentiment-gauge");
  const valEl = document.getElementById("sentiment-value");
  const labEl = document.getElementById("sentiment-label");
  if (!svg) return;
  const score = Math.max(0, Math.min(100, Number(data?.sentiment?.score ?? 50)));
  const label = data?.sentiment?.label || "Neutral";

  const cx = 100, cy = 100, r = 80;
  const segments = [
    { from: 0, to: 30, color: "#ef4444" },
    { from: 30, to: 50, color: "#f59e0b" },
    { from: 50, to: 70, color: "#94a3b8" },
    { from: 70, to: 100, color: "#22c55e" },
  ];
  function polar(angle) {
    const rad = (angle - 180) * Math.PI / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }
  function arcPath(from, to) {
    const a1 = (from / 100) * 180;
    const a2 = (to / 100) * 180;
    const p1 = polar(a1), p2 = polar(a2);
    return `M ${p1.x.toFixed(2)} ${p1.y.toFixed(2)} A ${r} ${r} 0 0 1 ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }
  let segHtml = "";
  for (const s of segments) {
    segHtml += `<path d="${arcPath(s.from, s.to)}" stroke="${s.color}" stroke-width="18" fill="none" stroke-linecap="butt" />`;
  }
  const pAngle = (score / 100) * 180;
  const radInner = (pAngle - 180) * Math.PI / 180;
  const innerR = r - 26;
  const pix = cx + innerR * Math.cos(radInner);
  const piy = cy + innerR * Math.sin(radInner);
  const tickHtml = `<line x1="${cx}" y1="${cy}" x2="${pix.toFixed(2)}" y2="${piy.toFixed(2)}" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" />
                    <circle cx="${cx}" cy="${cy}" r="5" fill="#ffffff" />`;

  svg.innerHTML = segHtml + tickHtml;
  if (valEl) valEl.textContent = Math.round(score);
  if (labEl) labEl.textContent = label;
}

// --- Widget: Sektoren-Balken ---

function renderSectorsBars() {
  const data = todayDashboard;
  const container = document.getElementById("sectors-list");
  if (!container) return;
  const sectors = data?.sectors || [];
  if (sectors.length === 0) {
    container.innerHTML = `<p class="loading">Keine Sektor-Daten.</p>`;
    return;
  }
  const maxAbs = Math.max(...sectors.map((s) => Math.abs(Number(s.change_pct || 0))), 1.5);
  container.innerHTML = sectors.map((s) => {
    const pct = Number(s.change_pct || 0);
    const polarity = pct >= 0 ? "up" : "down";
    const width = Math.min(100, (Math.abs(pct) / maxAbs) * 100);
    const sign = pct >= 0 ? "+" : "";
    return `<div class="sector-row">
      <span class="sector-row-name">${escapeHtml(s.name || "")}</span>
      <span class="sector-row-bar">
        <span class="sector-row-fill ${polarity}" style="width:${width.toFixed(1)}%"></span>
      </span>
      <span class="sector-row-pct ${polarity}">${sign}${pct.toFixed(2)}%</span>
    </div>`;
  }).join("");
}

// --- Widget: Top Movers ---

let dashboardMoversActive = "gainers";

function renderTopMovers() {
  const data = todayDashboard;
  const table = document.getElementById("movers-table");
  if (!table) return;
  drawMoversTable();
  document.querySelectorAll("#movers-tabs .movers-tab").forEach((t) => {
    if (t.dataset.bound) return;
    t.dataset.bound = "1";
    t.addEventListener("click", () => {
      document.querySelectorAll("#movers-tabs .movers-tab").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      dashboardMoversActive = t.dataset.movers;
      drawMoversTable();
    });
  });
}

function drawMoversTable() {
  const data = todayDashboard;
  const table = document.getElementById("movers-table");
  if (!table) return;
  const rows = (data?.top_movers?.[dashboardMoversActive]) || [];
  let html = `<thead><tr><th>Name</th><th>Kurs</th><th>Änd. %</th></tr></thead><tbody>`;
  rows.forEach((r, i) => {
    const polarity = r.change_pct >= 0 ? "up" : "down";
    const sign = r.change_pct >= 0 ? "+" : "";
    html += `<tr>
      <td>${i + 1}. ${escapeHtml(r.name || "")}</td>
      <td class="movers-value">${fmtNum(r.value)}</td>
      <td class="movers-pct ${polarity}">${sign}${r.change_pct.toFixed(2)}%</td>
    </tr>`;
  });
  html += `</tbody>`;
  table.innerHTML = html;
}

// --- Widget: Events heute ---

async function renderTodayEvents() {
  const list = document.getElementById("events-list");
  if (!list) return;
  try {
    const cal = await fetchJSON("calendar.json");
    const today = new Date().toISOString().slice(0, 10);
    let events = (cal.events || []).filter((e) => e.date === today);
    if (events.length === 0) {
      events = (cal.events || [])
        .filter((e) => e.date >= today)
        .sort((a, b) => a.date.localeCompare(b.date));
    }
    // Dedup + Rating-Filter
    events = dedupEvents(events).filter((e) => (e.rating || 0) >= 3).slice(0, 5);
    if (events.length === 0) {
      list.innerHTML = `<li class="events-empty">Keine wichtigen Events.</li>`;
    } else {
      list.innerHTML = events.map((e) => {
        const region = inferRegion(e.event || e.relevant_for || "");
        const time = e.time || (e.date === today ? "" : new Date(e.date + "T00:00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }));
        return `<li>
          <span class="events-time">${escapeHtml(time || "—")}</span>
          <span class="events-region">${escapeHtml(region)}</span>
          <span class="events-text">${escapeAndLinkify((e.event || "").slice(0, 80))}</span>
        </li>`;
      }).join("");
    }
  } catch (_) {
    list.innerHTML = `<li class="events-empty">Kalender nicht verfügbar.</li>`;
  }
  const ctaBtn = document.getElementById("events-to-calendar");
  if (ctaBtn && !ctaBtn.dataset.bound) {
    ctaBtn.dataset.bound = "1";
    ctaBtn.addEventListener("click", () => {
      document.querySelector('.tab[data-tab="calendar"]')?.click();
    });
  }
}

function inferRegion(text) {
  const t = String(text).toLowerCase();
  if (/\bfed\b|\bus\b|amerika|usa|treasury|empire state|michigan|fomc|nvidia|apple|microsoft|google|amazon|tesla/i.test(t)) return "US";
  if (/\bezb\b|euro|deutsch|dax|ecb|airbus/i.test(t)) return "EU";
  if (/\buk\b|britain|england|boe/i.test(t)) return "UK";
  if (/china|prc/i.test(t)) return "CN";
  if (/japan|boj/i.test(t)) return "JP";
  return "WW";
}

// --- Init Report-Widgets ---

async function loadReportWidgets() {
  if (!todayDashboard) {
    try { todayDashboard = await fetchJSON("today_dashboard.json"); } catch (_) { return; }
  }
  renderMarketOverview();
  renderSentimentGauge();
  renderSectorsBars();
  renderTopMovers();
  renderTodayEvents();
}

// ============================================================
// TAB 3: PORTFOLIO & WATCHLIST
// ============================================================

// --- Analytics-Donut ---

function renderAnalyticsDonut(data) {
  const svg = document.getElementById("analytics-donut");
  const legend = document.getElementById("analytics-legend");
  const posContainer = document.getElementById("analytics-positions");
  const posCount = document.getElementById("analytics-positions-count");
  if (!svg) return;

  const etfPct = data.allocation?.etf || 0;
  const stockPct = data.allocation?.stock || 0;
  const total = etfPct + stockPct || 1;
  const etfFrac = etfPct / total;

  const cx = 100, cy = 100, rOuter = 80, rInner = 50;
  // Donut: 2 Segmente, ETF (oben rechts, blau) und Aktien (unten links, hellblau)
  // Wir starten bei -90° (oben) und drehen im Uhrzeigersinn.
  function arcSegment(startFrac, endFrac, color) {
    const start = startFrac * Math.PI * 2 - Math.PI / 2;
    const end = endFrac * Math.PI * 2 - Math.PI / 2;
    const largeArc = (endFrac - startFrac) > 0.5 ? 1 : 0;
    const x1 = cx + rOuter * Math.cos(start), y1 = cy + rOuter * Math.sin(start);
    const x2 = cx + rOuter * Math.cos(end), y2 = cy + rOuter * Math.sin(end);
    const x3 = cx + rInner * Math.cos(end), y3 = cy + rInner * Math.sin(end);
    const x4 = cx + rInner * Math.cos(start), y4 = cy + rInner * Math.sin(start);
    return `<path d="M ${x1} ${y1} A ${rOuter} ${rOuter} 0 ${largeArc} 1 ${x2} ${y2} L ${x3} ${y3} A ${rInner} ${rInner} 0 ${largeArc} 0 ${x4} ${y4} Z" fill="${color}" />`;
  }
  let donutHtml = "";
  donutHtml += arcSegment(0, etfFrac, "#2563eb");
  donutHtml += arcSegment(etfFrac, 1, "#93c5fd");
  svg.innerHTML = donutHtml;

  if (legend) {
    legend.innerHTML = `
      <div class="analytics-legend-item">
        <span class="analytics-legend-dot" style="background:#2563eb"></span>
        <span class="analytics-legend-name">ETFs und Themen</span>
        <span class="analytics-legend-pct">${etfPct.toFixed(2).replace(".", ",")} %</span>
      </div>
      <div class="analytics-legend-item">
        <span class="analytics-legend-dot" style="background:#93c5fd"></span>
        <span class="analytics-legend-name">Aktien</span>
        <span class="analytics-legend-pct">${stockPct.toFixed(2).replace(".", ",")} %</span>
      </div>
    `;
  }

  if (posContainer) {
    const positions = (data.positions || []).slice().sort((a, b) => (b.pct || 0) - (a.pct || 0));
    posContainer.innerHTML = positions.map((p) => `<div class="analytics-position-row">
      <span class="analytics-position-name">${escapeHtml(p.name)}</span>
      <span class="analytics-position-pct">${(p.pct || 0).toFixed(2).replace(".", ",")} %</span>
    </div>`).join("");
    if (posCount) posCount.textContent = positions.length;
  }
}

// --- Forecast-Cards (wiederverwendet aus Welle 4) ---

let forecastState = { tickers: [] };

function renderStars(rating) {
  const r = Number(rating || 0);
  if (!r) return `<span class="potential-stars potential-empty">— Rating</span>`;
  const filled = "★".repeat(r);
  const empty = "☆".repeat(Math.max(0, 5 - r));
  return `<span class="potential-stars r${r}">${filled}${empty}</span>`;
}

function renderProConList(items, polarity) {
  if (!Array.isArray(items) || items.length === 0) return "";
  const cls = polarity === "con" ? "con-list" : "pro-list";
  const label = polarity === "con" ? "Risiken" : "Chancen";
  return `<div class="${cls}">
    <div class="pro-con-label">${label}</div>
    <ul>${items.map((s) => `<li>${escapeAndLinkify(s)}</li>`).join("")}</ul>
  </div>`;
}

function renderForecastCard(t, canvasId) {
  const scenario = t.scenario || "neutral";
  const exp30 = t.forecast?.expected_change_30d_pct;
  const exp90 = t.forecast?.expected_change_90d_pct;
  const unc = t.forecast?.uncertainty_pct;
  const fmtP = (v) => (v == null) ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(1)} %`;
  const pros = Array.isArray(t.pros) ? t.pros : [];
  const cons = Array.isArray(t.cons) ? t.cons : [];
  const hasProCon = pros.length > 0 || cons.length > 0;
  return `<div class="forecast-card">
    <div class="forecast-card-head">
      <span class="forecast-company">${escapeHtml(t.company || "")}</span>
      ${t.symbol ? `<span class="forecast-symbol">${escapeHtml(t.symbol)}</span>` : ""}
      <span class="scenario scenario-${scenario}">${SCENARIO_LABEL[scenario] || scenario}</span>
      ${renderStars(t.potential_rating)}
    </div>
    <div class="forecast-metrics">
      <div><span class="forecast-metric-label">4 W</span><span class="forecast-metric-val">${fmtP(exp30)}</span></div>
      <div><span class="forecast-metric-label">3 M</span><span class="forecast-metric-val">${fmtP(exp90)}</span></div>
      <div><span class="forecast-metric-label">± Band</span><span class="forecast-metric-val">${fmtP(unc)}</span></div>
      ${t.last_close ? `<div><span class="forecast-metric-label">Kurs</span><span class="forecast-metric-val">${fmtNum(t.last_close)}${t.currency && t.currency !== "USD" && t.currency !== "EUR" ? " " + escapeHtml(t.currency) : ""}</span></div>` : ""}
    </div>
    <div class="forecast-chart-wrap"><canvas id="${canvasId}"></canvas></div>
    ${hasProCon ? `<div class="pro-con-grid">${renderProConList(pros, "pro")}${renderProConList(cons, "con")}</div>` : ""}
    ${t.thesis ? `<p class="forecast-thesis">${escapeAndLinkify(t.thesis)}</p>` : ""}
    ${(t.key_drivers || []).length ? `<div class="forecast-drivers">Treiber: ${t.key_drivers.map((d) => `<span class="driver-tag">${escapeAndLinkify(d)}</span>`).join("")}</div>` : ""}
  </div>`;
}

function renderEmptyForecastCard(company) {
  return `<div class="forecast-card">
    <div class="forecast-card-head">
      <span class="forecast-company">${escapeHtml(company)}</span>
      <span class="potential-stars potential-empty">— Rating</span>
    </div>
    <p class="forecast-thesis dim">Noch keine Einschätzung im aktuellen Bericht.</p>
  </div>`;
}

let forecastChartInstances = [];

function destroyForecastCharts() {
  forecastChartInstances.forEach((c) => { try { c.destroy(); } catch (_) {} });
  forecastChartInstances = [];
}

function renderForecastChart(canvasId, ticker) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !window.Chart) return;
  const history = ticker.history || [];
  const proj = ticker.forecast || {};
  const labels = history.map((h) => h.date);
  const hPrices = history.map((h) => h.close);
  const projLabels = proj.projection?.dates || [];
  const projPath = proj.projection?.expected_path || [];
  const projHigh = proj.projection?.upper_band || [];
  const projLow = proj.projection?.lower_band || [];

  const allLabels = [...labels, ...projLabels];
  const histData = [...hPrices, ...Array(projLabels.length).fill(null)];
  const projData = [...Array(labels.length).fill(null), ...projPath];
  const highData = [...Array(labels.length).fill(null), ...projHigh];
  const lowData = [...Array(labels.length).fill(null), ...projLow];

  const ctx = canvas.getContext("2d");
  const instance = new Chart(ctx, {
    type: "line",
    data: {
      labels: allLabels,
      datasets: [
        { label: "Historie", data: histData, borderColor: "#94a3b8", borderWidth: 1.5, pointRadius: 0, tension: 0.2 },
        { label: "Erwartung", data: projData, borderColor: "#3b82f6", borderWidth: 1.8, pointRadius: 0, tension: 0.2, borderDash: [4, 3] },
        { label: "Obergrenze", data: highData, borderColor: "rgba(59,130,246,0.3)", borderWidth: 1, pointRadius: 0, tension: 0.2 },
        { label: "Untergrenze", data: lowData, borderColor: "rgba(59,130,246,0.3)", borderWidth: 1, pointRadius: 0, tension: 0.2, fill: "-1", backgroundColor: "rgba(59,130,246,0.08)" },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { intersect: false, mode: "index" },
      plugins: { legend: { display: false }, tooltip: { backgroundColor: "rgba(10,22,37,0.97)", borderColor: "rgba(148,163,184,0.2)", borderWidth: 1, padding: 8 } },
      scales: {
        x: { ticks: { display: false }, grid: { display: false } },
        y: { ticks: { color: "rgba(100,116,139,0.8)", font: { size: 9 } }, grid: { color: "rgba(148,163,184,0.06)" } },
      },
    },
  });
  forecastChartInstances.push(instance);
}

async function loadPortfolio() {
  const portfolioList = document.getElementById("forecast-portfolio-list");
  const watchlistList = document.getElementById("forecast-watchlist-list");
  if (!portfolioList || !watchlistList) return;

  // Analytics-Donut
  try {
    const analytics = await fetchJSON("portfolio_analytics.json");
    renderAnalyticsDonut(analytics);
  } catch (_) { /* still try forecast */ }

  try {
    const data = await fetchJSON("forecast_data.json");
    const tickers = data.tickers || [];
    forecastState.tickers = tickers;
    destroyForecastCharts();

    const byCompany = new Map(tickers.map((t) => [t.company, t]));

    // Portfolio (8 Werte)
    const portfolioCards = PORTFOLIO_COMPANIES.map((company, i) => {
      const t = byCompany.get(company);
      return t ? renderForecastCard(t, `forecast-chart-portfolio-${i}`) : renderEmptyForecastCard(company);
    });
    portfolioList.innerHTML = portfolioCards.join("");

    // Watchlist (5 Werte)
    const watchlistCards = WATCHLIST_COMPANIES.map((company, i) => {
      const t = byCompany.get(company);
      return t ? renderForecastCard(t, `forecast-chart-watchlist-${i}`) : renderEmptyForecastCard(company);
    });
    watchlistList.innerHTML = watchlistCards.join("");

    // Charts nach DOM-Injection
    PORTFOLIO_COMPANIES.forEach((company, i) => {
      const t = byCompany.get(company);
      if (t) renderForecastChart(`forecast-chart-portfolio-${i}`, t);
    });
    WATCHLIST_COMPANIES.forEach((company, i) => {
      const t = byCompany.get(company);
      if (t) renderForecastChart(`forecast-chart-watchlist-${i}`, t);
    });
  } catch (e) {
    portfolioList.innerHTML = `<div class="empty-state"><span class="em">📉</span>Noch keine Prognose-Daten.</div>`;
    watchlistList.innerHTML = "";
  }
}

// ============================================================
// TAB 4: ARCHIV
// ============================================================

async function loadArchive() {
  const list = document.getElementById("archive-list");
  if (!list) return;
  try {
    const index = await fetchJSON("reports/index.json");
    const reports = (index.reports || []).slice(0, 30);
    if (reports.length === 0) {
      list.innerHTML = `<div class="empty-state"><span class="em">📭</span>Noch keine archivierten Berichte.</div>`;
      return;
    }
    list.innerHTML = reports.map((r, i) => {
      const expanded = i < 3 ? "expanded" : "";
      return `<article class="archive-entry ${expanded}" data-filename="${escapeHtml(r.filename)}">
        <button type="button" class="archive-entry-head">
          <span>${escapeHtml(formatDateLong(r.date))}</span>
          <span style="color:var(--text-dim);font-size:13px">▾</span>
        </button>
        <div class="archive-entry-body"><p class="loading">Lade…</p></div>
      </article>`;
    }).join("");
    // Erst die 3 ausgeklappten laden
    document.querySelectorAll(".archive-entry.expanded").forEach((entry) => loadArchiveBody(entry));
    // Click-Handler
    document.querySelectorAll(".archive-entry-head").forEach((btn) => {
      btn.addEventListener("click", () => {
        const entry = btn.closest(".archive-entry");
        const willExpand = !entry.classList.contains("expanded");
        entry.classList.toggle("expanded");
        if (willExpand) loadArchiveBody(entry);
      });
    });
  } catch (e) {
    list.innerHTML = `<div class="empty-state"><span class="em">⚠️</span>Archiv konnte nicht geladen werden.</div>`;
  }
}

async function loadArchiveBody(entry) {
  const body = entry.querySelector(".archive-entry-body");
  if (!body || body.dataset.loaded === "1") return;
  body.dataset.loaded = "1";
  try {
    const report = await fetchJSON(`reports/${entry.dataset.filename}`);
    const macro = report.macro || {};
    const text = macro.market_state || macro.summary || "—";
    body.innerHTML = `<p class="overview-card-text">${escapeHtml(text)}</p>`;
  } catch (_) {
    body.innerHTML = `<p class="loading">Bericht nicht verfügbar.</p>`;
  }
}

// ============================================================
// TAB 5: KALENDER (mit Dedup + Rating-Filter)
// ============================================================

function dedupEvents(events) {
  // Gruppieren nach (date, relevant_for, similar event-text)
  const groups = new Map();
  for (const e of events) {
    const key = `${e.date}|${(e.relevant_for || "").toLowerCase().trim()}|${normalizeEventText(e.event || "")}`;
    if (!groups.has(key)) {
      groups.set(key, e);
    } else {
      const existing = groups.get(key);
      // Behalte den mit höchstem Rating, bei Gleichstand den längeren Text
      if ((e.rating || 0) > (existing.rating || 0)) {
        groups.set(key, e);
      } else if ((e.rating || 0) === (existing.rating || 0) && (e.event || "").length > (existing.event || "").length) {
        groups.set(key, e);
      }
    }
  }
  return Array.from(groups.values());
}

function normalizeEventText(text) {
  return String(text)
    .toLowerCase()
    .replace(/\(.*?\)/g, "")          // Klammern entfernen
    .replace(/[^\w\säöüß]/g, " ")      // Sonderzeichen
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 30);                    // Nur erste 30 Zeichen für Vergleich
}

let calendarState = { events: [], currentMonth: null, selectedDate: null, filter: null };

async function loadCalendar() {
  try {
    const cal = await fetchJSON("calendar.json");
    let events = (cal.events || []).filter((e) => (e.rating || 0) >= 3);
    events = dedupEvents(events);
    calendarState.events = events;
    const today = new Date();
    calendarState.currentMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    renderCalendarPicker();
    renderCalendarFilters();
    renderCalendarList();
    wireCalendarNav();
  } catch (e) {
    const list = document.getElementById("calendar-list");
    if (list) list.innerHTML = `<div class="empty-state"><span class="em">⚠️</span>Kalender konnte nicht geladen werden.</div>`;
  }
}

function wireCalendarNav() {
  document.getElementById("cal-prev")?.addEventListener("click", () => {
    calendarState.currentMonth.setMonth(calendarState.currentMonth.getMonth() - 1);
    renderCalendarPicker();
  });
  document.getElementById("cal-next")?.addEventListener("click", () => {
    calendarState.currentMonth.setMonth(calendarState.currentMonth.getMonth() + 1);
    renderCalendarPicker();
  });
  document.getElementById("cal-reset")?.addEventListener("click", () => {
    calendarState.selectedDate = null;
    renderCalendarPicker();
    renderCalendarList();
  });
}

function renderCalendarPicker() {
  const grid = document.getElementById("calendar-grid");
  const label = document.getElementById("cal-month-label");
  if (!grid || !label) return;
  const m = calendarState.currentMonth;
  label.textContent = `${MONTH_DE_FULL[m.getMonth()]} ${m.getFullYear()}`;

  const dayHeaders = WEEKDAY_SHORT.slice(1).concat(WEEKDAY_SHORT[0]);  // Mo-So
  let html = dayHeaders.map((d) => `<div class="cal-header">${d}</div>`).join("");

  const firstOfMonth = new Date(m.getFullYear(), m.getMonth(), 1);
  let weekday = firstOfMonth.getDay();  // 0 = So
  weekday = weekday === 0 ? 6 : weekday - 1;  // 0 = Mo
  const daysInMonth = new Date(m.getFullYear(), m.getMonth() + 1, 0).getDate();

  // Vor-Monat Tage (leer aber klickbar dim)
  const prevDays = weekday;
  for (let i = 0; i < prevDays; i++) html += `<button class="cal-cell dim" disabled></button>`;

  for (let day = 1; day <= daysInMonth; day++) {
    const dateIso = `${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const hasEvent = calendarState.events.some((e) => e.date === dateIso);
    const selected = calendarState.selectedDate === dateIso ? "selected" : "";
    html += `<button class="cal-cell ${hasEvent ? "has-event" : ""} ${selected}" data-date="${dateIso}">${day}</button>`;
  }
  grid.innerHTML = html;
  grid.querySelectorAll(".cal-cell[data-date]").forEach((c) => {
    c.addEventListener("click", () => {
      calendarState.selectedDate = c.dataset.date;
      renderCalendarPicker();
      renderCalendarList();
    });
  });
}

function renderCalendarFilters() {
  const row = document.getElementById("calendar-filters");
  if (!row) return;
  const categories = ["earnings", "fed", "economic", "product", "political", "other"];
  const labels = { earnings: "Earnings", fed: "Notenbank", economic: "Konjunktur", product: "Produkt", political: "Politik", other: "Sonstiges" };
  row.innerHTML = `<button class="filter-pill ${!calendarState.filter ? "active" : ""}" data-filter="">Alle</button>` +
    categories.map((c) => `<button class="filter-pill ${calendarState.filter === c ? "active" : ""}" data-filter="${c}">${labels[c]}</button>`).join("");
  row.querySelectorAll(".filter-pill").forEach((p) => {
    p.addEventListener("click", () => {
      calendarState.filter = p.dataset.filter || null;
      renderCalendarFilters();
      renderCalendarList();
    });
  });
}

function renderCalendarList() {
  const list = document.getElementById("calendar-list");
  if (!list) return;
  const today = new Date().toISOString().slice(0, 10);
  let events = calendarState.events.filter((e) => e.date >= today);
  if (calendarState.selectedDate) events = events.filter((e) => e.date === calendarState.selectedDate);
  if (calendarState.filter) events = events.filter((e) => e.category === calendarState.filter);
  events.sort((a, b) => a.date.localeCompare(b.date) || (b.rating || 0) - (a.rating || 0));
  if (events.length === 0) {
    list.innerHTML = `<div class="empty-state"><span class="em">📭</span>Keine Events für diese Auswahl.</div>`;
    return;
  }
  list.innerHTML = events.map((e) => {
    const d = new Date(e.date + "T00:00:00");
    const dateText = `${WEEKDAY_SHORT[d.getDay()]} ${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}`;
    const r = Number(e.rating || 0);
    return `<article class="calendar-event">
      <span class="calendar-event-date">${dateText}</span>
      <div>
        <h3 class="calendar-event-title">${escapeAndLinkify(e.event || "")}</h3>
        ${e.relevant_for ? `<p class="calendar-event-meta">${escapeAndLinkify(e.relevant_for)}</p>` : ""}
      </div>
      <span class="calendar-event-rating">${r}/5</span>
    </article>`;
  }).join("");
}

// ============================================================
// INIT
// ============================================================

// Glossar zuerst laden, danach alle Render-Funktionen (die linkifyTerms nutzen).
loadGlossary().then(() => {
  loadOverview();
  loadEtfGrid();
  loadReport().then(loadReportWidgets);
  loadPortfolio();
  loadArchive();
  loadCalendar();
});
