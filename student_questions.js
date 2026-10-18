/* Student questions are stored by the existing central lesson editor. */
(() => {
  const APP = 'https://garett-erb-lesson-log.garettwong3.chatgpt.site';
  const style = document.createElement('style');
  style.textContent = `
    .lesson-log-enabled .chip.has-student-questions{padding-bottom:48px!important}
    .lesson-actions{position:absolute;bottom:5px;left:5px;right:5px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.8fr) minmax(0,1fr);gap:4px;z-index:3}
    .lesson-log-enabled .chip .lesson-actions [role=button]{position:static!important;display:flex;align-items:center;justify-content:center;box-sizing:border-box;width:auto!important;min-width:0!important;min-height:34px!important;height:auto!important;padding:3px!important;border:1px solid #0f7074;border-radius:4px;background:#fff;color:#0f6266;font:900 10px/1.2 'Segoe UI',sans-serif;text-align:center;white-space:normal;cursor:pointer;box-shadow:0 1px 2px rgba(20,30,50,.15)}
    .lesson-log-enabled .chip .lesson-actions .logged{background:#0f7074;color:#fff}
    .lesson-log-enabled .chip .lesson-actions .student-questions-open.questions-recorded{background:#15803d;color:#fff;border-color:#166534}
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
    questions.dataset.questionId = id;
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
  const buttons = Array.from(document.querySelectorAll('.student-questions-open'));
  let running = false, refreshAgain = false;
  async function refreshQuestions() {
    if (document.hidden) return;
    if (running) { refreshAgain = true; return; }
    running = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(APP + '/api/question-status', { cache: 'no-store', signal: controller.signal });
      if (!response.ok) throw new Error('Question status unavailable');
      const data = await response.json();
      if (data.complete !== true || !Array.isArray(data.recorded) || data.recorded.some(id => typeof id !== 'string')) throw new Error('Incomplete status');
      const recorded = new Set(data.recorded);
      buttons.forEach(button => {
        const saved = recorded.has(button.dataset.questionId);
        button.classList.toggle('questions-recorded', saved);
        const label = saved ? '已儲存學生問題；按此查看或修改' : '尚未記錄學生問題；按此填寫';
        button.title = label;
        button.setAttribute('aria-label', label);
      });
    } catch {
      buttons.forEach(button => { button.title = '暫時未能核對學生問題，會自動重試；按此仍可查看或編輯'; });
    } finally {
      clearTimeout(timeout); running = false;
      if (refreshAgain) { refreshAgain = false; void refreshQuestions(); }
    }
  }
  void refreshQuestions();
  ['focus', 'pageshow', 'online'].forEach(name => window.addEventListener(name, () => void refreshQuestions()));
  document.addEventListener('visibilitychange', () => void refreshQuestions());
  window.addEventListener('message', event => {
    if (event.origin === APP && event.data?.type === 'erb-student-questions-saved') void refreshQuestions();
  });
  setInterval(() => void refreshQuestions(), 15000);
})();
