// Built email-centre UI; synthetic accounts, no source or production writes.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { monitoringEmailCentreCopy } from '../apps/web/lib/monitoring-email-centre-copy.ts';
import { monitoringNavigation } from '../apps/web/lib/monitoring-navigation.ts';
import { Cdp, evaluate, sleep } from './browser-cdp.mjs';
import { AccessibilityAudit } from './browser-accessibility.mjs';

const root=resolve(import.meta.dirname,'..');
const chrome=[process.env.CHROME_BIN,'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe','/usr/bin/google-chrome'].filter(Boolean).find(existsSync);assert.ok(chrome);
const reserve=createServer();await new Promise(r=>reserve.listen(0,'127.0.0.1',r));const port=reserve.address().port;await new Promise(r=>reserve.close(r));const base=`http://127.0.0.1:${port}`;
const server=spawn(process.execPath,[join(root,'node_modules/next/dist/bin/next'),'start','-H','127.0.0.1','-p',String(port)],{cwd:join(root,'apps/web'),stdio:'ignore',windowsHide:true});
const profile=await mkdtemp(join(tmpdir(),'helvetic-monitoring-email-centre-'));
const browser=spawn(chrome,['--headless=new','--no-email-centre','--no-default-browser-check','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{stdio:'ignore',windowsHide:true});
const audit=new AccessibilityAudit('monitoring-email-centre'),requests=[],exceptions=[];
let cdp,locale='en-CH',role='organization_admin',user='qa',navigation=0,fail=false,hold=false,held,denied=false,paginated=false;
const rows=monitoringNavigation.map(item=>({id:item.id,domain:item.id,name:`Private ${item.id}`,station_id:null,status:'active',href:item.href}));
const defaults=()=>({revision:0,monitor_version:1,configuration:{timezone:'Europe/Zurich',delivery:{email:'off',digest_at:null,quiet_hours:null}},consent_active:false,email_verified:true,uncertain_deliveries:0,mail_available:false,delivery_service_available:false,recipient_email:'qa@example.invalid'});
let policies={},pollen;
function reset(){policies=Object.fromEntries(rows.map(row=>[row.id,defaults()]));pollen={id:'pollen',status:'active',revision:1,configuration:{station_id:'BAS',timezone:'Europe/Zurich',selections:[{allergen:'grass',rules:[]}],delivery:{email:'daily_digest',digest_at:'08:00',quiet_hours:null}},runtime:{version:1,email_consent:true,muted:false},start_available:true,blocking_reasons:[],coverage:[],current:[]};}
reset();
const identity=()=>({authenticated:true,user:{id:user,name:user,email:'qa@example.invalid',locale},organization:{id:'qa-org',name:'QA'},role,onboarding_required:false});
const writes=()=>requests.filter(r=>!['GET','HEAD'].includes(r.method)&&!r.path.startsWith('/api/assistant/'));
async function navigate(){await evaluate(cdp,'window.__previousEmailCentre=true');await cdp.send('Page.navigate',{url:base+`/monitoring/email?qa=${++navigation}&locale=${locale}`});await wait(()=>evaluate(cdp,`!window.__previousEmailCentre&&document.documentElement.lang===${JSON.stringify(locale)}&&document.querySelectorAll('[data-email-monitor]').length===${paginated?2:9}`),'Email centre did not load');}
async function setValue(selector,value){await evaluate(cdp,`(()=>{const el=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(el.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype,'value').set.call(el,${JSON.stringify(value)});el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{bubbles:true}));})()`);}
async function pick(domain){await click(`[data-email-monitor="${domain}:${domain}"]`);if(domain!=='pollen')await click('[data-email-editor] summary');await wait(()=>evaluate(cdp,`!!document.querySelector('[data-email-editor] form select')`),'Native editor missing');}
async function check(name){await evaluate(cdp,'Promise.all(document.getAnimations().filter(a=>a.effect?.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})))');assert.ok(await evaluate(cdp,'document.documentElement.scrollWidth<=innerWidth+1'));await audit.check(cdp,name,'[data-monitoring-email-centre]');}
async function buttonText(label){const selector='[data-email-editor] button';await wait(()=>evaluate(cdp,`Array.from(document.querySelectorAll(${JSON.stringify(selector)})).some(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled)`),'Button missing '+label);await evaluate(cdp,`Array.from(document.querySelectorAll(${JSON.stringify(selector)})).find(b=>b.textContent.trim()===${JSON.stringify(label)}).setAttribute('data-qa-action','true')`);await click('[data-qa-action]');await evaluate(cdp,`document.querySelector('[data-qa-action]')?.removeAttribute('data-qa-action')`);}
async function wait(check,message){for(let i=0;i<250;i++){if(await Promise.resolve().then(check).catch(()=>false))return;await sleep(100);}throw Error(message);}
const text=selector=>evaluate(cdp,`document.querySelector(${JSON.stringify(selector)})?.innerText||''`);
async function respond(id,body,code=200){await cdp.send('Fetch.fulfillRequest',{requestId:id,responseCode:code,responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Cache-Control',value:'no-store'}],body:Buffer.from(JSON.stringify(body)).toString('base64')}).catch(()=>{});}
async function click(selector){await wait(()=>evaluate(cdp,`!!document.querySelector(${JSON.stringify(selector)})&&!document.querySelector(${JSON.stringify(selector)}).disabled`),`Missing ${selector}`);const point=await evaluate(cdp,`(()=>{const el=document.querySelector(${JSON.stringify(selector)});el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};})()`);for(const type of ['mousePressed','mouseReleased'])await cdp.send('Input.dispatchMouseEvent',{type,...point,button:'left',clickCount:1});}
try {
  await wait(async()=>(await fetch(base)).ok,'Next did not start');let debugPort;await wait(async()=>{debugPort=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];return !!debugPort;},'Chrome did not start');
  const target=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:'PUT'}).then(r=>r.json());cdp=new Cdp(target.webSocketDebuggerUrl);await cdp.send('Page.enable');await cdp.send('Runtime.enable');
  cdp.on('Runtime.exceptionThrown',({exceptionDetails})=>exceptions.push(exceptionDetails.exception?.description||exceptionDetails.text));
  cdp.on('Fetch.requestPaused',async({requestId,request})=>{
    const url=new URL(request.url),path=url.pathname,payload=request.postData?JSON.parse(request.postData):null;requests.push({path,method:request.method,payload,user});let body={},code=200;
    if(path==='/api/auth/session')body=identity();
    else if(path==='/api/health')body={status:'ok',database:'synthetic',apertus:{configured:false},firecrawl:{configured:false}};
    else if(path==='/api/monitoring-centre'){
      if(denied){code=403;body={code:'membership_required',detail:'Denied'};}
      else {const filtered=rows.filter(row=>!url.searchParams.get('domain')||row.domain===url.searchParams.get('domain'));const offset=paginated?Number(url.searchParams.get('cursor')||0):0;body={items:paginated?filtered.slice(offset,offset+2):filtered,next_cursor:paginated&&offset+2<filtered.length?String(offset+2):null};}
    }else if(path.startsWith('/api/monitoring-subjects/pollen')){
      if(request.method==='GET')body=pollen;
      else if(fail){code=409;body={code:'monitoring_version_conflict',detail:'Changed'};}
      else if(path.endsWith('/commands')){
        assert.equal(payload.expected_revision,pollen.revision);assert.equal(payload.expected_version,pollen.runtime.version);
        if(payload.action==='pause'){pollen.status='paused';pollen.runtime.email_consent=false;}
        else if(payload.action==='resume'){pollen.status='active';pollen.runtime.email_consent=payload.email_consent;}
        else if(payload.action==='unsubscribe')pollen.runtime.email_consent=false;
        else if(payload.action==='consent_email'){assert.equal(payload.email_consent,true);pollen.runtime.email_consent=true;}
        else if(['mute','unmute'].includes(payload.action))pollen.runtime.muted=payload.action==='mute';
        else throw Error('Unexpected Pollen activation '+payload.action);
        pollen.runtime.version++;body=pollen;
      }else{assert.equal(pollen.status,'paused');assert.equal(payload.expected_revision,pollen.revision);assert.equal(payload.configuration.station_id,pollen.configuration.station_id);assert.deepEqual(payload.configuration.selections,pollen.configuration.selections);pollen.configuration=payload.configuration;pollen.revision++;pollen.runtime.version++;pollen.runtime.email_consent=false;body=pollen;}
    }else if(/\/monitors\/[^/]+\/email(?:\/preview|-preview)?$/.test(path)){
      const id=path.match(/\/monitors\/([^/]+)/)[1];assert.ok(policies[id]);
      if(request.method==='GET')body=path.endsWith('preview')?{status:'unavailable',quiet_hours:false,more_available:false,items:[]}:policies[id];
      else if(hold){held={requestId,payload,path};return;}
      else if(fail){code=409;body={code:'email_version_conflict',detail:'Changed'};}
      else{assert.equal(payload.expected_version,policies[id].monitor_version);assert.equal(payload.consent,payload.configuration.delivery.email!=='off');policies[id]={...policies[id],configuration:payload.configuration,consent_active:payload.consent,revision:policies[id].revision+1,monitor_version:policies[id].monitor_version+1};body=policies[id];}
    }else if(['/api/jobs','/api/laws','/api/scans'].includes(path))body=[];
    else{code=503;body={detail:'Synthetic unavailable'};}
    await respond(requestId,body,code);
  });
  await cdp.send('Fetch.enable',{patterns:[{urlPattern:`${base}/api/*`,requestStage:'Request'}]});
  for(locale of Object.keys(monitoringEmailCentreCopy))for(const width of [390,1440]){
    reset();await cdp.send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<500});await navigate();
    const passive=writes().length;
    for(const row of rows.filter(row=>row.domain!=='pollen')){
      const before=writes().length;await pick(row.domain);assert.equal(writes().length,before);
      await setValue('[data-email-editor] form select','daily_digest');
      assert.equal(await evaluate(cdp,`document.querySelector('[data-email-editor] input[required][type=checkbox]').checked`),false);
      assert.equal(await evaluate(cdp,`document.querySelector('[data-email-editor] button[type=submit]').disabled`),true);
      await click('[data-email-editor] input[type=checkbox]:not([required])');
      await click('[data-email-editor] input[required][type=checkbox]');await click('[data-email-editor] button[type=submit]');
      await wait(()=>policies[row.id].revision===1,'Save missing');await wait(()=>evaluate(cdp,`!!document.querySelector('[data-email-editor] input[required][type=checkbox]')&&!document.querySelector('[data-email-editor] input[required][type=checkbox]').checked`),'Consent did not reset');
      assert.equal(writes().length,before+1);assert.equal(policies[row.id].configuration.delivery.digest_at,'08:00');assert.deepEqual(policies[row.id].configuration.delivery.quiet_hours,{start:'22:00',end:'07:00'});
      await check(`${row.domain}-${locale}-${width}`);
      await setValue('[data-email-editor] form select','off');await click('[data-email-editor] button[type=submit]');await wait(()=>policies[row.id].revision===2,'Off save missing');assert.equal(policies[row.id].consent_active,false);
    }
    assert.equal(writes().length,passive+16);
    await pick('pollen');assert.equal(await evaluate(cdp,`document.querySelector('[data-pollen-email] form fieldset').disabled`),true);
    const {pollenRuntimeCopy}=await import('../apps/web/lib/pollen-runtime-copy.ts');const p=pollenRuntimeCopy[locale];
    await buttonText(p.pause);await wait(()=>evaluate(cdp,`!!document.querySelector('[data-pollen-email] form fieldset')&&!document.querySelector('[data-pollen-email] form fieldset').disabled`),'Pause did not permit editing');
    await setValue('[data-pollen-email] select','immediate');assert.equal(await evaluate(cdp,`Array.from(document.querySelectorAll('[data-pollen-email] button')).find(b=>b.textContent.trim()===${JSON.stringify(p.resume)}).disabled`),true);await click('[data-pollen-email] button[type=submit]');await wait(()=>pollen.revision===2,'Schedule not saved');assert.equal(pollen.status,'paused');assert.equal(pollen.runtime.email_consent,false);
    await check(`pollen-${locale}-${width}`);if(locale==='en-CH')await writeFile(join(root,`test-results/monitoring-email-centre-${width}.png`),Buffer.from((await cdp.send('Page.captureScreenshot',{format:'png'})).data,'base64'));await buttonText(p.resume);await wait(()=>pollen.status==='active','Explicit resume missing');assert.equal(pollen.runtime.email_consent,false);
  }
  // Filters clear a selected private editor; preview reads never send.
  locale='en-CH';reset();await navigate();await pick('river');
  await setValue('[data-email-domain]','air');await wait(()=>evaluate(cdp,`document.querySelectorAll('[data-email-monitor]').length===1&&!document.querySelector('[data-email-editor]')`),'Filter leaked selection');
  await pick('air');const beforePreview=writes().length;
  await evaluate(cdp,`Array.from(document.querySelectorAll('[data-email-editor] button')).at(-1).click()`);
  await wait(()=>evaluate(cdp,`!!document.querySelector('[data-email-editor] section[aria-live]')`),'Preview missing');assert.equal(writes().length,beforePreview);await check('preview-filter');
  // A later inventory page remains reachable without replacing prior records.
  paginated=true;await navigate();const beforePages=writes().length;
  for(const count of [4,6,8,9]){await click('[data-monitoring-email-centre] section > button');await wait(()=>evaluate(cdp,`document.querySelectorAll('[data-email-monitor]').length===${count}`),'Pagination lost monitors');}
  assert.equal(await evaluate(cdp,`new Set(Array.from(document.querySelectorAll('[data-email-monitor]')).map(e=>e.dataset.emailMonitor)).size`),9);assert.equal(writes().length,beforePages);await pick('auctions');await check('pagination');paginated=false;
  // Invalid quiet hours remain editable and do not submit consent.
  await navigate();await pick('tenders');await click('[data-email-editor] input[type=checkbox]:not([required])');
  const times=await evaluate(cdp,`Array.from(document.querySelectorAll('[data-email-editor] input[type=time]')).map(el=>el.value)`);assert.deepEqual(times,['22:00','07:00']);
  await setValue('[data-email-editor] input[type=time]','07:00');const beforeInvalid=writes().length;await click('[data-email-editor] button[type=submit]');await wait(()=>evaluate(cdp,`!!document.querySelector('[data-email-editor] [role=alert]')`),'Quiet hours validation missing');assert.equal(writes().length,beforeInvalid);assert.equal(await evaluate(cdp,`document.querySelector('[data-email-editor] input[type=time]').matches(':disabled')`),false);await setValue('[data-email-editor] input[type=time]','22:00');await click('[data-email-editor] button[type=submit]');await wait(()=>writes().length===beforeInvalid+1,'Quiet hours correction cannot save');await check('quiet-hours-correction');
  // Native version conflict clears the form; refresh reads current state.
  locale='en-CH';reset();await navigate();await pick('tenders');fail=true;await click('[data-email-editor] button[type=submit]');await wait(()=>evaluate(cdp,`!!document.querySelector('[data-email-editor] [role=alert]')&&!document.querySelector('[data-email-editor] form')`),'Conflict kept stale form');await check('version-conflict');fail=false;
  // Closing a selected editor discards a held write response and consent.
  await navigate();await pick('tenders');hold=true;await click('[data-email-editor] button[type=submit]');await wait(()=>!!held,'No held mutation');const delayed=held;await pick('river');await respond(delayed.requestId,defaults());await sleep(150);assert.ok((await text('[data-email-editor]')).includes('Private river'));await check('late-response');hold=false;
  role='viewer';user='other';await navigate();await pick('air');assert.equal(await evaluate(cdp,`document.querySelector('[data-email-editor] form fieldset').disabled`),true);await check('viewer');
  await evaluate(cdp,"window.dispatchEvent(new PageTransitionEvent('pagehide'))");assert.equal(await evaluate(cdp,`document.querySelector('[data-email-editor]')===null`),true);
  denied=true;await navigate().catch(()=>{});assert.equal(await evaluate(cdp,`document.querySelector('[data-email-editor]')===null`),true);await check('denied');
  await writeFile(join(root,'test-results/monitoring-email-centre.png'),Buffer.from((await cdp.send('Page.captureScreenshot',{format:'png'})).data,'base64'));
  assert.deepEqual(exceptions,[]);assert.ok(writes().every(r=>/\/email$|\/monitoring-subjects\/pollen(?:\/commands)?$/.test(r.path)));audit.finish(97);
  console.log('Monitoring email centre: 97 axe checkpoints; all nine native editors in five locales at mobile/desktop, explicit consent/off, Pollen pause/save/resume, stale version, late response, viewer and access removal. Synthetic APIs only.');
}catch(error){console.error({locale,role,exceptions,requests:requests.slice(-7),text:cdp?await text('body').catch(()=>''):''});throw error;}
finally{cdp?.close();for(const child of [browser,server]){const stopped=new Promise(r=>child.once('exit',r));child.kill();await Promise.race([stopped,sleep(2000)]);}assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith('helvetic-monitoring-email-centre-'));await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});}
