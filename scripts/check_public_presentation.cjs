// Browser QA for the generated public site. Run after the public export gate.
// Usage: NODE_PATH=<playwright node_modules> node scripts/check_public_presentation.cjs <public-dir> <evidence-dir>
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');

(async () => {
  const root = path.resolve(process.argv[2] || 'release-gate/public');
  const evidence = path.resolve(process.argv[3] || 'release-gate/browser-qa');
  fs.mkdirSync(evidence, { recursive: true });
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const file = path.resolve(root, `.${pathname}`, pathname.endsWith('/') ? 'index.html' : '');
    if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
    try {
      res.setHeader('Content-Type', file.endsWith('.json') ? 'application/json' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream');
      res.end(fs.readFileSync(file));
    } catch { res.writeHead(404).end('Not found'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  let browser;
  const results = [];
  try {
    browser = await chromium.launch();
    for (const [device, width, height] of [['desktop', 1440, 1000], ['mobile', 390, 844]]) {
      const page = await browser.newPage({ viewport: { width, height } });
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
      for (const route of ['/', '/docs/', '/writing/', '/writing/what-the-ais-think-about-dotrepo/', '/repositories/', '/efficiency/']) {
        await page.goto(origin + route);
        await page.waitForLoadState('networkidle');
        assert.equal(new URL(page.url()).pathname, route);
        assert.match(await page.title(), /dotrepo/i);
        assert.ok((await page.locator('h1').textContent()).trim());
        assert.equal(await page.locator('vite-error-overlay, nextjs-portal').count(), 0);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `Horizontal overflow: ${device} ${route}`);
        if (route === '/docs/') {
          assert.equal(await page.locator('.start-paths a').count(), 3);
          const bounds = await page.locator('.start-paths a').first().boundingBox();
          assert.ok(bounds.y < height, 'First getting-started path must be visible without scrolling');
        }
        if (route === '/repositories/') {
          const search = page.locator('#repository-search');
          const cap = page.locator('#repository-cap-note');
          await search.fill('BurntSushi/ripgrep');
          assert.equal(await page.locator('.repo-card').count(), 1);
          assert.equal(await cap.isVisible(), false);
          assert.equal(await page.locator('#repository-load-more').isVisible(), false);
          await search.fill('zzzzzz-no-such-repository');
          assert.equal(await page.locator('#repository-no-results').isVisible(), true);
          assert.equal(await cap.isVisible(), false);
          await search.fill('');
          assert.equal(await cap.isVisible(), true);
          await page.locator('#repository-load-more').click();
          await page.locator('#repository-load-more').click();
          assert.equal(await page.locator('.repo-card').count(), 180);
          while (await page.locator('#repository-load-more').isVisible()) await page.locator('#repository-load-more').click();
          assert.equal(await cap.isVisible(), false);
          await search.fill('BurntSushi/ripgrep');
          assert.equal(await page.locator('.repo-card').count(), 1);
          assert.equal(await cap.isVisible(), false);
        }
        if (route === '/') {
          const config = await page.locator('#integrate pre').nth(2).textContent();
          assert.equal(JSON.parse(config).mcpServers.dotrepo.command, 'dotrepo-mcp');
          const summary = page.getByText('Inspect this export’s selection JSON', { exact: true });
          await summary.click();
          assert.equal(await summary.locator('..').getAttribute('open'), '');
          await summary.click();
          assert.equal(await summary.locator('..').getAttribute('open'), null);
          await page.locator('#repo-lookup-input').fill('bad');
          await page.locator('#repo-lookup-trust').click();
          assert.equal(await page.locator('#repo-lookup-feedback').getAttribute('data-state'), 'error');
          await page.locator('#repo-lookup-input').fill('BurntSushi/ripgrep');
          await page.getByRole('button', { name: 'Open profile', exact: true }).click();
          await page.waitForURL('**/BurntSushi/ripgrep/profile.json');
          await page.goBack();
          await page.locator('#repo-lookup-input').fill('BurntSushi/ripgrep');
          await page.locator('#repo-lookup-trust').click();
          await page.waitForURL('**/BurntSushi/ripgrep/trust.json');
          await page.goBack();
        }
        assert.deepEqual(errors, [], `${device} ${route} console errors`);
        await page.evaluate(() => scrollTo(0, 0));
        const filename = `${device}-${route.replaceAll('/', '-') || 'home'}.png`;
        await page.screenshot({ path: path.join(evidence, filename), fullPage: true });
        results.push({ device, width, height, route, title: await page.title(), passed: true, screenshot: filename });
      }
      await page.close();
    }
  } finally {
    fs.writeFileSync(path.join(evidence, 'results.json'), JSON.stringify(results, null, 2) + '\n');
    if (browser) await browser.close();
    server.close();
  }
  console.log(JSON.stringify(results, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
