// Isolated built-product journey. Synthetic API responses; no production writes.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { sourceOperationsCopy } from "../apps/web/lib/source-operations-copy.ts";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";

const root=resolve(import.meta.dirname,"..");
const chrome=[process.env.CHROME_BIN,"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe","/usr/bin/google-chrome"].filter(Boolean).find(existsSync);
assert.ok(chrome);
const reserve=createServer(); await new Promise(done=>reserve.listen(0,"127.0.0.1",done));
const port=reserve.address().port; await new Promise(done=>reserve.close(done));
const base=`http://127.0.0.1:${port}`;
const server=spawn(process.execPath,[join(root,"node_modules/next/dist/bin/next"),"start","-H","127.0.0.1","-p",String(port)],{cwd:join(root,"apps/web"),stdio:"ignore",windowsHide:true});
const profile=await mkdtemp(join(tmpdir(),"helvetic-source-ops-qa-"));
const browser=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{stdio:"ignore",windowsHide:true});
let cdp, locale="en-CH", admin=true, status=200, readCount=0;
const exceptions=[], mutations=[];
const audit=new AccessibilityAudit("monitoring-source-operations");
const packIds=["safety_environment","mobility","business_opportunities","intellectual_property"];
const sourceDefs=[["pollen",0,"pollen"],["river",0,"river"],["air",0,"air"],["warnings",0,"hazard"],["commute",1,"commute"],["traffic",1,"road"],["tenders",2,"tender"],["auctions",2,"auction"],["ip",3,"trademark"]];
const data={checked_at:"2026-09-14T06:00:00Z",release:"fixture-release",packs:packIds,items:sourceDefs.map(([id,pack,path],i)=>({
  id,pack:packIds[pack],href:`/${path}-watch`,section_enabled:true,
  collector:id==="warnings"?"channel_required":id==="traffic"?"credentials_required":"configured",
  access:{state:i===7?"expired":i===8?"revoked":i<3?"public_contract":"missing",expires_at:i===7?"2026-09-13T00:00:00Z":null},
  acquisition:{state:i===2?"errors":i===0?"invalid_clock":i<3?"recorded":"unobserved",record_count:i<3?2:0,never_succeeded_count:i===2?1:null,error_count:i===2?1:null,
    oldest_success_at:i<3?"2026-09-14T03:00:00Z":null,latest_success_at:i<3?"2026-09-14T05:55:00Z":null,source_published_at:null,next_request_at:"2026-09-14T06:05:00Z"},
}))};
data.items.find(i=>i.id==="commute").channels=["trip_updates","service_alerts"].map(id=>({id,collector:"credentials_required",access:{state:"missing",expires_at:null},acquisition:{...data.items[6].acquisition}}));
async function wait(check,message){for(let i=0;i<200;i++){if(await Promise.resolve().then(check).catch(()=>false))return;await sleep(100);}throw Error(message);}
const body=()=>evaluate(cdp,"document.body.innerText");
async function navigate(path="/admin/monitoring-sources") {await cdp.send("Page.navigate",{url:base+path});}
async function reload(){await evaluate(cdp,"document.querySelector('[data-monitoring-source-operations] header button').click()");}
try {
  await wait(async()=>(await fetch(base)).ok,"Next did not start");
  let debugPort; await wait(async()=>{debugPort=(await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0];return !!debugPort;},"Chrome did not start");
  const target=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());
  cdp=new Cdp(target.webSocketDebuggerUrl);await cdp.send("Page.enable");await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown",({exceptionDetails})=>exceptions.push(exceptionDetails.text));
  cdp.on("Fetch.requestPaused",async({requestId,request})=>{
    const path=new URL(request.url).pathname;let code=200,result={};
    if(request.method!=="GET")mutations.push(path);
    if(path==="/api/auth/session")result={authenticated:true,user:{id:"ops-user",name:"Source QA",email:"qa@example.invalid",locale},organization:{id:"qa-org",name:"Source QA"},role:"organization_admin",platform_admin:admin,onboarding_required:false};
    else if(path==="/api/health")result={status:"ok",database:"synthetic",apertus:{configured:false},firecrawl:{configured:false}};
    else if(path==="/api/admin/monitoring-sources"){readCount++;code=status;result=status===200?data:{code:status===403?"platform_admin_required":"unavailable"};await sleep(100);}
    else if(path==="/api/jobs")result=[];
    else {code=503;result={code:"unavailable"};}
    await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"Content-Type",value:"application/json"},{name:"Cache-Control",value:"no-store"}],body:Buffer.from(JSON.stringify(result)).toString("base64")}).catch(()=>{});
  });
  await cdp.send("Fetch.enable",{patterns:[{urlPattern:`${base}/api/*`,requestStage:"Request"}]});
  for(const language of Object.keys(sourceOperationsCopy)){
    locale=language;await cdp.send("Emulation.setDeviceMetricsOverride",{width:language==="en-CH"?1280:390,height:900,deviceScaleFactor:1,mobile:false});
    await navigate();await wait(()=>evaluate(cdp,"document.querySelectorAll('[data-source-direction]').length===9"),"All nine sources missing");
    assert.equal(await evaluate(cdp,"document.querySelectorAll('[data-source-pack]').length"),4);
    assert.ok((await body()).includes(sourceOperationsCopy[locale].channel_required));
    assert.ok((await body()).includes(sourceOperationsCopy[locale].unknown));
    assert.ok((await body()).includes(sourceOperationsCopy[locale].expired));
    assert.ok((await body()).includes(sourceOperationsCopy[locale].revoked));
    assert.equal(await evaluate(cdp,"document.documentElement.scrollWidth<=innerWidth+1"),true,`Overflow ${locale}`);
    await audit.check(cdp,`sources-${locale}`,"[data-monitoring-source-operations]");
  }
  const count=readCount;await evaluate(cdp,"document.querySelector('[data-monitoring-source-operations] header button').focus()");
  await cdp.send("Input.dispatchKeyEvent",{type:"keyDown",key:"Enter",code:"Enter",windowsVirtualKeyCode:13,text:"\r"});
  await cdp.send("Input.dispatchKeyEvent",{type:"keyUp",key:"Enter",code:"Enter",windowsVirtualKeyCode:13});
  await wait(()=>readCount>count,"Keyboard reload did not read");
  status=503;await reload();await wait(async()=>(await body()).includes(sourceOperationsCopy[locale].failed),"Failure missing");
  assert.equal(await evaluate(cdp,"document.querySelectorAll('[data-source-direction]').length"),0);
  status=200;await reload();await wait(()=>evaluate(cdp,"document.querySelectorAll('[data-source-direction]').length===9"),"Recovery missing");
  status=403;await reload();await wait(async()=>(await body()).includes(sourceOperationsCopy[locale].failed),"Revocation not surfaced");
  assert.ok(!(await body()).includes("fixture-release"));
  admin=false;const beforeDenied=readCount;await navigate();await wait(async()=>(await body()).includes(sourceOperationsCopy[locale].denied),"Non-admin denial missing");
  assert.equal(readCount,beforeDenied);assert.equal(await evaluate(cdp,"document.querySelectorAll('[data-source-direction]').length"),0);
  await audit.check(cdp,"access-denied","[data-monitoring-source-operations]");
  admin=true;status=200;await navigate("/admin");await wait(()=>evaluate(cdp,"!!document.querySelector('a[href=\"/admin/monitoring-sources\"]')"),"Admin entry link missing");
  // The shared shell initializes Marvin context independently of this reader.
  // No source/settings/monitor mutation is allowed by the diagnostic journey.
  assert.ok(mutations.every(path=>["/api/assistant/context","/api/assistant/conversations"].includes(path)));
  assert.deepEqual(exceptions,[]);audit.finish(6);
  console.log("Source operations: nine directions/four packs, five locales/mobile, keyboard reload, error recovery, revoked/non-admin redaction and admin navigation passed.");
} finally {
  cdp?.close();for(const child of [browser,server]){const stopped=new Promise(done=>child.once("exit",done));child.kill();await Promise.race([stopped,sleep(2000)]);}
  assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith("helvetic-source-ops-qa-"));
  await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
