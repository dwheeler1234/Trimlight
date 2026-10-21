/* Trimlight-style editor using the active Home Assistant theme. No dependencies. */
const DEFAULT_ENTITIES = {
  name: "text.trimlight_pattern_name", source: "select.trimlight_pattern_source",
  mode: "select.trimlight_pattern_mode", entry: "number.trimlight_pattern_entry",
  count: "number.trimlight_pattern_pixel_count", brightness: "number.trimlight_pattern_brightness",
  speed: "number.trimlight_pattern_speed", color: "light.trimlight_pattern_entry_color",
  disabled: "switch.trimlight_pattern_entry_disabled", preview: "button.trimlight_preview_pattern",
  save: "button.trimlight_save_new_pattern", new: "button.trimlight_new_pattern",
};
const PALETTE = [
  ["R", "#ff0000"], ["G", "#00ff00"], ["B", "#0000ff"], ["Y", "#ffff00"],
  ["PU", "#8000ff"], ["O", "#ff6000"], ["W", "#ffffff"], ["WW", "#ffe1a3"],
  ["PI", "#ff0080"], ["C", "#00ffff"], ["BK", "#000000"], ["X", null],
];
const CUSTOM_COLORS = ["#756400", "#24dd28", "#007c8c", "#e4be39", "#210074", "#000000", "#e40040", "#f7db35", "#ff8800", "#0088ff", "#ff66cc", "#88ffbb", "#ffcc88", "#7744bb", "#88ddff", "#ffffff"];
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
const hex = (value) => `#${Math.max(0, Math.min(0xffffff, Number(value) || 0)).toString(16).padStart(6, "0")}`;
const ink = (color) => {
  const n = parseInt(color.slice(1), 16);
  return (((n >> 16) * 299 + ((n >> 8) & 255) * 587 + (n & 255) * 114) / 1000) > 145 ? "#111111" : "#ffffff";
};

class TrimlightPatternCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this._expanded = false;
    this._paletteExpanded = false;
    this._customColors = [...CUSTOM_COLORS];
    this._busy = false;
    this._waiters = new Set();
    this._error = "";
    this._status = "";
  }

  setConfig(config) {
    const entities = {...DEFAULT_ENTITIES, ...(config.entities || {})};
    for (const id of Object.values(entities)) {
      if (typeof id !== "string" || !/^[a-z_]+\.[a-z0-9_]+$/.test(id)) throw new Error("Use valid Home Assistant entity IDs in entities");
    }
    this._config = {...config, entities};
    this._paletteStorageKey = `trimlight-palette:${entities.name}`;
    this._customColors = [...CUSTOM_COLORS];
    try {
      const stored = JSON.parse(localStorage.getItem(this._paletteStorageKey));
      if (Array.isArray(stored) && stored.length === 16 && stored.every((c) => /^#[0-9a-f]{6}$/i.test(c))) this._customColors = stored;
    } catch (_) { /* Storage may be disabled; the palette still works in memory. */ }
    this._render();
  }

  set hass(value) {
    this._hass = value;
    for (const notify of [...this._waiters]) notify();
    const signature = JSON.stringify(Object.values(this._config?.entities || {}).map((id) => value.states[id]));
    if (signature !== this._signature) {
      this._signature = signature;
      this._render();
    }
  }

  getCardSize() { return this._expanded ? 12 : 8; }
  _state(key) { return this._hass?.states[this._config.entities[key]]; }
  _value(key) { return this._state(key)?.state; }
  _attributes() { return this._state("name")?.attributes || {}; }
  _pixel() { return (this._attributes().pixels || []).find((p) => p.index === Number(this._value("entry"))) || {count:0, color:0, disable:false}; }

  _confirmed(predicate) {
    if (predicate()) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const finish = () => { if (predicate()) { clearTimeout(timer); this._waiters.delete(finish); resolve(); } };
      const timer = setTimeout(() => { this._waiters.delete(finish); reject(new Error("Home Assistant did not confirm the draft change. Check the editor entities.")); }, 6000);
      this._waiters.add(finish);
    });
  }

  async _call(key, service, data = {}, confirm) {
    const entity = this._config.entities[key];
    if (!this._state(key) || this._value(key) === "unavailable") throw new Error(`Editor entity unavailable: ${entity}`);
    await this._hass.callService(entity.split(".")[0], service, {entity_id: entity, ...data});
    if (confirm) await this._confirmed(confirm);
  }

  async _perform(work, status = "") {
    if (this._busy) return;
    this._busy = true; this._error = ""; this._status = ""; this._render();
    try { await work(); this._status = status; }
    catch (error) { this._error = error.message || String(error); }
    finally { this._busy = false; this._render(); }
  }

  async _setNumber(key, value) {
    await this._call(key, "set_value", {value:Number(value)}, () => Number(this._value(key)) === Number(value));
  }

  async _applyColor(color, preserveCount = false) {
    const rgb = [1, 3, 5].map((start) => parseInt(color.slice(start, start + 2), 16));
    await this._call("color", "turn_on", {rgb_color:rgb}, () => this._pixel().color === parseInt(color.slice(1), 16) && !this._pixel().disable);
    if (!preserveCount && !this._pixel().count) await this._setNumber("count", 1);
  }

  async _dropColor(index, color) {
    const target = Number(index);
    if (!Number.isInteger(target) || target < 0 || target > 29 || (color !== "disabled" && !/^#[0-9a-f]{6}$/i.test(color))) return;
    await this._perform(async () => {
      await this._setNumber("entry", target);
      if (color === "disabled") {
        await this._call("disabled", "turn_on", {}, () => this._pixel().disable);
      } else {
        await this._applyColor(color, true);
      }
    });
  }

  _setCustomColor(slot, color) {
    if (!Number.isInteger(slot) || slot < 0 || slot >= 16 || !/^#[0-9a-f]{6}$/i.test(color)) throw new Error("Invalid custom color slot");
    this._customColors[slot] = color.toLowerCase();
    try { localStorage.setItem(this._paletteStorageKey, JSON.stringify(this._customColors)); } catch (_) { /* Keep in memory. */ }
  }

  async _selectEntry(index) {
    await this._perform(() => this._setNumber("entry", index));
  }

  async _openEntry(index) {
    await this._perform(() => this._setNumber("entry", index));
    if (!this._error && Number(this._value("entry")) === Number(index)) this._showCountDialog(Number(index));
  }

  async _saveEntryCount(index, value) {
    await this._perform(async () => {
      if (!Number.isInteger(value) || value < 0 || value > 60) throw new Error("Pixel count must be a whole number from 0 to 60.");
      // Another dashboard may have changed the selected entry while the dialog was open.
      await this._setNumber("entry", index);
      await this._setNumber("count", value);
    }, "Entry count updated.");
  }

  _showCountDialog(index) {
    const dialog = document.createElement("dialog");
    dialog.setAttribute("aria-labelledby", "entry-count-title");
    dialog.innerHTML = `<form><h3 id="entry-count-title">Position ${index + 1}</h3><label>Pixel count<input type="number" name="count" min="0" max="60" step="1" required value="${Number(this._pixel().count) || 0}"></label><p class="hint">Choose 0–60 pixels. Zero leaves this position empty.</p><div class="actions"><button type="button" data-cancel>Cancel</button><button type="submit" class="primary">Save</button></div></form>`;
    this._countDialog = dialog;
    this.shadowRoot.append(dialog);
    dialog.addEventListener("close", () => {
      this._countDialog = null;
      dialog.remove();
      this._render();
      this.shadowRoot.querySelector(`[data-entry="${index}"]`)?.focus();
    });
    dialog.querySelector("[data-cancel]").onclick = () => dialog.close();
    dialog.querySelector("form").onsubmit = (event) => {
      event.preventDefault();
      const input = dialog.querySelector("input");
      if (!input.reportValidity()) return;
      const value = input.valueAsNumber;
      dialog.close();
      this._saveEntryCount(index, value);
    };
    dialog.showModal();
    dialog.querySelector("input").focus();
    dialog.querySelector("input").select();
  }

  async _runNamedAction(action, name) {
    await this._perform(async () => {
      const value = name.trim();
      if (!value || value.length > 64) throw new Error("Enter a pattern name from 1 to 64 characters.");
      if (action === "new") {
        await this._call("new", "press");
        await this._confirmed(() => this._value("name") === "New Pattern");
      }
      await this._call("name", "set_value", {value}, () => this._value("name") === value);
      if (action === "save") await this._call("save", "press");
    }, action === "save" ? "Saved a new pattern copy." : "New named draft created.");
  }

  _showNameDialog(action) {
    const dialog = document.createElement("dialog");
    const saving = action === "save";
    dialog.setAttribute("aria-labelledby", "pattern-name-title");
    dialog.innerHTML = `<form><h3 id="pattern-name-title">${saving ? "Save new pattern" : "New pattern"}</h3><label>Pattern name<input type="text" name="patternName" minlength="1" maxlength="64" required value="${esc(saving ? this._value("name") : "New Pattern")}"></label><p class="hint">${saving ? "Creates a saved copy without overwriting an existing pattern." : "Creates a new draft. Your lights stay unchanged."}</p><div class="actions"><button type="button" data-cancel>Cancel</button><button type="submit" class="primary">${saving ? "Save" : "Create"}</button></div></form>`;
    this._patternNameDialog = dialog;
    this.shadowRoot.append(dialog);
    dialog.addEventListener("close", () => {
      this._patternNameDialog = null; dialog.remove(); this._render();
      this.shadowRoot.querySelector(`[data-action="${action}"]`)?.focus();
    });
    dialog.querySelector("[data-cancel]").onclick = () => dialog.close();
    dialog.querySelector("form").onsubmit = (event) => {
      event.preventDefault();
      const input = dialog.querySelector("input");
      if (!input.reportValidity() || !input.value.trim()) return;
      const name = input.value;
      dialog.close();
      this._runNamedAction(action, name);
    };
    dialog.showModal();
    dialog.querySelector("input").focus();
    dialog.querySelector("input").select();
  }

  _render() {
    // Keep native drag source and destination nodes alive during HA updates.
    if (this._dragColor) return;
    if (!this._config || !this._hass) return;
    // Keep an in-progress count intact when Home Assistant sends state updates.
    if (this._countDialog?.open || this._patternNameDialog?.open) return;
    const attrs = this._attributes();
    const index = Number(this._value("entry")) || 0;
    const pixel = this._pixel();
    const missing = Object.keys(this._config.entities).filter((key) => !this._state(key));
    const locked = this._busy || missing.length > 0;
    const disabled = locked ? "disabled" : "";
    const pixels = Array.from({length:30}, (_, i) => (attrs.pixels || []).find((p) => p.index === i) || {index:i, color:0, count:0, disable:false});
    const fixedSwatch = ([label, color]) => `<button type="button" class="swatch ${color ? "" : "cross"}" data-color="${color || "disabled"}" draggable="${Boolean(color) && !locked}" style="--bulb:${color || "#000000"};--ink:${color ? ink(color) : "#ff4040"}" title="${label === "X" ? "Disable selected entry" : label}" aria-label="${label === "X" ? "Disable selected entry" : `Set entry color ${label}`}" ${disabled}>${label}</button>`;
    const customSwatch = (slot) => {
      const color = this._customColors[slot];
      return `<div class="custom-cell"><button type="button" class="swatch" data-color="${color}" draggable="${!locked}" style="--bulb:${color};--ink:${ink(color)}" aria-label="Apply custom color ${slot + 1}" title="Custom color ${slot + 1}" ${disabled}></button><label class="custom-edit" title="Edit custom color ${slot + 1}">✎<input type="color" data-custom-slot="${slot}" aria-label="Edit custom color ${slot + 1}" value="${color}" ${disabled}></label></div>`;
    };
    const swatches = PALETTE.map(fixedSwatch).join("") + customSwatch(0) + customSwatch(1);
    const extras = Array.from({length:7}, (_, i) => customSwatch(i + 2)).join("")
      + (this._paletteExpanded ? Array.from({length:7}, (_, i) => customSwatch(i + 9)).join("") : "");
    const optionList = (key) => {
      const draftLabel = key === "source" && this._value(key) === "New Pattern"
        ? `<option value="" selected disabled>${esc(this._value("name"))} (draft)</option>` : "";
      return draftLabel + (this._state(key)?.attributes.options || [])
        .filter((value) => key !== "source" || value !== "New Pattern")
        .map((value) => `<option value="${esc(value)}" ${value === this._value(key) ? "selected" : ""}>${esc(value)}</option>`).join("");
    };
    const range = (key, icon, label) => {
      const value = Math.max(0, Math.min(255, Number(this._value(key)) || 0));
      return `<label class="range-row"><ha-icon icon="${icon}" aria-hidden="true"></ha-icon><input aria-label="${label}" data-range="${key}" type="range" min="0" max="255" value="${value}" style="--fill:${value / 255 * 100}%" ${disabled}><output>${Math.round(value / 255 * 100)}%</output></label>`;
    };
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif)}
      *{box-sizing:border-box}ha-card{display:block;overflow:hidden;background:var(--ha-card-background,var(--card-background-color));border-radius:var(--ha-card-border-radius,16px);color:var(--primary-text-color)}
      .body{padding:16px;display:grid;gap:14px}.title{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:18px;font-weight:500}.subtitle{font-size:12px;color:var(--secondary-text-color);margin-top:4px}
      .panel{background:var(--secondary-background-color);border:1px solid var(--divider-color);border-radius:12px;padding:12px}
      .palette{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px;align-items:center;justify-items:center}
      button,input,select{font:inherit}button{cursor:pointer}button:disabled,input:disabled,select:disabled{cursor:wait;opacity:.55}
      .swatch,.entry{border:0;border-radius:50%;aspect-ratio:1;width:100%;max-width:44px;display:grid;place-items:center;background:var(--bulb);color:var(--ink);font-size:12px;padding:0;position:relative}
      .cross{font-size:24px;touch-action:none;user-select:none;cursor:grab}.cross.dragging{cursor:grabbing;outline:2px solid var(--primary-color)}.swatch{box-shadow:inset 0 0 0 1px rgb(128 128 128 / .3)}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid var(--primary-color);outline-offset:3px}
      .picker{position:relative;display:grid;place-items:center;aspect-ratio:1;width:100%;max-width:44px;border-radius:50%;background:var(--primary-background-color);border:1px solid var(--divider-color);font-size:22px;color:var(--primary-color);overflow:hidden}
      .picker input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}.palette-note{font-size:11px;text-align:center;color:var(--secondary-text-color);grid-column:1/-1;margin:0}
      .custom-cell{position:relative;width:100%;max-width:44px;aspect-ratio:1}.custom-cell .swatch{height:100%;max-width:none}.custom-edit{position:absolute;right:-3px;bottom:-3px;width:20px;height:20px;border-radius:50%;display:grid;place-items:center;font-size:13px;background:var(--card-background-color);color:var(--primary-color);border:1px solid var(--divider-color);overflow:hidden}.custom-edit input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}.palette-toggle{grid-column:1/-1;margin:0!important}
      select,input[type=text],input[type=number]{background:var(--card-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color);border-radius:8px;padding:10px;width:100%;min-width:0}
      .source{border:0;border-bottom:1px solid var(--divider-color);border-radius:0;margin-bottom:12px;background:transparent;padding:4px 0 12px;font-size:16px}
      .grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px 10px;justify-items:center}.entry{font-size:14px;max-width:46px}.entry-cell{position:relative;width:100%;max-width:46px;aspect-ratio:1}.entry-cell .entry{height:100%}.swatch[draggable="true"]{cursor:grab}.entry.drop-target{outline:3px dashed var(--primary-color);outline-offset:3px}.entry.selected{outline:3px solid var(--primary-color);outline-offset:3px}.entry.off::after{content:"";position:absolute;inset:5px;border-top:2px solid var(--primary-color);transform:translateY(50%) rotate(-45deg)}
      .expand{display:block;margin:10px auto -4px;background:none;border:0;color:var(--primary-color);width:44px;height:32px;font-size:24px}
      .edit-row{display:grid;grid-template-columns:1fr;gap:10px;align-items:end;margin-top:16px}.edit-row label{font-size:12px;color:var(--secondary-text-color)}.edit-row input{margin-top:5px}.disabled-toggle{display:flex;align-items:center;gap:8px;font-size:13px;margin-top:10px;color:var(--secondary-text-color)}input[type=checkbox]{accent-color:var(--primary-color);width:18px;height:18px}
      dialog{width:min(320px,calc(100vw - 32px));padding:22px;border:1px solid var(--divider-color);border-radius:16px;background:var(--ha-card-background,var(--card-background-color));color:var(--primary-text-color);font:inherit}dialog::backdrop{background:rgb(0 0 0 / .5)}dialog h3{margin:0 0 18px;font-size:20px}dialog label{display:grid;gap:8px}dialog .hint{margin:10px 0 20px}dialog .actions{justify-content:flex-end}
      .mode{text-transform:uppercase}.range-row{display:flex;align-items:center;gap:10px;margin:12px 0}.range-row ha-icon{--mdc-icon-size:21px;color:var(--secondary-text-color)}.range-row output{font-size:12px;min-width:36px;text-align:right;color:var(--secondary-text-color)}
      input[type=range]{appearance:none;width:100%;height:9px;border-radius:8px;background:linear-gradient(to right,var(--primary-color) 0%,var(--primary-color) var(--fill),var(--divider-color) var(--fill),var(--divider-color) 100%);cursor:pointer}input[type=range]::-webkit-slider-thumb{appearance:none;width:23px;height:23px;border-radius:50%;background:var(--primary-text-color)}input[type=range]::-moz-range-thumb{width:23px;height:23px;border:0;border-radius:50%;background:var(--primary-text-color)}
      .actions{display:flex;gap:8px;flex-wrap:wrap}.actions button{flex:1;min-height:42px;border:1px solid var(--divider-color);border-radius:9px;padding:8px;background:var(--secondary-background-color);color:var(--primary-text-color)}.actions .primary{background:var(--primary-color);color:var(--text-primary-color)}
      .message{font-size:13px;margin:0;overflow-wrap:anywhere}.error{color:var(--error-color)}.hint{font-size:12px;line-height:1.5;color:var(--secondary-text-color);margin:0}
      @media(max-width:360px){.body{padding:12px}.panel{padding:10px}.palette{gap:6px}.grid{gap:12px 8px}.swatch{font-size:11px}}
    </style><ha-card><div class="body">
      <div><div class="title">${esc(this._config.title || "Trimlight")} <ha-icon icon="mdi:palette-outline"></ha-icon></div><div class="subtitle">Custom pattern editor</div></div>
      ${missing.length ? `<p class="message error">Missing editor entities: ${esc(missing.map((key) => this._config.entities[key]).join(", "))}</p>` : ""}
      <div class="panel palette">${swatches}${extras}<button class="expand palette-toggle" aria-label="${this._paletteExpanded ? "Hide fourth color row" : "Show fourth color row"}" aria-expanded="${this._paletteExpanded}">${this._paletteExpanded ? "⌃" : "⌄"}</button><p class="palette-note">Click a color for entry ${index + 1}, or drag a color or X onto a pattern slot · ✎ edits custom colors</p></div>
      <div class="panel"><label class="hint">Pattern name<select class="source" data-select="source" aria-label="Pattern name" ${disabled}>${optionList("source")}</select></label>
        <div class="grid">${pixels.slice(0, this._expanded ? 30 : 6).map((p) => {
          const color = p.count ? hex(p.color) : "#000000";
          return `<div class="entry-cell"><button type="button" class="entry ${p.index === index ? "selected" : ""} ${p.disable ? "off" : ""}" data-entry="${p.index}" style="--bulb:${color};--ink:${ink(color)}" aria-label="Entry ${p.index + 1}: ${p.count} pixels${p.disable ? ", disabled" : ""}" aria-pressed="${p.index === index}" ${disabled}>${Number(p.count) || 0}</button></div>`;
        }).join("")}</div>
        <button class="expand" aria-label="${this._expanded ? "Collapse pattern" : "Show all 30 entries"}" aria-expanded="${this._expanded}">${this._expanded ? "⌃" : "⌄"}</button>
        <p class="hint">Tap a position to edit its pixel count.</p>
        <p class="hint">Draft: ${esc(this._value("name"))}</p>
        <label class="disabled-toggle"><input type="checkbox" data-disabled ${pixel.disable ? "checked" : ""} ${disabled}>Disable selected entry</label>
      </div>
      <div class="panel"><select class="mode" data-select="mode" aria-label="Pattern animation mode" ${disabled}>${optionList("mode")}</select>${range("brightness", "mdi:brightness-6", "Pattern brightness")}${range("speed", "mdi:speedometer", "Pattern speed")}</div>
      <div class="actions"><button data-action="new" ${disabled}>New</button><button data-action="preview" class="primary" ${disabled}>Preview</button><button data-action="save" ${disabled}>Save new</button></div>
      <p class="hint">Edit the draft, then Preview to run it. Save new creates a copy. Drafts reset on restart.</p>
      <p class="message ${this._error ? "error" : ""}" role="${this._error ? "alert" : "status"}" aria-live="polite">${esc(this._error || (this._busy ? "Updating…" : this._status))}</p>
    </div></ha-card>`;
    this._bind();
  }

  _bind() {
    const root = this.shadowRoot;
    root.querySelector(".expand:not(.palette-toggle)").onclick = () => { this._expanded = !this._expanded; this._render(); };
    root.querySelector(".palette-toggle").onclick = () => { this._paletteExpanded = !this._paletteExpanded; this._render(); };
    root.querySelectorAll("[data-entry]").forEach((el) => {
      el.onclick = () => this._openEntry(el.dataset.entry);
      el.ondragover = (event) => {
        if (!this._dragColor || this._busy || el.disabled) return;
        event.preventDefault(); event.dataTransfer.dropEffect = "copy";
        el.classList.add("drop-target");
      };
      el.ondragleave = () => el.classList.remove("drop-target");
      el.ondrop = (event) => {
        if (this._busy || el.disabled) return;
        const color = event.dataTransfer.getData("application/x-trimlight-color") || this._dragColor;
        if (color !== "disabled" && !/^#[0-9a-f]{6}$/i.test(color || "")) return;
        event.preventDefault();
        this._dragColor = null;
        el.classList.remove("drop-target");
        this._dropColor(el.dataset.entry, color);
      };
    });
    root.querySelectorAll("[data-color]").forEach((el) => { el.onclick = () => { if (this._suppressPaletteClick) { this._suppressPaletteClick = false; return; } return this._perform(() => el.dataset.color === "disabled" ? this._call("disabled", "turn_on", {}, () => this._pixel().disable) : this._applyColor(el.dataset.color)); }; });
    const disableSwatch = root.querySelector('[data-color="disabled"]');
    if (disableSwatch) {
      let gesture = null;
      const targetAt = (event) => {
        const hit = root.elementFromPoint(event.clientX, event.clientY);
        const cell = hit?.closest(".entry-cell");
        return hit?.closest("[data-entry]") || cell?.querySelector("[data-entry]");
      };
      const clearTargets = () => root.querySelectorAll(".drop-target").forEach((el) => el.classList.remove("drop-target"));
      disableSwatch.onpointerdown = (event) => {
        if (event.button !== 0 || this._busy || disableSwatch.disabled) return;
        gesture = {id:event.pointerId, x:event.clientX, y:event.clientY, moved:false};
        this._dragColor = "disabled";
        disableSwatch.setPointerCapture(event.pointerId);
      };
      disableSwatch.onpointermove = (event) => {
        if (!gesture || gesture.id !== event.pointerId) return;
        if (Math.hypot(event.clientX - gesture.x, event.clientY - gesture.y) > 6) gesture.moved = true;
        if (!gesture.moved) return;
        disableSwatch.classList.add("dragging");
        clearTargets(); targetAt(event)?.classList.add("drop-target");
      };
      const finish = (event, cancelled = false) => {
        if (!gesture || gesture.id !== event.pointerId) return;
        const moved = gesture.moved;
        const target = moved && !cancelled ? targetAt(event) : null;
        gesture = null; this._dragColor = null;
        disableSwatch.classList.remove("dragging"); clearTargets();
        if (disableSwatch.hasPointerCapture(event.pointerId)) disableSwatch.releasePointerCapture(event.pointerId);
        if (moved) {
          event.preventDefault(); this._suppressPaletteClick = true;
          // Consume only the synthetic click associated with this release.
          setTimeout(() => { this._suppressPaletteClick = false; }, 0);
        }
        if (target && !target.disabled) this._dropColor(target.dataset.entry, "disabled");
        else if (moved || cancelled) this._render();
      };
      disableSwatch.onpointerup = (event) => finish(event);
      disableSwatch.onpointercancel = (event) => finish(event, true);
      disableSwatch.onlostpointercapture = (event) => finish(event, true);
    }
    root.querySelectorAll('[data-color][draggable="true"]').forEach((el) => {
      el.ondragstart = (event) => {
        this._dragColor = el.dataset.color;
        event.dataTransfer.effectAllowed = "copy";
        event.dataTransfer.setData("text/plain", this._dragColor);
        event.dataTransfer.setData("application/x-trimlight-color", this._dragColor);
      };
      el.ondragend = () => {
        this._dragColor = null;
        root.querySelectorAll(".drop-target").forEach((target) => target.classList.remove("drop-target"));
        this._render();
      };
    });
    root.querySelectorAll("[data-custom-slot]").forEach((el) => { el.onchange = () => {
      const slot = Number(el.dataset.customSlot), color = el.value;
      this._perform(async () => { this._setCustomColor(slot, color); await this._applyColor(color); });
    }; });
    root.querySelector("[data-disabled]").onchange = (event) => { const value = event.target.checked; this._perform(() => this._call("disabled", value ? "turn_on" : "turn_off", {}, () => Boolean(this._pixel().disable) === value)); };
    root.querySelectorAll("[data-select]").forEach((el) => { el.onchange = () => { const key = el.dataset.select, value = el.value; this._perform(() => this._call(key, "select_option", {option:value}, () => this._value(key) === value)); }; });
    root.querySelectorAll("[data-range]").forEach((el) => {
      el.oninput = () => { el.style.setProperty("--fill", `${el.value / 255 * 100}%`); el.nextElementSibling.textContent = `${Math.round(el.value / 255 * 100)}%`; };
      el.onchange = () => { const value = el.value, key = el.dataset.range; this._perform(() => this._setNumber(key, value)); };
    });
    root.querySelectorAll("[data-action]").forEach((el) => { el.onclick = () => {
      const key = el.dataset.action;
      if (key === "new" || key === "save") this._showNameDialog(key);
      else this._perform(() => this._call(key, "press"), "Preview sent to controller.");
    }; });
  }
}

if (!customElements.get("trimlight-pattern-card")) customElements.define("trimlight-pattern-card", TrimlightPatternCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "trimlight-pattern-card")) {
  window.customCards.push({type:"trimlight-pattern-card", name:"Trimlight Pattern Editor", description:"Trimlight-style custom pattern editor using your Home Assistant theme"});
}
