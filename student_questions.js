/* Student questions are stored by the existing central lesson editor. */
(() => {
  const APP = 'https://garett-erb-lesson-log.garettwong3.chatgpt.site';
  const style = document.createElement('style');
  style.textContent = `
    .lesson-log-enabled .chip.has-student-questions{padding-bottom:48px!important}
    .lesson-actions{position:absolute;bottom:5px;left:5px;right:5px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.8fr) minmax(0,1fr);gap:4px;z-index:3}
    .lesson-log-enabled .chip .lesson-actions [role=button]{position:static!important;display:flex;align-items:center;justify-content:center;box-sizing:border-box;width:auto!important;min-width:0!important;min-height:34px!important;height:auto!important;padding:3px!important;border:1px solid #0f7074;border-radius:4px;background:#fff;color:#0f6266;font:900 10px/1.2 'Segoe UI',sans-serif;text-align:center;white-space:normal;cursor:pointer;box-shadow:0 1px 2px rgba(20,30,50,.15)}
    .lesson-log-enabled .chip .lesson-actions .logged{background:#0f7074;color:#fff}
    .lesson-actions [role=button]:focus-visible{outline:3px solid #f2a900;outline-offset:2px}
    @media(max-width:820px) and (orientation:portrait){.lesson-log-enabled .chip .lesson-actions [role=button]{font-size:10px;min-height:36px!important}.lesson-log-enabled .chip.has-student-questions{padding-bottom:50px!important}}
    @media(orientation:landscape) and (max-height:540px){.lesson-actions{left:2px;right:2px;bottom:3px;gap:2px}.lesson-log-enabled .chip .lesson-actions [role=button]{font-size:6.5px;min-height:22px!important;padding:1px!important}.lesson-log-enabled .chip.has-student-questions{padding-bottom:31px!important}}
    @media print{.lesson-actions{display:none!important}.lesson-log-enabled .chip.has-student-questions{padding-bottom:4px!important}}
  `;
  document.head.append(style);
  document.querySelectorAll('.lesson-log-open').forEach(record => {
    const chip = record.closest('.chip');
    if (!chip || chip.querySelector('.student-questions-open')) return;
    const questions = document.createElement('span');
    questions.className = 'student-questions-open';
    questions.textContent = 'Student questions';
    questions.setAttribute('role', 'button'); questions.tabIndex = 0;
    questions.setAttribute('aria-label', 'Student questions — ' + [record.dataset.logClass, record.dataset.logDate, record.dataset.logLesson].filter(Boolean).join(' · '));
    const params = new URLSearchParams({ view: 'questions', date: record.dataset.logDate || '', class: record.dataset.logClass || '', lesson: record.dataset.logLesson || '', time: record.dataset.logTime || '' });
    const bytes = new TextEncoder().encode(record.dataset.logKey || '');
    const id = btoa(Array.from(bytes, byte => String.fromCharCode(byte)).join('')).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    const url = APP + '/lesson/' + encodeURIComponent(id) + '?' + params;
    questions.dataset.questionsUrl = url;
    const open = event => { event.preventDefault(); event.stopPropagation(); location.href = url; };
    questions.addEventListener('click', open);
    questions.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') open(event); });
    const actions = document.createElement('span'); actions.className = 'lesson-actions';
    const plan = chip.querySelector('.lesson-plan-open');
    if (plan) actions.append(plan);
    actions.append(questions, record); chip.append(actions); chip.classList.add('has-student-questions');
  });
})();
