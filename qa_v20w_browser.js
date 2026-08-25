const { chromium } = require('C:/Users/garet/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('fs');
const http = require('http');
const path = require('path');

const root = process.cwd();
const origin = process.env.QA_ORIGIN || 'http://127.0.0.1:8790/';
const build = 'v20w-simple-synced-lesson-log-20260825a';
const versionId = '2026-08-25-V20w';
const config = { owner: 'garettwong', repo: 'erb-lesson-log', token: 'qa-token' };
const expectedText = '• Magic Layers\n• Flip\n• Remove Background\n• Change Color';
const ensure = (value, message) => { if (!value) throw new Error(message); };

let remoteStore = { schema_version: 2, updated_at: null, notes: {} };
let remoteSha = 'qa-sha-1';

function encode(value) {
  return Buffer.from(value, 'utf8').toString('base64');
}

async function installPrivateStoreMock(context) {
  await context.addInitScript(value => {
    localStorage.setItem('erbLessonLogConfigV1', JSON.stringify(value));
  }, config);
  await context.route('https://api.github.com/repos/garettwong/erb-lesson-log/contents/lesson-notes.json', async route => {
    const request = route.request();
    if (request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sha: remoteSha, content: encode(JSON.stringify(remoteStore)) }),
      });
      return;
    }
    if (request.method() === 'PUT') {
      const payload = request.postDataJSON();
      ensure(payload.sha === remoteSha, 'PUT did not preserve the latest remote SHA');
      remoteStore = JSON.parse(Buffer.from(payload.content, 'base64').toString('utf8'));
      remoteSha = `qa-sha-${Number(remoteSha.split('-').pop()) + 1}`;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ content: { sha: remoteSha } }),
      });
      return;
    }
    await route.abort();
  });
}

async function openTimetable(page) {
  await page.goto(`${origin}?today=2026-08-24&build=${build}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.version-menu-current');
  ensure((await page.locator('.version-menu-current').textContent()).trim() === 'V20w', 'version mismatch');
  await page.locator('.mode-option[data-mode="mine-confirmed"]').click();
}

async function lessonButton(page) {
  const candidates = page.locator('.chip.has-lesson-log[data-date="2026-08-24"]:visible', { hasText: 'HK244HG' });
  const count = await candidates.count();
  for (let index = 0; index < count; index += 1) {
    const card = candidates.nth(index);
    if (/Lesson 4|L4/.test(await card.textContent())) return card.locator('.lesson-log-open');
  }
  throw new Error('August 24 HK244HG Lesson 4 card missing');
}

function collectErrors(page) {
  const errors = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  return errors;
}

async function checkDesktopSave(browser) {
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  await installPrivateStoreMock(context);
  const page = await context.newPage();
  const errors = collectErrors(page);
  await openTimetable(page);
  const button = await lessonButton(page);
  const key = await button.getAttribute('data-log-key');
  ensure(key, 'lesson log key missing');

  remoteStore = {
    schema_version: 1,
    updated_at: '2026-08-24T10:00:00.000Z',
    notes: {
      [key]: {
        taught: 'Magic layers',
        progress: '完成示範',
        follow_up: '下堂練習',
        remarks: '舊記錄保留測試',
        updated_at: '2026-08-24T10:00:00.000Z',
      },
    },
  };

  await button.click();
  await page.waitForFunction(() => document.querySelector('#lessonLogStatus')?.textContent.includes('已讀取最新記錄'));
  ensure(await page.locator('#lessonLogModal textarea').count() === 1, 'modal must contain exactly one textarea');
  ensure(await page.locator('#lessonLogProgress, #lessonLogFollowUp, #lessonLogRemarks, #lessonLogSync').count() === 0, 'old controls remain');
  ensure((await page.locator('#lessonLogSave').textContent()).trim() === '整理並儲存', 'save label mismatch');
  ensure(await page.locator('#lessonLogSettings').isHidden(), 'technical settings are visible during normal use');
  const legacy = await page.locator('#lessonLogTaught').inputValue();
  ensure(legacy.includes('Magic layers'), 'legacy taught field was lost');
  ensure(legacy.includes('進度／未完成：完成示範'), 'legacy progress field was lost');
  ensure(legacy.includes('功課／下堂跟進：下堂練習'), 'legacy follow-up field was lost');
  ensure(legacy.includes('其他備註：舊記錄保留測試'), 'legacy remarks field was lost');
  const minHeight = await page.locator('#lessonLogTaught').evaluate(node => parseFloat(getComputedStyle(node).minHeight));
  ensure(minHeight >= 300, `desktop textarea is too small: ${minHeight}px`);

  await page.locator('#lessonLogTaught').fill('Magic layers\nFlip\nRemove background\nChange color\nflip');
  await page.locator('#lessonLogSave').click();
  await page.waitForFunction(() => document.querySelector('#lessonLogStatus')?.textContent.includes('已整理、儲存並同步'));
  ensure(await page.locator('#lessonLogTaught').inputValue() === expectedText, 'saved text was not normalized');
  ensure(remoteStore.schema_version === 2, 'remote schema was not upgraded');
  ensure(remoteStore.notes[key]?.combined_text === expectedText, 'remote combined text mismatch');
  ensure(remoteStore.notes[key]?.progress === '完成示範', 'legacy fields were not preserved remotely');
  await page.screenshot({ path: path.join(root, 'qa_v20w_lesson_log_desktop.png'), fullPage: false });
  ensure(errors.length === 0, `desktop browser errors: ${errors.join('; ')}`);
  await context.close();
  return { key, minHeight, polished: expectedText, legacyPreserved: true };
}

async function checkPhoneAutoRead(browser) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await installPrivateStoreMock(context);
  const page = await context.newPage();
  const errors = collectErrors(page);
  await openTimetable(page);
  await (await lessonButton(page)).click();
  await page.waitForFunction(() => document.querySelector('#lessonLogStatus')?.textContent.includes('已讀取最新記錄'));
  ensure(await page.locator('#lessonLogTaught').inputValue() === expectedText, 'phone did not auto-read the desktop record');
  ensure(await page.locator('#lessonLogSettings').isHidden(), 'phone exposes technical settings during normal use');
  const box = await page.locator('#lessonLogTaught').boundingBox();
  ensure(box && box.height >= 340, `phone textarea is too small: ${box ? box.height : 0}px`);
  await page.screenshot({ path: path.join(root, 'qa_v20w_lesson_log_phone.png'), fullPage: false });
  ensure(errors.length === 0, `phone browser errors: ${errors.join('; ')}`);
  await context.close();
  return { autoRead: true, textareaHeight: Math.round(box.height), settingsHidden: true };
}

async function checkSalary(browser) {
  const key = fs.readFileSync(path.join(root, 'private_earnings_key.txt'), 'utf8').trim();
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  await page.goto(`${origin}earnings/versions/${versionId}/#key=${key}`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelector('#grand')?.textContent.trim().startsWith('HK$'));
  const confirmed = (await page.locator('#grand').textContent()).trim();
  ensure(confirmed === 'HK$139,750', `V20w confirmed salary changed: ${confirmed}`);
  await context.close();
  return { confirmed, matchesV20v: true };
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
            '.html': 'text/html; charset=utf-8', '.json': 'application/json; charset=utf-8',
            '.js': 'text/javascript; charset=utf-8', '.webmanifest': 'application/manifest+json; charset=utf-8', '.png': 'image/png',
          }[path.extname(filePath)] || 'application/octet-stream';
          response.writeHead(200, { 'Content-Type': mime, 'Cache-Control': 'no-store' });
          response.end(data);
        });
      });
      await new Promise(resolve => server.listen(8790, '127.0.0.1', resolve));
    }
    browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
    const desktop = await checkDesktopSave(browser);
    const phone = await checkPhoneAutoRead(browser);
    const salary = await checkSalary(browser);
    const results = { build, versionId, desktop, phone, salary, result: 'PASS' };
    fs.writeFileSync(path.join(root, 'qa_v20w_browser_results.json'), JSON.stringify(results, null, 2));
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
