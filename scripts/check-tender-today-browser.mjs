// Local built product and synthetic responses; no provider/account/decision writes.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { stripTypeScriptTypes } from "node:module";
import { pathToFileURL } from "node:url";
import { tenderTodayCopy } from "../apps/web/lib/tender-today-copy.ts";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
const root=resolve(import.meta.dirname,"..");
const copy=(await readFile(join(root,"apps/web/lib/tender-copy.ts"),"utf8")).replace('"./river-copy"',JSON.stringify(pathToFileURL(join(root,"apps/web/lib/river-copy.ts")).href));
const {tenderCopy,simapNotice}=await import("data:text/javascript;base64,"+Buffer.from(stripTypeScriptTypes(copy)).toString("base64"));
const chrome=[process.env.CHROME_BIN,"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe","/usr/bin/google-chrome"].filter(Boolean).find(existsSync);assert.ok(chrome);
const reserve=createServer();await new Promise(done=>reserve.listen(0,"127.0.0.1",done));const port=reserve.address().port;await new Promise(done=>reserve.close(done));const base=`http://127.0.0.1:${port}`;
const server=spawn(process.execPath,[join(root,"node_modules/next/dist/bin/next"),"start","-H","127.0.0.1","-p",String(port)],{cwd:join(root,"apps/web"),stdio:"ignore",windowsHide:true});
const profile=await mkdtemp(join(tmpdir(),"helvetic-tender-today-qa-"));
const browser=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{stdio:"ignore",windowsHide:true});
let cdp,locale="en-CH",role="organization_admin",status=200,reads=0,empty=false;
const exceptions=[],mutations=[],requests=[];const audit=new AccessibilityAudit("tender-today");
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,"0")}`;
const entries=[1,2,3].map(n=>({id:id(n),monitor_id:id(10+n),monitor_name:"Private profile "+n,monitor_status:n===2?"paused":"active",sequence:2,version:4,
  following:n!==1,review_state:n===1?"new":n===2?"needs_review":"reviewed",decision:n===1?null:"bid",reviewed_sequence:n===1?null:1,
  summary:{title:{en:"Saved tender "+n,de:"Gespeicherte Ausschreibung "+n,fr:"Appel d’offres conservé "+n,it:"Gara conservata "+n},title_truncated:false,phase:"open",deadline:{utc:n===2?null:"2026-09-27T10:00:00Z",status:n===2?"unknown":"known"},verdict:"needs_review",match_scope:n===2?"project_context":"lot"},
  evidence_version_id:id(20+n),profile_revision:1,current_profile_revision:n===2?2:1,observed_at:"2026-09-14T12:00:00Z",href:`/tender-watch?monitor=${id(10+n)}&dossier=${id(n)}&version=${id(20+n)}`}));
async function wait(check,message){for(let i=0;i<200;i++){if(await Promise.resolve().then(check).catch(()=>false))return;await sleep(100);}throw Error(message);}
const text=()=>evaluate(cdp,"document.querySelector('[data-tender-today]')?.innerText||''");
async function ready(){await wait(()=>evaluate(cdp,"document.querySelector('[data-tender-today]')?.getAttribute('aria-busy')==='false'&&!!document.querySelector('[data-tender-pending]')"),"Tender queue not ready");}
async function navigate(path="/"){await cdp.send("Page.navigate",{url:base+path});await ready();}
async function button(label){const q=`[...document.querySelectorAll('[data-tender-today] button')].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled)`;await wait(()=>evaluate(cdp,`!!(${q})`),`Missing button ${label}`);await evaluate(cdp,`(${q}).click()`);}
async function filter(value){await evaluate(cdp,`(()=>{const e=document.querySelector('[data-tender-today] select');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('change',{bubbles:true}));})()`);await ready();}
try {
  await wait(async()=>(await fetch(base)).ok,"Next did not start");let debugPort;
  await wait(async()=>{debugPort=(await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0];return !!debugPort;},"Chrome did not start");
  const target=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());cdp=new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");await cdp.send("Runtime.enable");cdp.on("Runtime.exceptionThrown",({exceptionDetails})=>exceptions.push(exceptionDetails.text));
  cdp.on("Fetch.requestPaused",async({requestId,request})=>{
    const url=new URL(request.url),path=url.pathname;let code=200,result={};
    if(path.startsWith("/api/tender-watch")&&request.method!=="GET")mutations.push(path);
    if(path==="/api/auth/session")result={authenticated:true,user:{id:"qa-tender",name:"Tender QA",email:"qa@example.invalid",locale},organization:{id:"qa-org",name:"Tender QA"},role,platform_admin:false,onboarding_required:false};
    else if(path==="/api/health")result={status:"ok",database:"synthetic",apertus:{configured:false},firecrawl:{configured:false}};
    else if(path==="/api/jobs")result=[];
    else if(path==="/api/tender-watch/today"){
      reads++;requests.push(Object.fromEntries(url.searchParams));code=status;
      const following=url.searchParams.get("following")==="true",state=url.searchParams.get("review_state"),offset=url.searchParams.has("after_version")?2:0;
      const all=(empty?[]:entries).filter(e=>!following||e.following),list=all.filter(e=>!state||(state==="pending"?e.review_state!=="reviewed":e.review_state===state));
      result=status===200?{items:list.slice(offset,offset+2),pending_count:all.filter(e=>e.review_state!=="reviewed").length,next_cursor:list.length>offset+2?id(22):null}:{code:status===403?"membership_required":"unavailable"};await sleep(80);
    } else if(path==="/api/interest-feed")result={items:[],next_cursor:null,has_more:false,scanned_event_count:0};
    else if(path==="/api/impact-inbox")result={items:[],next_cursor:null};
    else if(path.endsWith("/today"))result={items:[],next_cursor:null,next:null,unreviewed_count:0};
    else {code=503;result={code:"unavailable"};}
    await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"Content-Type",value:"application/json"},{name:"Cache-Control",value:"no-store"}],body:Buffer.from(JSON.stringify(result)).toString("base64")}).catch(()=>{});
  });
  await cdp.send("Fetch.enable",{patterns:[{urlPattern:`${base}/api/*`,requestStage:"Request"}]});
  for(const language of Object.keys(tenderTodayCopy)){
    locale=language;await cdp.send("Emulation.setDeviceMetricsOverride",{width:language==="en-CH"?1280:390,height:900,deviceScaleFactor:1,mobile:false});await navigate();
    const c=tenderCopy[locale];for(const label of [tenderTodayCopy[locale].title,c.retained,c.profileOld,c.projectContext,c.noDeadline,simapNotice[locale]])assert.ok((await text()).includes(label),`Missing ${label}`);
    assert.equal(await evaluate(cdp,"document.documentElement.scrollWidth<=innerWidth+1"),true,`Overflow ${locale}`);
    assert.equal(await evaluate(cdp,"document.querySelector('[data-tender-today-entry] a').getAttribute('href')"),entries[0].href);
    await audit.check(cdp,`populated-${locale}`,"[data-tender-today]");
  }
  locale="en-CH";await navigate();const c=tenderCopy[locale],t=tenderTodayCopy[locale];
  await button(t.next);await ready();assert.ok((await text()).includes("Saved tender 3"));assert.ok(!(await text()).includes("Saved tender 1"));
  await button(t.previous);await ready();assert.ok((await text()).includes("Saved tender 1"));
  await filter("needs_review");assert.ok((await text()).includes("Saved tender 2"));assert.ok(!(await text()).includes("Saved tender 1"));
  await filter("");await evaluate(cdp,"document.querySelector('[data-tender-today] input').click()");await ready();assert.ok(!(await text()).includes("Saved tender 1"));assert.equal(requests.at(-1).following,"true");
  const count=reads;await evaluate(cdp,`[...document.querySelectorAll('[data-tender-today] button')].find(b=>b.textContent.trim()===${JSON.stringify(c.refresh)}).focus()`);
  await cdp.send("Input.dispatchKeyEvent",{type:"keyDown",key:"Enter",code:"Enter",windowsVirtualKeyCode:13,text:"\r"});await cdp.send("Input.dispatchKeyEvent",{type:"keyUp",key:"Enter",code:"Enter",windowsVirtualKeyCode:13});await wait(()=>reads>count,"Keyboard refresh missing");await ready();
  status=503;await button(c.refresh);await wait(async()=>(await text()).includes(c.failed),"Failure missing");assert.ok(!(await text()).includes("Saved tender"));
  status=200;await button(c.refresh);await ready();status=403;await button(c.refresh);await wait(async()=>(await text()).includes(c.failed),"Revocation missing");assert.ok(!(await text()).includes("Private profile"));
  status=200;role="viewer";await navigate();await audit.check(cdp,"viewer","[data-tender-today]");
  await evaluate(cdp,"window.dispatchEvent(new PageTransitionEvent('pagehide'))");assert.ok(!(await text()).includes("Saved tender"));
  await evaluate(cdp,"window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))");await ready();
  await evaluate(cdp,"document.querySelector('[data-tender-today-entry] a').click()");await wait(()=>evaluate(cdp,`location.pathname==='/tender-watch'&&new URLSearchParams(location.search).get('version')===${JSON.stringify(id(21))}`),"Exact-version navigation missing");
  role="organization_admin";await navigate("/impact");assert.equal(requests.at(-1).review_state,"pending");await audit.check(cdp,"inbox","[data-tender-today]");
  empty=true;await button(c.refresh);await ready();assert.ok((await text()).includes(c.none));await audit.check(cdp,"empty","[data-tender-today]");
  assert.deepEqual(mutations,[]);assert.deepEqual(exceptions,[]);audit.finish(8);
  console.log("Tender Today/Inbox: five locales/mobile, public source notice, pending/following filters, paging, exact version navigation, keyboard, viewer, recovery and access/page-return redaction passed.");
} finally {
  cdp?.close();for(const child of [browser,server]){const stopped=new Promise(done=>child.once("exit",done));child.kill();await Promise.race([stopped,sleep(2000)]);}
  assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith("helvetic-tender-today-qa-"));await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
