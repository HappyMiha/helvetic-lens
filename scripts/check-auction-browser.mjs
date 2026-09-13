import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import {existsSync} from "node:fs";
import {mkdir,mkdtemp,readFile,writeFile} from "node:fs/promises";
import {resolve,join} from "node:path";
import {setTimeout as delay} from "node:timers/promises";
import {Cdp} from "./browser-cdp.mjs";
import {auctionCopy} from "../apps/web/lib/auction-copy.ts";
const origin=new URL(process.argv[2]);assert.equal(origin.hostname,"127.0.0.1");assert.equal(origin.protocol,"http:");
const base=origin.origin,root=resolve(import.meta.dirname,".."),output=join(root,"test-results/accessibility"),c=auctionCopy["en-CH"];
const chrome=["C:/Program Files/Google/Chrome/Application/chrome.exe","C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"].find(existsSync);
assert.ok(chrome);await mkdir(output,{recursive:true});const profile=await mkdtemp(join(root,".tmp/auction-chrome-"));
const child=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--disable-background-networking","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{windowsHide:true,stdio:"ignore"});
let cdp;const checks=[];
async function bounded(p,ms=10000){let t;try{return await Promise.race([p,new Promise((_,reject)=>{t=setTimeout(()=>reject(Error("Browser operation timed out")),ms);})]);}finally{clearTimeout(t);}}
const call=(method,params={})=>bounded(cdp.send(method,params));
async function evaluate(expression){const value=await call("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:false});if(value.exceptionDetails)throw Error(value.exceptionDetails.text);return value.result.value;}
async function until(expression){const end=Date.now()+15000;while(Date.now()<end){if(await evaluate(expression))return;await delay(100);}throw Error("Condition timed out: "+expression);}
async function json(path,body){const response=await fetch(base+path,{...(body?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(3000)});assert.ok(response.ok);return response.json();}
async function click(label,scope="[data-auction-watch]"){const found=`[...document.querySelectorAll(${JSON.stringify(scope+" button")})].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled&&b.getClientRects().length)`;await until(`!!(${found})`);await evaluate(`(${found}).click()`);}
async function fill(selector,value){await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('field missing');const p=e.tagName==='SELECT'?HTMLSelectElement.prototype:e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));})()`);}
async function navigate(locale="en-CH"){await json("/__qa/state",{locale});await call("Page.navigate",{url:base+"/auction-watch"});await until(`document.querySelector('[data-auction-watch] h1')?.textContent===${JSON.stringify(auctionCopy[locale].title)}`);await until("!document.querySelector('[data-auction-watch] [role=status]')");}
function record(name){checks.push(name);console.log(name);}
async function audit(name){
  await evaluate("(()=>{const s=document.createElement('script');s.src='/__qa/axe.js';document.head.append(s);})()");await until("typeof window.axe==='object'");
  await evaluate("(()=>{window.__ipAudit=null;window.axe.run(document).then(v=>window.__ipAudit={violations:v.violations,incomplete:v.incomplete.map(i=>({id:i.id,nodes:i.nodes.map(n=>n.target)}))},e=>window.__ipAudit={error:String(e)});})()");await until("window.__ipAudit!==null");
  const result=await evaluate("window.__ipAudit");assert.ok(!result.error,result.error);assert.deepEqual(result.violations.map(v=>v.id),[]);await json("/__qa/audit",{name,...result});
  const shot=await call("Page.captureScreenshot",{format:"png"});await writeFile(join(output,`auction-${name}.png`),Buffer.from(shot.data,"base64"));record(`axe:${name}:0-violations`);
}
try{
  const end=Date.now()+15000;let port;while(Date.now()<end){try{port=Number((await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0]);break;}catch{await delay(100);}}
  assert.ok(port);const tabs=await fetch(`http://127.0.0.1:${port}/json/list`,{signal:AbortSignal.timeout(3000)}).then(r=>r.json());cdp=new Cdp(tabs.find(t=>t.type==="page").webSocketDebuggerUrl);await bounded(cdp.ready);await call("Page.enable");await call("Runtime.enable");
  await call("Emulation.setDeviceMetricsOverride",{width:1280,height:1000,deviceScaleFactor:1,mobile:false});await navigate();await click(c.create);

  await fill('[data-auction-form] > fieldset > label input',"Private auction fixture");
  await fill('[data-auction-form] textarea',"Lugano\nMendrisio");
  assert.equal(await evaluate("document.querySelector('[data-auction-form] textarea').value"),"Lugano\nMendrisio");record("multiline-locations-remain-editable");
  await fill('[data-auction-form] input[inputmode=decimal]',"1e3");await click(c.save);
  await until("document.querySelector('[data-auction-form] [role=alert]')?.textContent==="+JSON.stringify(c.invalid));record("ambiguous-budget-blocks-save");
  await fill('[data-auction-form] input[inputmode=decimal]',"12000,50");
  await fill('[data-auction-form] input[inputmode=numeric]',"24");
  await fill('[data-auction-form] select',"starting_price");
  await click(c.save);await until("document.querySelector('[data-auction-detail] h2')?.textContent==='Private auction fixture'");
  const captured=await json("/__qa/requests");const saved=captured.find(r=>r.path==='/api/auction-watch/monitors'&&r.method==='POST').body.configuration;
  assert.equal(saved.maximum_price_chf_cents,1200050);assert.equal(saved.budget_price_kind,"starting_price");assert.equal(saved.notify.ending_soon_hours,24);
  assert.deepEqual(saved.locations,["Lugano","Mendrisio"]);record("save-private-profile-exact-budget-and-reminder-preferences");
  await audit("desktop");await click(c.edit);await fill('[data-auction-form] > fieldset > label input',"Revised auction fixture");await click(c.save);
  await until("document.querySelector('[data-auction-detail] h2')?.textContent==='Revised auction fixture'");await click(c.history);await until("document.querySelectorAll('[data-auction-history] > details').length===2");record("edit-preserves-selected-profile-and-version-history");
  await click(c.edit);await fill('[data-auction-form] > fieldset > label input',"Conflict retains my changes");await json("/__qa/state",{conflict:true});await click(c.save);
  await until(`document.querySelector('[data-auction-form] [role=alert]')?.textContent===${JSON.stringify(c.conflict)}`);
  assert.equal(await evaluate("document.querySelector('[data-auction-form] > fieldset > label input').value"),"Conflict retains my changes");
  await json("/__qa/state",{conflict:false});await click(c.cancel);record("version-conflict-preserves-unsaved-input-until-cancelled");
  await click(c.archive);await until(`document.querySelector('[data-auction-detail]')?.textContent.includes(${JSON.stringify(c.archived)})`);await click(c.remove);await click(c.cancel);assert.ok(await evaluate("!!document.querySelector('[data-auction-detail]')"));record("archive-retains-history-and-delete-can-be-cancelled");
  await click(c.remove);await evaluate(`(()=>{const buttons=[...document.querySelectorAll('[data-auction-detail] button')].filter(b=>b.textContent.trim()===${JSON.stringify(c.remove)});buttons.at(-1).click();})()`);await until(`document.querySelector('[data-auction-watch] aside')?.textContent.includes(${JSON.stringify(c.empty)})`);record("confirmed-delete-removes-profile");
  await json("/__qa/state",{manager:false});await navigate();assert.ok(!await evaluate(`!![...document.querySelectorAll('[data-auction-watch] button')].find(b=>b.textContent.trim()===${JSON.stringify(c.create)})`));record("viewer-cannot-create-or-edit-profiles");
  await json("/__qa/state",{manager:true});await call("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  for(const locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){await navigate(locale);await click(auctionCopy[locale].create);await until("!!document.querySelector('[data-auction-form]')");assert.ok(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),locale);record(`mobile-profile:${locale}`);}
  await evaluate("document.querySelector('[data-auction-form]').scrollIntoView({block:'start'})");await audit("mobile");
  await fill('[data-auction-form] > fieldset > label input',"Hidden after denial");await fill('[data-auction-form] textarea',"PRIVATE-LOCATION");await json("/__qa/state",{denied:true});await click(c.save);await until("!document.querySelector('[data-auction-form]')");
  assert.ok(!await evaluate("document.body.textContent.includes('PRIVATE-LOCATION')"));record("mutation-membership-denial-redacts-private-form");
  const requests=await json("/__qa/requests");assert.ok(!requests.some(r=>/\/start|\/email|source.*poll|\/send/.test(r.path)));record("no-source-activation-email-or-bid");
}finally{
  await writeFile(join(output,"auction-browser-checks.json"),JSON.stringify(checks,null,2));cdp?.close();child.kill();await json("/__qa/finish",{});
}
