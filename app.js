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

const MACRO_ICON_SVG = {
  globe: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>`,
  target: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>`,
  pulse: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>`,
};

// ---------- theme ----------
function initTheme() {
  const saved = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", saved);
}
document.getElementById("theme-toggle").addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme") || "dark";
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
});
initTheme();

// Watchlist-Shortcut: Click springt zum Portfolio & Watchlist Tab.
document.addEventListener("click", (e) => {
  const btn = e.target.closest("#watchlist-shortcut");
  if (!btn) return;
  const tabBtn = document.querySelector('.tab[data-tab="forecast"]');
  if (tabBtn) tabBtn.click();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

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

  const macroCards = [
    { key: "globe", title: "Marktlage", text: marketState },
    { key: "target", title: "Makro-Treiber", text: macroDrivers },
    { key: "pulse", title: "Sentiment", text: sentiment },
  ].filter((c) => c.text);

  if (macroCards.length) {
    html += `<div class="macro-grid">`;
    for (const c of macroCards) {
      html += `<article class="macro-card">
        <div class="macro-icon icon-${c.key}">${MACRO_ICON_SVG[c.key]}</div>
        <div class="macro-body">
          <h3 class="macro-card-title">${escapeHtml(c.title)}</h3>
          <p class="macro-card-text">${escapeHtml(c.text)}</p>
        </div>
      </article>`;
    }
    html += `</div>`;
  }

  if (macro.sp500 || macro.nasdaq || macro.dax) {
    html += `<div class="indices">`;
    if (macro.sp500) html += `<div><strong>S&amp;P 500:</strong> ${escapeHtml(macro.sp500)}</div>`;
    if (macro.nasdaq) html += `<div><strong>Nasdaq:</strong> ${escapeHtml(macro.nasdaq)}</div>`;
    if (macro.dax) html += `<div><strong>DAX:</strong> ${escapeHtml(macro.dax)}</div>`;
    html += `</div>`;
  }

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
let calendarState = {
  events: [],
  filter: "all",
  viewMonth: null,
  selectedDate: null,
};

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function isoFromYM(year, month) {
  return `${year}-${String(month + 1).padStart(2, "0")}`;
}

function renderCalendar() {
  const list = document.getElementById("calendar-list");
  const today = todayISO();
  let events = calendarState.selectedDate
    ? calendarState.events.filter((e) => e.date === calendarState.selectedDate)
    : calendarState.events.filter((e) => e.date >= today);
  if (calendarState.filter !== "all") {
    events = events.filter((e) => (e.category || "other") === calendarState.filter);
  }
  if (events.length === 0) {
    const ctx = calendarState.selectedDate
      ? ` am ${formatDateLong(calendarState.selectedDate)}`
      : (calendarState.filter !== "all" ? " in dieser Kategorie" : "");
    list.innerHTML = `<div class="empty-state"><span class="em">🗓️</span>Keine Ereignisse${ctx}.</div>`;
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
      renderCalendarPicker();
      renderCalendar();
    });
  });
}

function renderCalendarPicker() {
  const grid = document.getElementById("calendar-grid");
  const label = document.getElementById("cal-month-label");
  if (!grid || !label) return;

  const [yStr, mStr] = calendarState.viewMonth.split("-");
  const year = parseInt(yStr, 10);
  const month = parseInt(mStr, 10) - 1;

  label.textContent = `${MONTH_DE_FULL[month]} ${year}`;

  // Set with all ISO-dates that have events (for highlight lookup)
  const eventDates = new Set(
    calendarState.events
      .filter((e) => calendarState.filter === "all" || (e.category || "other") === calendarState.filter)
      .map((e) => e.date),
  );

  // Build a 6×7 grid starting on Monday
  const firstOfMonth = new Date(Date.UTC(year, month, 1));
  // JS Sunday=0, we want Monday=0 → Sunday=6
  const startWeekday = (firstOfMonth.getUTCDay() + 6) % 7;
  const gridStart = new Date(Date.UTC(year, month, 1 - startWeekday));
  const today = todayISO();

  const headers = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
  let html = headers.map((d) => `<div class="cal-dow">${d}</div>`).join("");

  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart);
    d.setUTCDate(d.getUTCDate() + i);
    const iso = d.toISOString().slice(0, 10);
    const dayMonth = d.getUTCMonth();
    const cls = ["calendar-day"];
    if (dayMonth !== month) cls.push("muted");
    if (iso === today) cls.push("today");
    if (eventDates.has(iso)) cls.push("has-event");
    if (calendarState.selectedDate === iso) cls.push("selected");
    html += `<button type="button" class="${cls.join(" ")}" data-date="${iso}">
      <span class="cal-day-num">${d.getUTCDate()}</span>
    </button>`;
  }
  grid.innerHTML = html;

  grid.querySelectorAll(".calendar-day").forEach((btn) => {
    btn.addEventListener("click", () => {
      const date = btn.dataset.date;
      calendarState.selectedDate = calendarState.selectedDate === date ? null : date;
      renderCalendarPicker();
      renderCalendar();
    });
  });
}

function wireCalendarNav() {
  const prev = document.getElementById("cal-prev");
  const next = document.getElementById("cal-next");
  const reset = document.getElementById("cal-reset");
  if (prev) prev.addEventListener("click", () => shiftMonth(-1));
  if (next) next.addEventListener("click", () => shiftMonth(1));
  if (reset) reset.addEventListener("click", () => {
    calendarState.selectedDate = null;
    calendarState.filter = "all";
    const today = new Date();
    calendarState.viewMonth = isoFromYM(today.getFullYear(), today.getMonth());
    renderCalendarFilters();
    renderCalendarPicker();
    renderCalendar();
  });
}

function shiftMonth(delta) {
  const [y, m] = calendarState.viewMonth.split("-").map((s) => parseInt(s, 10));
  const d = new Date(Date.UTC(y, m - 1 + delta, 1));
  calendarState.viewMonth = isoFromYM(d.getUTCFullYear(), d.getUTCMonth());
  renderCalendarPicker();
}

async function loadCalendar() {
  try {
    const cal = await fetchJSON("calendar.json");
    calendarState.events = cal.events || [];
    if (!calendarState.viewMonth) {
      const t = new Date();
      calendarState.viewMonth = isoFromYM(t.getFullYear(), t.getMonth());
    }
    if (cal.updated_at) {
      document.getElementById("footer-info").textContent =
        `Kalender zuletzt aktualisiert: ${new Date(cal.updated_at).toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" })}`;
    }
    wireCalendarNav();
    renderCalendarFilters();
    renderCalendarPicker();
    renderCalendar();
  } catch (e) {
    document.getElementById("calendar-list").innerHTML =
      `<div class="error">Konnte Kalender nicht laden: ${escapeHtml(e.message)}</div>`;
  }
}

// ---------- hot takes ----------
const SCENARIO_LABEL = { bullish: "📈 Bullish", neutral: "➡️ Neutral", bearish: "📉 Bearish" };

let hotTakesState = { takes: [], sort: "rating" };

async function loadHotTakes() {
  const container = document.getElementById("hot-takes-list");
  try {
    // Hot Takes liegen rollierend in hot_takes.json (Top-Level-Datei).
    const data = await fetchJSON("hot_takes.json");
    const today = new Date().toISOString().slice(0, 10);
    hotTakesState.takes = (data.takes || []).filter((t) => (t.event_date || "9999-12-31") >= today);
    if (hotTakesState.takes.length === 0) {
      container.innerHTML = `<div class="empty-state"><span class="em">🤷</span>Aktuell keine offenen Hot Takes. Neue erscheinen, sobald greifbare Events kommen.</div>`;
      return;
    }
    wireHotTakesSort();
    renderHotTakesList();
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><span class="em">📭</span>Noch keine Hot Takes vorhanden.</div>`;
  }
}

function wireHotTakesSort() {
  const btn = document.getElementById("hot-takes-sort");
  if (!btn || btn.dataset.wired) return;
  btn.dataset.wired = "1";
  btn.addEventListener("click", () => {
    hotTakesState.sort = hotTakesState.sort === "rating" ? "date" : "rating";
    const label = document.getElementById("hot-takes-sort-label");
    if (label) label.textContent = hotTakesState.sort === "rating" ? "Höchstes Rating zuerst" : "Nächstes Event zuerst";
    renderHotTakesList();
  });
}

function renderHotTakesList() {
  const container = document.getElementById("hot-takes-list");
  if (!container) return;
  const takes = [...hotTakesState.takes];
  if (hotTakesState.sort === "rating") {
    takes.sort((a, b) => (Number(b.rating) || 0) - (Number(a.rating) || 0) ||
      (a.event_date || "").localeCompare(b.event_date || ""));
  } else {
    takes.sort((a, b) => (a.event_date || "").localeCompare(b.event_date || "") ||
      (Number(b.rating) || 0) - (Number(a.rating) || 0));
  }
  let html = "";
  for (const t of takes) {
    const r = Number(t.rating || 0);
    const forecastBox = renderHotTakeForecast(t);
    const direction = t.expected_move_pct?.direction === "down" ? "down" : "up";
    const initials = (t.company || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0] || "").join("").toUpperCase().slice(0, 2);
    const eventDate = formatHotTakeDate(t.event_date);
    const thesisLabel = direction === "down" ? "Bearische These" : "Bullische These";
    const thesisIcon = direction === "down"
      ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="22 17 13.5 8.5 8.5 13.5 2 7"></polyline><polyline points="16 17 22 17 22 11"></polyline></svg>`
      : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline><polyline points="16 7 22 7 22 13"></polyline></svg>`;
    html += `<article class="hot-take r${r} dir-${direction}">
      <span class="hot-take-accent" aria-hidden="true"></span>
      <div class="hot-take-main">
        <header class="hot-take-head">
          <div class="hot-take-avatar" aria-hidden="true">${escapeHtml(initials || "?")}</div>
          <div class="hot-take-id">
            <h3 class="hot-take-company">${escapeHtml(t.company || "?")}</h3>
            ${eventDate ? `<p class="hot-take-eventdate">${escapeHtml(eventDate)}</p>` : ""}
          </div>
          <span class="rating-pill r${r}">
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
            ${r}/5
          </span>
        </header>
        ${t.event_basis ? `<ul class="hot-take-event-list"><li>${escapeHtml(t.event_basis)}</li></ul>` : ""}
        ${t.time_horizon ? `<div class="hot-take-horizon-row"><span class="hot-take-horizon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>${escapeHtml(t.time_horizon)}</span></div>` : ""}
        ${forecastBox}
        ${t.thesis ? `<section class="hot-take-section thesis dir-${direction}">
          <div class="hot-take-section-head">${thesisIcon}<span>${thesisLabel}</span></div>
          <p>${escapeHtml(t.thesis)}</p>
        </section>` : ""}
        ${t.risks ? `<section class="hot-take-section risks">
          <div class="hot-take-section-head"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg><span>Bewertung im Blick</span></div>
          <p>${escapeHtml(t.risks)}</p>
        </section>` : ""}
        ${t.first_seen ? `<footer class="hot-take-foot">seit ${escapeHtml(formatHotTakeDate(t.first_seen) || t.first_seen)}</footer>` : ""}
      </div>
    </article>`;
  }
  container.innerHTML = html;
}

function formatHotTakeDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  if (isNaN(d.getTime())) return iso;
  return `${d.getDate()}. ${MONTH_DE_FULL[d.getMonth()]} ${d.getFullYear()}`;
}

function renderHotTakeForecast(t) {
  const mv = t.expected_move_pct;
  const pt = t.price_target;
  const parts = [];
  if (mv && (mv.low != null || mv.high != null)) {
    const dir = mv.direction === "down" ? "down" : "up";
    const sign = dir === "down" ? "−" : "+";
    const arrow = dir === "down" ? "▼" : "▲";
    const lo = mv.low != null ? formatNum(mv.low, 1) : null;
    const hi = mv.high != null ? formatNum(mv.high, 1) : null;
    const range = lo != null && hi != null ? `${sign}${lo} % bis ${sign}${hi} %`
                : (lo != null ? `${sign}${lo} %` : `${sign}${hi} %`);
    parts.push(`<span class="move-badge ${dir}"><span class="move-arrow">${arrow}</span>${range}</span>`);
  }
  if (pt && (pt.low != null || pt.high != null)) {
    const lo = pt.low != null ? formatNum(pt.low, 2) : null;
    const hi = pt.high != null ? formatNum(pt.high, 2) : null;
    const range = lo != null && hi != null ? `${lo}–${hi}`
                : (lo != null ? `${lo}` : `${hi}`);
    const curr = pt.currency ? ` ${escapeHtml(pt.currency)}` : "";
    parts.push(`<span class="target-badge"><span class="target-icon">◎</span>Kursziel ${range}${curr}</span>`);
  }
  if (parts.length === 0) return "";
  return `<div class="hot-take-forecast">${parts.join("")}</div>`;
}

function formatNum(v, digits) {
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n.toLocaleString("de-DE", { minimumFractionDigits: 0, maximumFractionDigits: digits });
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

// Statisch konfigurierte Watchlist-Werte. Müssen im forecast.tickers (vom
// Claude-Lauf) auftauchen — falls Claude einen Eintrag vergisst, zeigen
// wir einen Platzhalter, damit die Sektion vollständig wirkt.
const WATCHLIST_COMPANIES = ["Walmart", "Oracle", "MSCI World Health Care", "Boeing", "Airbus"];

function renderStars(rating) {
  const r = Number(rating || 0);
  if (!r) return `<span class="potential-stars potential-empty" title="Kein Rating">— Rating</span>`;
  const filled = "★".repeat(r);
  const empty = "☆".repeat(Math.max(0, 5 - r));
  return `<span class="potential-stars r${r}" title="Potential-Rating ${r}/5">${filled}${empty}</span>`;
}

function renderEmptyWatchlistCard(company) {
  return `<div class="forecast-card forecast-card-empty">
    <div class="forecast-card-head">
      <span class="forecast-company">${escapeHtml(company)}</span>
      <span class="potential-stars potential-empty">— Rating</span>
    </div>
    <p class="forecast-thesis dim">Noch keine Einschätzung im aktuellen Bericht. Wird beim nächsten 19-Uhr-Lauf ergänzt.</p>
  </div>`;
}

function renderProConList(items, polarity) {
  if (!Array.isArray(items) || items.length === 0) return "";
  const cls = polarity === "con" ? "con-list" : "pro-list";
  const label = polarity === "con" ? "Risiken" : "Chancen";
  const lis = items.map((s) => `<li>${escapeHtml(s)}</li>`).join("");
  return `<div class="${cls}">
    <div class="pro-con-label">${label}</div>
    <ul>${lis}</ul>
  </div>`;
}

function renderForecastCard(t, canvasId) {
  const scenario = t.scenario || "neutral";
  const exp30 = t.forecast?.expected_change_30d_pct;
  const exp90 = t.forecast?.expected_change_90d_pct;
  const unc = t.forecast?.uncertainty_pct;
  const fmtPct = (v) => (v === null || v === undefined) ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(1)} %`;
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
      <div><span class="forecast-metric-label">4 W</span><span class="forecast-metric-val">${fmtPct(exp30)}</span></div>
      <div><span class="forecast-metric-label">3 M</span><span class="forecast-metric-val">${fmtPct(exp90)}</span></div>
      <div><span class="forecast-metric-label">± Band</span><span class="forecast-metric-val">${fmtPct(unc)}</span></div>
      ${t.last_close ? `<div><span class="forecast-metric-label">Kurs</span><span class="forecast-metric-val">${Number(t.last_close).toFixed(2)}</span></div>` : ""}
    </div>
    <div class="forecast-chart-wrap"><canvas id="${canvasId}"></canvas></div>
    ${hasProCon ? `<div class="pro-con-grid">
      ${renderProConList(pros, "pro")}
      ${renderProConList(cons, "con")}
    </div>` : ""}
    ${t.thesis ? `<p class="forecast-thesis">${escapeHtml(t.thesis)}</p>` : ""}
    ${(t.key_drivers || []).length ? `<div class="forecast-drivers">Treiber: ${t.key_drivers.map((d) => `<span class="driver-tag">${escapeHtml(d)}</span>`).join(" ")}</div>` : ""}
  </div>`;
}

async function loadForecast() {
  const portfolioList = document.getElementById("forecast-portfolio-list");
  const watchlistList = document.getElementById("forecast-watchlist-list");
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
    destroyForecastCharts();

    // Fallback-Kategorisierung: Watchlist-Werte erkennen wir auch ohne explizites Feld.
    const enriched = tickers.map((t) => ({
      ...t,
      category: t.category === "watchlist" || t.category === "portfolio"
        ? t.category
        : (WATCHLIST_COMPANIES.includes(t.company) ? "watchlist" : "portfolio"),
    }));

    const portfolio = enriched.filter((t) => t.category === "portfolio");
    const watchlist = enriched.filter((t) => t.category === "watchlist");

    // --- Portfolio-Sektion ---
    if (portfolio.length === 0) {
      portfolioList.innerHTML = `<div class="empty-state"><span class="em">📉</span>Keine Portfolio-Einschätzungen im aktuellen Bericht.</div>`;
    } else {
      portfolioList.innerHTML = portfolio
        .map((t, i) => renderForecastCard(t, `forecast-chart-portfolio-${i}`))
        .join("");
    }

    // --- Watchlist-Sektion: fehlende Werte als Platzhalter zeigen ---
    const watchlistByCompany = new Map(watchlist.map((t) => [t.company, t]));
    const watchlistCards = WATCHLIST_COMPANIES.map((company, i) => {
      const t = watchlistByCompany.get(company);
      return t
        ? renderForecastCard(t, `forecast-chart-watchlist-${i}`)
        : renderEmptyWatchlistCard(company);
    });
    // Falls Claude zusätzliche Watchlist-Einträge schickt, hängen wir die hinten an.
    const extra = watchlist.filter((t) => !WATCHLIST_COMPANIES.includes(t.company));
    extra.forEach((t, i) =>
      watchlistCards.push(renderForecastCard(t, `forecast-chart-watchlist-extra-${i}`))
    );
    watchlistList.innerHTML = watchlistCards.join("");

    // Charts erst nach DOM-Injection erzeugen.
    portfolio.forEach((t, i) => renderForecastChart(`forecast-chart-portfolio-${i}`, t));
    WATCHLIST_COMPANIES.forEach((company, i) => {
      const t = watchlistByCompany.get(company);
      if (t) renderForecastChart(`forecast-chart-watchlist-${i}`, t);
    });
    extra.forEach((t, i) => renderForecastChart(`forecast-chart-watchlist-extra-${i}`, t));
  } catch (e) {
    portfolioList.innerHTML = `<div class="empty-state"><span class="em">📉</span>Noch keine Prognose-Daten. Wird beim nächsten 19-Uhr-Lauf erzeugt.</div>`;
    watchlistList.innerHTML = WATCHLIST_COMPANIES.map(renderEmptyWatchlistCard).join("");
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
