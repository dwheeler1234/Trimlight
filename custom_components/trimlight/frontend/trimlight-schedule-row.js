/* Custom entities-card row for daily switches with pending progress feedback. */
const tsrEscape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
class TrimlightScheduleRow extends HTMLElement {
 constructor(){super();this.attachShadow({mode:'open'});this._busy=false;this._error='';}
 setConfig(config){if(!/^switch\.[a-z0-9_]+$/.test(config.entity||''))throw Error('Configure a daily schedule switch entity');this._config={...config};this._signature=null;this._render();}
 set hass(hass){this._hass=hass;const state=hass.states[this._config?.entity];const signature=JSON.stringify([state?.state,state?.attributes.verification_status,state?.attributes.friendly_name,state?.attributes.reported_enabled]);if(signature!==this._signature){this._signature=signature;this._render();}}
 async _toggle(){
  const state=this._hass?.states[this._config.entity];
  if(this._busy||!state||!['on','off'].includes(state.state)||state.attributes.verification_status==='pending')return;
  this._busy=true;this._error='';this._render();
  try{await this._hass.callService('switch',state.state==='on'?'turn_off':'turn_on',{entity_id:this._config.entity});}
  catch(error){this._error=error.message||String(error);}
  finally{this._busy=false;this._render();}
 }
 _render(){
  if(!this._config||!this._hass)return;
  const state=this._hass.states[this._config.entity];
  const pending=this._busy||state?.attributes.verification_status==='pending';
  const on=state?.state==='on',available=Boolean(state&&['on','off'].includes(state.state));
  const status=state?.attributes.verification_status;
  const note=this._error||(status==='not_confirmed'?'Change not confirmed by controller':status==='read_failed'?'Unable to confirm controller state':'');
  const label=this._config.name||state?.attributes.friendly_name||'Daily schedule';
  this.shadowRoot.innerHTML=`<style>
   :host{display:block;color:var(--primary-text-color);font-family:inherit}.row{display:flex;align-items:center;gap:16px;min-height:48px}ha-icon{width:24px;height:24px;flex:0 0 24px;color:${on?'var(--state-switch-active-color,var(--primary-color))':'var(--state-icon-color,var(--secondary-text-color))'}}
   .label{flex:1;min-width:0;overflow-wrap:anywhere}.note{font-size:12px;color:var(--error-color);margin-top:4px}.pending{display:flex;align-items:center;justify-content:center;width:48px;height:44px;flex:0 0 48px}.spinner{width:24px;height:24px;box-sizing:border-box;border:3px solid var(--divider-color);border-top-color:var(--primary-color);border-radius:50%;animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
   button{display:grid;place-items:center;border:0;background:transparent;cursor:pointer;min-width:48px;min-height:44px;padding:0;flex:0 0 48px}button:disabled{opacity:.4;cursor:default}.track{display:block;position:relative;width:36px;height:18px;border-radius:12px;background:${on?'var(--primary-color)':'var(--disabled-text-color,var(--secondary-text-color))'}}.thumb{display:block;position:absolute;top:-2px;left:${on?'16px':'-2px'};width:22px;height:22px;border-radius:50%;background:var(--card-background-color);box-shadow:0 1px 4px #0005}button:focus-visible{outline:2px solid var(--primary-color);border-radius:8px}.unavailable{font-size:12px;color:var(--secondary-text-color)}
  </style><div class="row" aria-busy="${pending}"><ha-icon icon="mdi:timer-outline" aria-hidden="true"></ha-icon><div class="label">${tsrEscape(label)}${note?`<div class="note" role="alert">${tsrEscape(note)}</div>`:''}${!available&&!pending?'<div class="unavailable">Unavailable</div>':''}</div>
  ${pending?`<div class="pending" role="status" aria-label="Updating ${tsrEscape(label)}"><span class="spinner" aria-hidden="true"></span></div>`:`<button type="button" role="switch" aria-label="${tsrEscape(label)}" aria-checked="${on}" ${available?'':'disabled'}><span class="track" aria-hidden="true"><span class="thumb"></span></span></button>`}</div>`;
  const toggle=this.shadowRoot.querySelector('button');if(toggle)toggle.onclick=()=>this._toggle();
 }
}
if(!customElements.get('trimlight-schedule-row'))customElements.define('trimlight-schedule-row',TrimlightScheduleRow);
