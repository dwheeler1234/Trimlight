/* Offline card logic checks. A minimal DOM stand-in does not validate browser layout. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class ShadowRoot {
  constructor() { this.innerHTML = ""; }
  querySelector() { return {focus(){}}; }
  querySelectorAll() { return []; }
  append(element) { this.appended = element; }
}
class Element {
  attachShadow() { this.shadowRoot = new ShadowRoot(); }
}
const registry = new Map();
const paletteStorage = new Map();
const context = vm.createContext({HTMLElement:Element, window:{}, setTimeout, clearTimeout,
  localStorage:{getItem:(key) => paletteStorage.get(key) || null, setItem:(key, value) => paletteStorage.set(key, value)},
  customElements:{get:(name) => registry.get(name), define:(name, cls) => registry.set(name, cls)}});
const source = fs.readFileSync(path.join(__dirname, "../www/trimlight-pattern-card.js"), "utf8");
vm.runInContext(source, context);
const Card = registry.get("trimlight-pattern-card");
const card = new Card();
card.setConfig({type:"custom:trimlight-pattern-card"});
const fixture = fs.readFileSync(path.join(__dirname, "test_pattern_card.cjs"), "utf8");
const setup = fixture.match(/await page\.evaluate\(\(\) => \{([\s\S]*?)\n    \}\);/)[1];
context.document = {querySelector:() => card};
context.document.createElement = () => {
  const listeners = {};
  const input = {focus(){}, select(){}, reportValidity:() => true};
  const cancel = {}, form = {};
  return {open:false, setAttribute(){}, remove(){},
    addEventListener:(name, handler) => {listeners[name] = handler;},
    querySelector:(selector) => selector === "input" ? input : selector === "form" ? form : cancel,
    showModal(){this.open = true;},
    close(){this.open = false; listeners.close?.();},
  };
};
context.structuredClone = structuredClone;
vm.runInContext(setup, context);

async function main() {
  assert.equal((card.shadowRoot.innerHTML.match(/data-entry="/g) || []).length, 6);
  card._expanded = true; card._render();
  assert.equal((card.shadowRoot.innerHTML.match(/data-entry="/g) || []).length, 30);
  assert.match(card.shadowRoot.innerHTML, /grid-template-columns:repeat\(6/);
  assert.match(card.shadowRoot.innerHTML, /background:var\(--ha-card-background,var\(--card-background-color\)\)/);
  assert.match(card.shadowRoot.innerHTML, /background:var\(--secondary-background-color\)/);
  assert.equal((card.shadowRoot.innerHTML.match(/data-custom-slot="/g) || []).length, 9);
  assert.equal((card.shadowRoot.innerHTML.match(/data-color="/g) || []).length, 21);
  card._paletteExpanded = true; card._render();
  assert.equal((card.shadowRoot.innerHTML.match(/data-custom-slot="/g) || []).length, 16);
  assert.equal((card.shadowRoot.innerHTML.match(/data-color="/g) || []).length, 28);
  card._paletteExpanded = false; card._render();
  assert.equal((card.shadowRoot.innerHTML.match(/data-custom-slot="/g) || []).length, 9);
  assert.equal((card.shadowRoot.innerHTML.match(/data-color="/g) || []).length, 21);
  card._setCustomColor(15, "#123ABC");
  const restoredPalette = new Card();
  restoredPalette.setConfig({});
  assert.equal(restoredPalette._customColors[15], "#123abc");
  assert.throws(() => card._setCustomColor(16, "#112233"), /Invalid/);
  card._paletteExpanded = true; card._render();
  assert.equal(card.shadowRoot.innerHTML.includes("data-count"), false);
  await card._selectEntry(7);
  assert.equal(Number(card._value("entry")), 7);
  assert.equal(card._countDialog == null, true);
  await card._setNumber("count", 5);
  await card._applyColor("#00ff00");
  assert.equal(card._pixel().count, 5);
  assert.equal(card._countDialog == null, true);
  assert.equal((card.shadowRoot.innerHTML.match(/data-edit-entry="/g) || []).length, 30);
  const markupBeforeDragUpdate = card.shadowRoot.innerHTML;
  card._dragColor = "#123456";
  card._expanded = false;
  card._render();
  assert.equal(card.shadowRoot.innerHTML, markupBeforeDragUpdate);
  card._dragColor = null;
  card._expanded = true;
  await card._dropColor(7, "#123456");
  assert.match(card.shadowRoot.innerHTML, /data-entry="7" style="--bulb:#123456/);
  assert.equal(card._pixel().color, 0x123456);
  assert.equal(card._pixel().count, 5);
  assert.equal(card._countDialog == null, true);
  const beforeInvalidDrop = context.window.mockCalls.length;
  await card._dropColor(30, "#abcdef");
  await card._dropColor(7, "not-a-color");
  assert.equal(context.window.mockCalls.length, beforeInvalidDrop);
  await card._dropColor(6, "#abcdef");
  assert.equal(Number(card._value("entry")), 6);
  assert.equal(card._pixel().count, 1);
  assert.equal(card._pixel().color, 0xabcdef);
  await card._openEntry(7);
  assert.equal(card._countDialog.open, true);
  assert.match(card._countDialog.innerHTML, /Position 8/);
  const openDialog = card._countDialog;
  card._render();
  assert.equal(card._countDialog, openDialog);
  openDialog.querySelector("input").valueAsNumber = 5;
  openDialog.querySelector("form").onsubmit({preventDefault(){}});
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(card._pixel().count, 5);
  assert.equal(card._countDialog, null);
  await card._openEntry(8);
  card._countDialog.querySelector("[data-cancel]").onclick();
  assert.equal(card._pixel().count, 0);
  assert.equal(card._countDialog, null);
  await card._saveEntryCount(8, 61);
  assert.match(card._error, /0 to 60/);
  assert.equal(card._pixel().count, 0);
  await card._setNumber("entry", 9);
  assert.equal(Number(card._value("entry")), 9);
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
  assert.equal(card.shadowRoot.innerHTML.includes("data-name"), false);
  const callsBeforeCancel = context.window.mockCalls.length;
  card._showNameDialog("new");
  assert.match(card._patternNameDialog.innerHTML, /New pattern/);
  card._patternNameDialog.querySelector("[data-cancel]").onclick();
  assert.equal(context.window.mockCalls.length, callsBeforeCancel);
  await card._runNamedAction("new", "My New Pattern");
  assert.equal(card._value("name"), "My New Pattern");
  await card._runNamedAction("save", "Saved Holiday");
  assert.equal(card._value("name"), "Saved Holiday");
  assert.equal(context.window.mockCalls.at(-1).entity_id, "button.trimlight_save_new_pattern");
  const beforeInvalid = context.window.mockCalls.length;
  await card._runNamedAction("save", "   ");
  assert.equal(context.window.mockCalls.length, beforeInvalid);
  assert.match(card._error, /1 to 64/);
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
