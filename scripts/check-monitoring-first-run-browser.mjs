// Built first-run UI; synthetic accounts, no source or production writes.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { monitoringFirstRunCopy } from '../apps/web/lib/monitoring-first-run-copy.ts';
import { monitoringNavigation } from '../apps/web/lib/monitoring-navigation.ts';
import { centreCopy } from '../apps/web/lib/monitoring-centre-copy.ts';
import { Cdp, evaluate, sleep } from './browser-cdp.mjs';
import { AccessibilityAudit } from './browser-accessibility.mjs';

const root=resolve(import.meta.dirname,'..');
const chrome=[process.env.CHROME_BIN,'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe','/usr/bin/google-chrome'].filter(Boolean).find(existsSync);assert.ok(chrome);
const reserve=createServer();await new Promise(r=>reserve.listen(0,'127.0.0.1',r));const port=reserve.address().port;await new Promise(r=>reserve.close(r));const base=`http://127.0.0.1:${port}`;
const server=spawn(process.execPath,[join(root,'node_modules/next/dist/bin/next'),'start','-H','127.0.0.1','-p',String(port)],{cwd:join(root,'apps/web'),stdio:'ignore',windowsHide:true});
const profile=await mkdtemp(join(tmpdir(),'helvetic-monitoring-first-run-'));
const browser=spawn(chrome,['--headless=new','--no-first-run','--no-default-browser-check','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{stdio:'ignore',windowsHide:true});
const audit=new AccessibilityAudit('monitoring-first-run'),requests=[],exceptions=[];
const fresh=()=>({state:'new',intent:null,monitoring_template:null,source_review:null,milestones:[],started_at:null,deferred_at:null,updated_at:null,visibility:'personal',completion_verified:false,organization_setup:{source_package_enabled:false,active_document_watch:false,active_topic:false}});
let cdp,locale='en-CH',user='qa',role='organization_admin',authenticated=false,state=fresh(),fail=false,hold=false,held,navigation=0;
const identity=()=>({authenticated,user:authenticated?{id:user,name:user,email:'qa@example.invalid',locale}:null,organization:authenticated?{id:'qa-org',name:'Personal QA'}:null,role,onboarding_required:state.state==='new'});
async function wait(check,message){for(let i=0;i<250;i++){if(await Promise.resolve().then(check).catch(()=>false))return;await sleep(100);}throw Error(message);}
const text=selector=>evaluate(cdp,`document.querySelector(${JSON.stringify(selector)})?.innerText||''`);
async function respond(id,body,code=200){await cdp.send('Fetch.fulfillRequest',{requestId:id,responseCode:code,responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Cache-Control',value:'no-store'}],body:Buffer.from(JSON.stringify(body)).toString('base64')}).catch(()=>{});}
async function click(selector){await wait(()=>evaluate(cdp,`!!document.querySelector(${JSON.stringify(selector)})&&!document.querySelector(${JSON.stringify(selector)}).disabled`),`Missing ${selector}`);const point=await evaluate(cdp,`(()=>{const el=document.querySelector(${JSON.stringify(selector)});el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};})()`);for(const type of ['mousePressed','mouseReleased'])await cdp.send('Input.dispatchMouseEvent',{type,...point,button:'left',clickCount:1});}
async function navigate(path){await evaluate(cdp,'window.__previousFirstRun=true');const url=new URL(path,base);url.searchParams.set('qa',String(++navigation));url.searchParams.set('locale',locale);await cdp.send('Page.navigate',{url:url.href});await wait(()=>evaluate(cdp,`!window.__previousFirstRun&&document.documentElement.lang===${JSON.stringify(locale)}`),'New document missing');}
async function guide(){await navigate('/onboarding');await wait(()=>evaluate(cdp,`document.querySelectorAll('[data-onboarding-template]').length===9&&!document.querySelector('[data-onboarding-template]').disabled`),'Nine available first-run choices missing');}
const writes=()=>requests.filter(r=>!['GET','HEAD'].includes(r.method)&&!r.path.startsWith('/api/assistant/'));
async function check(name,selector='[data-monitoring-first-run]'){await evaluate(cdp,'Promise.all(document.getAnimations().filter(a=>a.effect?.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})))');assert.ok(await evaluate(cdp,'document.documentElement.scrollWidth<=innerWidth+1'));await audit.check(cdp,name,selector);}
try{
  await wait(async()=>(await fetch(base)).ok,'Next did not start');let debugPort;await wait(async()=>{debugPort=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];return !!debugPort;},'Chrome did not start');
  const target=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:'PUT'}).then(r=>r.json());cdp=new Cdp(target.webSocketDebuggerUrl);await cdp.send('Page.enable');await cdp.send('Runtime.enable');
  cdp.on('Runtime.exceptionThrown',({exceptionDetails})=>exceptions.push(exceptionDetails.exception?.description||exceptionDetails.text));
  cdp.on('Fetch.requestPaused',async({requestId,request})=>{
    const path=new URL(request.url).pathname,payload=request.postData?JSON.parse(request.postData):null;requests.push({path,method:request.method,payload,user});let body={},code=200;
    if(path==='/api/auth/session')body=identity();
    else if(path==='/api/auth/register'){assert.equal(payload.organization_name,'');assert.equal(payload.locale,locale);authenticated=true;body=identity();}
    else if(path==='/api/health')body={status:'ok',database:'synthetic',apertus:{configured:false},firecrawl:{configured:false}};
    else if(path==='/api/onboarding'){
      if(request.method==='PATCH'){
        if(hold){held={requestId,payload};return;}
        if(fail){code=503;body={detail:'Synthetic save unavailable'};}
        else {assert.deepEqual(Object.keys(payload).sort(),['action','monitoring_template']);assert.equal(payload.action,'monitoring');assert.ok(monitoringNavigation.some(x=>x.id===payload.monitoring_template));state={...state,state:'started',intent:'explore',monitoring_template:payload.monitoring_template};body=state;}
      }else body=state;
    }else if(['/api/jobs','/api/laws','/api/scans'].includes(path))body=[];
    else {code=503;body={detail:'Synthetic source unavailable'};}
    await respond(requestId,body,code);
  });
  await cdp.send('Fetch.enable',{patterns:[{urlPattern:`${base}/api/*`,requestStage:'Request'}]});
  for(const language of Object.keys(monitoringFirstRunCopy)){
    locale=language;authenticated=false;user=`qa-${locale}`;role='organization_admin';state=fresh();const copy=monitoringFirstRunCopy[locale];
    await cdp.send('Emulation.setDeviceMetricsOverride',{width:390,height:950,deviceScaleFactor:1,mobile:true});await navigate('/login');
    await wait(async()=>(await text('body')).includes(copy.company),'Personal signup hint missing');
    assert.equal(await evaluate(cdp,`document.querySelector('input[autocomplete="organization"]').required`),false);await check(`signup-${locale}`,'form');
    for(const [selector,value] of [['input[autocomplete="name"]',user],['input[type="email"]','qa@example.invalid'],['input[type="password"]','synthetic-password-123']])await evaluate(cdp,`(()=>{const el=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,${JSON.stringify(value)});el.dispatchEvent(new Event('input',{bubbles:true}));})()`);
    await click('form button[type="submit"],form button:last-of-type');
    await wait(()=>evaluate(cdp,`location.pathname==='/onboarding'&&document.querySelectorAll('[data-onboarding-template]').length===9&&!document.querySelector('[data-onboarding-template]').disabled`),'Signup did not reach native guide');
    for(const width of [390,1440]){
      await cdp.send('Emulation.setDeviceMetricsOverride',{width,height:950,deviceScaleFactor:1,mobile:width<500});await guide();await check(`choice-${locale}-${width}`);
      assert.equal(await evaluate(cdp,`document.querySelector('[data-onboarding-template]').getAttribute('data-onboarding-template')`),'pollen');
      for(const item of monitoringNavigation){
        const before=writes().length;await click(`[data-onboarding-template="${item.id}"]`);await wait(()=>evaluate(cdp,`location.pathname===${JSON.stringify(item.href)}&&!document.querySelector('[data-monitoring-first-run]')`),`Wrong ${item.id} destination`);
        assert.equal(writes().length,before+1);assert.equal(state.monitoring_template,item.id);await guide();
        assert.equal(await evaluate(cdp,`document.querySelector('[data-monitoring-first-run-saved] a').getAttribute('href')`),item.href);
        assert.ok((await text('[data-monitoring-first-run-saved]')).includes(centreCopy[locale].templates[item.id][0]));
      }
      await check(`saved-${locale}-${width}`);
    }
    fail=true;const before=writes().length;await click('[data-onboarding-template="pollen"]');await wait(async()=>(await text('body')).includes('Synthetic save unavailable'),'Save failure missing');assert.equal(await evaluate(cdp,'location.pathname'),'/onboarding');assert.equal(writes().length,before+1);await check(`failed-${locale}`);fail=false;
    await click('[data-onboarding-template="pollen"]');await wait(()=>evaluate(cdp,`location.pathname==='/pollen-watch'`),'Retry did not navigate');
    role='viewer';user=`viewer-${locale}`;state=fresh();await guide();assert.ok((await text('[data-monitoring-first-run-viewer]')).includes(copy.viewer));assert.equal(await text('[data-monitoring-first-run-saved]'),'');await check(`viewer-${locale}`);
  }
  hold=true;await click('[data-onboarding-template="air"]');await wait(()=>!!held,'Held save missing');const delayed=held;await evaluate(cdp,"window.dispatchEvent(new PageTransitionEvent('pagehide'))");await respond(delayed.requestId,{...state,state:'started',intent:'explore',monitoring_template:'air'});await sleep(200);assert.equal(await evaluate(cdp,'location.pathname'),'/onboarding');
  await writeFile(join(root,'test-results/monitoring-first-run.png'),Buffer.from((await cdp.send('Page.captureScreenshot',{format:'png'})).data,'base64'));
  assert.deepEqual(exceptions,[]);assert.ok(writes().every(r=>['/api/auth/register','/api/onboarding'].includes(r.path)));audit.finish(35);
  console.log('Monitoring first run: 35 built-browser/axe checkpoints; five personal registrations, 90 nine-direction mobile/desktop journeys, saved choice, error/retry, viewer and late-response checks. Synthetic APIs only.');
}catch(error){console.error({locale,role,exceptions,requests:requests.slice(-7),text:cdp?await text('body').catch(()=>''):''});throw error;}
finally{cdp?.close();for(const child of [browser,server]){const stopped=new Promise(r=>child.once('exit',r));child.kill();await Promise.race([stopped,sleep(2000)]);}assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith('helvetic-monitoring-first-run-'));await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});}
