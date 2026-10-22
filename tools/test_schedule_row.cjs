/* Browser progress-row checks use simulated HA and never touch a controller. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const page=await browser.newPage({viewport:{width:390,height:350}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setContent('<style>html{--primary-color:#a968e8;--primary-text-color:#eee;--secondary-text-color:#bbb;--card-background-color:#20232c;--secondary-background-color:#303440;--divider-color:#505563;--error-color:#ff8888;font-family:Arial}body{margin:12px;background:#111}.card{padding:16px;background:var(--card-background-color);border-radius:16px}h3{color:#eee;font-size:17px}</style><div class="card"><h3>Trimlight Schedules and Playlist</h3><trimlight-schedule-row id="one"></trimlight-schedule-row><trimlight-schedule-row id="two"></trimlight-schedule-row></div>');
 await page.addScriptTag({content:fs.readFileSync(path.join(__dirname,'../www/trimlight-schedule-row.js'),'utf8')});
 await page.evaluate(()=>{window.calls=[];window.states={
 'switch.not_assigned_trimlight_daily_schedule_1':{state:'off',attributes:{friendly_name:'Daily Schedule 1',verification_status:'reported'}},
 'switch.not_assigned_trimlight_daily_schedule_2':{state:'on',attributes:{friendly_name:'Daily Schedule 2',verification_status:'reported'}}};
 const one=document.querySelector('#one'),two=document.querySelector('#two');one.setConfig({entity:'switch.not_assigned_trimlight_daily_schedule_1'});two.setConfig({entity:'switch.not_assigned_trimlight_daily_schedule_2'});
 window.publish=()=>{for(const row of [one,two])row.hass={states:window.states,callService:async(domain,service,data)=>{window.calls.push({domain,service,...data});if(window.fail)throw Error('Cloud rejected request');await new Promise(resolve=>window.finish=resolve);window.states[data.entity_id].attributes.verification_status='pending';window.publish()}}};window.publish();});
 const one=page.locator('#one'),two=page.locator('#two');assert.equal(await one.getByRole('switch').getAttribute('aria-checked'),'false');
 await one.getByRole('switch').click();assert.equal(await one.locator('.spinner').count(),1);assert.equal(await one.getByRole('switch').count(),0);
 assert.equal(await one.locator('.spinner').evaluate(el=>getComputedStyle(el).animationName),'spin');
 await page.evaluate(()=>document.querySelector('#one')._toggle());assert.equal(await page.evaluate(()=>window.calls.length),1);
 await page.evaluate(()=>window.finish());await page.waitForFunction(()=>!document.querySelector('#one')._busy);
 assert.equal(await one.locator('.spinner').count(),1);assert.equal(await two.getByRole('switch').count(),1);
 await page.screenshot({path:path.resolve(__dirname,'../../../outputs/trimlight-switch-progress-preview.png'),fullPage:true});
 await page.evaluate(()=>{window.states['switch.not_assigned_trimlight_daily_schedule_1']={state:'on',attributes:{friendly_name:'Daily Schedule 1',verification_status:'confirmed'}};window.publish()});assert.equal(await one.locator('.spinner').count(),0);assert.equal(await one.getByRole('switch').getAttribute('aria-checked'),'true');
 await page.evaluate(()=>window.fail=true);await one.getByRole('switch').click();await page.waitForFunction(()=>!document.querySelector('#one')._busy);assert.equal(await one.locator('.spinner').count(),0);assert.match(await one.getByRole('alert').textContent(),/Cloud rejected/);assert.equal((await page.evaluate(()=>window.calls.at(-1))).service,'turn_off');
 await page.evaluate(()=>{window.states['switch.not_assigned_trimlight_daily_schedule_2'].attributes.verification_status='not_confirmed';window.publish()});assert.match(await two.getByRole('alert').textContent(),/not confirmed/);
 await page.evaluate(()=>{window.states['switch.not_assigned_trimlight_daily_schedule_2'].state='unavailable';window.publish()});assert.equal(await two.getByRole('switch').isDisabled(),true);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.deepEqual(errors,[]);
 console.log('PASS: rotating progress during request and pending, no on/off buttons while waiting, no duplicate writes, confirmed toggle restore, rejected/unconfirmed/offline handling, independent rows and phone layout');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
