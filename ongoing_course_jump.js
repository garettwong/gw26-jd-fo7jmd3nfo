/* Open one ongoing class in the existing filtered calendar. */
(() => {
  const style = document.createElement('style');
  style.textContent = `
    .ongoing-course-jump{grid-column:1/-1;width:100%;min-height:44px;margin-top:6px;padding:10px 14px;border:1px solid #0f7074;border-radius:7px;background:#0f7074;color:#fff;font:800 14px/1.4 'Microsoft JhengHei','Segoe UI',sans-serif;cursor:pointer}
    .ongoing-course-jump:hover{background:#095d61}
    .ongoing-course-jump:focus-visible{outline:3px solid #d89a24;outline-offset:3px}
    @media print{.ongoing-course-jump{display:none}}
  `;
  document.head.append(style);
  document.querySelectorAll('#ongoingCourseList .ongoing-course-card[data-course-group]').forEach(card => {
    if (card.querySelector('.ongoing-course-jump')) return;
    const group = card.dataset.courseGroup;
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'ongoing-course-jump';
    button.textContent = '查看此班時間表 →';
    button.setAttribute('aria-label', '查看 ' + card.querySelector('h3').textContent + ' 的時間表，只顯示此班');
    button.addEventListener('click', () => {
      const previous = window.__cardCourseFilter;
      window.__cardCourseFilter = { group, previousFilter: previous ? previous.previousFilter : window.__courseFilter };
      window.__upcomingFilterState = null;
      window.__courseFilter = group;
      window.__modeCompareAnchor = null;
      syncCourseFilterUI();
      applyFilters();
      document.getElementById('calendarTab').click();
      // The date updater keeps nextDate current when the page stays open overnight.
      const cards = Array.from(document.querySelectorAll('.grid .chip')).filter(chip => chip.dataset.group === group);
      const dates = Array.from(new Set(cards.map(chip => chip.dataset.date))).sort();
      const next = card.dataset.nextDate;
      const today = window.erbTodayDate ? window.erbTodayDate() : '';
      const date = dates.includes(next) ? next : dates.find(day => day >= today) || dates[dates.length - 1];
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const portrait = matchMedia('(orientation: portrait) and (max-width: 820px)').matches;
        const target = Array.from(document.querySelectorAll((portrait ? '.agenda' : '.grid') + ' .chip'))
          .find(chip => chip.dataset.group === group && chip.dataset.date === date && chip.style.display !== 'none');
        if (!target) return;
        const previousScroll = document.documentElement.style.scrollBehavior;
        document.documentElement.style.scrollBehavior = 'auto';
        target.scrollIntoView({ block: portrait ? 'start' : 'center', inline: 'center', behavior: 'auto' });
        if (portrait) {
          const tabs = document.querySelector('.view-tabs');
          const offset = (tabs ? tabs.getBoundingClientRect().height : 48) + 12;
          window.scrollBy({ top: -offset, behavior: 'auto' });
        }
        document.documentElement.style.scrollBehavior = previousScroll;
        target.tabIndex = -1;
        target.focus({ preventScroll: true });
      }));
    });
    card.append(button);
  });
})();
