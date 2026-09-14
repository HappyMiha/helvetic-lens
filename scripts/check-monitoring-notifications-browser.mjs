// Built UI with synthetic private queues and immutable Pollen evidence.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { monitoringNotificationsCopy } from "../apps/web/lib/monitoring-notifications-copy.ts";
import { pollenEvidenceCopy } from "../apps/web/lib/pollen-evidence-copy.ts";
import { pollenRuntimeCopy } from "../apps/web/lib/pollen-runtime-copy.ts";
import { documentHistoryCopy } from "../apps/web/lib/document-history-copy.ts";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";

const root=resolve(import.meta.dirname,"..");
const chrome=[process.env.CHROME_BIN,"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe","/usr/bin/google-chrome"].filter(Boolean).find(existsSync);assert.ok(chrome);
const reserve=createServer();await new Promise(r=>reserve.listen(0,"127.0.0.1",r));const port=reserve.address().port;await new Promise(r=>reserve.close(r));const base=`http://127.0.0.1:${port}`;
const server=spawn(process.execPath,[join(root,"node_modules/next/dist/bin/next"),"start","-H","127.0.0.1","-p",String(port)],{cwd:join(root,"apps/web"),stdio:"ignore",windowsHide:true});
const profile=await mkdtemp(join(tmpdir(),"helvetic-monitoring-notifications-"));
const browser=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{stdio:"ignore",windowsHide:true});
const audit=new AccessibilityAudit("monitoring-notifications"),exceptions=[],requests=[];
const domains=["pollen","air","river","tenders","commute","traffic","warnings","ip","auctions"];
const routes={pollen:"pollen",air:"air",river:"river",tenders:"tender",commute:"commute",traffic:"road",warnings:"hazard",ip:"trademark",auctions:"auction"};
const subject="00000000-0000-4000-8000-000000000001",entry="00000000-0000-4000-8000-000000000002",clock="2026-09-14T12:00:00Z";
const pollenHref=`/pollen-watch?entry=${entry}#draft=${subject}`;
const config={station_id:"PBS",selections:[{allergen:"birch",rules:[]}],timezone:"Europe/Zurich",delivery:{email:"off",digest_at:null,quiet_hours:null}};
const draft={id:subject,status:"active",revision:1,runtime_version:1,configuration:config,configuration_hash:"a".repeat(64)};
const sample=value=>({series:{source_id:"synthetic",method_version:"synthetic-v1",station_id:"PBS",allergen:"birch",period:"observation_hourly",unit:"number/m3",forecast:null},value,valid_at:clock,fetched_at:clock,fresh_until:clock,quality:"usable",source_revision:1,artifact_hashes:["a".repeat(64)],policy_version:"synthetic"});
let cdp,locale="en-CH",user="qa-a",role="organization_admin",mode="ready",withheld=false,reviewed=false,pinnedReads=0;
const pinned=()=>({subject_id:subject,current_configuration:true,newer_available:true,entry:{id:entry,sequence:1,kind:"material",material_id:entry,created_at:clock,current:sample(withheld?null:"12.500001"),previous:withheld?null:sample("1.25"),baseline:null,reasons:withheld?[]:["threshold_triggered"],configuration_revision:1,binding:{rule:null},raw_export_available:false,source_withheld:withheld,review:reviewed?{version:1,decision:"reviewed"}:null}});
const modal='[data-notification-centre]',queue='[data-monitoring-notification-queue]';
async function wait(check,message){for(let i=0;i<220;i++){if(await Promise.resolve().then(check).catch(()=>false))return;await sleep(100);}throw Error(message);}
const text=selector=>evaluate(cdp,`document.querySelector(${JSON.stringify(selector)})?.innerText || ''`);
async function click(selector){await wait(()=>evaluate(cdp,`!!document.querySelector(${JSON.stringify(selector)}) && !document.querySelector(${JSON.stringify(selector)}).disabled`),`Missing ${selector}`);await evaluate(cdp,`document.querySelector(${JSON.stringify(selector)}).click()`);}
async function button(label){await wait(()=>evaluate(cdp,`[...document.querySelectorAll(${JSON.stringify(modal+' button')})].some(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled)`),`Missing ${label}`);await evaluate(cdp,`[...document.querySelectorAll(${JSON.stringify(modal+' button')})].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled).click()`);}
const ready=()=>wait(()=>evaluate(cdp,`document.querySelector(${JSON.stringify(queue)})?.getAttribute('aria-busy')==='false'`),"Queue not ready");
async function check(name,selector=queue){await evaluate(cdp,"Promise.all(document.getAnimations().filter(a=>a.effect?.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})))");assert.ok(await evaluate(cdp,"document.documentElement.scrollWidth <= innerWidth+1"));await audit.check(cdp,name,selector);}
async function open(){await click('[data-notifications-trigger]');await wait(()=>evaluate(cdp,`document.querySelectorAll(${JSON.stringify(modal+' [data-domain]')}).length===10`),"Ten review queues missing");}
let navigation=0;
async function navigate(path){const url=new URL(path,base);url.searchParams.set('qa',String(++navigation));await evaluate(cdp,"window.__oldQueueDocument=true");await cdp.send("Page.navigate",{url:url.href});await wait(()=>evaluate(cdp,`!window.__oldQueueDocument && document.documentElement.lang===${JSON.stringify(locale)} && [...document.querySelectorAll('button[title]')].some(b=>b.title.includes(${JSON.stringify(user)}))`),"Authenticated page not ready");}
try {
  await wait(async()=>(await fetch(base)).ok,"Next did not start");let debugPort;await wait(async()=>{debugPort=(await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0];return !!debugPort;},"Chrome did not start");
  const target=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());cdp=new Cdp(target.webSocketDebuggerUrl);await cdp.send("Page.enable");await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown",({exceptionDetails})=>exceptions.push(exceptionDetails.exception?.description||exceptionDetails.text));
  cdp.on("Fetch.requestPaused",async({requestId,request})=>{
    const url=new URL(request.url),path=url.pathname;requests.push({path,method:request.method,body:request.postData,user});let code=200,body={};
    if(path==="/api/auth/session")body={authenticated:true,user:{id:user,name:user,email:`${user}@example.invalid`,locale},organization:{id:"qa-org",name:"Queue QA"},role,onboarding_required:false};
    else if(path==="/api/health")body={status:"ok",database:"synthetic",apertus:{configured:false},firecrawl:{configured:false}};
    else if(path==="/api/jobs")body=[];
    else if(path==="/api/monitoring-centre/today-counts")body={items:[...domains,"legal"].map(domain=>({domain,count:1,state:"complete"})),total:10,state:"complete",evaluated_at:clock};
    else if(path==="/api/monitoring-centre/notifications"){
      const domain=url.searchParams.get("domain"),cursor=url.searchParams.get("cursor");
      if(mode==="failure"){code=503;body={code:"unavailable"};}
      else body={domain,state:mode==="unavailable"?"unavailable":"available",items:mode==="unavailable"||mode==="empty"||cursor==="sparse"?[]:[{id:cursor==="last"?"last":entry,domain,monitor_name:`Private ${domain} <script>literal</script>`,allergen:domain==="pollen"?"birch":null,detected_at:clock,href:domain==="pollen"?pollenHref:`/${routes[domain]}-watch?monitor=${subject}&event=${entry}`}],next_cursor:mode!=="ready"||cursor==="last"?null:cursor==="sparse"?"last":"sparse"};
    } else if(path==="/api/monitoring-subjects")body={items:[draft],next_cursor:null};
    else if(path===`/api/monitoring-subjects/${subject}`)body=draft;
    else if(path===`/api/monitoring-subjects/${subject}/history`)body={items:[{revision:1,configuration:config,configuration_hash:"a".repeat(64)}],next_before_revision:null};
    else if(path===`/api/monitoring-subjects/${subject}/state`)body={...draft,runtime:{version:1,run_id:subject,health:"ready",email_consent:false,muted:false},current:[{stream_id:subject,entry_id:"newer",sample:sample("98.5"),availability:"usable",category:null}],start_available:true,blocking_reasons:[],coverage:[]};
    else if(path===`/api/monitoring-subjects/${subject}/activity`)body={items:[],next_cursor:null};
    else if(path===`/api/monitoring-subjects/${subject}/activity/${entry}`){pinnedReads++;body=pinned();}
    else if(path===`/api/monitoring-subjects/${subject}/activity/${entry}/review`){assert.equal(request.method,"POST");assert.deepEqual(JSON.parse(request.postData),{decision:"reviewed",expected_version:0});reviewed=true;body={version:1,decision:"reviewed"};}
    else {code=503;body={code:"unavailable"};}
    await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"Content-Type",value:"application/json"},{name:"Cache-Control",value:"no-store"}],body:Buffer.from(JSON.stringify(body)).toString("base64")}).catch(()=>{});
  });
  await cdp.send("Fetch.enable",{patterns:[{urlPattern:`${base}/api/*`,requestStage:"Request"}]});
  for(const language of Object.keys(monitoringNotificationsCopy)){
    locale=language;mode="ready";withheld=false;reviewed=false;
    await cdp.send("Emulation.setDeviceMetricsOverride",{width:locale==="en-CH"?1280:390,height:950,deviceScaleFactor:1,mobile:false});
    await navigate("/overview");await open();await check(`overview-${locale}`,modal);
    for(const domain of domains){
      await click(`${modal} [data-domain="${domain}"]`);await ready();
      assert.ok((await text(queue)).includes(`Private ${domain} <script>literal</script>`));assert.equal(await evaluate(cdp,`document.querySelectorAll(${JSON.stringify(queue+' script')}).length`),0);
      assert.ok((await text(queue)).includes(monitoringNotificationsCopy[locale].open));await check(`${domain}-${locale}`);
      if(domain==="traffic"){
        await button(documentHistoryCopy[locale].next);await ready();assert.ok((await text(queue)).includes(monitoringNotificationsCopy[locale].sparse));
        await button(documentHistoryCopy[locale].next);await ready();assert.equal(await evaluate(cdp,`document.querySelectorAll(${JSON.stringify(queue+' [data-monitoring-notification]')}).length`),1);
        await button(documentHistoryCopy[locale].previous);await ready();assert.ok((await text(queue)).includes(monitoringNotificationsCopy[locale].sparse));
      }
      await button(monitoringNotificationsCopy[locale].overview);
    }
    await click(`${modal} [data-domain="pollen"]`);await ready();await click(`${queue} [data-monitoring-notification] a`);
    await wait(()=>evaluate(cdp,`!!document.querySelector('[data-pollen-pinned]') && document.querySelector('[data-pollen-pinned]').getAttribute('aria-busy')==='false'`),"Pinned Pollen missing");
    const copy=pollenEvidenceCopy[locale],oldNumber=await evaluate(cdp,`new Intl.NumberFormat(${JSON.stringify(locale)},{maximumFractionDigits:6}).format(12.500001)`);
    assert.ok((await text('[data-pollen-pinned]')).includes(oldNumber));assert.ok((await text('[data-pollen-pinned]')).includes(copy.newer));
    assert.ok(!(await text('[data-pollen-pinned]')).includes("98.5"));assert.ok((await text('[data-pollen-runtime]')).includes("98.5"));
    assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-pollen-pinned] a[download]').length`),0);await check(`pinned-${locale}`,'[data-pollen-pinned]');
    withheld=true;await click('[data-pollen-pinned] > button');await wait(async()=>!(await text('[data-pollen-pinned]')).includes(oldNumber)&&(await text('[data-pollen-pinned]')).includes(copy.withheld),"Revoked evidence remained visible");await check(`withheld-${locale}`,'[data-pollen-pinned]');
    assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-pollen-pinned] button[aria-pressed]').length`),0);
  }
  locale="en-CH";withheld=false;reviewed=false;await navigate(pollenHref);
  await wait(()=>evaluate(cdp,`document.querySelector('[data-pollen-pinned]')?.getAttribute('aria-busy')==='false'`),"Pinned review not ready");
  const before=pinnedReads;await evaluate(cdp,`[...document.querySelectorAll('[data-pollen-pinned] button')].find(b=>b.textContent.trim()===${JSON.stringify(pollenRuntimeCopy[locale].reviewed)}).click()`);
  await wait(()=>pinnedReads>before&&reviewed,"Pinned review did not reload exact evidence");await wait(async()=>(await text('[data-pollen-pinned]')).includes("12.500001"),"Review replaced saved value");
  await check("pinned-review",'[data-pollen-pinned]');
  await navigate("/overview");await open();await click(`${modal} [data-domain="traffic"]`);await ready();
  for(const scenario of ["failure","unavailable","empty"]){mode=scenario;await button(documentHistoryCopy[locale].restart);await ready();assert.ok((await text(queue)).includes(monitoringNotificationsCopy[locale][scenario==="failure"?"failed":scenario]));await check(scenario);if(scenario==="failure"){mode="ready";await button(documentHistoryCopy[locale].retry);await ready();}}
  await writeFile(join(root,"test-results/monitoring-notifications.png"),Buffer.from((await cdp.send("Page.captureScreenshot",{format:"png"})).data,"base64"));
  await evaluate(cdp,"window.dispatchEvent(new PageTransitionEvent('pagehide'))");assert.equal(await text(queue),"");await wait(async()=>(await text(modal))==="","Closed dialog remained mounted");
  user="qa-b";role="viewer";mode="ready";await navigate(pollenHref);await wait(()=>evaluate(cdp,`document.querySelector('[data-pollen-pinned]')?.getAttribute('aria-busy')==='false'`),"Viewer evidence missing");
  assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-pollen-pinned] button[aria-pressed]').length`),0);await check("viewer-pinned",'[data-pollen-pinned]');
  assert.deepEqual(exceptions,[]);assert.equal(requests.filter(r=>r.method==="POST"&&!r.path.startsWith('/api/assistant/')).length,1);audit.finish(65);
  console.log("Monitoring notifications: 65 full-document built-browser/axe checks. All nine queues and pinned Pollen in five locales, sparse pagination, source/error redaction, explicit review and viewer scope. Synthetic evidence only.");
} catch(error){console.error({locale,mode,withheld,exceptions,requests:requests.slice(-10),text:cdp?await text('body').catch(()=>""):""});throw error;}
finally {cdp?.close();for(const child of [browser,server]){const stopped=new Promise(r=>child.once("exit",r));child.kill();await Promise.race([stopped,sleep(2000)]);}assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith("helvetic-monitoring-notifications-"));await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});}
