/* Browser checks use simulated schedules and never contact a controller. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const page=await browser.newPage({viewport:{width:390,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setContent('<style>html{--primary-color:#a968e8;--primary-text-color:#eee;--secondary-text-color:#bbb;--card-background-color:#20232c;--secondary-background-color:#303440;--divider-color:#505563;--text-primary-color:#fff;--error-color:#ff8888}body{margin:12px;background:#111}</style><trimlight-timer-card></trimlight-timer-card>');
 await page.addScriptTag({content:fs.readFileSync(path.join(__dirname,'../www/trimlight-timer-card.js'),'utf8')});
 await page.evaluate(()=>{const card=document.querySelector('trimlight-timer-card');card.setConfig({entity:'sensor.not_assigned_trimlight_daily_schedules'});window.calls=[];window.registryCalls=0;
 window.states={
 'sensor.not_assigned_trimlight_daily_schedules':{state:'2',attributes:{schedules:[
 {id:0,enable:true,effectId:13,repetition:1,startTime:{hours:19,minutes:0},endTime:{hours:22,minutes:30}},
 {id:1,enable:false,effectId:1,repetition:0,startTime:{hours:0,minutes:2},endTime:{hours:0,minutes:3}}],presets:[{id:13,name:'Security'},{id:1,name:'Holiday <test>'}],playlist_available:true}},
 'select.not_assigned_trimlight_operating_mode':{state:'Manual',attributes:{options:['Off','Manual','Timer']}}};
 window.publish=()=>{card.hass={states:window.states,callWS:async()=>{window.registryCalls++;return [{entity_id:'sensor.not_assigned_trimlight_daily_schedules',platform:'trimlight',config_entry_id:'entry-one'}]},callService:async(domain,service,data)=>{window.calls.push({domain,service,...data});if(window.fail)throw Error('Controller rejected save');if(service==='enable_daily_schedule'&&!window.stale)window.states['sensor.not_assigned_trimlight_daily_schedules'].attributes.schedules.find(r=>r.id===data.schedule_id).enable=data.enabled;if(service==='set_daily_schedule'){const records=window.states['sensor.not_assigned_trimlight_daily_schedules'].attributes.schedules;records[data.schedule_id]={id:data.schedule_id,enable:data.enabled,effectId:data.effect_id,repetition:['today_only','everyday','weekdays','weekend'].indexOf(data.repetition),startTime:data.start_time,endTime:data.end_time}}if(domain==='select')window.states[data.entity_id].state=data.option;window.publish();}}};window.publish();});
 const first=page.locator('form[data-timer="0"]'),second=page.locator('form[data-timer="1"]');
 await page.waitForFunction(()=>Boolean(document.querySelector('trimlight-timer-card')._entryId));
 assert.equal(await page.locator('form').count(),2);
 assert.equal(await first.locator('[data-field="start"]').inputValue(),'19:00');
 assert.equal(await second.locator('[data-field="start"]').inputValue(),'00:02');
 assert.equal(await page.locator('[data-enable]').count(),0);
 assert.equal(await second.locator('[data-field="effect"] option[value="1"]').textContent(),'Holiday <test> (id 1)');
 await second.locator('[data-field="start"]').fill('00:00');await second.locator('[data-field="end"]').fill('06:00');
 await second.locator('[data-field="effect"]').selectOption('200');await second.locator('[data-field="repetition"]').selectOption('weekend');
 assert.equal(await second.locator('[data-field="start"]').inputValue(),'00:00');
 await page.evaluate(()=>window.publish());assert.equal(await second.locator('[data-field="start"]').inputValue(),'00:00');
 await second.locator('button[type=submit]').click();await page.waitForFunction(()=>!document.querySelector('trimlight-timer-card')._busy);
 let calls=await page.evaluate(()=>window.calls);assert.equal(calls.length,1);assert.equal(calls[0].enabled,false);calls=calls.filter(c=>c.service==='set_daily_schedule');assert.equal(calls[0].schedule_id,1);assert.equal(calls[0].config_entry_id,'entry-one');assert.equal(calls[0].effect_id,200);assert.equal(calls[0].repetition,'weekend');assert.deepEqual(calls[0].start_time,{hours:0,minutes:0});assert.deepEqual(calls[0].end_time,{hours:6,minutes:0});
 assert.equal(await first.locator('[data-field="start"]').inputValue(),'19:00');
 await first.locator('[data-field="end"]').fill('23:00');await page.evaluate(()=>{window.states['sensor.not_assigned_trimlight_daily_schedules'].attributes.schedules[0].endTime={hours:21,minutes:0};window.publish()});
 await first.locator('button[type=submit]').click();assert.match(await page.locator('[role=alert]').textContent(),/changed on the controller/);assert.equal(await page.evaluate(()=>window.calls.length),1);
 await first.locator('[data-reload]').click();assert.equal(await first.locator('[data-field="end"]').inputValue(),'21:00');
 await page.evaluate(()=>window.fail=true);await first.locator('[data-field="start"]').fill('20:00');await first.locator('button[type=submit]').click();await page.waitForFunction(()=>!document.querySelector('trimlight-timer-card')._busy);assert.match(await page.locator('[role=alert]').textContent(),/Controller rejected/);assert.equal(await first.locator('[data-field="start"]').inputValue(),'20:00');
 await page.evaluate(()=>window.fail=false);
 assert.equal(await page.locator('[data-mode], [data-refresh], .mode').count(),0);
 assert.equal(await page.locator('trimlight-timer-card').getByText('Save applies pattern', {exact:false}).count(),0);
 await first.locator('[data-reload]').click();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.screenshot({path:path.resolve(__dirname,'../../../outputs/trimlight-timers-preview.png'),fullPage:true});
 await page.evaluate(()=>{window.states['sensor.not_assigned_trimlight_daily_schedules'].state='unavailable';window.publish()});assert.equal(await first.locator('button[type=submit]').isDisabled(),true);
 await page.evaluate(()=>{
  window.states['sensor.not_assigned_trimlight_daily_schedules'].state='2';window.publish();
  const source=document.querySelector('trimlight-timer-card');
  for(const timer of [1,2]){const card=document.createElement('trimlight-timer-card');card.dataset.single=timer;card.setConfig({entity:'sensor.not_assigned_trimlight_daily_schedules',timer,config_entry_id:'entry-one'});document.body.append(card);card.hass=source._hass;}
 });
 const one=page.locator('trimlight-timer-card[data-single="1"]'),two=page.locator('trimlight-timer-card[data-single="2"]');
 assert.equal(await one.locator('form').count(),1);assert.equal(await one.locator('form').getAttribute('data-timer'),'0');
 assert.equal(await two.locator('form').count(),1);assert.equal(await two.locator('form').getAttribute('data-timer'),'1');
 await one.locator('[data-field="start"]').fill('18:00');await one.locator('button[type=submit]').click();assert.equal((await page.evaluate(()=>window.calls.at(-1))).schedule_id,0);assert.equal((await page.evaluate(()=>window.calls.at(-1))).enabled,true);
 await two.locator('[data-field="start"]').fill('01:00');await two.locator('button[type=submit]').click();assert.equal((await page.evaluate(()=>window.calls.at(-1))).schedule_id,1);
 await page.screenshot({path:path.resolve(__dirname,'../../../outputs/trimlight-separate-timers-preview.png'),fullPage:true});
 assert.equal(await page.evaluate(()=>window.calls.some(c=>c.service==='enable_daily_schedule')),false);
 assert.deepEqual(errors,[]);console.log('PASS: two timer forms, real reported times, midnight, repetition/playlist, explicit entry targeting, no operating-mode/refresh controls, dirty-form protection, stale-conflict guard, errors, reload, offline and mobile layout');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
