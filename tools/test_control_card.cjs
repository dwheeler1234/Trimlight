const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const page=await browser.newPage({viewport:{width:390,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setContent('<style>html{--primary-color:#a968e8;--primary-text-color:#eee;--secondary-text-color:#bbb;--card-background-color:#20232c;--secondary-background-color:#303440;--divider-color:#505563;--text-primary-color:#fff;--error-color:#ff8888}body{margin:12px;background:#111}</style><trimlight-control-card></trimlight-control-card>');
 await page.addScriptTag({content:fs.readFileSync(path.join(__dirname,'../www/trimlight-control-card.js'),'utf8')});
 await page.evaluate(()=>{const card=document.querySelector('trimlight-control-card');card.setConfig({entity:'light.not_assigned_trimlight'});window.calls=[];window.states={
  'light.not_assigned_trimlight':{state:'on',attributes:{brightness:128,rgb_color:[255,0,0]}},
  'select.not_assigned_trimlight_custom_preset':{state:'Security',attributes:{options:['Security','Game Day']}},
  'select.not_assigned_trimlight_custom_effect_mode':{state:'Static',attributes:{options:['Static','Chase Forward']}},
  'number.not_assigned_trimlight_effect_speed':{state:'40',attributes:{min:0,max:100,step:1}},
  'number.not_assigned_trimlight_effect_length':{state:'30',attributes:{min:1,max:90,step:1}},
  'switch.not_assigned_trimlight_reverse_animation':{state:'off',attributes:{}},
  'select.not_assigned_trimlight_built_in_preset':{state:'unknown',attributes:{options:['Rainbow','Wave']}}};
 window.publish=()=>{card.hass={states:window.states,callService:async(domain,service,data)=>{window.calls.push({domain,service,...data});if(window.fail)throw Error('Request failed');if(domain==='light'&&service==='turn_off')window.states[data.entity_id].state='off';if(domain==='select')window.states[data.entity_id].state=data.option;if(domain==='number')window.states[data.entity_id].state=String(data.value);if(domain==='switch')window.states[data.entity_id].state=service==='turn_on'?'on':'off';window.publish();}}};window.publish();});
 assert.equal(await page.locator('[data-pattern]').evaluate(el => Boolean(el.closest('.pattern').compareDocumentPosition(el.getRootNode().querySelector('.color')) & Node.DOCUMENT_POSITION_FOLLOWING)),true);
 assert.equal(await page.locator('[data-color]').count(),7);
 await page.locator('.expand').click();assert.equal(await page.locator('[data-color]').count(),28);
 await page.locator('[data-power]').click();assert.equal((await page.evaluate(()=>window.calls.at(-1))).service,'turn_off');
 await page.locator('[data-color="#00ff00"]').click();assert.deepEqual((await page.evaluate(()=>window.calls.at(-1))).rgb_color,[0,255,0]);
 await page.locator('[data-picker]').evaluate(el=>{el.value='#112233';el.dispatchEvent(new Event('change',{bubbles:true}));});assert.deepEqual((await page.evaluate(()=>window.calls.at(-1))).rgb_color,[17,34,51]);
 await page.locator('input[type=range]:not([data-number])').evaluate(el=>{el.value='75';el.dispatchEvent(new Event('input'));el.dispatchEvent(new Event('change'));});assert.equal((await page.evaluate(()=>window.calls.at(-1))).brightness_pct,75);
 await page.locator('[data-pattern]').selectOption('builtin:1');assert.equal((await page.evaluate(()=>window.calls.at(-1))).entity_id,'select.not_assigned_trimlight_built_in_preset');assert.equal((await page.evaluate(()=>window.calls.at(-1))).option,'Wave');
 await page.locator('[data-pattern]').selectOption('custom:1');assert.equal((await page.evaluate(()=>window.calls.at(-1))).option,'Game Day');
 await page.locator('[data-effect]').selectOption('1');assert.equal((await page.evaluate(()=>window.calls.at(-1))).option,'Chase Forward');
 await page.locator('[data-number="speed"]').evaluate(el=>{el.value='65';el.dispatchEvent(new Event('change'));});assert.equal((await page.evaluate(()=>window.calls.at(-1))).value,65);assert.equal((await page.evaluate(()=>window.calls.at(-1))).entity_id,'number.not_assigned_trimlight_effect_speed');
 await page.locator('[data-reverse]').click();assert.equal((await page.evaluate(()=>window.calls.at(-1))).service,'turn_on');assert.equal(await page.locator('[data-reverse]').getAttribute('aria-checked'),'true');
 await page.locator('[data-reverse]').click();assert.equal((await page.evaluate(()=>window.calls.at(-1))).service,'turn_off');
 await page.evaluate(()=>{window.states['number.not_assigned_trimlight_effect_length'].state='unavailable';window.states['switch.not_assigned_trimlight_reverse_animation'].state='unavailable';window.publish()});
 assert.equal(await page.locator('[data-number="length"]').count(),0);assert.equal(await page.locator('[data-reverse]').isDisabled(),true);
 await page.locator('.expand').click();assert.equal(await page.locator('[data-color]').count(),7);
 await page.evaluate(()=>{window.states['light.not_assigned_trimlight'].state='unknown';window.publish()});assert.match(await page.locator('.state').textContent(),/unknown/);
 await page.evaluate(()=>{window.fail=true});await page.locator('[data-power]').click();assert.match(await page.locator('[role=alert]').textContent(),/Request failed/);
 await page.evaluate(()=>{window.fail=false;window.states['light.not_assigned_trimlight'].state='on';document.querySelector('trimlight-control-card')._error='';window.publish()});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.screenshot({path:path.resolve(__dirname,'../../../outputs/trimlight-controls-preview.png'),fullPage:true});
 await page.evaluate(()=>{window.states['light.not_assigned_trimlight'].state='unavailable';window.publish()});assert.equal(await page.locator('[data-power]').isDisabled(),true);
 assert.deepEqual(errors,[]);console.log('PASS: power, horizontal brightness, RGB picker/palette, both preset groups, entity inference, expanded colors, unknown/offline/error states and phone-width layout');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
