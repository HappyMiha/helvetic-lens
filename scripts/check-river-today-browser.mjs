// Owned local production build, synthetic identity/source evidence and review API.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { riverCopy } from "../apps/web/lib/river-copy.ts";
import { riverTodayCopy } from "../apps/web/lib/river-today-copy.ts";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";

const root=resolve(import.meta.dirname,"..");
const chrome=[process.env.CHROME_BIN,"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe","/usr/bin/google-chrome"].filter(Boolean).find(existsSync);
assert.ok(chrome);
const reserve=createServer();await new Promise(done=>reserve.listen(0,"127.0.0.1",done));
const port=reserve.address().port;await new Promise(done=>reserve.close(done));const base=`http://127.0.0.1:${port}`;
const server=spawn(process.execPath,[join(root,"node_modules/next/dist/bin/next"),"start","-H","127.0.0.1","-p",String(port)],{cwd:join(root,"apps/web"),stdio:"ignore",windowsHide:true});
const profile=await mkdtemp(join(tmpdir(),"helvetic-river-today-qa-"));
const browser=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{stdio:"ignore",windowsHide:true});
let cdp,locale="en-CH",role="organization_admin",status=200,reviewStatus=200,reads=0;
const exceptions=[],mutations=[],requests=[];const audit=new AccessibilityAudit("river-today");
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,"0")}`;
const monitor=id(10),clock="2026-09-14T12:00:00Z";
const sample={metric:"W",value:"244.9",unit:"m",timestamp:clock,quality:"provisional",datum:"FOEN:2289:m ü.M.",aggregation:"10min_mean",source:"FOEN",source_url:"https://data.bafu.admin.ch/dataproduct-water-observations"};
let entries=[];
function reset(){entries=[1,2,3].map((n)=>({id:id(n),development_id:id(n+20),sequence:n,revision:1,review_version:0,decision:null,created_at:clock,
  kind:n===2?"danger_escalation":"threshold_crossed",priority:n===2?1:2,monitor_id:monitor,monitor_name:"Private Rhine "+n,monitor_status:n===2?"paused":"active",
  current_configuration:n!==2,sample_state:n===2?"stale":"recent",href:`/river-watch?monitor=${monitor}&change=${id(n)}`,
  evidence:{sample:n===2?{...sample,metric:"danger",value:"3",unit:"official_level",datum:null}:sample,baseline:n===2?null:{...sample,value:"244.7"},
    rule:n===2?null:{metric:"W",kind:"absolute",threshold:"244.8",unit:"m",window_minutes:null},evaluated_value:"244.9",station_id:"2289",corrected:n===1,recovered:n===2}}));}
reset();
async function wait(check,message){for(let i=0;i<200;i++){if(await Promise.resolve().then(check).catch(()=>false))return;await sleep(100);}throw Error(message);}
const text=()=>evaluate(cdp,"document.querySelector('[data-river-today]')?.innerText||''");
async function ready(){await wait(()=>evaluate(cdp,"document.querySelector('[data-river-today]')?.getAttribute('aria-busy')==='false' && !!document.querySelector('[data-river-unreviewed]')"),"River feed not ready");}
async function navigate(path="/"){await cdp.send("Page.navigate",{url:base+path});await ready();}
async function button(label){const expression=`[...document.querySelectorAll('[data-river-today] button')].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled)`;await wait(()=>evaluate(cdp,`!!(${expression})`),`Button missing ${label}`);await evaluate(cdp,`(${expression}).click()`);}
try {
  await wait(async()=>(await fetch(base)).ok,"Next did not start");let debugPort;
  await wait(async()=>{debugPort=(await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0];return !!debugPort;},"Chrome did not start");
  const target=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());
  cdp=new Cdp(target.webSocketDebuggerUrl);await cdp.send("Page.enable");await cdp.send("Runtime.enable");
  await cdp.send("Network.setCookie",{name:"helvetic_lens_csrf",value:"synthetic-river-today",url:base});
  cdp.on("Runtime.exceptionThrown",({exceptionDetails})=>exceptions.push(exceptionDetails.text));
  cdp.on("Fetch.requestPaused",async({requestId,request})=>{
    const url=new URL(request.url),path=url.pathname;let code=200,result={};
    if(path==="/api/auth/session")result={authenticated:true,user:{id:"qa-river",name:"River QA",email:"qa@example.invalid",locale},organization:{id:"qa-org",name:"River QA"},role,platform_admin:false,onboarding_required:false};
    else if(path==="/api/health")result={status:"ok",database:"synthetic",apertus:{configured:false},firecrawl:{configured:false}};
    else if(path==="/api/jobs")result=[];
    else if(path==="/api/river-watch/today"){
      reads++;requests.push(url.searchParams.get("unreviewed"));code=status;
      const list=entries.filter(e=>url.searchParams.get("unreviewed")!=="true"||!e.decision),offset=url.searchParams.has("before")?2:0;
      result=status===200?{items:list.slice(offset,offset+2),unreviewed_count:entries.filter(e=>!e.decision).length,next:list.length>offset+2?{before:clock,before_id:id(2)}:null}:{code:status===403?"membership_required":"unavailable"};
      await sleep(80);
    } else if(path.startsWith("/api/river-watch/monitors/")&&path.endsWith("/review")){
      const body=JSON.parse(request.postData);mutations.push({path,body});code=reviewStatus;
      if(code===200){const entry=entries.find(e=>path.includes(e.id));assert.equal(body.expected_version,entry.review_version);entry.decision=body.decision;entry.review_version++;result=entry;}
      else result={code:code===409?"river_newer_change":"membership_required"};
    } else if(path==="/api/interest-feed")result={items:[],next_cursor:null,has_more:false,scanned_event_count:0};
    else if(path==="/api/impact-inbox")result={items:[],next_cursor:null};
    else if(path.endsWith("/today"))result={items:[],next_cursor:null,next:null};
    else {code=503;result={code:"unavailable"};}
    await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"Content-Type",value:"application/json"},{name:"Cache-Control",value:"no-store"}],body:Buffer.from(JSON.stringify(result)).toString("base64")}).catch(()=>{});
  });
  await cdp.send("Fetch.enable",{patterns:[{urlPattern:`${base}/api/*`,requestStage:"Request"}]});
  for(const language of Object.keys(riverTodayCopy)){
    locale=language;await cdp.send("Emulation.setDeviceMetricsOverride",{width:language==="en-CH"?1280:390,height:900,deviceScaleFactor:1,mobile:false});
    await navigate();const t=riverTodayCopy[locale],c=riverCopy[locale];
    for(const label of [t.title,t.historical,t.stale,t.baseline,t.corrected,c.recovered,c.danger_escalation,"244.9","244.7"])assert.ok((await text()).includes(label),`Missing ${label}`);
    assert.equal(await evaluate(cdp,"document.documentElement.scrollWidth<=innerWidth+1"),true,`Overflow ${locale}`);
    assert.equal(await evaluate(cdp,"document.querySelector('[data-river-today-entry] a').getAttribute('href')"),entries[0].href);
    await audit.check(cdp,`populated-${locale}`,"[data-river-today]");
  }
  locale="en-CH";await navigate();const t=riverTodayCopy[locale],c=riverCopy[locale];
  await button(t.next);await ready();assert.ok((await text()).includes("Private Rhine 3"));assert.ok(!(await text()).includes("Private Rhine 1"));
  await button(t.back);await ready();assert.ok((await text()).includes("Private Rhine 1"));
  const before=reads;await evaluate(cdp,`[...document.querySelectorAll('[data-river-today] button')].find(b=>b.textContent.trim()===${JSON.stringify(c.refresh)}).focus()`);
  await cdp.send("Input.dispatchKeyEvent",{type:"keyDown",key:"Enter",code:"Enter",windowsVirtualKeyCode:13,text:"\r"});await cdp.send("Input.dispatchKeyEvent",{type:"keyUp",key:"Enter",code:"Enter",windowsVirtualKeyCode:13});
  await wait(()=>reads>before,"Keyboard reload missing");await ready();
  await button(c.reviewed);await wait(()=>mutations.length===1,"Review missing");await ready();assert.equal(entries[0].decision,"reviewed");
  await evaluate(cdp,"document.querySelector('[data-river-today] input').click()");await ready();assert.ok(!(await text()).includes("Private Rhine 1"));
  reviewStatus=409;await button(c.not_relevant);await wait(async()=>(await text()).includes(c.conflict),"Revision conflict missing");await ready();assert.equal(entries[1].decision,null);
  status=503;await button(c.refresh);await wait(async()=>(await text()).includes(c.failed),"Failure missing");assert.ok(!(await text()).includes("Private Rhine"));
  status=200;await button(c.refresh);await ready();
  reviewStatus=403;await button(c.reviewed);await wait(async()=>(await text()).includes(c.failed),"Review revocation missing");assert.ok(!(await text()).includes("Private Rhine"));
  reviewStatus=200;role="viewer";reset();await navigate();
  assert.equal(await evaluate(cdp,`[...document.querySelectorAll('[data-river-today] button')].some(b=>[${JSON.stringify(c.reviewed)},${JSON.stringify(c.not_relevant)}].includes(b.textContent.trim()))`),false);
  await audit.check(cdp,"viewer","[data-river-today]");
  await evaluate(cdp,"window.dispatchEvent(new PageTransitionEvent('pagehide'))");assert.ok(!(await text()).includes("Private Rhine"));
  await evaluate(cdp,"window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))");await ready();
  status=403;await button(c.refresh);await wait(async()=>(await text()).includes(c.failed),"Read revocation missing");assert.ok(!(await text()).includes("Private Rhine"));
  status=200;role="organization_admin";await navigate("/impact");assert.equal(requests.at(-1),"true");
  await audit.check(cdp,"inbox","[data-river-today]");
  entries=[];await button(c.refresh);await ready();assert.ok((await text()).includes(t.empty));
  await audit.check(cdp,"empty","[data-river-today]");
  assert.deepEqual(exceptions,[]);assert.equal(mutations.length,3);audit.finish(8);
  console.log("River Today/Inbox: five locales, mobile, equal-page navigation, exact links, keyboard, review/conflict, viewer, page-return and access redaction passed.");
} finally {
  cdp?.close();for(const child of [browser,server]){const stopped=new Promise(done=>child.once("exit",done));child.kill();await Promise.race([stopped,sleep(2000)]);}
  assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith("helvetic-river-today-qa-"));
  await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
