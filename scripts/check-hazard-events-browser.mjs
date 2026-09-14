// Built UI against an owned disposable local fixture; no real users or source grants.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { resolve, join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { Cdp } from "./browser-cdp.mjs";
import { hazardEventCopy } from "../apps/web/lib/hazard-event-copy.ts";
import { hazardCopy } from "../apps/web/lib/hazard-copy.ts";
import { roadCopy } from "../apps/web/lib/road-copy.ts";
import { hazardHref } from "../apps/web/lib/hazard-events.ts";
import { hazardLifecycleCopy } from "../apps/web/lib/hazard-lifecycle-copy.ts";

const origin=new URL(process.argv[2]);assert.equal(origin.hostname,"127.0.0.1");assert.equal(origin.protocol,"http:");
const base=origin.origin,root=resolve(import.meta.dirname,".."),output=join(root,"test-results/accessibility");
const chrome=["C:/Program Files/Google/Chrome/Application/chrome.exe","C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"].find(existsSync);
assert.ok(chrome);await mkdir(output,{recursive:true});
const profile=await mkdtemp(join(root,".tmp/hazard-events-chrome-"));
const child=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--disable-background-networking","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{windowsHide:true,stdio:"ignore"});
let cdp;const checks=[],c=hazardEventCopy["en-CH"],h=hazardCopy["en-CH"],r=roadCopy["en-CH"];
async function bounded(p,ms=10000){let t;try{return await Promise.race([p,new Promise((_,reject)=>{t=setTimeout(()=>reject(Error("Browser operation timed out")),ms);})]);}finally{clearTimeout(t);}}
const call=(method,params={})=>bounded(cdp.send(method,params));
async function evaluate(expression){const value=await call("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:false});if(value.exceptionDetails)throw Error(value.exceptionDetails.text);return value.result.value;}
async function until(expression){const end=Date.now()+15000;while(Date.now()<end){if(await evaluate(expression))return;await delay(100);}throw Error("Condition timed out: "+expression);}
async function json(path,body){const response=await fetch(base+path,{...(body?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(3000)});assert.ok(response.ok);return response.json();}
async function click(label,scope="[data-hazard-watch]"){
  const found=`[...document.querySelectorAll(${JSON.stringify(scope+" button")})].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled&&b.getClientRects().length)`;
  await until(`!!(${found})`);await evaluate(`(${found}).click()`);
}
async function link(label){await evaluate(`(()=>{const a=[...document.querySelectorAll('[data-hazard-watch] a')].find(a=>a.textContent.trim()===${JSON.stringify(label)});if(!a)throw Error('Link missing');a.click();})()`);}
async function navigate(path,locale="en-CH") {await json("/__qa/state",{locale});await call("Page.navigate",{url:base+path});await until(`document.querySelector('[data-hazard-watch] h1')?.textContent===${JSON.stringify(hazardCopy[locale].title)}`);}
const readerText=()=>evaluate("document.querySelector('[data-hazard-event-reader]')?.textContent||''");
async function ready(){await until("!!document.querySelector('[data-hazard-official]')");}
async function refresh(){await click(r.refresh,"[data-hazard-event-reader]");}
function record(name){checks.push(name);console.log(name);}
async function audit(name){
  await evaluate("(()=>{const s=document.createElement('script');s.src='/__qa/axe.js';document.head.append(s);})()");await until("typeof window.axe==='object'");
  await evaluate("(()=>{window.__hazardAudit=null;window.axe.run(document).then(v=>window.__hazardAudit={violations:v.violations,incomplete:v.incomplete.map(i=>({id:i.id,nodes:i.nodes.map(n=>n.target)}))},e=>window.__hazardAudit={error:String(e)});})()");
  await until("window.__hazardAudit!==null");const result=await evaluate("window.__hazardAudit");assert.ok(!result.error,result.error);
  await json("/__qa/audit",{name,...result});assert.deepEqual(result.violations.map(v=>v.id),[]);
  await evaluate("document.querySelector('[data-hazard-official]')?.scrollIntoView({block:'center',behavior:'instant'})");
  const shot=await call("Page.captureScreenshot",{format:"png"});await writeFile(join(output,`hazard-${name}.png`),Buffer.from(shot.data,"base64"));record(`axe:${name}:0-violations`);
}
try{
  const end=Date.now()+15000;let port;
  while(Date.now()<end){try{port=Number((await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0]);break;}catch{await delay(100);}}
  assert.ok(port);const tabs=await fetch(`http://127.0.0.1:${port}/json/list`,{signal:AbortSignal.timeout(3000)}).then(r=>r.json());
  cdp=new Cdp(tabs.find(t=>t.type==="page").webSocketDebuggerUrl);await bounded(cdp.ready);await call("Page.enable");await call("Runtime.enable");
  await call("Emulation.setDeviceMetricsOverride",{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
  await json("/__qa/state",{suite:"events"});
  const {id,eventId}=await json("/__qa/seed-events",{}),path=hazardHref(id,eventId);
  await json("/__qa/seed-events",{native:true});
  await call("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  for(const locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){
    await navigate(path,locale);await ready();const copy=hazardEventCopy[locale];
    assert.ok(await evaluate(`document.querySelector('[data-hazard-source]')?.textContent.includes(${JSON.stringify(hazardCopy[locale].sourceCurrent)})`));
    assert.ok((await readerText()).includes(copy.incompleteHistory));
    assert.ok((await readerText()).includes("Synthetic redistribution delay disclaimer."));
    assert.ok(await evaluate("!!document.querySelector('[data-hazard-official] a[href=\"https://meteoalarm.org/en/live/\"]')"));
    assert.ok(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"));record(`native-warning-mobile:${locale}`);
  }
  assert.ok((await readerText()).includes("Falling branches."));assert.ok(!await evaluate("window.__hazardInjected===true"));
  assert.ok(await evaluate("!!document.querySelector('[data-hazard-official] a[href=\"http://example.invalid/official-warning\"]')"));
  await audit("native-warning-mobile");
  for(const [reason,label] of [["hazard_source_no_longer_listed",c.noLongerListed],["hazard_source_poll_not_current",c.sourceNotCurrent]]){
    await json("/__qa/state",{nativeUnavailable:reason});await refresh();
    await until(`document.querySelector('[data-hazard-event-reader]')?.textContent.includes(${JSON.stringify(label)})`);
    assert.ok(!await evaluate("!!document.querySelector('[data-hazard-official]')"));
    assert.ok(!await evaluate("!!document.querySelector('[data-hazard-review-actions]')"));record(`native-warning-unavailable:${reason}`);
  }
  await navigate(path+"&revision=1");await ready();assert.ok((await readerText()).includes(c.incompleteHistory));record("native-unavailable-warning-retains-labelled-history");
  assert.ok(await evaluate(`document.querySelector('[data-hazard-source]')?.textContent.includes(${JSON.stringify(h.sourceWaiting)})`));record("native-source-status-refreshes-and-keeps-drafts-visible");
  await json("/__qa/seed-events",{});
  await call("Emulation.setDeviceMetricsOverride",{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
  await navigate(path);await ready();
  assert.ok((await readerText()).includes("Stay indoors."));assert.ok(!await evaluate("window.__hazardInjected===true"));
  assert.ok((await readerText()).includes(c.importance));assert.ok(!(await readerText()).includes(h.importance));assert.ok(!(await readerText()).includes(h.warning));
  assert.ok((await readerText()).includes(c.fetched));record("exact-current-reader-original-instructions-freshness-no-script-execution");
  await evaluate("(()=>{const s=document.querySelector('[data-hazard-event-reader] select');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(s,'de-CH');s.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await until("document.querySelector('[data-hazard-official]')?.textContent.includes('Bleiben Sie im Haus.')");record("explicit-official-language-selection");
  await click(c.markReviewed);await until(`document.querySelector('[data-hazard-event-reader]')?.textContent.includes(${JSON.stringify("· "+c.reviewed)})`);
  let reviews=(await json("/__qa/requests")).filter(x=>x.path.endsWith("/review"));assert.equal(reviews.at(-1).body.expected_revision,1);assert.equal(reviews.at(-1).body.expected_version,1);
  await click(c.audit);await until("document.querySelector('[data-hazard-review-history] li')!==null");record("review-binds-opened-revision-and-retains-action-audit");
  await json("/__qa/event",{mode:"translate"});await refresh();await until("document.querySelector('[data-hazard-event-reader] option[value=\"fr-CH\"]')!==null");assert.ok(await evaluate("document.querySelector('[data-hazard-review-actions] button')?.disabled"));record("translation-does-not-reopen-review");
  await json("/__qa/event",{mode:"escalate"});await refresh();await ready();
  await evaluate("(()=>{const s=document.querySelector('[data-hazard-event-reader] select');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(s,'en-CH');s.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await until("document.querySelector('[data-hazard-official]')?.textContent.includes('Evacuate through the north exit.')");
  assert.ok(!await evaluate("document.querySelector('[data-hazard-review-actions] button')?.disabled"));record("new-instructions-reopen-reviewed-warning");
  await click(c.history);await until("document.querySelector('[data-hazard-event-history] a[href$=\"revision=1\"]')!==null");
  await evaluate("document.querySelector('[data-hazard-event-history] a[href$=\"revision=1\"]').click()");
  await until(`document.querySelector('[data-hazard-event-reader] h4')?.textContent.includes(${JSON.stringify(c.historical)})`);await ready();
  assert.ok((await readerText()).includes(c.historical));assert.ok((await readerText()).includes("Stay indoors."));
  assert.ok(!await evaluate("!!document.querySelector('[data-hazard-review-actions]')"));record("historical-reader-retains-old-text-and-has-no-current-review-action");
  await link(c.openCurrent);await until(`document.querySelector('[data-hazard-event-reader] h4')?.textContent.includes(${JSON.stringify(c.current)})`);
  await ready();await click(c.dismiss);await until(`document.querySelector('[data-hazard-event-reader]')?.textContent.includes(${JSON.stringify(c.dismissed)})`);
  await click(`${c.mute}: ${h.storm}`,"[data-hazard-mutes]");await ready();
  await until(`document.querySelector('[data-hazard-mutes]')?.textContent.includes(${JSON.stringify(c.unmute+": "+h.storm)})`);
  assert.ok((await readerText()).includes(c.muted));await click(`${c.unmute}: ${h.storm}`,"[data-hazard-mutes]");await ready();record("private-dismiss-and-type-mute-unmute-preserve-history");
  await audit("events-desktop");
  await json("/__qa/event",{mode:"cancel"});await refresh();await until(`document.querySelector('[data-hazard-event-reader]')?.textContent.includes(${JSON.stringify(c.cancelledDetail)})`);record("withdrawal-is-distinct-from-all-clear");
  await json("/__qa/seed-events",{});await json("/__qa/event",{mode:"resolve"});await navigate(path);await ready();assert.ok((await readerText()).includes(c.resolved));record("explicit-all-clear-display");
  await json("/__qa/state",{evidenceUnavailable:true});await refresh();await until(`document.querySelector('[data-hazard-event-reader]')?.textContent.includes(${JSON.stringify(c.unavailableDetail)})`);
  assert.ok(!await evaluate("!!document.querySelector('[data-hazard-official]')"));assert.ok(!await evaluate("!!document.querySelector('[data-hazard-review-actions]')"));record("revoked-or-missing-evidence-redacts-source-and-actions");
  await navigate(path+"&revision=0");await until(`document.querySelector('[data-hazard-events]')?.textContent.includes(${JSON.stringify(c.invalidLink)})`);assert.ok(!await evaluate("!!document.querySelector('[data-hazard-event-reader]')"));record("invalid-historical-link-never-falls-back-to-current");
  await json("/__qa/state",{denied:true});await navigate(path);await until(`document.querySelector('[data-hazard-watch]')?.textContent.includes(${JSON.stringify(h.unavailable)})`);
  assert.ok(!await evaluate("document.querySelector('[data-hazard-watch]').textContent.includes('Home warning fixture')"));record("membership-denial-clears-private-workspace");
  await json("/__qa/seed-events",{});await json("/__qa/state",{manager:false});await navigate(path);await ready();
  assert.ok(!await evaluate("!!document.querySelector('[data-hazard-review-actions], [data-hazard-mutes] button')"));record("viewer-can-read-without-review-or-mute-controls");
  await json("/__qa/state",{manager:true,delayEventMs:2000});await navigate(path);await until("!!document.querySelector('[data-hazard-event-reader] [role=status]')");
  await call("Page.navigate",{url:base+hazardHref("00000000-0000-4000-8000-000000000099")});
  await until("document.querySelector('[data-hazard-watch] [role=alert]')!==null");await delay(2200);
  assert.ok(!await evaluate("!!document.querySelector('[data-hazard-official]')"));record("late-reader-response-cannot-repopulate-another-location");
  await json("/__qa/state",{delayEventMs:0});await call("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  for(const locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){
    await navigate(path,locale);await ready();assert.ok((await readerText()).includes(hazardEventCopy[locale].instructions));
    assert.ok(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),`overflow:${locale}`);record(`mobile-official-reader:${locale}`);
  }
  await audit("events-mobile");
  const openFeed=async(inbox=false,locale="en-CH")=>{
    await json("/__qa/state",{locale});await call("Page.navigate",{url:base+(inbox?"/impact":"/")});
    await until(`document.querySelector('[data-hazard-${inbox?"inbox":"today"}] h2')?.textContent===${JSON.stringify(hazardEventCopy[locale][inbox?"inbox":"today"])}`);
  };
  await json("/__qa/seed-events",{});await call("Emulation.setDeviceMetricsOverride",{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
  await openFeed();await until("!!document.querySelector('[data-hazard-today] li a')");
  assert.equal(await evaluate("document.querySelector('[data-hazard-today] li a').getAttribute('href')"),hazardHref(id,eventId,1));
  assert.ok(await evaluate(`document.querySelector('[data-hazard-today]').textContent.includes(${JSON.stringify(c.coverage)})`));
  await evaluate("document.querySelector('[data-hazard-today] li a').click()");await ready();
  assert.ok((await readerText()).includes(c.historical));assert.ok((await readerText()).includes("Stay indoors."));record("today-opens-exact-warning-and-original-instructions");
  await link(c.openCurrent);await until(`document.querySelector('[data-hazard-event-reader] h4')?.textContent.includes(${JSON.stringify(c.current)})`);
  await ready();await click(c.markReviewed);await until(`document.querySelector('[data-hazard-event-reader]')?.textContent.includes(${JSON.stringify("· "+c.reviewed)})`);
  await openFeed();await until(`document.querySelector('[data-hazard-today]')?.textContent.includes(${JSON.stringify(c.feedEmpty)})`);
  assert.ok(!await evaluate("!!document.querySelector('[data-hazard-today] li')"));record("reviewed-warning-leaves-today");
  await json("/__qa/event",{mode:"escalate"});await click(r.refresh,"[data-hazard-today]");await until("!!document.querySelector('[data-hazard-today] li')");
  await openFeed(true);assert.ok(await evaluate(`document.querySelector('[data-hazard-inbox]').textContent.includes(${JSON.stringify(c.alarm)})`));record("new-instructions-reopen-today-and-active-inbox");
  await audit("inbox-desktop");
  await json("/__qa/event",{mode:"cancel"});await click(r.refresh,"[data-hazard-inbox]");
  await until(`document.querySelector('[data-hazard-inbox]')?.textContent.includes(${JSON.stringify(c.feedEmpty)})`);
  await openFeed();await until(`document.querySelector('[data-hazard-today] li')?.textContent.includes(${JSON.stringify(c.cancelled)})`);record("withdrawal-leaves-active-inbox-and-remains-in-today");
  await json("/__qa/seed-events",{});await navigate(path);await ready();await click(`${c.mute}: ${h.storm}`,"[data-hazard-mutes]");
  await until(`document.querySelector('[data-hazard-mutes]')?.textContent.includes(${JSON.stringify(c.unmute+": "+h.storm)})`);
  await openFeed(true);await until(`document.querySelector('[data-hazard-inbox]')?.textContent.includes(${JSON.stringify(c.feedEmpty)})`);record("type-mute-hides-inbox-without-review");
  await json("/__qa/seed-events",{});await json("/__qa/state",{feedContinuation:true});await openFeed();
  await click(r.more,"[data-hazard-today]");await until("!!document.querySelector('[data-hazard-today] li')");
  assert.ok((await json("/__qa/requests")).some(x=>x.path==="/api/hazard-watch/today"&&x.query.includes("cursor=")));record("empty-filtered-today-page-can-continue");
  await json("/__qa/state",{feedContinuation:false,evidenceUnavailable:true});await click(r.refresh,"[data-hazard-today]");
  await until(`document.querySelector('[data-hazard-today]')?.textContent.includes(${JSON.stringify(c.unavailableDetail)})`);
  assert.ok(!await evaluate("!!document.querySelector('[data-hazard-today] li')"));record("rights-loss-redacts-summary-without-allclear");
  await json("/__qa/state",{denied:true});await click(r.refresh,"[data-hazard-today]");
  await until("!document.querySelector('[data-hazard-today]')");record("membership-loss-removes-feed-content");
  await json("/__qa/seed-events",{});await json("/__qa/state",{feedFailure:true});await openFeed();
  await until("!!document.querySelector('[data-hazard-today] [role=alert]')");assert.ok(!await evaluate("!!document.querySelector('[data-hazard-today] li')"));
  await json("/__qa/state",{feedFailure:false});await click(r.refresh,"[data-hazard-today]");await until("!!document.querySelector('[data-hazard-today] li')");record("feed-failure-redacts-and-refresh-recovers");
  await call("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  for(const locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){
    await openFeed(false,locale);await until("!!document.querySelector('[data-hazard-today] li')");
    assert.ok(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),`today-overflow:${locale}`);record(`mobile-warning-today:${locale}`);
  }
  await evaluate("document.querySelector('[data-hazard-today]').scrollIntoView({block:'start',behavior:'instant'})");await audit("today-mobile");
  const life=hazardLifecycleCopy["en-CH"],lifeRoot="[data-hazard-lifecycle]";
  await json("/__qa/seed-lifecycle",{});await call("Emulation.setDeviceMetricsOverride",{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
  await navigate(hazardHref(id));await until(`document.querySelector('${lifeRoot}')?.textContent.includes(${JSON.stringify(life.source)})`);
  assert.ok(await evaluate(`[...document.querySelectorAll('${lifeRoot} button')].find(b=>b.textContent===${JSON.stringify(r.start)})?.disabled`));record("lifecycle-draft-cannot-start-without-reviewed-source");
  await json("/__qa/state",{lifecycleReady:true});await click(r.refresh,lifeRoot);
  await until(`document.querySelector('${lifeRoot}')?.textContent.includes(${JSON.stringify(life.prepared)})`);await click(r.start,lifeRoot);
  await until(`[...document.querySelectorAll('${lifeRoot} button')].some(b=>b.textContent===${JSON.stringify(r.pause)})`);
  const start=(await json("/__qa/requests")).filter(x=>x.path.endsWith("/commands")&&x.body.action==="start");
  assert.equal(start.length,1);assert.equal(start[0].body.expected_version,1);record("explicit-start-binds-current-monitor-version");
  await click(life.history,lifeRoot);await until("!!document.querySelector('[data-hazard-status-history] li')");
  await evaluate("document.querySelector('[data-hazard-lifecycle]').scrollIntoView({block:'center',behavior:'instant'})");await audit("lifecycle-desktop");
  await json("/__qa/state",{lifecycleReady:false,readinessCode:"hazard_source_poll_not_current"});await click(r.refresh,lifeRoot);
  await until(`document.querySelector('${lifeRoot}')?.textContent.includes(${JSON.stringify(life.poll)})`);await click(r.pause,lifeRoot);
  await until(`document.querySelector('${lifeRoot}')?.textContent.includes(${JSON.stringify(life.stopped)})`);
  assert.ok(await evaluate(`[...document.querySelectorAll('${lifeRoot} button')].find(b=>b.textContent===${JSON.stringify(r.resume)})?.disabled`));record("source-loss-allows-pause-but-blocks-resume");
  await json("/__qa/state",{lifecycleReady:true});await click(r.refresh,lifeRoot);await click(r.resume,lifeRoot);
  await until(`[...document.querySelectorAll('${lifeRoot} button')].some(b=>b.textContent===${JSON.stringify(r.pause)})`);
  await json("/__qa/state",{lifecycleReady:false,evidenceUnavailable:true});await click(r.archive,lifeRoot);
  await until(`document.querySelector('[data-hazard-watch]')?.textContent.includes(${JSON.stringify(h.remove)})`);
  await click(life.history,lifeRoot);await until("document.querySelectorAll('[data-hazard-status-history] li').length===4");record("resume-archive-preserve-status-history-even-with-source-loss");
  await json("/__qa/seed-lifecycle",{});await json("/__qa/state",{manager:false,lifecycleReady:true});await navigate(hazardHref(id));
  assert.ok(!await evaluate(`[...document.querySelectorAll('${lifeRoot} button')].some(b=>[${JSON.stringify(r.start)},${JSON.stringify(r.pause)},${JSON.stringify(r.archive)}].includes(b.textContent))`));record("viewer-cannot-start-pause-or-archive");
  await json("/__qa/state",{manager:true,lifecycleReady:false,readinessCode:"hazard_source_location_scope_incomplete"});
  await call("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  for(const locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){
    await navigate(hazardHref(id),locale);await until(`document.querySelector('${lifeRoot}')?.textContent.includes(${JSON.stringify(hazardLifecycleCopy[locale].geography)})`);
    assert.ok(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),`lifecycle-overflow:${locale}`);record(`mobile-warning-lifecycle:${locale}`);
  }
  await evaluate("document.querySelector('[data-hazard-lifecycle]').scrollIntoView({block:'center',behavior:'instant'})");await audit("lifecycle-mobile");
  assert.ok(!(await json("/__qa/requests")).some(x=>/\/start|\/email|source.*poll/.test(x.path)));record("no-source-activation-or-email-requests");
}finally{
  await writeFile(join(output,"hazard-events-browser-checks.json"),JSON.stringify(checks,null,2));
  cdp?.close();child.kill();await json("/__qa/finish",{});
}
