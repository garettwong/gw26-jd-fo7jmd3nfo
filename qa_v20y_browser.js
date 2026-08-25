const { chromium } = require('C:/Users/garet/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('fs');
const http = require('http');
const path = require('path');

const root = process.cwd();
const origin = process.env.QA_ORIGIN || 'http://127.0.0.1:8792/';
const build = 'v20y-hk239-city-dec-first-lesson-marker-20260825a';
const versionId = '2026-08-25-V20y';
const targetLabel = 'HK239HG · 城市一條龍';
const writeKey = 'v20y-local-qa-write-key';
const ensure = (value, message) => { if (!value) throw new Error(message); };

function collectErrors(page) {
  const errors = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  return errors;
}

async function checkMarkerGeometry(page, expectedCount, viewportName) {
  const cards = page.locator('.chip[data-first-lesson="1"]:visible');
  ensure(await cards.count() === expectedCount, `${viewportName}: expected ${expectedCount} visible first-lesson cards`);
  const groups = await cards.evaluateAll(nodes => nodes.map(node => node.dataset.group));
  ensure(new Set(groups).size === expectedCount, `${viewportName}: first-lesson groups are not unique`);
  const metrics = await cards.evaluateAll(nodes => nodes.map(card => {
    const banner = card.querySelector('.first-lesson-banner');
    const status = card.querySelector('.status');
    const identity = card.querySelector('.class-id');
    const cardRect = card.getBoundingClientRect();
    const bannerRect = banner.getBoundingClientRect();
    const statusRect = status.getBoundingClientRect();
    const identityRect = identity.getBoundingClientRect();
    const overlap = (a, b) => !(
      a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top
    );
    const style = getComputedStyle(banner);
    return {
      text: banner.textContent.trim(),
      fontSize: parseFloat(style.fontSize),
      background: style.backgroundColor,
      color: style.color,
      insideCard: bannerRect.left >= cardRect.left - 1 && bannerRect.right <= cardRect.right + 1
        && bannerRect.top >= cardRect.top - 1 && bannerRect.bottom <= cardRect.bottom + 1,
      textFits: banner.scrollWidth <= banner.clientWidth + 1 && banner.scrollHeight <= banner.clientHeight + 1,
      overlapsStatus: overlap(bannerRect, statusRect),
      followsIdentity: bannerRect.top >= identityRect.bottom - 1,
    };
  }));
  for (const metric of metrics) {
    ensure(metric.text === '此班第一堂', `${viewportName}: marker text mismatch`);
    ensure(metric.fontSize >= 10, `${viewportName}: marker font is too small (${metric.fontSize}px)`);
    ensure(metric.background === 'rgb(255, 212, 59)', `${viewportName}: marker background mismatch`);
    ensure(metric.color === 'rgb(87, 24, 0)', `${viewportName}: marker text color mismatch`);
    ensure(metric.insideCard, `${viewportName}: marker escapes its card`);
    ensure(metric.textFits, `${viewportName}: marker text overflows`);
    ensure(!metric.overlapsStatus, `${viewportName}: marker overlaps status`);
    ensure(metric.followsIdentity, `${viewportName}: marker overlaps the cohort identity`);
  }
  return { count: expectedCount, groups: new Set(groups).size, minFontSize: Math.min(...metrics.map(item => item.fontSize)) };
}

async function checkTimetableViewport(browser, viewport, viewportName, screenshotName) {
  const context = await browser.newContext({
    viewport,
    isMobile: viewportName === 'phone',
    hasTouch: viewportName === 'phone',
    serviceWorkers: 'block',
  });
  const page = await context.newPage();
  const errors = collectErrors(page);
  await page.goto(`${origin}?today=2026-12-16&build=${build}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.version-menu-current');
  ensure((await page.locator('.version-menu-current').textContent()).trim() === 'V20y', `${viewportName}: current version mismatch`);
  ensure(await page.locator(`.version-menu-item[data-version-id="${versionId}"]`).count() === 1, `${viewportName}: V20y selector item missing`);
  ensure(await page.locator(`.version-menu-item[data-version-id="${versionId}"]`).getAttribute('data-build-id') === build, `${viewportName}: V20y build metadata mismatch`);

  const oldCards = page.locator('.chip', { hasText: '一條龍' }).filter({ has: page.locator('[data-date="2026-11-11"], [data-date="2026-11-12"], [data-date="2026-11-13"]') });
  ensure(await oldCards.count() === 0, `${viewportName}: old November target card remains`);
  for (const oldDate of ['2026-11-11', '2026-11-12', '2026-11-13']) {
    ensure(await page.locator(`.chip[data-date="${oldDate}"][data-group-label*="一條龍"]`).count() === 0, `${viewportName}: old target remains on ${oldDate}`);
  }

  const targetCards = page.locator(`.chip[data-group-label="${targetLabel}"]:visible`);
  ensure(await targetCards.count() === 6, `${viewportName}: expected six visible replacement cards`);
  const target = await targetCards.evaluateAll(nodes => nodes.map(node => ({
    date: node.dataset.date,
    text: node.textContent.replace(/\s+/g, ' ').trim(),
    room: node.dataset.teachingRoom,
    first: node.dataset.firstLesson === '1',
    changed: node.dataset.changed === '1',
    logKey: node.querySelector('.lesson-log-open')?.dataset.logKey || '',
    logOverlapsContent: (() => {
      const log = node.querySelector('.lesson-log-open');
      if (!log) return false;
      const a = log.getBoundingClientRect();
      return Array.from(node.querySelectorAll('.erb-foot, .assessment-reminder')).some(item => {
        const b = item.getBoundingClientRect();
        return !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);
      });
    })(),
  })).sort((a, b) => a.date.localeCompare(b.date) || a.text.localeCompare(b.text)));
  ensure(target.filter(item => item.date === '2026-12-16').length === 2, `${viewportName}: December 16 card count mismatch`);
  ensure(target.filter(item => item.date === '2026-12-17').length === 2, `${viewportName}: December 17 card count mismatch`);
  ensure(target.filter(item => item.date === '2026-12-18').length === 2, `${viewportName}: December 18 card count mismatch`);
  ensure(target.every(item => item.room === '102' && item.text.includes('課室102')), `${viewportName}: room 102 is not visible on every target card`);
  ensure(target.every(item => item.changed), `${viewportName}: replacement cards lack V20y change marking`);
  ensure(target.every(item => item.logKey), `${viewportName}: lesson-log trigger/key missing from a target card`);
  ensure(target.every(item => !item.logOverlapsContent), `${viewportName}: lesson-log button overlaps target lesson text`);
  ensure(target.filter(item => item.first).length === 1, `${viewportName}: target cohort must have one first-lesson card`);
  ensure(target.find(item => item.first)?.date === '2026-12-16', `${viewportName}: target first-lesson date mismatch`);
  ensure(target.some(item => item.text.includes('持續評估／小組討論／專題報告')), `${viewportName}: L5 assessment note missing`);
  ensure(target.some(item => item.text.includes('期末考試 15:30-16:30')), `${viewportName}: L6 final-exam note missing`);

  const marker = await checkMarkerGeometry(page, 17, viewportName);
  const bodyWidth = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
  ensure(bodyWidth.scroll <= bodyWidth.client + 1, `${viewportName}: page has horizontal overflow (${bodyWidth.scroll} > ${bodyWidth.client})`);
  const l1 = targetCards.filter({ hasText: 'Lesson 1' }).first();
  await l1.scrollIntoViewIfNeeded();
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(root, screenshotName), fullPage: false });
  ensure(errors.length === 0, `${viewportName}: browser errors: ${errors.join('; ')}`);
  await context.close();
  return { targetCards: target.length, marker, bodyWidth, browserErrors: errors };
}

async function checkMasterSelector(browser) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
  const page = await context.newPage();
  const errors = collectErrors(page);
  await page.goto(`${origin}master/`, { waitUntil: 'networkidle' });
  const first = page.locator('.version').first();
  const href = await first.getAttribute('href');
  ensure((await first.textContent()).includes('V20y'), 'master selector does not promote V20y');
  ensure(href.includes(`versions/${versionId}/`), 'master V20y href mismatch');
  ensure(await first.locator('.latest').count() === 1, 'master V20y latest badge missing');
  ensure(errors.length === 0, `master selector browser errors: ${errors.join('; ')}`);
  await context.close();
  return { latest: 'V20y', href };
}

async function checkSalary(browser) {
  const key = fs.readFileSync(path.join(root, 'private_earnings_key.txt'), 'utf8').trim();
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, serviceWorkers: 'block' });
  const page = await context.newPage();
  const errors = collectErrors(page);
  await page.goto(`${origin}earnings/#key=${encodeURIComponent(key)}`, { waitUntil: 'networkidle' });
  await page.waitForSelector(`[data-version="${versionId}"]`);
  ensure(await page.locator(`[data-version="${versionId}"]`).count() === 1, 'salary selector is missing V20y');
  ensure(await page.locator(`[data-version="${versionId}"] .latest`).count() === 1, 'salary selector does not mark V20y latest');

  await page.goto(`${origin}earnings/versions/${versionId}/#key=${encodeURIComponent(key)}`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.querySelector('#grand')?.textContent.trim().startsWith('HK$'));
  ensure((await page.locator('#subtitle').textContent()).includes('V20y'), 'salary report subtitle is not V20y');
  ensure((await page.locator('#grand').textContent()).trim() === 'HK$139,750', 'confirmed salary total mismatch');
  ensure((await page.locator('#events').textContent()).trim() === '147', 'confirmed counted-entry total mismatch');
  const november = page.locator('#rows tr', { hasText: 'November' });
  const december = page.locator('#rows tr', { hasText: 'December' });
  ensure((await november.textContent()).includes('26') && (await november.textContent()).includes('HK$7,800'), 'November salary row mismatch');
  ensure((await december.textContent()).includes('18') && (await december.textContent()).includes('HK$5,400'), 'December salary row mismatch');
  const targetRow = page.locator('#expectedRows tr', { hasText: '城市一條龍' });
  ensure(await targetRow.count() === 1, 'target expected-payment row missing');
  const targetText = (await targetRow.textContent()).replace(/\s+/g, ' ');
  for (const token of ['2026-12-18', '2027-01-08', '18 hours', 'HK$5,400']) {
    ensure(targetText.includes(token), `target expected-payment row missing ${token}`);
  }
  await targetRow.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(root, 'qa_v20y_salary_phone.png'), fullPage: false });
  ensure(errors.length === 0, `salary browser errors: ${errors.join('; ')}`);
  await context.close();
  return { latest: 'V20y', confirmedTotal: 'HK$139,750', countedEntries: 147, novemberHours: 26, decemberHours: 18, expectedPayment: '2027-01-08', browserErrors: errors };
}

function installLessonLogMock(context, store) {
  return context.route('https://garett-erb-lesson-log.garettwong3.chatgpt.site/**', async route => {
    const request = route.request();
    const lessonId = decodeURIComponent(new URL(request.url()).pathname.split('/').pop());
    if (request.method() === 'GET') {
      const saved = store.get(lessonId);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(saved || { content: '', updated_at: null }),
      });
      return;
    }
    if (request.method() === 'PUT') {
      ensure(request.headers().authorization === `Bearer ${writeKey}`, 'lesson-log write authorization mismatch');
      const payload = request.postDataJSON();
      const saved = { content: payload.content, updated_at: '2026-08-25T08:30:00.000Z' };
      store.set(lessonId, saved);
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(saved) });
      return;
    }
    await route.fulfill({ status: 405, contentType: 'application/json', body: JSON.stringify({ error: 'Method not allowed' }) });
  });
}

async function openTargetLog(page) {
  const card = page.locator(`.chip[data-date="2026-12-16"][data-group-label="${targetLabel}"]:visible`, { hasText: 'Lesson 1' }).first();
  ensure(await card.count() === 1, 'target L1 lesson-log card missing');
  const button = card.locator('.lesson-log-open');
  ensure(await button.isVisible(), 'target L1 lesson-log trigger is not visible');
  await button.click();
  await page.waitForSelector('#lessonLogModal:not([hidden])');
}

async function checkLessonLog(browser) {
  const store = new Map();
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, serviceWorkers: 'block' });
  const desktop = await browser.newContext({ viewport: { width: 1920, height: 1080 }, serviceWorkers: 'block' });
  await installLessonLogMock(phone, store);
  await installLessonLogMock(desktop, store);
  const phonePage = await phone.newPage();
  const desktopPage = await desktop.newPage();
  const phoneErrors = collectErrors(phonePage);
  const desktopErrors = collectErrors(desktopPage);
  await phonePage.goto(`${origin}#lesson-log-key=${encodeURIComponent(writeKey)}`, { waitUntil: 'networkidle' });
  ensure(!phonePage.url().includes('lesson-log-key='), 'lesson-log key remained in the phone URL');
  await openTargetLog(phonePage);
  await phonePage.waitForFunction(() => (document.querySelector('#lessonLogStatus')?.textContent || '').includes('尚未有記錄'));
  await phonePage.locator('#lessonLogTaught').fill('magic layers\nflip\nflip');
  await phonePage.locator('#lessonLogSave').click();
  await phonePage.waitForFunction(() => (document.querySelector('#lessonLogStatus')?.textContent || '').includes('其他裝置會自動更新'));
  ensure(await phonePage.locator('#lessonLogTaught').inputValue() === '• Magic Layers\n• Flip', 'phone lesson text was not normalized');

  await desktopPage.goto(`${origin}#lesson-log-key=${encodeURIComponent(writeKey)}`, { waitUntil: 'networkidle' });
  ensure(!desktopPage.url().includes('lesson-log-key='), 'lesson-log key remained in the desktop URL');
  await openTargetLog(desktopPage);
  await desktopPage.waitForFunction(() => (document.querySelector('#lessonLogStatus')?.textContent || '').includes('已讀取最新記錄'));
  ensure(await desktopPage.locator('#lessonLogTaught').inputValue() === '• Magic Layers\n• Flip', 'desktop did not read the phone record');
  const errors = [...phoneErrors, ...desktopErrors];
  ensure(errors.length === 0, `lesson-log browser errors: ${errors.join('; ')}`);
  await phone.close();
  await desktop.close();
  return { localMockOnly: true, phoneSave: true, desktopAutoRead: true, normalizedText: true, liveRecordsModified: false, browserErrors: errors };
}

async function run() {
  const local = !process.env.QA_ORIGIN;
  let server;
  let browser;
  try {
    if (local) {
      server = http.createServer((request, response) => {
        const requestPath = decodeURIComponent(new URL(request.url, origin).pathname);
        let filePath = path.join(root, requestPath.replace(/^\/+/, ''));
        if (requestPath.endsWith('/')) filePath = path.join(filePath, 'index.html');
        fs.readFile(filePath, (error, data) => {
          if (error) { response.writeHead(404); response.end('Not found'); return; }
          const mime = {
            '.html': 'text/html; charset=utf-8',
            '.json': 'application/json; charset=utf-8',
            '.js': 'text/javascript; charset=utf-8',
            '.webmanifest': 'application/manifest+json; charset=utf-8',
            '.png': 'image/png',
          }[path.extname(filePath)] || 'application/octet-stream';
          response.writeHead(200, { 'Content-Type': mime, 'Cache-Control': 'no-store' });
          response.end(data);
        });
      });
      await new Promise(resolve => server.listen(8792, '127.0.0.1', resolve));
    }
    browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
    const desktop = await checkTimetableViewport(browser, { width: 2560, height: 1440 }, 'desktop', 'qa_v20y_desktop2k.png');
    const phone = await checkTimetableViewport(browser, { width: 390, height: 844 }, 'phone', 'qa_v20y_phone.png');
    const master = await checkMasterSelector(browser);
    const salary = await checkSalary(browser);
    const lessonLog = await checkLessonLog(browser);
    const results = { result: 'PASS', versionId, build, desktop, phone, master, salary, lessonLog };
    fs.writeFileSync(path.join(root, 'qa_v20y_browser_results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally {
    if (browser) await browser.close();
    if (server) {
      if (typeof server.closeAllConnections === 'function') server.closeAllConnections();
      await new Promise(resolve => server.close(resolve));
    }
  }
}

run().catch(error => { console.error(error); process.exitCode = 1; });
