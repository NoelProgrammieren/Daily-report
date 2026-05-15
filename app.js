// Frontend für den Börsen-Tracker.
// Liest statische JSON-Dateien aus reports/ und calendar.json.

const PRIORITY_ICON = { fire: "🔥", lightning: "⚡", pin: "📌" };
const CATEGORY_LABEL = {
  earnings: "Earnings",
  fed: "Notenbank",
  economic: "Konjunktur",
  product: "Produkt",
  political: "Politik",
  other: "Sonstiges",
};
const MONTH_DE = [
  "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
  "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
];
const MONTH_DE_FULL = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];
const WEEKDAY_DE = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"];

// ---------- theme ----------
function initTheme() {
  const saved = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", saved);
  document.getElementById("theme-toggle").textContent = saved === "dark" ? "🌙" : "☀️";
}
document.getElementById("theme-toggle").addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme") || "dark";
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
  document.getElementById("theme-toggle").textContent = next === "dark" ? "🌙" : "☀️";
});
initTheme();

// ---------- tabs ----------
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// ---------- helpers ----------
function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDateLong(isoDate) {
  const d = new Date(isoDate + "T00:00:00");
  return `${WEEKDAY_DE[d.getDay()]}, ${d.getDate()}. ${MONTH_DE_FULL[d.getMonth()]} ${d.getFullYear()}`;
}

async function fetchJSON(path) {
  const r = await fetch(path + "?t=" + Date.now());
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

// ---------- report rendering ----------
function renderReport(report, container) {
  if (!report || !report.macro) {
    container.innerHTML = `<div class="empty-state"><span class="em">📭</span>Kein Bericht für diesen Tag.</div>`;
    return;
  }

  const macro = report.macro || {};
  let html = "";

  // Macro – gegliedert in Marktlage / Makro-Treiber / Sentiment
  // Abwärtskompatibel: falls nur das alte `summary`-Feld existiert, als Marktlage rendern.
  const marketState = macro.market_state || macro.summary || "";
  const macroDrivers = macro.macro_drivers || "";
  const sentiment = macro.sentiment || "";
  html += `<div class="macro">
    <h3>Makro-Kontext</h3>
    <div class="macro-sections">`;
  if (marketState) {
    html += `<div class="macro-section">
      <div class="macro-label">📊 Marktlage</div>
      <p>${escapeHtml(marketState)}</p>
    </div>`;
  }
  if (macroDrivers) {
    html += `<div class="macro-section">
      <div class="macro-label">🌐 Makro-Treiber</div>
      <p>${escapeHtml(macroDrivers)}</p>
    </div>`;
  }
  if (sentiment) {
    html += `<div class="macro-section">
      <div class="macro-label">🎯 Sentiment</div>
      <p>${escapeHtml(sentiment)}</p>
    </div>`;
  }
  html += `</div>`;
  if (macro.sp500 || macro.nasdaq || macro.dax) {
    html += `<div class="indices">`;
    if (macro.sp500) html += `<div><strong>S&amp;P 500:</strong> ${escapeHtml(macro.sp500)}</div>`;
    if (macro.nasdaq) html += `<div><strong>Nasdaq:</strong> ${escapeHtml(macro.nasdaq)}</div>`;
    if (macro.dax) html += `<div><strong>DAX:</strong> ${escapeHtml(macro.dax)}</div>`;
    html += `</div>`;
  }
  html += `</div>`;

  // Sectors
  const sectors = report.sectors || [];
  if (sectors.length === 0) {
    html += `<div class="empty-state" style="padding:32px"><span class="em">🤫</span>Heute nichts Berichtenswertes – Markt unaufgeregt.</div>`;
  } else {
    for (const s of sectors) {
      html += `<div class="sector">
        <div class="sector-header">
          <span style="font-size:18px">${escapeHtml(s.emoji || "📌")}</span>
          <h3>${escapeHtml(s.name || "")}</h3>
        </div>`;
      if (s.positions_mentioned && s.positions_mentioned.length) {
        html += `<p class="positions">Positionen: ${s.positions_mentioned.map(escapeHtml).join(" · ")}</p>`;
      }
      for (const n of s.news || []) {
        const r = Number(n.rating || 0);
        const ratingClass = `rating r${r}`;
        const pc = n.price_change ? String(n.price_change) : null;
        const pcClass = pc && (pc.includes("-") ? "negative" : pc.includes("+") ? "positive" : "");
        html += `<div class="news-item">
          <div class="news-head">
            <span class="priority">${PRIORITY_ICON[n.priority] || "📌"}</span>
            <span class="news-title">${escapeHtml(n.title || "")}</span>
            <span class="${ratingClass}">⭐ ${r}/5</span>
          </div>
          <p class="news-summary">${escapeHtml(n.summary || "")}</p>
          <div class="news-meta">
            ${pc ? `<span class="price-change ${pcClass}">${escapeHtml(pc)}</span>` : ""}
            ${n.investor_relevance ? `<span class="relevance">→ ${escapeHtml(n.investor_relevance)}</span>` : ""}
          </div>
        </div>`;
      }
      html += `</div>`;
    }
  }

  // Outlook
  const outlook = report.outlook || [];
  if (outlook.length) {
    html += `<div class="outlook"><h3>📅 Ausblick</h3><ul>`;
    for (const ev of outlook) {
      const r = Number(ev.rating || 0);
      html += `<li>
        <span class="ev-date">${escapeHtml(ev.date || "")}</span>
        <span class="ev-body">
          ${escapeHtml(ev.event || "")} <span class="rating r${r}" style="margin-left:6px">⭐ ${r}/5</span>
          ${ev.relevant_for ? `<span class="ev-rel">→ ${escapeHtml(ev.relevant_for)}</span>` : ""}
        </span>
      </li>`;
    }
    html += `</ul></div>`;
  }

  container.innerHTML = html;
}

// ---------- today ----------
async function loadToday() {
  const container = document.getElementById("today-report");
  const meta = document.getElementById("today-meta");
  const heroDate = document.getElementById("hero-date");
  try {
    const index = await fetchJSON("reports/index.json");
    if (!index.reports || index.reports.length === 0) {
      meta.innerHTML = "";
      if (heroDate) heroDate.textContent = formatDateLong(new Date().toISOString().slice(0, 10));
      container.innerHTML = `<div class="empty-state"><span class="em">⏳</span>Noch kein Bericht erstellt. Der erste Lauf startet beim nächsten 19-Uhr-Termin.</div>`;
      return;
    }
    const latest = index.reports[0];
    const report = await fetchJSON(`reports/${latest.filename}`);
    if (heroDate) heroDate.textContent = formatDateLong(report.date);
    meta.innerHTML = ""; // Datum/Generiert-Info ist jetzt im Hero / Status-Box.
    renderReport(report, container);
  } catch (e) {
    container.innerHTML = `<div class="error">Konnte Bericht nicht laden: ${escapeHtml(e.message)}</div>`;
  }
}

// ---------- market indices (hero chips) ----------
function fmtIndexValue(v) {
  if (v == null) return "—";
  return Number(v).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtIndexChange(pct) {
  if (pct == null) return "—";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${Number(pct).toFixed(2)} %`;
}

function renderSparkline(values, polarity) {
  if (!Array.isArray(values) || values.length < 2) return "";
  const w = 100;
  const h = 36;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = w / (values.length - 1);
  const points = values
    .map((v, i) => `${(i * step).toFixed(2)},${(h - ((v - min) / range) * h).toFixed(2)}`)
    .join(" ");
  const stroke = polarity === "negative" ? "var(--negative)" : "var(--positive)";
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
    <polyline points="${points}" fill="none" stroke="${stroke}" stroke-width="1.5"
              stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
  </svg>`;
}

async function loadMarketIndices() {
  const row = document.getElementById("indices-row");
  if (!row) return;
  try {
    const data = await fetchJSON("market_indices.json");
    const indices = data.indices || [];
    if (indices.length === 0) {
      row.innerHTML = `<p class="loading">Keine Indizes-Daten verfügbar.</p>`;
      return;
    }
    row.innerHTML = indices.map((idx) => {
      const hasData = idx.last_close != null;
      const polarity = idx.change_pct == null ? null : (idx.change_pct >= 0 ? "positive" : "negative");
      const changeClass = polarity ? `index-chip-change ${polarity}` : "index-chip-change";
      const spark = renderSparkline(idx.sparkline, polarity);
      return `<div class="index-chip${hasData ? "" : " is-empty"}">
        <div class="index-chip-head">
          <span class="index-chip-name">${escapeHtml(idx.short || idx.name || "")}</span>
          ${idx.currency ? `<span class="index-chip-currency">${escapeHtml(idx.currency)}</span>` : ""}
        </div>
        <div class="index-chip-value">${fmtIndexValue(idx.last_close)}</div>
        <div class="${changeClass}">${fmtIndexChange(idx.change_pct)}</div>
        <div class="index-chip-spark">${spark}</div>
      </div>`;
    }).join("");
  } catch (e) {
    row.innerHTML = `<p class="loading">Indizes gerade nicht verfügbar.</p>`;
  }
}

// ---------- hero status box ----------
async function loadHeroStatus() {
  const box = document.getElementById("hero-status");
  if (!box) return;
  const today = new Date().toISOString().slice(0, 10);
  const rows = [];

  try {
    const idx = await fetchJSON("reports/index.json");
    const latest = (idx.reports || [])[0];
    if (latest?.generated_at) {
      const gen = new Date(latest.generated_at);
      rows.push({
        label: "Bericht",
        value: gen.toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" }),
      });
    }
  } catch (_) { /* fall through */ }

  try {
    const ht = await fetchJSON("hot_takes.json");
    const active = (ht.takes || []).filter((t) => (t.event_date || "9999-12-31") >= today).length;
    rows.push({ label: "Hot Takes aktiv", value: String(active) });
  } catch (_) { /* fall through */ }

  try {
    const cal = await fetchJSON("calendar.json");
    const next = (cal.events || [])
      .filter((e) => e.date >= today)
      .sort((a, b) => a.date.localeCompare(b.date))[0];
    if (next) {
      const d = new Date(next.date + "T00:00:00");
      const datePart = `${d.getDate()}. ${MONTH_DE[d.getMonth()]}`;
      const evTitle = (next.event || "").length > 28
        ? next.event.slice(0, 26) + "…"
        : (next.event || "");
      rows.push({ label: "Nächstes Event", value: `${datePart} · ${evTitle}` });
    }
  } catch (_) { /* fall through */ }

  if (rows.length === 0) {
    box.innerHTML = `<div class="hero-status-row">
      <span class="hero-status-label">Status</span>
      <span class="hero-status-value dim">—</span>
    </div>`;
    return;
  }
  box.innerHTML = rows.map((r) =>
    `<div class="hero-status-row">
      <span class="hero-status-label">${escapeHtml(r.label)}</span>
      <span class="hero-status-value">${escapeHtml(r.value)}</span>
    </div>`
  ).join("");
}

// ---------- archive ----------
async function loadArchive() {
  const container = document.getElementById("archive-list");
  try {
    const index = await fetchJSON("reports/index.json");
    if (!index.reports || index.reports.length === 0) {
      container.innerHTML = `<div class="empty-state"><span class="em">📭</span>Noch keine archivierten Berichte.</div>`;
      return;
    }
    // Skip today (already on Heute tab); show next 3 days expanded, rest collapsed.
    const items = index.reports.slice(1);
    if (items.length === 0) {
      container.innerHTML = `<p class="hint">Noch keine älteren Berichte.</p>`;
      return;
    }
    container.innerHTML = "";
    for (let i = 0; i < items.length; i++) {
      const meta = items[i];
      const isOpen = i < 3;
      const details = document.createElement("details");
      details.className = "archive-item";
      if (isOpen) details.open = true;
      details.innerHTML = `
        <summary>
          <span class="archive-date">${formatDateLong(meta.date)}</span>
          <span class="archive-summary">Lade…</span>
        </summary>
        <div class="archive-body"><p class="loading">Lade Bericht…</p></div>`;
      container.appendChild(details);

      // Lazy-load body on first open
      const loadBody = async () => {
        if (details.dataset.loaded) return;
        details.dataset.loaded = "1";
        try {
          const report = await fetchJSON(`reports/${meta.filename}`);
          const body = details.querySelector(".archive-body");
          renderReport(report, body);
          const summaryNote = details.querySelector(".archive-summary");
          const archiveSnippet = report.macro?.market_state || report.macro?.summary || "";
          summaryNote.textContent = archiveSnippet
            ? archiveSnippet.slice(0, 110) + (archiveSnippet.length > 110 ? "…" : "")
            : "";
        } catch (e) {
          details.querySelector(".archive-body").innerHTML =
            `<div class="error">Fehler: ${escapeHtml(e.message)}</div>`;
        }
      };
      if (isOpen) loadBody();
      details.addEventListener("toggle", () => {
        if (details.open) loadBody();
      });
    }
  } catch (e) {
    container.innerHTML = `<div class="error">Konnte Archiv nicht laden: ${escapeHtml(e.message)}</div>`;
  }
}

// ---------- calendar ----------
let calendarState = { events: [], filter: "all" };

function renderCalendar() {
  const list = document.getElementById("calendar-list");
  const today = new Date().toISOString().slice(0, 10);
  let events = calendarState.events.filter((e) => e.date >= today);
  if (calendarState.filter !== "all") {
    events = events.filter((e) => (e.category || "other") === calendarState.filter);
  }
  if (events.length === 0) {
    list.innerHTML = `<div class="empty-state"><span class="em">🗓️</span>Keine kommenden Ereignisse${calendarState.filter !== "all" ? " in dieser Kategorie" : ""}.</div>`;
    return;
  }
  // Group by month
  const groups = {};
  for (const ev of events) {
    const d = new Date(ev.date + "T00:00:00");
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    (groups[key] ||= []).push(ev);
  }
  let html = "";
  for (const key of Object.keys(groups).sort()) {
    const [y, m] = key.split("-");
    html += `<div class="cal-month">
      <h3 class="cal-month-head">${MONTH_DE_FULL[parseInt(m, 10) - 1]} ${y}</h3>`;
    for (const ev of groups[key]) {
      const d = new Date(ev.date + "T00:00:00");
      const r = Number(ev.rating || 0);
      const cat = ev.category || "other";
      html += `<div class="cal-event">
        <div class="cal-event-date">
          <span class="cal-event-day">${d.getDate()}</span>
          <span class="cal-event-month">${MONTH_DE[d.getMonth()]}</span>
        </div>
        <div class="cal-event-body">
          <div class="cal-event-title">${escapeHtml(ev.event || "")}</div>
          <div class="cal-event-meta">
            <span class="cat-tag ${escapeHtml(cat)}">${CATEGORY_LABEL[cat] || cat}</span>
            ${ev.relevant_for ? `Relevant für: ${escapeHtml(ev.relevant_for)}` : ""}
          </div>
        </div>
        <div class="cal-event-rating"><span class="rating r${r}">⭐ ${r}/5</span></div>
      </div>`;
    }
    html += `</div>`;
  }
  list.innerHTML = html;
}

function renderCalendarFilters() {
  const cats = new Set(
    calendarState.events
      .filter((e) => e.date >= new Date().toISOString().slice(0, 10))
      .map((e) => e.category || "other"),
  );
  const filters = ["all", ...Array.from(cats)];
  const row = document.getElementById("calendar-filters");
  row.innerHTML = filters
    .map((f) => {
      const label = f === "all" ? "Alle" : CATEGORY_LABEL[f] || f;
      const active = f === calendarState.filter ? " active" : "";
      return `<button class="filter-pill${active}" data-filter="${f}">${label}</button>`;
    })
    .join("");
  row.querySelectorAll(".filter-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      calendarState.filter = btn.dataset.filter;
      renderCalendarFilters();
      renderCalendar();
    });
  });
}

async function loadCalendar() {
  try {
    const cal = await fetchJSON("calendar.json");
    calendarState.events = cal.events || [];
    if (cal.updated_at) {
      document.getElementById("footer-info").textContent =
        `Kalender zuletzt aktualisiert: ${new Date(cal.updated_at).toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" })}`;
    }
    renderCalendarFilters();
    renderCalendar();
  } catch (e) {
    document.getElementById("calendar-list").innerHTML =
      `<div class="error">Konnte Kalender nicht laden: ${escapeHtml(e.message)}</div>`;
  }
}

// ---------- hot takes ----------
const SCENARIO_LABEL = { bullish: "📈 Bullish", neutral: "➡️ Neutral", bearish: "📉 Bearish" };

async function loadHotTakes() {
  const container = document.getElementById("hot-takes-list");
  try {
    // Hot Takes liegen rollierend in hot_takes.json (Top-Level-Datei).
    const data = await fetchJSON("hot_takes.json");
    const today = new Date().toISOString().slice(0, 10);
    const takes = (data.takes || []).filter((t) => (t.event_date || "9999-12-31") >= today);
    if (takes.length === 0) {
      container.innerHTML = `<div class="empty-state"><span class="em">🤷</span>Aktuell keine offenen Hot Takes. Neue erscheinen, sobald greifbare Events kommen.</div>`;
      return;
    }
    // Sortieren: Rating absteigend, dann Event-Datum aufsteigend
    takes.sort((a, b) => (Number(b.rating) || 0) - (Number(a.rating) || 0) ||
      (a.event_date || "").localeCompare(b.event_date || ""));
    let html = "";
    for (const t of takes) {
      const r = Number(t.rating || 0);
      html += `<div class="hot-take r${r}">
        <div class="hot-take-head">
          <span class="hot-take-company">${escapeHtml(t.company || "?")}</span>
          <span class="rating r${r}">⭐ ${r}/5</span>
        </div>
        <div class="hot-take-event">
          <span class="hot-take-eventdate">${escapeHtml(t.event_date || "")}</span>
          · ${escapeHtml(t.event_basis || "")}
          ${t.time_horizon ? `<span class="hot-take-horizon">⏱ ${escapeHtml(t.time_horizon)}</span>` : ""}
        </div>
        <p class="hot-take-thesis">${escapeHtml(t.thesis || "")}</p>
        ${t.risks ? `<div class="hot-take-risks">⚠️ ${escapeHtml(t.risks)}</div>` : ""}
        <div class="hot-take-foot">
          ${t.first_seen ? `<span>seit ${escapeHtml(t.first_seen)}</span>` : ""}
        </div>
      </div>`;
    }
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><span class="em">📭</span>Noch keine Hot Takes vorhanden.</div>`;
  }
}

// ---------- forecast ----------
function chartColors() {
  const styles = getComputedStyle(document.documentElement);
  return {
    text: styles.getPropertyValue("--text").trim() || "#e6edf3",
    textDim: styles.getPropertyValue("--text-dim").trim() || "#8b96a4",
    border: styles.getPropertyValue("--border").trim() || "#2a3340",
    accent: styles.getPropertyValue("--accent").trim() || "#4a9eff",
    positive: styles.getPropertyValue("--positive").trim() || "#2ea043",
    negative: styles.getPropertyValue("--negative").trim() || "#f85149",
    warning: styles.getPropertyValue("--warning").trim() || "#d29922",
  };
}

function withAlpha(hex, alpha) {
  // Akzeptiert #rrggbb oder benannte Farben → fällt sonst auf den Hex-String zurück.
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return hex;
  const num = parseInt(m[1], 16);
  const r = (num >> 16) & 0xff;
  const g = (num >> 8) & 0xff;
  const b = num & 0xff;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

let forecastCharts = [];

function destroyForecastCharts() {
  for (const c of forecastCharts) {
    try { c.destroy(); } catch (_) { /* ignore */ }
  }
  forecastCharts = [];
}

function renderForecastChart(canvasId, ticker) {
  if (typeof Chart === "undefined") return; // Chart.js noch nicht geladen
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const colors = chartColors();
  const history = ticker.history || [];
  const path = ticker.forecast?.path || [];

  // Konstruiere die kombinierte Datums-Achse: History + Forecast-Pfade.
  const allDates = [...history.map((p) => p.date), ...path.map((p) => p.date)];

  // Forecast-Linie startet beim letzten History-Punkt (visueller Anschluss).
  const forecastCentral = [];
  const forecastUpper = [];
  const forecastLower = [];
  const histLen = history.length;
  for (let i = 0; i < allDates.length; i++) {
    if (i < histLen - 1) {
      forecastCentral.push(null);
      forecastUpper.push(null);
      forecastLower.push(null);
    } else if (i === histLen - 1 && histLen > 0) {
      const anchor = history[histLen - 1].close;
      forecastCentral.push(anchor);
      forecastUpper.push(anchor);
      forecastLower.push(anchor);
    } else {
      const p = path[i - histLen];
      forecastCentral.push(p?.central ?? null);
      forecastUpper.push(p?.upper ?? null);
      forecastLower.push(p?.lower ?? null);
    }
  }
  const histSeries = [];
  for (let i = 0; i < allDates.length; i++) {
    histSeries.push(i < histLen ? history[i].close : null);
  }

  const chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: allDates,
      datasets: [
        {
          label: "Historisch",
          data: histSeries,
          borderColor: colors.accent,
          backgroundColor: withAlpha(colors.accent, 0.05),
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.2,
          spanGaps: false,
        },
        {
          label: "Erwartung",
          data: forecastCentral,
          borderColor: colors.warning,
          borderDash: [6, 4],
          borderWidth: 2,
          pointRadius: 2,
          pointBackgroundColor: colors.warning,
          tension: 0.25,
          spanGaps: false,
        },
        {
          label: "Bandbreite (oben)",
          data: forecastUpper,
          borderColor: "transparent",
          backgroundColor: withAlpha(colors.warning, 0.15),
          pointRadius: 0,
          fill: "+1",
          tension: 0.25,
        },
        {
          label: "Bandbreite (unten)",
          data: forecastLower,
          borderColor: "transparent",
          backgroundColor: withAlpha(colors.warning, 0.15),
          pointRadius: 0,
          fill: false,
          tension: 0.25,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          display: true,
          labels: {
            color: colors.textDim,
            font: { size: 11 },
            filter: (item) => !item.text.startsWith("Bandbreite"),
          },
        },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(2) ?? "—"}`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: colors.textDim, maxTicksLimit: 6, autoSkip: true, font: { size: 10 } },
          grid: { color: withAlpha(colors.border, 0.4) },
        },
        y: {
          ticks: { color: colors.textDim, font: { size: 10 } },
          grid: { color: withAlpha(colors.border, 0.4) },
        },
      },
    },
  });
  forecastCharts.push(chart);
}

async function loadForecast() {
  const list = document.getElementById("forecast-list");
  const commentBox = document.getElementById("forecast-commentary");
  try {
    const data = await fetchJSON("forecast_data.json");
    if (data.commentary) {
      commentBox.innerHTML = `<p>${escapeHtml(data.commentary)}</p>
        <p class="forecast-disclaimer">Erwartungspfade und Bandbreite sind <strong>begründete Einschätzungen</strong>, keine Vorhersagen. Tatsächliche Kursverläufe können davon erheblich abweichen.</p>`;
    } else {
      commentBox.innerHTML = "";
    }
    const tickers = data.tickers || [];
    if (tickers.length === 0) {
      list.innerHTML = `<div class="empty-state"><span class="em">📉</span>Noch keine Prognose-Daten. Wird beim nächsten 19-Uhr-Lauf erzeugt.</div>`;
      return;
    }
    destroyForecastCharts();
    let html = "";
    for (let i = 0; i < tickers.length; i++) {
      const t = tickers[i];
      const canvasId = `forecast-chart-${i}`;
      const scenario = t.scenario || "neutral";
      const exp30 = t.forecast?.expected_change_30d_pct;
      const exp90 = t.forecast?.expected_change_90d_pct;
      const unc = t.forecast?.uncertainty_pct;
      const fmtPct = (v) => (v === null || v === undefined) ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(1)} %`;
      html += `<div class="forecast-card">
        <div class="forecast-card-head">
          <span class="forecast-company">${escapeHtml(t.company || "")}</span>
          ${t.symbol ? `<span class="forecast-symbol">${escapeHtml(t.symbol)}</span>` : ""}
          <span class="scenario scenario-${scenario}">${SCENARIO_LABEL[scenario] || scenario}</span>
        </div>
        <div class="forecast-metrics">
          <div><span class="forecast-metric-label">30 T</span><span class="forecast-metric-val">${fmtPct(exp30)}</span></div>
          <div><span class="forecast-metric-label">90 T</span><span class="forecast-metric-val">${fmtPct(exp90)}</span></div>
          <div><span class="forecast-metric-label">± Band</span><span class="forecast-metric-val">${fmtPct(unc)}</span></div>
          ${t.last_close ? `<div><span class="forecast-metric-label">Stand</span><span class="forecast-metric-val">${Number(t.last_close).toFixed(2)}</span></div>` : ""}
        </div>
        <div class="forecast-chart-wrap"><canvas id="${canvasId}"></canvas></div>
        ${t.thesis ? `<p class="forecast-thesis">${escapeHtml(t.thesis)}</p>` : ""}
        ${(t.key_drivers || []).length ? `<div class="forecast-drivers">Treiber: ${t.key_drivers.map((d) => `<span class="driver-tag">${escapeHtml(d)}</span>`).join(" ")}</div>` : ""}
      </div>`;
    }
    list.innerHTML = html;
    // Charts erst nach DOM-Injection erzeugen
    for (let i = 0; i < tickers.length; i++) {
      renderForecastChart(`forecast-chart-${i}`, tickers[i]);
    }
  } catch (e) {
    list.innerHTML = `<div class="empty-state"><span class="em">📉</span>Noch keine Prognose-Daten. Wird beim nächsten 19-Uhr-Lauf erzeugt.</div>`;
  }
}

// ---------- init ----------
loadToday();
loadMarketIndices();
loadHeroStatus();
loadArchive();
loadCalendar();
loadHotTakes();
loadForecast();
