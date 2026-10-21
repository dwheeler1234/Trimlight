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
    const sourceBox = await page.locator('[data-color="disabled"]').boundingBox();
    const targetBox = await page.locator('[data-entry="2"]').boundingBox();
    await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(targetBox.x + targetBox.width / 2, targetBox.y + targetBox.height / 2, {steps:12});
    await page.mouse.up();
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
    await page.locator('[data-color="#ff0000"]').click();
    await page.waitForFunction(() => !document.querySelector('trimlight-pattern-card')._busy);
    await page.locator('[data-color="disabled"]').click();
    await page.waitForFunction(() => !document.querySelector('trimlight-pattern-card')._busy);
    assert.equal(await page.evaluate(() => document.querySelector('trimlight-pattern-card')._attributes().pixels[2].disable), true);
    assert.equal(await page.locator('[data-edit-entry]').count(), 0);
    await page.locator('[data-entry="1"]').click();
    await page.locator('dialog').waitFor({state:'visible'});
    await page.locator('dialog input').fill('99');
    await page.locator('dialog button[type="submit"]').click();
    await page.waitForFunction(() => !document.querySelector('trimlight-pattern-card')._busy);
    assert.equal(await page.evaluate(() => document.querySelector('trimlight-pattern-card')._attributes().pixels[1].count), 99);
    await page.locator('.expand:not(.palette-toggle)').click();
    await page.locator('[data-color="#00ff00"]').dragTo(page.locator('[data-entry="8"]'));
    await page.waitForFunction(() => !document.querySelector('trimlight-pattern-card')._busy);
    const empty = await page.evaluate(() => document.querySelector('trimlight-pattern-card')._attributes().pixels[8]);
    assert.equal(empty.color, 0x00ff00);
    assert.equal(empty.count, 0);
    assert.equal(await page.locator('[data-entry="8"]').evaluate(el => el.style.getPropertyValue('--bulb')), '#00ff00');
    assert.equal(await page.locator('[data-entry="8"]').textContent(), '0');
    assert.deepEqual(errors, []);
    console.log('PASS: native browser drag sends color service, updates destination color and preserves count; dragging X disables destination without changing color/count or browser errors');
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1});
