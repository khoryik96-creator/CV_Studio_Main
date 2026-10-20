import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile, mkdir} from 'node:fs/promises';
import {createServer} from 'node:http';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const require = createRequire(import.meta.url);
const {chromium} = require(process.env.POC_PLAYWRIGHT || 'playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const reader = await readFile(path.join(root, 'extension/reader.js'), 'utf8');
const html = body => `<!doctype html><html><body><main>${body}</main></body></html>`;
const candidate = (mode, suffix = 'a', extra = '') => `<${mode === 'standard' ? 'li class="reusable-search__result-container"' : 'article data-test-candidate-card'}>
  <a href="https://www.linkedin.com/${mode === 'standard' ? 'in/' : 'talent/profile/'}sample-${suffix}?tracking=1">Sample Person ${suffix}</a>
  <div>Finance Manager · Manufacturing · SAP · Regional reporting</div>${extra}</${mode === 'standard' ? 'li' : 'article'}>`;

test('real Chrome DOM: three layouts, duplicates, pagination, unavailable profiles and access checks', async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true, args: ['--disable-background-networking']});
  try {
    const context = await browser.newContext();
    let body = '';
    // Every request is intercepted. No LinkedIn request reaches the network.
    await context.route('**/*', route => route.fulfill({contentType: 'text/html', body: html(body)}));
    const page = await context.newPage();
    for (const mode of ['standard', 'lite', 'recruiter']) {
      body = candidate(mode) + candidate(mode) + candidate(mode, 'b') +
        '<div class="artdeco-pagination"><button class="artdeco-pagination__button--next" onclick="this.dataset.clicked=\'yes\'">Next</button></div>';
      await page.goto('https://www.linkedin.com/' + (mode === 'standard' ? 'search/results/people/' : 'talent/search'));
      await page.evaluate(reader);
      const snapshot = await page.evaluate(mode => SourcerReader.readSearch(mode), mode);
      assert.equal(snapshot.profiles.length, 2);
      assert.equal(snapshot.profiles[0].name, 'Sample Person a');
      assert.equal(snapshot.profiles[0].url.includes('?'), false);
      assert(snapshot.hasNext);
      await page.evaluate(([mode, signature]) => SourcerReader.next(mode, signature), [mode, snapshot.signature]);
      assert.equal(await page.locator('button').getAttribute('data-clicked'), 'yes');
      await assert.rejects(page.evaluate(mode => SourcerReader.next(mode, 'stale-page'), mode), /search changed/);
      await page.locator('button').evaluate(el => el.disabled = true);
      assert.equal((await page.evaluate(mode => SourcerReader.readSearch(mode), mode)).hasNext, false);
    }
    body = '<h1>Sample Person</h1><p>Finance Manager with manufacturing and SAP experience.</p><a href="/in/unrelated-person">Someone else</a>';
    await page.goto('https://www.linkedin.com/talent/profile/sample-a');
    await page.evaluate(reader);
    const profile = await page.evaluate(() => SourcerReader.readProfile('https://www.linkedin.com/talent/profile/sample-a'));
    assert.equal(profile.publicUrl, '');
    assert.equal(profile.name, 'Sample Person');
    await assert.rejects(page.evaluate(() => SourcerReader.readProfile('https://www.linkedin.com/talent/profile/different')), /profile changed/);
    body = candidate('standard');
    await page.goto('https://www.linkedin.com/checkpoint/challenge');
    await page.evaluate(reader);
    await assert.rejects(page.evaluate(() => SourcerReader.readSearch('standard')), /sign in or complete a check/);
    body = '<p>Unusual activity detected. Security verification required.</p>';
    await page.goto('https://www.linkedin.com/search/results/people/');
    await page.evaluate(reader);
    await assert.rejects(page.evaluate(() => SourcerReader.readSearch('standard')), /access or usage restriction/);
    await context.close();
  } finally { await browser.close(); }
});

test('real Chrome panel: session restore, escaped content, consent and readable layout', async () => {
  const files = new Set(['panel.html', 'panel.css', 'panel.js', 'core.js']);
  const server = createServer(async (request, response) => {
    const name = request.url.slice(1).split('?')[0];
    if (!files.has(name)) { response.writeHead(404).end(); return; }
    response.setHeader('Content-Type', name.endsWith('.js') ? 'text/javascript' : name.endsWith('.css') ? 'text/css' : 'text/html');
    response.end(await readFile(path.join(root, 'extension', name)));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const browser = await chromium.launch({channel: 'chrome', headless: true, args: ['--disable-background-networking']});
  try {
    const context = await browser.newContext({viewport: {width: 430, height: 1100}, deviceScaleFactor: 1});
    const errors = [];
    await context.route('**/*', route => {
      const url = route.request().url();
      if (url === 'http://127.0.0.1:5073/api/status') return route.fulfill({contentType: 'application/json', body: JSON.stringify({configured: true, run: null})});
      if (url.startsWith(`http://127.0.0.1:${port}/`)) return route.continue();
      return route.abort();
    });
    await context.addInitScript(() => {
      window.chrome = {storage: {session: {get: async () => ({pairing: 'synthetic-pairing', sourcer: {run: null, results: [
        {name: 'Sample Person A', url: 'https://www.linkedin.com/in/sample-a', score: 82, checked: true,
         evidence: ['Finance Manager · Manufacturing · SAP'], unknowns: ['Regional scope', 'Availability']},
        {name: '<img src=x onerror=alert(1)>', url: 'https://www.linkedin.com/in/sample-b', score: 65, checked: false,
         evidence: ['Accounting and reporting'], unknowns: ['SAP experience']}
      ]}}), set: async () => {}}}, tabs: {query: async () => [{id: 1, url: 'https://www.linkedin.com/search/results/people/'}]}};
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`http://127.0.0.1:${port}/panel.html`);
    await page.waitForFunction(() => document.querySelector('#count').textContent === '2');
    assert.equal(await page.locator('#results img').count(), 0);
    assert.match(await page.locator('#results').innerText(), /<img src=x/);
    assert.equal(await page.locator('#export').isEnabled(), true);
    await page.locator('#brief').fill('Finance managers in Klang Valley with SAP and manufacturing experience.');
    await page.locator('#start').click();
    assert.match(await page.locator('#status').innerText(), /Tick the DeepSeek/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const runtime = path.join(root, 'runtime'); await mkdir(runtime, {recursive: true});
    await page.screenshot({path: path.join(runtime, 'panel-sample.png'), fullPage: true});
    await page.locator('#clear').click();
    assert.equal(await page.locator('#count').textContent(), '0');
    assert.deepEqual(errors, []);
    await context.close();
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
});
