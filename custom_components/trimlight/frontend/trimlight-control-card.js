/* Compact Trimlight controller card; HA theme colors and no external dependencies. */
const TL_FIXED = [["R","#ff0000"],["G","#00ff00"],["B","#0000ff"],["Y","#ffff00"],["PU","#8000ff"],["O","#ff6000"],["W","#ffffff"],["WW","#ffe1a3"],["PI","#ff0080"],["C","#00ffff"],["BK","#000000"],["X",null]];
const TL_CUSTOM = ["#756400","#24dd28","#007c8c","#e4be39","#210074","#000000","#e40040","#f7db35","#ff8800","#0088ff","#ff66cc","#88ffbb","#ffcc88","#7744bb","#88ddff","#ffffff"];
const tlEsc = v => String(v ?? "").replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const tlInk = c => {const n=parseInt(c.slice(1),16);return ((n>>16)*299+((n>>8)&255)*587+(n&255)*114)/1000>145?'#111':'#fff';};
class TrimlightControlCard extends HTMLElement {
  constructor(){super();this.attachShadow({mode:'open'});this._expanded=false;this._busy=false;this._error='';}
  setConfig(config){
    const entity=config.entity || 'light.trimlight';
    if(!/^light\.[a-z0-9_]+$/.test(entity))throw new Error('Choose a valid light entity');
    const prefix=entity.split('.')[1];
    this._config={...config,entity,builtin:config.builtin_entity || `select.${prefix}_built_in_preset`,custom:config.pattern_entity || `select.${prefix}_custom_preset`,palette:config.palette_entity || `text.${prefix}_pattern_name`};
    for(const key of ['builtin','custom','palette'])if(!/^[a-z_]+\.[a-z0-9_]+$/.test(this._config[key]))throw new Error('Use valid entity IDs');
    this._storageKey=`trimlight-palette:${this._config.palette}`;this._colors=[...TL_CUSTOM];this._loadColors();this._render();
  }
  _loadColors(){try{const colors=JSON.parse(localStorage.getItem(this._storageKey));if(Array.isArray(colors)&&colors.length===16&&colors.every(c=>/^#[0-9a-f]{6}$/i.test(c)))this._colors=colors;}catch(_){} }
  set hass(hass){this._hass=hass;this._loadColors();if(!this._interacting)this._render();}
  getCardSize(){return this._expanded?8:7;}
  static getStubConfig(){return {entity:'light.trimlight'};}
  _state(key){return this._hass?.states[this._config?.[key]];}
  async _call(domain,service,data){
    if(this._busy)return;
    this._busy=true;this._error='';this._render();
    try{await this._hass.callService(domain,service,data);}catch(error){this._error=error.message || String(error);}
    finally{this._busy=false;this._render();}
  }
  _color(color){if(!/^#[0-9a-f]{6}$/i.test(color))return;return this._call('light','turn_on',{entity_id:this._config.entity,rgb_color:[1,3,5].map(i=>parseInt(color.slice(i,i+2),16))});}
  _render(){
    if(!this._config||!this._hass||this._interacting)return;
    const light=this._state('entity'),offline=!light||light.state==='unavailable';
    const disabled=this._busy||offline?'disabled':'';
    const on=light?.state==='on',unknown=light?.state==='unknown';
    const brightness=Math.round((light?.attributes.brightness??0)/255*100);
    const rgb=light?.attributes.rgb_color||[255,255,255];
    const currentColor='#'+rgb.map(v=>Math.round(v).toString(16).padStart(2,'0')).join('');
    const swatch=(label,color)=>`<button type="button" class="swatch" data-color="${color||'off'}" style="--bulb:${color||'#000000'};--ink:${color?tlInk(color):'#ff4040'}" title="${label==='X'?'Turn lights off':label}" aria-label="${label==='X'?'Turn lights off':`Set color ${label}`}" ${disabled}>${label}</button>`;
    const custom=i=>`<div class="cell">${swatch('',this._colors[i])}<label class="edit" title="Edit custom color ${i+1}">✎<input type="color" data-custom="${i}" value="${this._colors[i]}" aria-label="Edit custom color ${i+1}" ${disabled}></label></div>`;
    const options=[];
    for(const [key,label] of [['custom','Saved patterns'],['builtin','Built-in patterns']]){
      const state=this._state(key);if(!state||state.state==='unavailable')continue;
      options.push(`<optgroup label="${label}">${(state.attributes.options||[]).map((name,i)=>`<option value="${key}:${i}" ${state.state===name?'selected':''}>${tlEsc(name)}</option>`).join('')}</optgroup>`);
    }
    this.shadowRoot.innerHTML=`<style>
      :host{display:block;color:var(--primary-text-color);font-family:Roboto,Arial,sans-serif}*{box-sizing:border-box}
      ha-card{display:block;padding:16px;background:var(--ha-card-background,var(--card-background-color));border-radius:var(--ha-card-border-radius,16px)}
      .header,.brightness,.color{display:flex;align-items:center;gap:12px}.header{justify-content:space-between;margin-bottom:18px}.title{font-size:18px;font-weight:500}.state,.hint{font-size:12px;color:var(--secondary-text-color)}
      button,input,select{font:inherit}button{cursor:pointer}button:disabled,input:disabled,select:disabled{opacity:.5;cursor:wait}
      .power{min-height:44px;border:1px solid var(--divider-color);border-radius:24px;padding:8px 16px;background:${on?'var(--primary-color)':'var(--secondary-background-color)'};color:${on?'var(--text-primary-color)':'var(--primary-text-color)'}}
      .brightness{margin:16px 0}.brightness input{flex:1;min-width:0;accent-color:var(--primary-color);touch-action:none}.brightness output{min-width:42px;text-align:right}.color{justify-content:space-between;margin-bottom:12px}.color input{width:52px;height:38px;border:1px solid var(--divider-color);border-radius:8px;background:var(--secondary-background-color)}
      .palette{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px;justify-items:center;background:var(--secondary-background-color);border-radius:12px;padding:12px;touch-action:none}
      .swatch{display:grid;place-items:center;width:100%;max-width:44px;aspect-ratio:1;border:0;border-radius:50%;background:var(--bulb);color:var(--ink);font-size:12px;padding:0;user-select:none;-webkit-touch-callout:none}
      .cell{position:relative;width:100%;max-width:44px;aspect-ratio:1}.cell .swatch{height:100%}.edit{position:absolute;right:-3px;bottom:-3px;width:20px;height:20px;display:grid;place-items:center;border-radius:50%;background:var(--card-background-color);color:var(--primary-color);border:1px solid var(--divider-color);overflow:hidden}.edit input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}
      .expand{grid-column:1/-1;background:transparent;color:var(--primary-color);border:0;min-height:30px;width:100%}.pattern{display:block;margin:16px 0}.pattern select{display:block;width:100%;margin-top:6px;padding:10px;border-radius:8px;border:1px solid var(--divider-color);background:var(--secondary-background-color);color:var(--primary-text-color)}
      .error{color:var(--error-color);overflow-wrap:anywhere}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid var(--primary-color);outline-offset:2px}
    </style><ha-card>
      <div class="header"><div><div class="title">${tlEsc(this._config.title||'Trimlight')}</div><div class="state">${offline?'Unavailable':unknown?'Power unknown / timer mode':on?'On':'Off'}</div></div><button class="power" data-power aria-label="${on?'Turn off':'Turn on'}" ${disabled}>⏻ ${on?'Off':'On'}</button></div>
      ${this._error?`<p class="error" role="alert">${tlEsc(this._error)}</p>`:''}
      <label class="brightness">Brightness<input type="range" min="0" max="100" step="1" value="${brightness}" aria-label="Brightness" ${disabled}><output>${brightness}%</output></label>
      <label class="pattern">Pattern<select data-pattern aria-label="Pattern" ${this._busy||offline||!options.length?'disabled':''}><option value="" ${!['custom','builtin'].some(k=>this._state(k)?.attributes.options?.includes(this._state(k)?.state))?'selected':''} disabled>Choose a pattern</option>${options.join('')}</select></label>
      ${!options.length?'<p class="hint">No pattern options available. Check the preset entity IDs.</p>':''}
      <label class="color">Color<input type="color" data-picker value="${currentColor}" aria-label="Color" ${disabled}></label>
      <div class="palette">${TL_FIXED.map(([label,color])=>swatch(label,color)).join('')}${custom(0)}${custom(1)}${Array.from({length:this._expanded?14:7},(_,i)=>custom(i+2)).join('')}<button class="expand" aria-label="${this._expanded?'Hide fourth color row':'Show fourth color row'}" aria-expanded="${this._expanded}">${this._expanded?'⌃':'⌄'}</button></div>

    </ha-card>`;
    const root=this.shadowRoot;
    root.querySelector('[data-power]').onclick=()=>this._call('light',on?'turn_off':'turn_on',{entity_id:this._config.entity});
    const slider=root.querySelector('input[type=range]');
    slider.onpointerdown=()=>{this._interacting=true;};
    slider.oninput=()=>{this._interacting=true;root.querySelector('output').textContent=`${slider.value}%`;};
    slider.onchange=()=>{this._interacting=false;this._call('light','turn_on',{entity_id:this._config.entity,brightness_pct:Number(slider.value)});};
    slider.onpointerup=()=>{this._interacting=false;};slider.onpointercancel=()=>{this._interacting=false;this._render();};slider.onblur=()=>{this._interacting=false;};
    root.querySelector('[data-picker]').onchange=e=>this._color(e.target.value);
    root.querySelectorAll('[data-color]').forEach(el=>{el.onclick=()=>el.dataset.color==='off'?this._call('light','turn_off',{entity_id:this._config.entity}):this._color(el.dataset.color);});
    root.querySelectorAll('[data-custom]').forEach(el=>{el.onchange=()=>{const color=el.value;if(!/^#[0-9a-f]{6}$/i.test(color))return;this._colors[Number(el.dataset.custom)]=color;try{localStorage.setItem(this._storageKey,JSON.stringify(this._colors));}catch(_){}this._color(color);};});
    root.querySelector('.expand').onclick=()=>{this._expanded=!this._expanded;this._render();};
    root.querySelector('[data-pattern]').onchange=e=>{const [key,index]=e.target.value.split(':');if(!['custom','builtin'].includes(key))return;const option=this._state(key)?.attributes.options?.[Number(index)];if(option!==undefined)this._call('select','select_option',{entity_id:this._config[key],option});};
  }
}
if(!customElements.get('trimlight-control-card'))customElements.define('trimlight-control-card',TrimlightControlCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(c=>c.type==='trimlight-control-card'))window.customCards.push({type:'trimlight-control-card',name:'Trimlight Controls',description:'Power, horizontal brightness, RGB palette and patterns'});
