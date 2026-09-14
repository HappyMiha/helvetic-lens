import {checkReview} from "./check-trademark-review-journey.mjs";
import assert from "node:assert/strict";
import { checkIPI } from "./check-ipi-source-journey.mjs";
import { checkDeadlineChoice } from "./check-trademark-deadline-journey.mjs";
import {spawn} from "node:child_process";
import {existsSync} from "node:fs";
import {mkdir,mkdtemp,readFile,writeFile} from "node:fs/promises";
import {resolve,join} from "node:path";
import {setTimeout as delay} from "node:timers/promises";
import {Cdp} from "./browser-cdp.mjs";
import {trademarkCopy} from "../apps/web/lib/trademark-copy.ts";
const origin=new URL(process.argv[2]);assert.equal(origin.hostname,"127.0.0.1");assert.equal(origin.protocol,"http:");
const base=origin.origin,root=resolve(import.meta.dirname,".."),output=join(root,"test-results/accessibility"),c=trademarkCopy["en-CH"];
const chrome=["C:/Program Files/Google/Chrome/Application/chrome.exe","C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"].find(existsSync);
assert.ok(chrome);await mkdir(output,{recursive:true});const profile=await mkdtemp(join(root,".tmp/trademark-chrome-"));
const child=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--disable-background-networking","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{windowsHide:true,stdio:"ignore"});
let cdp;const checks=[];
async function bounded(p,ms=10000){let t;try{return await Promise.race([p,new Promise((_,reject)=>{t=setTimeout(()=>reject(Error("Browser operation timed out")),ms);})]);}finally{clearTimeout(t);}}
const call=(method,params={})=>bounded(cdp.send(method,params));
async function evaluate(expression){const value=await call("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:false});if(value.exceptionDetails)throw Error(value.exceptionDetails.text);return value.result.value;}
async function until(expression){const end=Date.now()+15000;while(Date.now()<end){if(await evaluate(expression))return;await delay(100);}throw Error("Condition timed out: "+expression);}
async function json(path,body){const response=await fetch(base+path,{...(body?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(3000)});assert.ok(response.ok);return response.json();}
async function click(label,scope="[data-trademark-watch]"){const found=`[...document.querySelectorAll(${JSON.stringify(scope+" button")})].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled&&b.getClientRects().length)`;await until(`!!(${found})`);await evaluate(`(${found}).click()`);}
async function fill(selector,value){await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('field missing');const p=e.tagName==='SELECT'?HTMLSelectElement.prototype:e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));})()`);}
async function navigate(locale="en-CH"){await json("/__qa/state",{locale});await call("Page.navigate",{url:base+"/trademark-watch"});await until(`document.querySelector('[data-trademark-watch] h1')?.textContent===${JSON.stringify(trademarkCopy[locale].title)}`);await until("!document.querySelector('[data-trademark-watch] [role=status]')");}
function record(name){checks.push(name);console.log(name);}
async function audit(name){
  await evaluate("(()=>{const s=document.createElement('script');s.src='/__qa/axe.js';document.head.append(s);})()");await until("typeof window.axe==='object'");
  await evaluate("(()=>{window.__ipAudit=null;window.axe.run(document).then(v=>window.__ipAudit={violations:v.violations,incomplete:v.incomplete.map(i=>({id:i.id,nodes:i.nodes.map(n=>n.target)}))},e=>window.__ipAudit={error:String(e)});})()");await until("window.__ipAudit!==null");
  const result=await evaluate("window.__ipAudit");assert.ok(!result.error,result.error);assert.deepEqual(result.violations.map(v=>v.id),[]);await json("/__qa/audit",{name,...result});
  const shot=await call("Page.captureScreenshot",{format:"png"});await writeFile(join(output,`trademark-${name}.png`),Buffer.from(shot.data,"base64"));record(`axe:${name}:0-violations`);
}
try{
  const end=Date.now()+15000;let port;while(Date.now()<end){try{port=Number((await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0]);break;}catch{await delay(100);}}
  assert.ok(port);const tabs=await fetch(`http://127.0.0.1:${port}/json/list`,{signal:AbortSignal.timeout(3000)}).then(r=>r.json());cdp=new Cdp(tabs.find(t=>t.type==="page").webSocketDebuggerUrl);await bounded(cdp.ready);await call("Page.enable");await call("Runtime.enable");
  await call("Emulation.setDeviceMetricsOverride",{width:1280,height:1000,deviceScaleFactor:1,mobile:false});await navigate();
  await checkIPI({click,until,evaluate,json,record});await click(c.create);
  await checkDeadlineChoice({click,fill,until,evaluate,json,record,copy:c});
  await fill('[data-trademark-form] > fieldset > label input',"Private IP fixture");await fill('[data-trademark-brand] > label input',"ALMORA");
  await fill('[data-trademark-brand] > label select',"en");await fill('[data-trademark-brand] textarea',"ALMORA AI\nALMORA DIGITAL");
  assert.equal(await evaluate("document.querySelector('[data-trademark-brand] textarea').value"),"ALMORA AI\nALMORA DIGITAL");record("multiline-word-variants-remain-editable");
  await fill('[data-trademark-brand] > label:last-of-type input',"46");await click(c.save);await until(`document.querySelector('[data-trademark-form] [role=alert]')?.textContent===${JSON.stringify(c.invalid)}`);record("invalid-nice-class-blocks-save");
  await fill('[data-trademark-brand] > label:last-of-type input',"9, 42");await evaluate("document.querySelector('[data-trademark-brand] details').open=true");await click(c.addGoods);
  await fill('[data-trademark-goods] > label input',"Software");await fill('[data-trademark-goods] div input',"computer software");await click(c.addPhrase);
  await fill('[data-trademark-goods] div:nth-of-type(2) select',"fr");await fill('[data-trademark-goods] div:nth-of-type(2) input',"logiciels informatiques");
  await click(c.addBrand);await fill('[data-trademark-brand]:nth-last-of-type(1) > label input',"PULSANTO");await fill('[data-trademark-brand]:nth-last-of-type(1) > label select',"it");
  await click(c.save);await until("document.querySelector('[data-trademark-detail] h2')?.textContent==='Private IP fixture'");
  assert.equal(await evaluate("document.querySelectorAll('[data-trademark-detail] [data-trademark-facts] > details').length"),2);record("save-private-multi-brand-portfolio-and-language-phrases");
  await audit("desktop");await click(c.edit);await until("document.querySelector('[data-deadline-domicile]')?.value==='representative'");record("saved-deadline-context-survives-edit");await fill('[data-trademark-form] > fieldset > label input',"Revised IP fixture");await click(c.save);
  await until("document.querySelector('[data-trademark-detail] h2')?.textContent==='Revised IP fixture'");await click(c.history);await until("document.querySelectorAll('[data-trademark-history] > details').length===2");record("edit-preserves-selected-portfolio-and-version-history");
  await click(c.edit);await fill('[data-trademark-form] > fieldset > label input',"Conflict retains my changes");await json("/__qa/state",{conflict:true});await click(c.save);
  await until(`document.querySelector('[data-trademark-form] [role=alert]')?.textContent===${JSON.stringify(c.conflict)}`);
  assert.equal(await evaluate("document.querySelector('[data-trademark-form] > fieldset > label input').value"),"Conflict retains my changes");
  await json("/__qa/state",{conflict:false});await click(c.cancel);record("version-conflict-preserves-unsaved-input-until-cancelled");
  await checkReview({click,until,evaluate,json,call,record,audit,base});
  await click(c.archive);await until(`document.querySelector('[data-trademark-detail]')?.textContent.includes(${JSON.stringify(c.archived)})`);await click(c.remove);await click(c.cancel);assert.ok(await evaluate("!!document.querySelector('[data-trademark-detail]')"));record("archive-retains-history-and-delete-can-be-cancelled");
  await click(c.remove);await evaluate(`(()=>{const buttons=[...document.querySelectorAll('[data-trademark-detail] button')].filter(b=>b.textContent.trim()===${JSON.stringify(c.remove)});buttons.at(-1).click();})()`);await until(`document.querySelector('[data-trademark-watch] aside')?.textContent.includes(${JSON.stringify(c.empty)})`);record("confirmed-delete-removes-portfolio");
  await json("/__qa/state",{manager:false});await navigate();assert.ok(!await evaluate(`!![...document.querySelectorAll('[data-trademark-watch] button')].find(b=>b.textContent.trim()===${JSON.stringify(c.create)})`));record("viewer-cannot-create-or-edit-portfolios");
  await json("/__qa/state",{manager:true});await call("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  for(const locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){await navigate(locale);await click(trademarkCopy[locale].create);await until("!!document.querySelector('[data-trademark-form]')");assert.ok(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),locale);record(`mobile-portfolio:${locale}`);}
  await evaluate("document.querySelector('[data-trademark-form]').scrollIntoView({block:'start'})");await audit("mobile");
  await fill('[data-trademark-form] > fieldset > label input',"Hidden after denial");await fill('[data-trademark-brand] > label input',"PRIVATE-BRAND");await json("/__qa/state",{denied:true});await click(c.save);await until("!document.querySelector('[data-trademark-form]')");
  assert.ok(!await evaluate("document.body.textContent.includes('PRIVATE-BRAND')"));record("mutation-membership-denial-redacts-private-form");
  const requests=await json("/__qa/requests");assert.ok(!requests.some(r=>/\/email|source.*poll|\/send/.test(r.path)));record("no-native-ipi-network-email-or-legal-action");
}finally{
  await writeFile(join(output,"trademark-browser-checks.json"),JSON.stringify(checks,null,2));cdp?.close();child.kill();await json("/__qa/finish",{});
}
