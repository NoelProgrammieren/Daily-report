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

  // Macro
  html += `<div class="macro">
    <h3>Makro-Kontext</h3>
    <p>${escapeHtml(macro.summary || "Keine Makro-Notizen.")}</p>`;
  if (macro.sp500 || macro.nasdaq) {
    html += `<div class="indices">`;
    if (macro.sp500) html += `<div><strong>S&amp;P 500:</strong> ${escapeHtml(macro.sp500)}</div>`;
    if (macro.nasdaq) html += `<div><strong>Nasdaq:</strong> ${escapeHtml(macro.nasdaq)}</div>`;
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
  try {
    const index = await fetchJSON("reports/index.json");
    if (!index.reports || index.reports.length === 0) {
      meta.innerHTML = "";
      container.innerHTML = `<div class="empty-state"><span class="em">⏳</span>Noch kein Bericht erstellt. Der erste Lauf startet beim nächsten 19-Uhr-Termin.</div>`;
      return;
    }
    const latest = index.reports[0];
    const report = await fetchJSON(`reports/${latest.filename}`);
    const generatedNote = report.generated_at
      ? `· generiert ${new Date(report.generated_at).toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" })}`
      : "";
    meta.innerHTML = `
      <span class="date">${formatDateLong(report.date)}</span>
      <span class="generated">${generatedNote}</span>`;
    renderReport(report, container);
  } catch (e) {
    container.innerHTML = `<div class="error">Konnte Bericht nicht laden: ${escapeHtml(e.message)}</div>`;
  }
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
          summaryNote.textContent = report.macro?.summary
            ? report.macro.summary.slice(0, 110) + (report.macro.summary.length > 110 ? "…" : "")
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

// ---------- init ----------
loadToday();
loadArchive();
loadCalendar();
