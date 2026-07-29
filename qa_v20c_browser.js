const { chromium } = require('C:/Users/garet/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('fs');
const http = require('http');
const path = require('path');

const root = process.cwd();
const siteRoot = 'http://127.0.0.1:8782/';
const build = 'v20c-full-upcoming-source-reconciliation-20260730a';
const base = `${siteRoot}?today=2026-07-30&build=${build}`;
const tracePath = `${root}/qa_v20c_trace.txt`;
function trace(message) {
  fs.appendFileSync(tracePath, `${new Date().toISOString()} ${message}\n`);
}

function ensure(value, message) {
  if (!value) throw new Error(message);
}

async function visibleCount(locator) {
  return locator.evaluateAll(nodes => nodes.filter(node => {
    const style = getComputedStyle(node);
    return style.display !== 'none' &&
      style.visibility !== 'hidden' &&
      node.getClientRects().length > 0;
  }).length);
}

function daySelector(width, date) {
  return `${width < 700 ? '#a-d-' : '#d-'}${date}`;
}

async function checkViewport(browser, name, viewport, mobile) {
  trace(`${name}: start`);
  const context = await browser.newContext({
    viewport,
    isMobile: mobile,
    hasTouch: mobile,
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  const errors = [];
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base, { waitUntil: 'domcontentloaded' });
  trace(`${name}: loaded`);
  await page.waitForTimeout(300);

  ensure(
    (await page.locator('.version-menu-current').textContent()).trim() === 'V20c',
    `${name}: V20c is not current`,
  );
  ensure(
    (await page.locator('.version-menu-summary').textContent()).includes('MC106DS'),
    `${name}: V20c summary is wrong`,
  );
  trace(`${name}: version checked`);

  const allCards = page.locator('.chip');
  ensure(
    await visibleCount(allCards) === 332,
    `${name}: visible display count is not 332`,
  );
  ensure(
    await page.locator('.chip[data-text*="HK280HG"][data-text*="Class SS"]').count() === 0,
    `${name}: superseded HK280HG SS is still visible`,
  );
  trace(`${name}: display checked`);

  const mcCards = page.locator('.chip[data-text*="MC0106DS"]');
  ensure(
    await visibleCount(mcCards) === 47,
    `${name}: visible MC0106DS card count is not 47`,
  );
  const teacherCounts = {
    Garett: await visibleCount(mcCards.filter({ hasText: 'Teacher: Garett' })),
    Demian: await visibleCount(mcCards.filter({ hasText: 'Teacher: Demian Yuen' })),
    Calvin: await visibleCount(mcCards.filter({ hasText: 'Teacher: Calvin' })),
    Melody: await visibleCount(mcCards.filter({ hasText: 'Teacher: Melody' })),
    Ricky: await visibleCount(mcCards.filter({ hasText: 'Teacher: Ricky Leung' })),
  };
  ensure(
    JSON.stringify(teacherCounts) === JSON.stringify({
      Garett: 6, Demian: 29, Calvin: 8, Melody: 2, Ricky: 2,
    }),
    `${name}: MC0106DS teacher counts are wrong: ${JSON.stringify(teacherCounts)}`,
  );
  trace(`${name}: teachers checked`);

  await page.locator('.mode-option[data-mode="mine-confirmed"]').click();
  const aug14 = page.locator(daySelector(viewport.width, '2026-08-14'));
  const aug14Transit = aug14.locator('.transit-bar.tight');
  ensure(await aug14Transit.count() === 1, `${name}: Aug 14 tight transit bar missing`);
  const aug14TransitText = (await aug14Transit.innerText()).replace(/\s+/g, ' ');
  ensure(
    aug14TransitText.includes('40m transit') &&
      aug14TransitText.includes('20m spare') &&
      aug14TransitText.includes('NO MEAL BUFFER'),
    `${name}: Aug 14 transit text is wrong: ${aug14TransitText}`,
  );

  const oct7 = page.locator(daySelector(viewport.width, '2026-10-07'));
  const oct7TransitText = (await oct7.locator('.transit-bar').first().innerText())
    .replace(/\s+/g, ' ');
  ensure(
    oct7TransitText.includes('64m transit') && oct7TransitText.includes('56m spare'),
    `${name}: Oct 7 transit text is wrong: ${oct7TransitText}`,
  );
  trace(`${name}: transit checked`);

  ensure(
    await visibleCount(mcCards) === 6,
    `${name}: ME CONF does not show exactly six MC Garett lessons`,
  );
  await page.locator('.mode-option[data-mode="mine-all"]').click();
  ensure(
    await visibleCount(mcCards) === 6,
    `${name}: ME ALL does not show exactly six MC Garett lessons`,
  );
  await page.locator('.mode-option[data-mode="both"]').click();
  ensure(
    await visibleCount(mcCards) === 47,
    `${name}: ALL FULL does not restore all 47 MC lessons`,
  );
  trace(`${name}: modes checked`);

  await page.locator('#spansTab').click({ force: true });
  trace(`${name}: spans clicked`);
  ensure(await page.locator('.span-row').count() === 18, `${name}: class-span count is not 18`);
  ensure(errors.length === 0, `${name}: browser errors: ${errors.join('; ')}`);

  await page.locator('#calendarTab').click({ force: true });
  await aug14.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${root}/qa_v20c_${name}.png`, fullPage: false });
  trace(`${name}: screenshot`);
  await context.close();
  trace(`${name}: context closed`);
  return { name, aug14TransitText, oct7TransitText };
}

async function checkSalary(browser) {
  trace('salary: start');
  const key = fs.readFileSync(`${root}/private_earnings_key.txt`, 'utf8').trim();
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  const errors = [];
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${siteRoot}earnings/#key=${key}`, { waitUntil: 'domcontentloaded' });
  trace('salary: loaded');
  ensure(
    await page.locator('[data-version="2026-07-30-V20c"]').count() === 1,
    'salary V20c missing',
  );
  await page.locator('[data-version="2026-07-30-V20c"]').click({ force: true });
  await page.waitForURL(/\/earnings\/versions\/2026-07-30-V20c\//, {
    timeout: 15000,
    waitUntil: 'domcontentloaded',
  });
  trace('salary: version selected');
  await page.waitForFunction(
    () => document.querySelector('#grand')?.textContent.trim().startsWith('HK$'),
  );
  const confirmed = (await page.locator('#grand').textContent()).trim();
  trace('salary: confirmed checked');
  await page.getByRole('button', { name: 'Confirmed + unconfirmed' }).click();
  const all = (await page.locator('#grand').textContent()).trim();
  trace('salary: all checked');
  ensure(confirmed === 'HK$187,450', `confirmed salary mismatch: ${confirmed}`);
  ensure(all === 'HK$187,450', `all salary mismatch: ${all}`);
  ensure(errors.length === 0, `salary browser errors: ${errors.join('; ')}`);
  await page.screenshot({ path: `${root}/qa_v20c_salary.png`, fullPage: false });
  await context.close();
  trace('salary: context closed');
  return { confirmed, all };
}

(async () => {
  fs.writeFileSync(tracePath, '');
  const server = http.createServer((request, response) => {
    const requestPath = decodeURIComponent(new URL(request.url, siteRoot).pathname);
    let filePath = path.join(root, requestPath.replace(/^\/+/, ''));
    if (requestPath.endsWith('/')) filePath = path.join(filePath, 'index.html');
    fs.readFile(filePath, (error, data) => {
      if (error) {
        response.writeHead(404);
        response.end('Not found');
        return;
      }
      const mime = {
        '.html': 'text/html; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.js': 'text/javascript; charset=utf-8',
        '.webmanifest': 'application/manifest+json; charset=utf-8',
        '.png': 'image/png',
      }[path.extname(filePath)] || 'application/octet-stream';
      response.writeHead(200, {
        'Content-Type': mime,
        'Connection': 'close',
      });
      response.end(data);
    });
  });
  let browser;
  try {
    await new Promise(resolve => server.listen(8782, '127.0.0.1', resolve));
    trace('server listening');
    browser = await chromium.launch({
      headless: true,
      executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    });
    trace('browser launched');
    const checks = [];
    checks.push(await checkViewport(
      browser, 'desktop2k', { width: 2560, height: 1440 }, false,
    ));
    process.stdout.write('desktop2k passed\n');
    checks.push(await checkViewport(
      browser, 'desktop4k', { width: 3840, height: 2160 }, false,
    ));
    process.stdout.write('desktop4k passed\n');
    checks.push(await checkViewport(
      browser, 'phone', { width: 390, height: 844 }, true,
    ));
    process.stdout.write('phone passed\n');
    checks.push(await checkViewport(
      browser, 'landscape', { width: 844, height: 390 }, true,
    ));
    process.stdout.write('landscape passed\n');
    const salary = await checkSalary(browser);
    process.stdout.write('salary passed\n');
    const result = { checks, salary };
    fs.writeFileSync(
      `${root}/qa_v20c_browser_results.json`,
      JSON.stringify(result, null, 2),
    );
    process.stdout.write(`${JSON.stringify(result)}\n`);
  } finally {
    if (browser) {
      await Promise.race([
        browser.close(),
        new Promise(resolve => setTimeout(resolve, 5000)),
      ]);
    }
    server.closeAllConnections();
    server.close();
    server.unref();
  }
})().catch(error => {
  process.stderr.write(`${error.stack}\n`);
  process.exitCode = 1;
}).finally(() => {
  setTimeout(() => process.exit(process.exitCode || 0), 100);
});
