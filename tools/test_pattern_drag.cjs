/* Real native drag regression against simulated HA; never contacts a controller. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
(async () => {
  const channel = process.argv.find(s => s.startsWith('--channel='))?.split('=')[1];
  const browser = await chromium.launch({headless:true, ...(channel ? {channel} : {})});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent('<trimlight-pattern-card></trimlight-pattern-card>');
    await page.addScriptTag({content:fs.readFileSync(path.join(__dirname, '../www/trimlight-pattern-card.js'), 'utf8')});
    const fixture = fs.readFileSync(path.join(__dirname, 'test_pattern_card.cjs'), 'utf8');
    const setup = fixture.match(/await page\.evaluate\(\(\) => \{([\s\S]*?)\n    \}\);/)[1];
    await page.evaluate(setup);
    await page.locator('[data-color="#00ff00"]').dragTo(page.locator('[data-entry="2"]'));
    await page.waitForFunction(() => !document.querySelector('trimlight-pattern-card')._busy);
    const result = await page.evaluate(() => {
      const card = document.querySelector('trimlight-pattern-card');
      return {pixel:card._attributes().pixels[2], calls:window.mockCalls,
        bulb:card.shadowRoot.querySelector('[data-entry="2"]').style.getPropertyValue('--bulb')};
    });
    assert.equal(result.pixel.color, 0x00ff00);
    assert.equal(result.pixel.count, 12);
    assert.equal(result.bulb, '#00ff00');
    assert.equal(result.calls.at(-1).domain, 'light');
    await page.locator('[data-color="disabled"]').dragTo(page.locator('[data-entry="2"]'));
    await page.waitForFunction(() => !document.querySelector('trimlight-pattern-card')._busy);
    const disabled = await page.evaluate(() => {
      const card = document.querySelector('trimlight-pattern-card');
      return {pixel:card._attributes().pixels[2], crossed:card.shadowRoot.querySelector('[data-entry="2"]').classList.contains('off'), lastCall:window.mockCalls.at(-1)};
    });
    assert.equal(disabled.pixel.disable, true);
    assert.equal(disabled.pixel.color, 0x00ff00);
    assert.equal(disabled.pixel.count, 12);
    assert.equal(disabled.crossed, true);
    assert.equal(disabled.lastCall.domain, 'switch');
    assert.deepEqual(errors, []);
    console.log('PASS: native browser drag sends color service, updates destination color and preserves count; dragging X disables destination without changing color/count or browser errors');
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1});
