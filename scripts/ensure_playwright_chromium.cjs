// The browser cache contains binaries, not this runner's operating-system libraries.
// Run after `playwright install chromium`; repair dependencies once if a real
// launch fails, then require a successful second launch before presentation QA.
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const { chromium } = require('playwright');

async function probe() {
  const browser = await chromium.launch({ timeout: 30_000 });
  await browser.close();
}

(async () => {
  try {
    await probe();
    console.log('Chromium launches on this runner; no dependency installation needed.');
    return;
  } catch (error) {
    console.error(`Chromium launch failed; attempting one dependency repair: ${error.message}`);
  }
  const cli = path.join(path.dirname(require.resolve('playwright/package.json')), 'cli.js');
  const installed = spawnSync(process.execPath, [cli, 'install-deps', 'chromium'], {
    stdio: 'inherit', timeout: 300_000,
  });
  if (installed.error || installed.status !== 0) {
    throw installed.error || new Error(`Chromium dependency installation failed (${installed.status}).`);
  }
  await probe();
  console.log('Chromium launches after dependency repair.');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
