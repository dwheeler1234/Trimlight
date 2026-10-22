/* Trimlight controller daily timers: local forms with explicit, per-slot saves. */
const TT_REPEAT=[['today_only','Today only'],['everyday','Every day'],['weekdays','Weekdays'],['weekend','Weekend']];
const ttEsc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
class TrimlightTimerCard extends HTMLElement {
 constructor(){super();this.attachShadow({mode:'open'});this._drafts={};this._busy=false;this._error='';this._message='';}
 setConfig(config){
  if(config.timer!==undefined&&config.timer!==1&&config.timer!==2)throw Error('timer must be 1 or 2');
  const entity=config.entity||'sensor.trimlight_daily_schedules';
  if(!/^sensor\.[a-z0-9_]+_daily_schedules$/.test(entity)&&!config.operating_mode_entity)throw Error('Use the daily schedules sensor, or provide operating_mode_entity for renamed sensors');
  if(!/^sensor\.[a-z0-9_]+$/.test(entity))throw Error('Use a valid schedules sensor');
  const prefix=entity.split('.')[1].replace(/_daily_schedules$/,'');
  const mode=config.operating_mode_entity||`select.${prefix}_operating_mode`;
  if(!/^select\.[a-z0-9_]+$/.test(mode))throw Error('Use a valid operating mode entity');
  if(config.time_encoding&&!['clock','one_based'].includes(config.time_encoding))throw Error('time_encoding must be clock or one_based');
  this._config={...config,entity,mode,time_encoding:config.time_encoding||'clock'};
  this._entryId=config.config_entry_id||null;this._entryLookup=false;this._drafts={};this._render();
 }
 set hass(value){this._hass=value;if(!this._config)return;this._sync();this._resolveEntry();const focused=this.shadowRoot.activeElement;if(focused&&['INPUT','SELECT'].includes(focused.tagName))return;this._render();}
 getCardSize(){return this._config?.timer?7:12;}
 static getStubConfig(){return {entity:'sensor.trimlight_daily_schedules',timer:1};}
 _sensor(){return this._hass?.states[this._config?.entity];}
 _records(){return this._sensor()?.attributes.schedules||[];}
 _record(id){return this._records().find(row=>row.id===id);}
 _time(raw){if(!raw)return '';const offset=this._config.time_encoding==='one_based'?1:0;const h=Number(raw.hours)-offset,m=Number(raw.minutes)-offset;if(!Number.isInteger(h)||!Number.isInteger(m)||h<0||h>23||m<0||m>59)return '';return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;}
 _makeDraft(id){const row=this._record(id);return {enabled:Boolean(row?.enable),effect:row?.effectId??'',repetition:TT_REPEAT[row?.repetition]?.[0]||'everyday',start:this._time(row?.startTime),end:this._time(row?.endTime),dirty:false,baseline:JSON.stringify(row??null),original:row?JSON.parse(JSON.stringify(row)):null};}
 _sync(){for(let id=0;id<2;id++)if(!this._drafts[id]?.dirty)this._drafts[id]=this._makeDraft(id);}
 async _resolveEntry(){
  if(this._entryId||this._entryLookup||!this._hass?.callWS)return;
  this._entryLookup=true;
  try{const rows=await this._hass.callWS({type:'config/entity_registry/list'});const row=rows.find(r=>r.entity_id===this._config.entity);if(row?.platform==='trimlight'&&row.config_entry_id)this._entryId=row.config_entry_id;else this._error='Cannot identify this Trimlight controller. Set config_entry_id in the card configuration.';}
  catch(error){this._error='Cannot read entity registry. Set config_entry_id in the card configuration.';}
  this._render();
 }
 _rawTime(text,original){
  // Preserve device-reported values exactly when the field was not changed.
  if(original&&text===this._time(original))return {...original};
  if(!/^\d{2}:\d{2}$/.test(text))throw Error('Choose both start and off times. Existing values outside clock range require the correct time_encoding setting.');
  const [h,m]=text.split(':').map(Number);if(h>23||m>59)throw Error('Invalid clock time');
  const offset=this._config.time_encoding==='one_based'?1:0;return {hours:h+offset,minutes:m+offset};
 }
 async _save(id){
  if(this._busy)return;this._error='';this._message='';
  try{
   if(this._config.timer&&id!==this._config.timer-1)throw Error('This card can only save its assigned timer');
   const draft=this._drafts[id];if(!this._entryId)throw Error('Controller configuration entry is not resolved.');
   if(['unknown','unavailable'].includes(this._sensor()?.state)||!this._sensor())throw Error('Schedules sensor is unavailable.');
   if(JSON.stringify(this._record(id)??null)!==draft.baseline)throw Error(`Timer ${id+1} changed on the controller while you were editing. Reload that timer before saving.`);
   if(draft.effect==='')throw Error('Choose a saved pattern or combined-effect playlist.');
   const effect=Number(draft.effect);if(!Number.isInteger(effect)||!(effect>=0&&effect<=59||effect===200))throw Error('Invalid saved pattern ID');
   const data={config_entry_id:this._entryId,schedule_id:id,enabled:this._record(id)?.enable??draft.enabled,effect_id:effect,repetition:draft.repetition,start_time:this._rawTime(draft.start,draft.original?.startTime),end_time:this._rawTime(draft.end,draft.original?.endTime)};
   this._busy=true;this._render();
   await this._hass.callService('trimlight','set_daily_schedule',data);
   // Do not discard edits if the accepted write's follow-up read is delayed.
   const reported=this._record(id);
   const confirmed=reported&&reported.enable===data.enabled&&reported.effectId===data.effect_id&&reported.repetition===TT_REPEAT.findIndex(([key])=>key===data.repetition)&&JSON.stringify(reported.startTime)===JSON.stringify(data.start_time)&&JSON.stringify(reported.endTime)===JSON.stringify(data.end_time);
   if(confirmed)draft.dirty=false;
   draft.baseline=JSON.stringify(reported??null);draft.original=reported?JSON.parse(JSON.stringify(reported)):null;
   this._message=confirmed?`Timer ${id+1} settings confirmed by controller readback.`:`Timer ${id+1} save request accepted, but controller readback has not confirmed the changes. Refresh controller before retrying.`;
  }catch(error){this._error=error.message||String(error);}
  finally{this._busy=false;this._render();}
 }
 async _toggleEnabled(id,enabled){
  if(this._busy)return;this._error='';this._message='';
  try{
   if(this._config.timer&&id!==this._config.timer-1)throw Error('This card can only change its assigned timer');
   if(!this._entryId)throw Error('Controller configuration entry is not resolved.');
   const before=this._record(id);if(!before)throw Error('Save this timer definition before enabling it.');
   const draft=this._drafts[id];
   const withoutEnable=row=>{if(!row)return null;const copy={...row};delete copy.enable;return JSON.stringify(copy);};
   const sameDefinition=withoutEnable(draft.original)===withoutEnable(before);
   this._busy=true;this._render();
   await this._hass.callService('trimlight','enable_daily_schedule',{config_entry_id:this._entryId,schedule_id:id,enabled});
   const reported=this._record(id);
   // Rebase only our enable change; do not hide conflicts in other saved fields.
   if(sameDefinition&&withoutEnable(before)===withoutEnable(reported)){
    draft.enabled=Boolean(reported?.enable);draft.baseline=JSON.stringify(reported??null);draft.original=reported?JSON.parse(JSON.stringify(reported)):null;
   }
   const confirmed=reported?.enable===enabled;
   this._message=confirmed?`Timer ${id+1} ${enabled?'enabled':'disabled'} on the controller.`:`Timer ${id+1} ${enabled?'enable':'disable'} request accepted; awaiting controller readback.`;
   if(enabled&&this._hass.states[this._config.mode]?.state!=='Timer')this._message+=' Select Use Timer mode to run controller schedules.';
   if(draft.dirty)this._message+=' Other form edits are not saved yet.';
  }catch(error){this._error=error.message||String(error);}
  finally{this._busy=false;this._render();}
 }
 async _refreshController(){
  if(this._busy)return;this._busy=true;this._error='';this._message='';this._render();
  try{await this._hass.callService('homeassistant','update_entity',{entity_id:this._config.entity});this._message='Controller refresh requested. Enabled follows reported state; Reload timer replaces unsaved form edits.';}
  catch(error){this._error=error.message||String(error);}finally{this._busy=false;this._render();}
 }
 async _timerMode(){if(this._busy)return;this._busy=true;this._error='';this._message='';this._render();try{await this._hass.callService('select','select_option',{entity_id:this._config.mode,option:'Timer'});this._message='Timer mode requested.';}catch(error){this._error=error.message||String(error);}finally{this._busy=false;this._render();}}
 _render(){
  if(!this._config||!this._hass)return;this._sync();
  const sensor=this._sensor(),offline=!sensor||['unknown','unavailable'].includes(sensor.state);
  const disabled=this._busy||offline?'disabled':'';
  const presets=sensor?.attributes.presets||[];const playlist=sensor?.attributes.playlist_available;
  const mode=this._hass.states[this._config.mode];
  const form=id=>{const d=this._drafts[id];const has=presets.some(p=>p.id===Number(d.effect))||(Number(d.effect)===200&&playlist);
   const patternOptions=presets.map(p=>`<option value="${p.id}" ${Number(d.effect)===p.id&&d.effect!==''?'selected':''}>${ttEsc(p.name||'Unnamed')} (id ${p.id})</option>`).join('')+(playlist?`<option value="200" ${Number(d.effect)===200?'selected':''}>Combined-effect playlist</option>`:'');
   return `<form data-timer="${id}"><div class="heading"><h3>Timer ${id+1}</h3><label class="enable"><input type="checkbox" data-enable="${id}" ${this._record(id)?.enable?'checked':''} ${this._busy||offline||!this._entryId||!this._record(id)?'disabled':''}>Enabled</label></div>
   <label>Repetition<select data-field="repetition" ${disabled}>${TT_REPEAT.map(([key,label])=>`<option value="${key}" ${d.repetition===key?'selected':''}>${label}</option>`).join('')}</select></label>
   <label>Library / pattern<select data-field="effect" ${disabled}><option value="" disabled ${d.effect===''?'selected':''}>Choose saved pattern</option>${d.effect!==''&&!has?`<option value="${Number(d.effect)}" selected>Unavailable saved pattern (id ${Number(d.effect)})</option>`:''}${patternOptions}</select></label>
   <div class="times"><label>Start time<input type="time" data-field="start" value="${ttEsc(d.start)}" step="60" required ${disabled}></label><label>Off time<input type="time" data-field="end" value="${ttEsc(d.end)}" step="60" required ${disabled}></label></div>
   <div class="actions"><button type="button" data-reload="${id}" ${this._busy?'disabled':''}>Reload timer</button><button class="primary" type="submit" ${this._busy||offline||!this._entryId?'disabled':''}>Save Timer ${id+1}</button></div><p class="hint">${d.dirty?'Unsaved form changes.':'Loaded controller settings.'}</p></form>`;};
  this.shadowRoot.innerHTML=`<style>:host{display:block;color:var(--primary-text-color);font-family:Roboto,Arial,sans-serif}*{box-sizing:border-box}ha-card{display:block;padding:16px;background:var(--ha-card-background,var(--card-background-color));border-radius:var(--ha-card-border-radius,16px)}h2{font-size:18px;margin:0 0 12px}h3{font-size:16px;margin:0}.heading,.actions{display:flex;align-items:center;justify-content:space-between;gap:12px}.heading{margin-bottom:12px}form{background:var(--secondary-background-color);border:1px solid var(--divider-color);border-radius:12px;padding:14px;margin-top:14px}label{display:block;font-size:14px;margin-bottom:12px}input,select,button{font:inherit}select,input[type=time]{display:block;width:100%;min-width:0;margin-top:6px;padding:9px;border:1px solid var(--divider-color);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color)}.enable{display:flex;align-items:center;gap:6px;margin:0}.enable input{accent-color:var(--primary-color);width:20px;height:20px}.times{display:grid;grid-template-columns:1fr 1fr;gap:12px}button{min-height:40px;border:1px solid var(--divider-color);border-radius:8px;padding:8px 12px;cursor:pointer;color:var(--primary-text-color);background:var(--card-background-color)}.primary{background:var(--primary-color);color:var(--text-primary-color)}button:disabled,input:disabled,select:disabled{opacity:.5;cursor:wait}.hint,.mode{font-size:12px;color:var(--secondary-text-color);line-height:1.5}.error{color:var(--error-color);overflow-wrap:anywhere}.message{color:var(--primary-color);font-size:13px}.hint{margin-bottom:0}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--primary-color)}@media(max-width:340px){.times{grid-template-columns:1fr}.actions{gap:6px;flex-wrap:wrap}}</style><ha-card><h2>${ttEsc(this._config.title||(this._config.timer?`Trimlight Timer ${this._config.timer}`:'Trimlight Timers'))}</h2><p class="mode">Operating mode: ${ttEsc(mode?.state||'Unavailable')}</p><button data-mode ${this._busy||!mode||['unknown','unavailable'].includes(mode.state)?'disabled':''}>Use Timer mode</button> <button data-refresh ${this._busy?'disabled':''}>Refresh controller</button>
  <p class="hint">Enabled applies immediately to the saved timer. Save applies pattern, repetition and time edits separately. Use Timer mode to run controller schedules. Off times earlier than start can cross midnight; verify execution in the app.</p>
  ${offline?'<p class="error">Daily schedules sensor unavailable. Check the entity ID and integration connection.</p>':''}${!this._entryId?'<p class="hint">Resolving controller configuration entry…</p>':''}${this._error?`<p class="error" role="alert">${ttEsc(this._error)}</p>`:''}${this._message?`<p class="message" role="status">${ttEsc(this._message)}</p>`:''}${this._config.timer?form(this._config.timer-1):form(0)+form(1)}</ha-card>`;
  this.shadowRoot.querySelector('[data-refresh]').onclick=()=>this._refreshController();
  this.shadowRoot.querySelector('[data-mode]').onclick=()=>this._timerMode();
  this.shadowRoot.querySelectorAll('[data-enable]').forEach(input=>{input.onchange=()=>this._toggleEnabled(Number(input.dataset.enable),input.checked);});
  this.shadowRoot.querySelectorAll('form').forEach(form=>{const id=Number(form.dataset.timer);form.onsubmit=event=>{event.preventDefault();this._save(id);};
   form.querySelectorAll('[data-field]').forEach(input=>{const update=()=>{this._drafts[id][input.dataset.field]=input.type==='checkbox'?input.checked:input.value;this._drafts[id].dirty=true;form.querySelector('.hint').textContent='Unsaved form changes.';};input.oninput=update;input.onchange=update;});
  });
  this.shadowRoot.querySelectorAll('[data-reload]').forEach(button=>{button.onclick=()=>{this._drafts[Number(button.dataset.reload)]=this._makeDraft(Number(button.dataset.reload));this._error='';this._message='';this._render();};});
 }
}
if(!customElements.get('trimlight-timer-card'))customElements.define('trimlight-timer-card',TrimlightTimerCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(c=>c.type==='trimlight-timer-card'))window.customCards.push({type:'trimlight-timer-card',name:'Trimlight Timers',description:'Edit both controller daily timers with explicit saves'});
