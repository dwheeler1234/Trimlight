/* Browser regression checks against a simulated hass object; no live HA access. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

async function main() {
  const channel = process.argv.find((s) => s.startsWith("--channel="))?.split("=")[1];
  const output = process.argv.find((s) => s.startsWith("--output-dir="))?.slice(13) || path.join(__dirname, "../work/card-preview");
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, ...(channel ? { channel } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 1100 }, deviceScaleFactor: 1 });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setContent(`<style>
      html{--primary-color:#ac67ef;--primary-background-color:#111318;--secondary-background-color:#222630;--card-background-color:#181c24;--primary-text-color:#f1f3f9;--secondary-text-color:#b7bfce;--divider-color:#3d4350;--text-primary-color:#fff;--error-color:#ff8c91}
      body{margin:0;padding:12px;background:var(--primary-background-color)}
      ha-icon{display:inline-grid;place-items:center;width:22px;height:22px}
    </style><trimlight-pattern-card></trimlight-pattern-card>`);
    await page.addScriptTag({ content: fs.readFileSync(path.join(__dirname, "../www/trimlight-pattern-card.js"), "utf8") });
    await page.evaluate(() => {
      const card = document.querySelector("trimlight-pattern-card");
      card.setConfig({ type: "custom:trimlight-pattern-card" });
      const pixels = Array.from({length:30}, (_, index) => ({index, count:[3,8,12,10,12,8][index] || 0,
        color:[0x6700ff,0xff0000,0xff6500,0xffff00,0xff6500,0xff0000][index] || 0, disable:false}));
      const state = (value, attributes = {}) => ({ state:String(value), attributes });
      const states = {
        "text.trimlight_pattern_name":state("Evening Sunset", {pixels, mode:0, brightness:230, speed:125, selected_index:0}),
        "select.trimlight_pattern_source":state("Evening Sunset (id 1)", {options:["New Pattern", "Evening Sunset (id 1)", "Custom Game Day (id 2)"]}),
        "select.trimlight_pattern_mode":state("Static", {options:["Static", "Chase Forward", "Stars"]}),
        "number.trimlight_pattern_entry":state(0), "number.trimlight_pattern_pixel_count":state(3),
        "number.trimlight_pattern_brightness":state(230), "number.trimlight_pattern_speed":state(125),
        "light.trimlight_pattern_entry_color":state("on"), "switch.trimlight_pattern_entry_disabled":state("off"),
        "button.trimlight_preview_pattern":state("unknown"), "button.trimlight_save_new_pattern":state("unknown"),
        "button.trimlight_new_pattern":state("unknown"),
      };
      const attrs = states["text.trimlight_pattern_name"].attributes;
      window.mockCalls = [];
      window.rejectPreview = false;
      const publish = () => { card.hass = {states:structuredClone(states), callService}; };
      const callService = async (domain, service, data) => {
        window.mockCalls.push({domain, service, ...data});
        const selected = () => attrs.pixels[Number(states["number.trimlight_pattern_entry"].state)];
        if (data.entity_id === "button.trimlight_preview_pattern" && window.rejectPreview) throw new Error("Controller rejected preview");
        if (domain === "number") {
          states[data.entity_id].state = String(data.value);
          if (data.entity_id.endsWith("pattern_entry")) attrs.selected_index = Number(data.value);
          if (data.entity_id.endsWith("pixel_count")) selected().count = Number(data.value);
          if (data.entity_id.endsWith("brightness")) attrs.brightness = Number(data.value);
          if (data.entity_id.endsWith("speed")) attrs.speed = Number(data.value);
        }
        if (domain === "light") {
          selected().color = (data.rgb_color[0] << 16) | (data.rgb_color[1] << 8) | data.rgb_color[2];
          selected().disable = false;
        }
        if (domain === "switch") selected().disable = service === "turn_on";
        if (domain === "text") states[data.entity_id].state = data.value;
        if (domain === "select") {
          states[data.entity_id].state = data.option;
          if (data.entity_id.endsWith("pattern_mode")) attrs.mode = states[data.entity_id].attributes.options.indexOf(data.option);
        }
        states["number.trimlight_pattern_pixel_count"].state = String(selected().count);
        states["switch.trimlight_pattern_entry_disabled"].state = selected().disable ? "on" : "off";
        publish();
      };
      window.publishMock = publish;
      publish();
    });
    const card = page.locator("trimlight-pattern-card");
    await card.locator(".grid .entry").first().waitFor();
    assert.equal(await card.locator(".grid .entry").count(), 6);
    assert.equal(await card.locator(".palette .swatch").count(), 28);
    assert.equal(await card.locator("ha-card").evaluate((el) => getComputedStyle(el).backgroundColor), "rgb(24, 28, 36)");
    await page.screenshot({path:path.join(output, "trimlight-editor-dark-collapsed.png"), fullPage:true});

    await card.locator(".expand:not(.palette-toggle)").click();
    assert.equal(await card.locator(".grid .entry").count(), 30);
    await page.screenshot({path:path.join(output, "trimlight-editor-dark-expanded.png"), fullPage:true});
    await card.locator('[data-entry="7"]').click();
    await card.locator("dialog").waitFor({state:"visible"});
    await card.locator("dialog [data-cancel]").click();
    await card.locator('[data-entry="7"]').getAttribute("aria-pressed").then((value) => assert.equal(value, "true"));
    await card.locator('[data-color="#ff0000"]').click();
    await page.waitForFunction(() => !document.querySelector("trimlight-pattern-card")._busy);
    await card.locator('[data-entry="7"]').click();
    await card.locator('dialog input[name="count"]').fill("5");
    await card.locator('dialog button[type="submit"]').click();
    await page.waitForFunction(() => !document.querySelector("trimlight-pattern-card")._busy);
    assert.equal(await card.locator('[data-entry="7"]').innerText(), "5");
    await card.locator('[data-disabled]').check();
    await page.waitForFunction(() => !document.querySelector("trimlight-pattern-card")._busy);
    assert.match(await card.locator('[data-entry="7"]').getAttribute("class"), /off/);
    await card.locator('[data-select="mode"]').selectOption("Chase Forward");
    await page.waitForFunction(() => !document.querySelector("trimlight-pattern-card")._busy);
    await card.locator('[data-name]').fill('<img src=x onerror="alert(1)">');
    await card.locator('[data-name]').press("Tab");
    await page.waitForFunction(() => !document.querySelector("trimlight-pattern-card")._busy);
    assert.equal(await card.locator("img").count(), 0);
    assert.equal(await page.evaluate(() => window.mockCalls.some((c) => c.domain === "button")), false);
    await card.locator('[data-action="save"]').click();
    await card.locator('[role="status"]').filter({hasText:"Saved a new copy"}).waitFor();
    assert.equal(await page.evaluate(() => window.mockCalls.filter((c) => c.domain === "button").length), 1);
    await page.evaluate(() => { window.rejectPreview = true; });
    await card.locator('[data-action="preview"]').click();
    await card.locator('[role="alert"]').filter({hasText:"Controller rejected preview"}).waitFor();

    await page.evaluate(() => {
      const style = document.documentElement.style;
      for (const [key,value] of Object.entries({"primary-color":"#3768b7", "primary-background-color":"#eef0f5", "secondary-background-color":"#f4f6fa", "card-background-color":"#ffffff", "primary-text-color":"#1b2433", "secondary-text-color":"#546174", "divider-color":"#d5dbe4"})) style.setProperty(`--${key}`,value);
      document.querySelector("trimlight-pattern-card")._error = "";
      document.querySelector("trimlight-pattern-card")._status = "";
      window.publishMock();
      document.querySelector("trimlight-pattern-card")._render();
    });
    assert.equal(await card.locator("ha-card").evaluate((el) => getComputedStyle(el).backgroundColor), "rgb(255, 255, 255)");
    await page.screenshot({path:path.join(output, "trimlight-editor-light-expanded.png"), fullPage:true});
    await page.setViewportSize({width:320, height:1100});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path:path.join(output, "trimlight-editor-320px.png"), fullPage:true});
    assert.deepEqual(errors, []);
    console.log("PASS: layout, 30-entry grid, palette/count/disabled/mode edits, draft isolation, save routing, API error display, HTML escaping, dark/light themes, and 320px width");
    console.log(`Preview images: ${output}`);
  } finally {
    await browser.close();
  }
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
