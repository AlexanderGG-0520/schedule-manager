async function fetchEvents(start, end, query = "") {
  const params = new URLSearchParams({ start, end, query });
  const res = await fetch(`/api/v1/events?${params.toString()}`, {
    credentials: "same-origin",
    headers: { "Accept": "application/json" },
  });
  if (!res.ok) {
    console.error("イベント取得失敗", res.status);
    return [];
  }
  return await res.json();
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function endOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 1);
}

function startOfWeek(date) {
  const d = new Date(date);
  const diff = (d.getDay() + 6) % 7; // Monday-start
  d.setDate(d.getDate() - diff);
  d.setHours(0,0,0,0);
  return d;
}

function endOfWeek(date) {
  const s = startOfWeek(date);
  s.setDate(s.getDate() + 7);
  return s;
}

function startOfDay(date) {
  const d = new Date(date);
  d.setHours(0,0,0,0);
  return d;
}

function endOfDay(date) {
  const d = new Date(date);
  d.setHours(23,59,59,999);
  return d;
}

function iso(t) {
  return t.toISOString();
}

async function renderCalendar() {
  const root = document.getElementById("calendar-root");
  const view = document.getElementById("view-mode").value;
  const search = document.getElementById("search").value || "";
  const now = window._calendarCurrentDate || new Date();
  window._calendarCurrentDate = now;

  let start, end;
  if (view === "month") {
    start = startOfMonth(now);
    end = endOfMonth(now);
  } else if (view === "week") {
    start = startOfWeek(now);
    end = endOfWeek(now);
  } else {
    start = startOfDay(now);
    end = endOfDay(now);
  }

  // update current month label if present
  try {
    const currentMonthEl = document.getElementById('current-month');
    if (currentMonthEl) {
      const opts = { year: 'numeric', month: 'long' };
      currentMonthEl.textContent = now.toLocaleDateString(undefined, opts);
    }
  } catch (e) { /* ignore if locale unavailable */ }

  const events = await fetchEvents(iso(start), iso(end), search);

  // simple render: clear and list events
  root.innerHTML = "";
  const heading = document.createElement("div");
  heading.className = "calendar-heading";
  heading.textContent = `${view.toUpperCase()} - ${start.toLocaleDateString()} ~ ${new Date(end).toLocaleDateString()}`;
  root.appendChild(heading);

  if (!events.length) {
    const p = document.createElement("p");
    p.textContent = "予定はありません。";
    root.appendChild(p);
    // continue and render an empty calendar grid so layout is visible
  }

  // group events by date (YYYY-MM-DD)
  const buckets = {};
  for (const e of events) {
    const d = new Date(e.start);
    const key = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
    if (!buckets[key]) buckets[key] = [];
    buckets[key].push(e);
  }

  if (view === 'month') {
    // build month grid starting from start (first of month) to end (first of next month)
    const grid = document.createElement('div');
    grid.className = 'calendar-grid month-grid';
    // header row (weekday names)
    const header = document.createElement('div');
    header.className = 'calendar-row header';
    const weekdays = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
    for (const wd of weekdays) {
      const cell = document.createElement('div');
      cell.className = 'calendar-cell header-cell';
      cell.textContent = wd;
      header.appendChild(cell);
    }
    grid.appendChild(header);

    // compute first cell (startOfWeek of the first of month)
    let cursor = startOfWeek(start);
    while (cursor < end) {
      const row = document.createElement('div');
      row.className = 'calendar-row';
      for (let i=0;i<7;i++){
        const cell = document.createElement('div');
        cell.className = 'calendar-cell';
        const dayNum = document.createElement('div');
        dayNum.className = 'calendar-day-num';
        dayNum.textContent = String(cursor.getDate());
        cell.appendChild(dayNum);
        const key = cursor.getFullYear() + '-' + String(cursor.getMonth()+1).padStart(2,'0') + '-' + String(cursor.getDate()).padStart(2,'0');
        const evs = buckets[key] || [];
        const list = document.createElement('ul');
        list.className = 'day-events';
        for (const e of evs) {
          const li = document.createElement('li');
          li.className = 'day-event';
          li.style.borderLeft = `4px solid ${e.color || '#4287f5'}`;
          li.textContent = `${new Date(e.start).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} ${e.title}`;
          list.appendChild(li);
        }
        cell.appendChild(list);
        row.appendChild(cell);
        cursor.setDate(cursor.getDate()+1);
      }
      grid.appendChild(row);
    }
    root.appendChild(grid);
    return;
  }

  if (view === 'week') {
    const grid = document.createElement('div');
    grid.className = 'calendar-grid week-grid';
    const header = document.createElement('div');
    header.className = 'calendar-row header';
    for (let i=0;i<7;i++){
      const cell = document.createElement('div');
      cell.className = 'calendar-cell header-cell';
      const d = new Date(start);
      d.setDate(d.getDate()+i);
      cell.textContent = `${d.toLocaleDateString()} (${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][i]})`;
      header.appendChild(cell);
    }
    grid.appendChild(header);
    const row = document.createElement('div');
    row.className = 'calendar-row';
    for (let i=0;i<7;i++){
      const cell = document.createElement('div');
      cell.className = 'calendar-cell';
      const d = new Date(start);
      d.setDate(d.getDate()+i);
      const key = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
      const evs = buckets[key] || [];
      const list = document.createElement('ul');
      list.className = 'day-events';
      for (const e of evs) {
        const li = document.createElement('li');
        li.className = 'day-event';
        li.style.borderLeft = `4px solid ${e.color || '#4287f5'}`;
        li.textContent = `${new Date(e.start).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} ${e.title}`;
        list.appendChild(li);
      }
      cell.appendChild(list);
      row.appendChild(cell);
    }
    grid.appendChild(row);
    root.appendChild(grid);
    return;
  }

  // day view

// Modal helper: create or reuse modal element and populate with events
function openEventsModal(year, month, date, evs) {
  let modal = document.getElementById('events-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'events-modal';
    modal.className = 'events-modal';
    modal.innerHTML = `
      <div class="events-modal-backdrop"></div>
      <div class="events-modal-dialog" role="dialog" aria-modal="true">
        <button class="events-modal-close" aria-label="閉じる">✕</button>
        <div class="events-modal-content"></div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('.events-modal-close').addEventListener('click', closeEventsModal);
    modal.querySelector('.events-modal-backdrop').addEventListener('click', closeEventsModal);
  }
  const title = `${year}/${String(month + 1).padStart(2, '0')}/${String(date).padStart(2, '0')} の予定`;
  const content = modal.querySelector('.events-modal-content');
  content.innerHTML = `<h3>${title}</h3>`;
  const ul = document.createElement('ul');
  ul.className = 'modal-event-list';
  for (const e of evs) {
    const li = document.createElement('li');
    li.className = 'modal-event';
    li.innerHTML = `<strong>${new Date(e.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</strong> ${e.title}<div class="modal-event-meta">${e.location || ''}</div>`;
    ul.appendChild(li);
  }
  content.appendChild(ul);
  modal.classList.add('open');
}

function closeEventsModal() {
  const modal = document.getElementById('events-modal');
  if (modal) modal.classList.remove('open');
}
  const day = startOfDay(start);
  const key = day.getFullYear() + '-' + String(day.getMonth()+1).padStart(2,'0') + '-' + String(day.getDate()).padStart(2,'0');
  const evs = buckets[key] || [];
  const list = document.createElement('ul');
  list.className = 'day-events full-day';
  for (const e of evs) {
    const li = document.createElement('li');
    li.className = 'day-event';
    li.style.borderLeft = `4px solid ${e.color || '#4287f5'}`;
    li.textContent = `${new Date(e.start).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} - ${new Date(e.end).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} ${e.title}`;
    list.appendChild(li);
  }
  root.appendChild(list);
}

document.addEventListener("DOMContentLoaded", function () {
  const prev = document.getElementById("prev");
  const next = document.getElementById("next");
  const view = document.getElementById("view-mode");
  const search = document.getElementById("search");

  prev.addEventListener("click", function () {
    const v = view.value;
    if (v === 'month') window._calendarCurrentDate.setMonth(window._calendarCurrentDate.getMonth() - 1);
    else if (v === 'week') window._calendarCurrentDate.setDate(window._calendarCurrentDate.getDate() - 7);
    else window._calendarCurrentDate.setDate(window._calendarCurrentDate.getDate() - 1);
    renderCalendar();
  });
  next.addEventListener("click", function () {
    const v = view.value;
    if (v === 'month') window._calendarCurrentDate.setMonth(window._calendarCurrentDate.getMonth() + 1);
    else if (v === 'week') window._calendarCurrentDate.setDate(window._calendarCurrentDate.getDate() + 7);
    else window._calendarCurrentDate.setDate(window._calendarCurrentDate.getDate() + 1);
    renderCalendar();
  });
  view.addEventListener("change", renderCalendar);
  search.addEventListener("input", function () { setTimeout(renderCalendar, 300); });
  renderCalendar();

  // Accessibility & theming: initialize theme/font controls and keyboard shortcuts
  function announce(message) {
    // create or reuse an aria-live region for announcements
    let live = document.getElementById('a11y-live');
    if (!live) {
      live = document.createElement('div');
      live.id = 'a11y-live';
      live.setAttribute('aria-live', 'polite');
      live.setAttribute('aria-atomic', 'true');
      live.style.position = 'absolute';
      live.style.left = '-9999px';
      live.style.width = '1px';
      live.style.height = '1px';
      live.style.overflow = 'hidden';
      document.body.appendChild(live);
    }
    live.textContent = message;
  }

  function initTheme() {
    const t = localStorage.getItem('theme') || document.documentElement.classList.contains('theme-dark') ? 'dark' : 'light';
    if (t === 'dark') document.documentElement.classList.add('theme-dark');
    else document.documentElement.classList.remove('theme-dark');
    // ensure --font-scale exists
    if (!document.documentElement.style.getPropertyValue('--font-scale')) {
      document.documentElement.style.setProperty('--font-scale', '1');
    }
  }

  function toggleTheme() {
    const isDark = document.documentElement.classList.toggle('theme-dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    announce(isDark ? 'ダークテーマに切り替えました' : 'ライトテーマに切り替えました');
  }

  function getFontScale() {
    const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--font-scale')) || 1;
    return v;
  }

  function applyFontScale(scale) {
    const clamped = Math.min(1.5, Math.max(0.8, scale));
    document.documentElement.style.setProperty('--font-scale', String(clamped));
    localStorage.setItem('fontScale', String(clamped));
    announce('フォントサイズを ' + Math.round(clamped * 100) + '% に設定しました');
  }

  function increaseFontScale() { applyFontScale(getFontScale() + 0.1); }
  function decreaseFontScale() { applyFontScale(getFontScale() - 0.1); }
  function resetFontScale() { applyFontScale(1); }

  // wire theme toggle button if present
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.setAttribute('role', 'button');
    themeBtn.setAttribute('tabindex', '0');
    themeBtn.setAttribute('aria-pressed', String(document.documentElement.classList.contains('theme-dark')));
    themeBtn.addEventListener('click', function () {
      toggleTheme();
      themeBtn.setAttribute('aria-pressed', String(document.documentElement.classList.contains('theme-dark')));
    });
    themeBtn.addEventListener('keydown', function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); themeBtn.click(); } });
  }

  // keyboard shortcuts (avoid when typing into inputs)
  function isTypingTarget(el) {
    if (!el) return false;
    const tag = el.tagName && el.tagName.toLowerCase();
    return tag === 'input' || tag === 'textarea' || el.isContentEditable;
  }

  function handleShortcuts(e) {
    if (isTypingTarget(document.activeElement)) return;
    // '/' focuses search
    if (e.key === '/') {
      e.preventDefault();
      if (search) { search.focus(); search.select(); announce('検索にフォーカスしました'); }
      return;
    }
    // 't' toggles theme
    if (e.key.toLowerCase() === 't') { e.preventDefault(); if (themeBtn) themeBtn.click(); else toggleTheme(); return; }
    // '+' / '=' increase font
    if (e.key === '+' || e.key === '=') { e.preventDefault(); increaseFontScale(); return; }
    if (e.key === '-') { e.preventDefault(); decreaseFontScale(); return; }
    if (e.key.toLowerCase() === '0') { e.preventDefault(); resetFontScale(); return; }
    // navigation: left/right arrows or h/l
    if (e.key === 'ArrowLeft' || e.key.toLowerCase() === 'h') { e.preventDefault(); prev && prev.click(); return; }
    if (e.key === 'ArrowRight' || e.key.toLowerCase() === 'l') { e.preventDefault(); next && next.click(); return; }
  }

  // restore persisted fontScale
  const persistedScale = parseFloat(localStorage.getItem('fontScale'));
  if (!Number.isNaN(persistedScale)) applyFontScale(persistedScale);
  initTheme();
  document.addEventListener('keydown', handleShortcuts);

  // expose controls for automated tests or other scripts
  window._calendarControls = {
    toggleTheme, increaseFontScale, decreaseFontScale, resetFontScale, applyFontScale
  };
});
