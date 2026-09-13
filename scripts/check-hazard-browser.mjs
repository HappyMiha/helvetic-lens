// Built UI acceptance against the disposable synthetic hazard-browser-fixture.
import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import {existsSync} from "node:fs";
import {mkdir,readFile,writeFile,mkdtemp} from "node:fs/promises";
import {resolve,join} from "node:path";
import {pathToFileURL} from "node:url";
import {setTimeout as delay} from "node:timers/promises";
import {Cdp} from "./browser-cdp.mjs";

const root=resolve(import.meta.dirname,".."),origin=new URL(process.argv[2]);
assert.equal(origin.hostname,"127.0.0.1");assert.equal(origin.protocol,"http:");
const base=origin.origin;
const {hazardCopy}=await import(pathToFileURL(join(root,"apps/web/lib/hazard-copy.ts")).href);
const {roadCopy}=await import(pathToFileURL(join(root,"apps/web/lib/road-copy.ts")).href);
const c=hazardCopy["en-CH"],r=roadCopy["en-CH"];
const chrome=["C:/Program Files/Google/Chrome/Application/chrome.exe","C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"].find(existsSync);
assert.ok(chrome,"Chrome must be installed");
await mkdir(join(root,".tmp"),{recursive:true});
const profile=await mkdtemp(join(root,".tmp/hazard-chrome-"));
const output=join(root,"test-results/accessibility");await mkdir(output,{recursive:true});
const child=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--disable-background-networking","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{windowsHide:true,stdio:"ignore"});
const events=[];let cdp;
async function bounded(promise,ms=10000){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error("Browser operation timed out")),ms);})]);}finally{clearTimeout(timer);}}
async function call(method,params={}){return bounded(cdp.send(method,params));}
async function evaluate(expression){const result=await call("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:false});if(result.exceptionDetails)throw Error(result.exceptionDetails.text);return result.result.value;}
async function until(expression){const end=Date.now()+15000;while(Date.now()<end){if(await evaluate(expression))return;await delay(100);}throw Error(`UI condition timed out: ${expression}`);}
async function json(path,body){const res=await fetch(base+path,{...(body?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(3000)});assert.ok(res.ok);return res.json();}
async function click(label){await evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled);if(!b)throw Error('button missing');b.click();})()`);}
async function fill(selector,value){await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('field missing');const p=e.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));})()`);}
async function navigate(locale="en-CH"){
  await json("/__qa/state",{locale});await call("Page.navigate",{url:base+"/hazard-watch"});
  await until(`document.querySelector('[data-hazard-watch] h1')?.textContent===${JSON.stringify(hazardCopy[locale].title)}`);
  await until("!document.querySelector('[data-hazard-watch] [role=status]')");
}
async function record(name){events.push(name);console.log(name);}
async function audit(name){
  await evaluate(`(()=>{const s=document.createElement('script');s.src='/__qa/axe.js';document.head.append(s);})()`);
  await until("typeof window.axe==='object'");
  await evaluate(`(()=>{window.__hazardAudit=null;window.axe.run(document).then(v=>window.__hazardAudit={violations:v.violations,incomplete:v.incomplete.map(x=>({id:x.id,nodes:x.nodes.map(n=>n.target)}))},e=>window.__hazardAudit={error:String(e)});})()`);
  await until("window.__hazardAudit!==null");
  const result=await evaluate("window.__hazardAudit");assert.ok(!result.error,result.error);
  await json("/__qa/audit",{name,...result});assert.deepEqual(result.violations.map(v=>v.id),[]);
  const screenshot=await call("Page.captureScreenshot",{format:"png"});await writeFile(join(output,`hazard-${name}.png`),Buffer.from(screenshot.data,"base64"));
  await record(`axe:${name}:0-violations`);
}
try{
  const deadline=Date.now()+15000;let port;
  while(Date.now()<deadline){try{port=Number((await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0]);break;}catch{await delay(100);}}
  assert.ok(port,"Chrome did not expose its isolated port");
  const tabs=await fetch(`http://127.0.0.1:${port}/json/list`,{signal:AbortSignal.timeout(3000)}).then(r=>r.json());
  cdp=new Cdp(tabs.find(t=>t.type==="page").webSocketDebuggerUrl);await bounded(cdp.ready);
  await call("Page.enable");await call("Runtime.enable");
  await call("Emulation.setDeviceMetricsOverride",{width:1280,height:900,deviceScaleFactor:1,mobile:false});
  await navigate();await click(c.create);
  await fill('input[name="name"]',"Home fixture");await fill('select[name="canton"]',"BS");
  await fill('input[name="latitude"]',"47.56");await fill('input[name="longitude"]',"7.59");await fill('input[name="radius"]',"5");
  await click(r.preview);await until("!document.querySelector('form fieldset')?.disabled");
  assert.ok((await json("/__qa/requests")).some(x=>x.path.endsWith("/preview")&&x.body.configuration.name==="Home fixture"));
  await until(`document.querySelector('form')?.textContent.includes(${JSON.stringify(c.locationVerified)})`);
  assert.ok(await evaluate(`document.querySelector('form').textContent.includes(${JSON.stringify(c.radiusUnverified)})`));
  assert.ok(await evaluate("document.querySelector('form').textContent.includes('Basel fixture (2701)')"));
  await evaluate("document.querySelector('form section[role=status]').scrollIntoView({block:'center',behavior:'instant'})");
  const previewShot=await call("Page.captureScreenshot",{format:"png"});
  await writeFile(join(output,"hazard-desktop-preview.png"),Buffer.from(previewShot.data,"base64"));
  await record("verified-municipality-preview-with-radius-coverage-unconfirmed");
  for(const [geography,label] of [["outside_switzerland",c.locationOutside],["municipality_canton_mismatch",c.locationCantonMismatch],["boundary_version_outside_review",c.catalogueExpired],["boundary_catalogue_not_installed",c.catalogueUnavailable]]){
    await json("/__qa/state",{geography});await click(r.preview);
    await until(`document.querySelector('form')?.textContent.includes(${JSON.stringify(label)})`);
    assert.ok(!await evaluate("document.querySelector('form').textContent.includes('Basel fixture')"));
    await record(`geography-preview:${geography}`);
  }
  await json("/__qa/state",{geography:"verified"});await click(r.preview);
  await until(`document.querySelector('form')?.textContent.includes(${JSON.stringify(c.locationVerified)})`);
  await fill('input[name="radius"]',"6");
  assert.ok(!await evaluate(`document.querySelector('form').textContent.includes(${JSON.stringify(c.locationVerified)})`));
  await record("editing-location-clears-stale-geography-proof");
  await click(r.save);await until("document.querySelector('[data-hazard-watch] h2')?.textContent==='Home fixture'");
  await record("preview-save-private-point");
  await click(r.edit);await fill('input[name="name"]',"Office fixture");
  await fill('form select:not([name])',"municipality");await fill('input[name="municipality"]',"2701");
  await click(r.save);await until("document.querySelector('[data-hazard-watch] h2')?.textContent==='Office fixture'");
  await click(r.revisions);await until("document.querySelectorAll('[data-hazard-watch] article h4').length===2");
  assert.ok(await evaluate("document.querySelector('[data-hazard-watch]').textContent.includes('Home fixture')"));
  await record("edit-municipality-and-private-history");await audit("desktop-history");
  await click(r.archive);await until(`!![...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(c.remove)})`);
  await click(c.remove);await click(r.cancel);
  assert.equal((await json("/__qa/requests")).filter(x=>x.method==="DELETE").length,0);
  await click(c.remove);
  await evaluate(`(()=>{const bs=[...document.querySelectorAll('button')].filter(b=>b.textContent.trim()===${JSON.stringify(c.remove)});bs[bs.length-1].click();})()`);
  await until(`document.querySelector('[data-hazard-watch]').textContent.includes(${JSON.stringify(c.empty)})`);
  await record("archive-confirm-cancel-delete");
  await click(c.create);await fill('input[name="name"]',"Private retained fixture");await fill('select[name="canton"]',"TI");
  await fill('form select:not([name])',"municipality");await fill('input[name="municipality"]',"5192");await click(r.save);
  await until("document.querySelector('[data-hazard-watch] h2')?.textContent==='Private retained fixture'");
  await json("/__qa/state",{denied:true});await click(r.archive);
  await until(`document.querySelector('[data-hazard-watch] [role=alert]')?.textContent===${JSON.stringify(c.unavailable)}`);
  assert.ok(!await evaluate("document.querySelector('[data-hazard-watch]').textContent.includes('Private retained fixture')"));
  await record("mutation-denial-redacts-all-private-content");
  await json("/__qa/state",{denied:false,manager:false});await navigate();
  assert.ok(!await evaluate(`!![...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(c.create)})`));
  await record("viewer-has-no-create-action");
  await json("/__qa/state",{manager:true});
  await call("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  for(const locale of Object.keys(hazardCopy)){
    await navigate(locale);await click(hazardCopy[locale].create);
    await fill('input[name="name"]',"Mobile fixture");await fill('select[name="canton"]',"BS");
    await fill('input[name="latitude"]',"47.56");await fill('input[name="longitude"]',"7.59");await click(roadCopy[locale].preview);
    await until(`document.querySelector('form')?.textContent.includes(${JSON.stringify(hazardCopy[locale].locationVerified)})`);
    assert.ok(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),`overflow:${locale}`);
    assert.ok(await evaluate("[...document.querySelectorAll('[data-hazard-watch] input')].every(e=>e.closest('label'))"));
    await record(`mobile-form:${locale}`);
  }
  await evaluate("document.querySelector('form section[role=status]').scrollIntoView({block:'center',behavior:'instant'})");
  await audit("mobile-form");
  const requests=await json("/__qa/requests");
  assert.ok(!requests.some(x=>/start|email|source.*poll/.test(x.path)));
  await record("no-start-source-or-email-requests");
}finally{
  await writeFile(join(output,"hazard-browser-checks.json"),JSON.stringify(events,null,2));
  cdp?.close();child.kill();
  await json("/__qa/finish",{});
}
