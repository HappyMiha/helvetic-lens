// Synthetic localhost consent/preview UI only. No SMTP or real account is used.
import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import {existsSync} from "node:fs";
import {mkdir,mkdtemp,readFile,writeFile} from "node:fs/promises";
import {resolve,join} from "node:path";
import {setTimeout as delay} from "node:timers/promises";
import {Cdp} from "./browser-cdp.mjs";
import {roadEmailCopy} from "../apps/web/lib/road-email-copy.ts";
import {roadCopy} from "../apps/web/lib/road-copy.ts";
import {pollenDeliveryCopy} from "../apps/web/lib/pollen-delivery-copy.ts";

const origin=new URL(process.argv[2]);assert.equal(origin.hostname,"127.0.0.1");assert.equal(origin.protocol,"http:");
const base=origin.origin,root=resolve(import.meta.dirname,".."),output=join(root,"test-results/accessibility");
const chrome=["C:/Program Files/Google/Chrome/Application/chrome.exe","C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"].find(existsSync);
assert.ok(chrome);await mkdir(output,{recursive:true});
const profile=await mkdtemp(join(root,".tmp/hazard-email-chrome-"));
const child=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--disable-background-networking","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{windowsHide:true,stdio:"ignore"});
let cdp;const checks=[],e=roadEmailCopy["en-CH"],r=roadCopy["en-CH"],scope="[data-hazard-email]";
async function bounded(p,ms=10000){let timer;try{return await Promise.race([p,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error("Browser operation timed out")),ms);})]);}finally{clearTimeout(timer);}}
const call=(method,params={})=>bounded(cdp.send(method,params));
async function evaluate(expression){const value=await call("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:false});if(value.exceptionDetails)throw Error(value.exceptionDetails.text);return value.result.value;}
async function until(expression){const end=Date.now()+15000;while(Date.now()<end){if(await evaluate(expression))return;await delay(100);}throw Error("Condition timed out: "+expression);}
async function json(path,body){const response=await fetch(base+path,{...(body?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(3000)});assert.ok(response.ok);return response.json();}
async function click(label){const found=`[...document.querySelectorAll('${scope} button')].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled&&b.getClientRects().length)`;await until(`!!(${found})`);await evaluate(`(${found}).click()`);}
async function open(locale="en-CH"){
  await until(`!![...document.querySelectorAll('[data-hazard-watch] summary')].find(s=>s.textContent.trim()===${JSON.stringify(pollenDeliveryCopy[locale].title)})`);
  await evaluate(`(()=>{const s=[...document.querySelectorAll('[data-hazard-watch] summary')].find(s=>s.textContent.trim()===${JSON.stringify(pollenDeliveryCopy[locale].title)});s.parentElement.open=true;})()`);
  await until(`!!document.querySelector('${scope} select')`);
}
async function navigate(id,locale="en-CH"){await json("/__qa/state",{locale});await call("Page.navigate",{url:base+`/hazard-watch?monitor=${id}`});await open(locale);}
async function mode(value){await evaluate(`(()=>{const s=document.querySelector('${scope} select');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(s,${JSON.stringify(value)});s.dispatchEvent(new Event('change',{bubbles:true}));})()`);}
async function consent(){await evaluate(`document.querySelector('${scope} input[type=checkbox][required]').click()`);}
function record(name){checks.push(name);console.log(name);}
async function audit(name){
  await evaluate("(()=>{const s=document.createElement('script');s.src='/__qa/axe.js';document.head.append(s);})()");await until("typeof window.axe==='object'");
  await evaluate("(()=>{window.__hazardAudit=null;window.axe.run(document).then(v=>window.__hazardAudit={violations:v.violations,incomplete:v.incomplete.map(i=>({id:i.id,nodes:i.nodes.map(n=>n.target)}))},e=>window.__hazardAudit={error:String(e)});})()");
  await until("window.__hazardAudit!==null");const result=await evaluate("window.__hazardAudit");assert.ok(!result.error,result.error);assert.deepEqual(result.violations.map(v=>v.id),[]);
  await json("/__qa/audit",{name,...result});await evaluate(`document.querySelector('${scope}').scrollIntoView({block:'start',behavior:'instant'})`);
  const shot=await call("Page.captureScreenshot",{format:"png"});await writeFile(join(output,`hazard-${name}.png`),Buffer.from(shot.data,"base64"));record(`axe:${name}:0-violations`);
}
try{
  const end=Date.now()+15000;let port;
  while(Date.now()<end){try{port=Number((await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0]);break;}catch{await delay(100);}}
  assert.ok(port);const tabs=await fetch(`http://127.0.0.1:${port}/json/list`,{signal:AbortSignal.timeout(3000)}).then(r=>r.json());
  cdp=new Cdp(tabs.find(t=>t.type==="page").webSocketDebuggerUrl);await bounded(cdp.ready);await call("Page.enable");await call("Runtime.enable");
  await call("Emulation.setDeviceMetricsOverride",{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
  await json("/__qa/state",{suite:"email"});const {id}=await json("/__qa/seed-lifecycle",{});await navigate(id);
  assert.equal(await evaluate(`document.querySelector('${scope} select').value`),"off");record("email-default-off-and-private-recipient");
  await mode("immediate");assert.ok(await evaluate(`document.querySelector('${scope} button[type=submit]').disabled`));record("explicit-consent-required");
  await consent();await click(e.save);await until(`!document.querySelector('${scope}')`);await open();
  assert.equal(await evaluate(`document.querySelector('${scope} select').value`),"immediate");
  assert.ok(await evaluate(`document.querySelector('${scope}').textContent.includes(${JSON.stringify(e.active)})`));record("consent-saved-with-expected-monitor-version");
  await click(e.preview);await until(`!!document.querySelector('${scope} a[href*=revision]')`);
  assert.ok((await evaluate(`document.querySelector('${scope} a').getAttribute('href')`)).endsWith("&revision=1"));record("preview-links-exact-warning-without-sending");
  await audit("email-desktop");
  await mode("daily_digest");assert.ok(await evaluate(`!!document.querySelector('${scope} input[type=time]')`));
  assert.ok(!await evaluate(`document.querySelector('${scope} input[type=checkbox][required]').checked`));record("schedule-change-resets-consent-and-preview");
  await mode("off");await click(e.save);await until(`!document.querySelector('${scope}')`);await open();
  assert.equal(await evaluate(`document.querySelector('${scope} select').value`),"off");record("turn-off-without-new-opt-in");
  await json("/__qa/state",{emailVerified:false});await navigate(id);
  assert.ok(await evaluate(`document.querySelector('${scope} option[value=immediate]').disabled`));record("unverified-address-cannot-enable");
  await json("/__qa/state",{emailVerified:true,emailService:false,emailUncertain:true});await navigate(id);
  assert.ok(await evaluate(`document.querySelector('${scope}').textContent.includes(${JSON.stringify(e.uncertain)})`));record("unavailable-service-and-uncertain-attempt-visible");
  await json("/__qa/state",{emailConflict:true});await mode("immediate");await consent();await click(e.save);
  await until(`!!document.querySelector('${scope} [role=alert]')`);assert.ok(!await evaluate(`!!document.querySelector('${scope} select')`));record("conflict-clears-stale-private-form");
  await json("/__qa/state",{emailConflict:false,manager:false});await navigate(id);
  assert.ok(await evaluate(`document.querySelector('${scope} fieldset').disabled`));assert.ok(!await evaluate(`!!document.querySelector('${scope} button[type=submit]')`));record("viewer-cannot-change-consent");
  await json("/__qa/state",{manager:true,emailService:true,emailUncertain:false});
  await call("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  for(const locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){await navigate(id,locale);await mode("immediate");
    assert.ok(await evaluate(`document.querySelector('${scope} input[type=checkbox][required]').parentElement.textContent.includes('Hazard')`));
    assert.ok(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),locale);record(`mobile-email-consent:${locale}`);}
  await audit("email-mobile");
  await json("/__qa/state",{denied:true});await click(r.refresh);await until(`!document.querySelector('${scope}')`);
  assert.ok(!await evaluate("document.body.textContent.includes('synthetic@example.invalid')"));record("membership-denial-redacts-email-and-consent");
  const requests=await json("/__qa/requests");const writes=requests.filter(x=>x.method==="PUT"&&x.path.endsWith("/email"));
  assert.equal(writes.length,3);assert.deepEqual(writes.slice(0,2).map(x=>x.body.consent),[true,false]);
  assert.ok(!requests.some(x=>/\/commands|\/send|source.*poll/.test(x.path)));record("no-monitor-activation-source-poll-or-send");
  await writeFile(join(root,".tmp/hazard-email-browser-requests.json"),JSON.stringify(requests,null,2));
}finally{
  await writeFile(join(output,"hazard-email-browser-checks.json"),JSON.stringify(checks,null,2));
  cdp?.close();child.kill();await json("/__qa/finish",{});
}
