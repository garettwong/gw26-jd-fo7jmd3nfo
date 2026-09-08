(function () {
  'use strict';
  const DAY_MS = 86400000;
  const displayLabel = label => label === 'HK265HG · FS · SEP 2026' ? 'HK265HG · FS-6 · SEP 2026' : label;
  const dateFormat = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit'
  });
  function dayNumber(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return NaN;
    const [year, month, day] = value.split('-').map(Number);
    const stamp = Date.UTC(year, month - 1, day);
    return new Date(stamp).toISOString().slice(0, 10) === value ? stamp / DAY_MS : NaN;
  }
  function todayDate() {
    const override = new URLSearchParams(location.search).get('today');
    if (Number.isFinite(dayNumber(override))) return override;
    const parts = Object.fromEntries(dateFormat.formatToParts(new Date()).map(part => [part.type, part.value]));
    return `${parts.year}-${parts.month}-${parts.day}`;
  }
  window.erbTodayDate = todayDate;
  const limits = Array.from(document.querySelectorAll('.next-course-limit'));
  const upcoming = Array.from(document.querySelectorAll('.next-course-card'));
  const list = document.getElementById('nextCourseList');
  const empty = document.getElementById('nextCourseEmpty');
  let limit = 5;
  let lastDate = '';

  function updateUpcoming(today) {
    let visible = 0;
    upcoming.forEach(card => {
      const days = dayNumber(card.dataset.firstDate) - dayNumber(today);
      const eligible = Number.isFinite(days) && days >= 0;
      card.hidden = !eligible || visible >= limit;
      if (!card.hidden) visible += 1;
      const countdown = card.querySelector('.next-new-countdown strong');
      if (countdown) countdown.textContent = days === 0 ? '今天' : eligible ? `${days} 日` : '已開始';
    });
    if (list) {
      list.style.setProperty('--next-course-rows', String(Math.max(1, Math.ceil(visible / 2))));
      list.dataset.visibleCount = String(visible);
      list.dataset.activeLimit = String(limit);
      list.dataset.asOf = today;
    }
    if (empty) empty.hidden = visible > 0;
    limits.forEach(button => {
      const active = Number(button.dataset.nextCourseLimit) === limit;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  // Use full-class dates for lifecycle labels; a last personal lesson is not the class end.
  function updateClassLifecycle(today) {
    const groups = new Map();
    document.querySelectorAll('.gridwrap .chip[data-group]').forEach(card => {
      const key = card.dataset.group;
      if (!groups.has(key)) groups.set(key, []);
      if (!/cancelled|canceled|取消/i.test(card.dataset.text || '')) groups.get(key).push(card);
    });
    const counts = { upcoming: 0, pending: 0, completed: 0, context: 0 };
    const upcomingList = document.querySelector('.upcoming-summary .class-summary-list');
    const completedList = document.querySelector('.completed-summary .class-summary-list');
    const summaries = Array.from(document.querySelectorAll('.class-summary-card'));
    for (const [group, cards] of groups) {
      const future = cards.filter(card => card.dataset.date >= today);
      const personal = card => card.dataset.layer === 'mine';
      const noteOnly = cards.every(card => card.dataset.status === 'note');
      const lifecycle = noteOnly ? 'note' : !future.length ? 'completed'
        : future.some(card => personal(card) && card.dataset.status === 'unconfirmed') ? 'pending'
        : future.some(personal) ? 'upcoming' : 'context';
      const isErb = cards.some(card => card.dataset.course === '1');
      if (isErb && lifecycle in counts) counts[lifecycle] += 1;
      document.querySelectorAll('.filter-group-buttons .course-filter').forEach(button => {
        if (button.dataset.filter !== group) return;
        button.classList.remove('upcoming', 'pending', 'completed', 'context', 'note');
        button.classList.add(lifecycle);
        button.dataset.statusSummary = lifecycle;
        button.title = `${displayLabel(cards[0]?.dataset.groupLabel || '')} · ${lifecycle}`;
      });
      const summary = summaries.find(card => card.dataset.filter === group);
      if (!summary) continue;
      const isPast = !future.length;
      const statuses = new Set((isPast ? cards : future).map(card => card.dataset.status));
      const status = statuses.size === 1 && statuses.has('confirmed') ? 'confirmed'
        : statuses.size === 1 && statuses.has('unconfirmed') ? 'unconfirmed' : 'mixed';
      summary.classList.remove('upcoming', 'completed', 'confirmed', 'unconfirmed', 'mixed');
      summary.classList.add(isPast ? 'completed' : 'upcoming');
      if (!isPast) summary.classList.add(status);
      const statusLabel = isPast ? 'COMPLETED' : status.toUpperCase();
      summary.querySelector('.summary-status').textContent = statusLabel;
      const personalCards = cards.filter(personal);
      const countLabel = `我的堂數 ${personalCards.length} / 全班 ${cards.length}`;
      summary.querySelector('.summary-lesson-count').textContent = countLabel;
      summary.setAttribute('aria-label', `Filter ${displayLabel(cards[0]?.dataset.groupLabel || '')}; ${statusLabel}; ${countLabel}`);
      const targetDates = (isPast ? cards : future).map(card => card.dataset.date).sort();
      summary.dataset.firstDate = isPast ? targetDates[targetDates.length - 1] : targetDates[0];
      const target = isPast ? completedList : upcomingList;
      if (target) target.appendChild(summary);
    }
    [upcomingList, completedList].forEach(container => {
      if (!container) return;
      const direction = container === completedList ? -1 : 1;
      Array.from(container.children).sort((a, b) => direction * a.dataset.firstDate.localeCompare(b.dataset.firstDate))
        .forEach(card => container.appendChild(card));
    });
    const labels = { upcoming: 'Upcoming', pending: 'Pending', completed: 'Completed', context: 'Full-class context' };
    document.querySelectorAll('[data-filter-status]').forEach(pill => {
      const status = pill.dataset.filterStatus;
      if (!(status in counts)) return;
      const swatch = pill.querySelector('.filter-status-swatch');
      pill.replaceChildren();
      if (swatch) pill.appendChild(swatch);
      pill.appendChild(document.createTextNode(`${labels[status]} ${counts[status]}`));
    });
  }

  function refresh() {
    const today = todayDate();
    updateUpcoming(today);
    if (today !== lastDate) {
      updateClassLifecycle(today);
      lastDate = today;
      window.dispatchEvent(new CustomEvent('erb-date-changed', { detail: { date: today } }));
    }
  }
  limits.forEach(button => button.addEventListener('click', () => {
    limit = Number(button.dataset.nextCourseLimit);
    refresh();
  }));
  window.refreshErbDateUI = refresh;
  refresh();
  window.addEventListener('focus', refresh);
  window.addEventListener('pageshow', refresh);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  setInterval(refresh, 60000);
})();
