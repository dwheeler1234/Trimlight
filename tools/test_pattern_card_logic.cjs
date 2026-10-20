/* Offline card logic checks. A minimal DOM stand-in does not validate browser layout. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class ShadowRoot {
  constructor() { this.innerHTML = ""; }
  querySelector() { return {}; }
  querySelectorAll() { return []; }
}
class Element {
  attachShadow() { this.shadowRoot = new ShadowRoot(); }
}
const registry = new Map();
const context = vm.createContext({HTMLElement:Element, window:{}, setTimeout, clearTimeout,
  customElements:{get:(name) => registry.get(name), define:(name, cls) => registry.set(name, cls)}});
const source = fs.readFileSync(path.join(__dirname, "../www/trimlight-pattern-card.js"), "utf8");
vm.runInContext(source, context);
const Card = registry.get("trimlight-pattern-card");
const card = new Card();
card.setConfig({type:"custom:trimlight-pattern-card"});
const fixture = fs.readFileSync(path.join(__dirname, "test_pattern_card.cjs"), "utf8");
const setup = fixture.match(/await page\.evaluate\(\(\) => \{([\s\S]*?)\n    \}\);/)[1];
context.document = {querySelector:() => card};
context.structuredClone = structuredClone;
vm.runInContext(setup, context);

async function main() {
  assert.equal((card.shadowRoot.innerHTML.match(/data-entry="/g) || []).length, 6);
  card._expanded = true; card._render();
  assert.equal((card.shadowRoot.innerHTML.match(/data-entry="/g) || []).length, 30);
  assert.match(card.shadowRoot.innerHTML, /grid-template-columns:repeat\(6/);
  assert.match(card.shadowRoot.innerHTML, /background:var\(--ha-card-background,var\(--card-background-color\)\)/);
  assert.match(card.shadowRoot.innerHTML, /background:var\(--secondary-background-color\)/);
  await card._setNumber("entry", 7);
  assert.equal(Number(card._value("entry")), 7);
  await card._applyColor("#ff0000");
  assert.equal(card._pixel().color, 0xff0000);
  assert.equal(card._pixel().count, 1);
  await card._setNumber("count", 5);
  await card._call("disabled", "turn_on", {}, () => card._pixel().disable);
  assert.equal(card._pixel().disable, true);
  await card._call("mode", "select_option", {option:"Chase Forward"});
  assert.equal(card._value("mode"), "Chase Forward");
  await card._call("name", "set_value", {value:'<img src=x onerror="alert(1)">'});
  assert.equal(card.shadowRoot.innerHTML.includes("<img"), false);
  assert.match(card.shadowRoot.innerHTML, /&lt;img/);
  assert.equal(context.window.mockCalls.some((c) => c.domain === "button"), false);
  await card._perform(() => card._call("save", "press"), "Saved");
  assert.equal(card._status, "Saved");
  assert.equal(context.window.mockCalls.filter((c) => c.domain === "button").length, 1);
  context.window.rejectPreview = true;
  await card._perform(() => card._call("preview", "press"));
  assert.equal(card._error, "Controller rejected preview");
  assert.equal(card._busy, false);
  card._hass.states[card._config.entities.preview].state = "unavailable";
  await assert.rejects(card._call("preview", "press"), /unavailable/);
  assert.throws(() => new Card().setConfig({entities:{name:'text.bad" onclick="bad'}}), /valid Home Assistant entity IDs/);
  const custom = new Card();
  custom.setConfig({entities:{name:"text.trimlight_pattern_name_2"}});
  assert.equal(custom._config.entities.name, "text.trimlight_pattern_name_2");
  console.log("PASS: offline card markup, collapsed/expanded grid, theme variables, service routing, draft edits, save routing, API errors, HTML escaping, and entity overrides");
}
main().catch((error) => {console.error(error); process.exitCode = 1;});
