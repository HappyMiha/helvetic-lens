// Real built Today, synthetic APIs. No production account or source mutations.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { todayCountsCopy } from "../apps/web/lib/today-counts-copy.ts";
import { riverCopy } from "../apps/web/lib/river-copy.ts";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";

const root = resolve(import.meta.dirname, "..");
const chrome = [process.env.CHROME_BIN, "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "/usr/bin/google-chrome"].filter(Boolean).find(existsSync);
assert.ok(chrome);
const reserve = createServer();
await new Promise(done => reserve.listen(0, "127.0.0.1", done));
const port = reserve.address().port;
await new Promise(done => reserve.close(done));
const base = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, [join(root, "node_modules/next/dist/bin/next"), "start", "-H", "127.0.0.1", "-p", String(port)], {cwd: join(root, "apps/web"), stdio: "ignore", windowsHide: true});
const profile = await mkdtemp(join(tmpdir(), "helvetic-today-counts-"));
const browser = spawn(chrome, ["--headless=new", "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], {stdio: "ignore", windowsHide: true});
const selector = '[data-testid="today-review-counts"]';
const domains = ["pollen", "air", "river", "tenders", "commute", "traffic", "warnings", "ip", "auctions", "legal"];
const clock = "2026-09-14T12:00:00Z";
let cdp, locale = "en-CH", status = 200, mode = "full", reads = 0, reviewed = false, user = "qa-a", hold = false;
const held = [], exceptions = [], mutations = [];
const audit = new AccessibilityAudit("today-counts");
const counts = () => ({items: domains.map(domain => ({domain, count: mode === "incomplete" && domain === "ip" ? null : mode === "empty" ? 0 : domain === "river" ? Number(!reviewed) : 6, state: mode === "incomplete" && domain === "ip" ? "incomplete" : "complete"})),
  total: mode === "incomplete" ? null : mode === "empty" ? 0 : 54 + Number(!reviewed), state: mode === "incomplete" ? "incomplete" : "complete", evaluated_at: clock});
const sample = {metric:"W",value:"244.9",unit:"m",timestamp:clock,quality:"provisional",datum:"FOEN:2289:m ü.M.",aggregation:"10min_mean",source:"FOEN",source_url:"https://data.bafu.admin.ch/dataproduct-water-observations"};
const river = () => ({id:"00000000-0000-4000-8000-000000000001",development_id:"00000000-0000-4000-8000-000000000002",monitor_id:"00000000-0000-4000-8000-000000000003",sequence:1,revision:1,review_version:Number(reviewed),decision:reviewed?"reviewed":null,created_at:clock,kind:"threshold_crossed",priority:2,monitor_name:"Synthetic private Rhine",monitor_status:"active",current_configuration:true,sample_state:"recent",href:"/river-watch?monitor=synthetic",evidence:{sample,baseline:{...sample,value:"244.7"},rule:{metric:"W",kind:"absolute",threshold:"244.8",unit:"m",window_minutes:null},evaluated_value:"244.9",station_id:"2289",corrected:false,recovered:false}});
async function wait(check, message) { for(let i=0;i<200;i++){if(await Promise.resolve().then(check).catch(()=>false)) return; await sleep(100);} throw Error(message); }
const text = () => evaluate(cdp, `document.querySelector(${JSON.stringify(selector)})?.innerText || ''`);
const ready = () => wait(() => evaluate(cdp, `document.querySelector(${JSON.stringify(selector)})?.getAttribute('aria-busy') === 'false'`), "Counts not ready");
async function respond(requestId, body, code=200) {
  await cdp.send("Fetch.fulfillRequest", {requestId,responseCode:code,responseHeaders:[{name:"Content-Type",value:"application/json"},{name:"Cache-Control",value:"no-store"}],body:Buffer.from(JSON.stringify(body)).toString("base64")}).catch(()=>{});
}
async function refresh(keyboard=false) {
  const before = reads;
  await evaluate(cdp, `document.querySelector(${JSON.stringify(selector + " button")}).focus()`);
  if(keyboard) for(const type of ["keyDown","keyUp"]) await cdp.send("Input.dispatchKeyEvent", {type,key:"Enter",code:"Enter",windowsVirtualKeyCode:13,...(type==="keyDown"?{text:"\r"}:{})});
  else await evaluate(cdp, `document.querySelector(${JSON.stringify(selector + " button")}).click()`);
  await wait(()=>reads>before,"No refresh request"); await ready();
}
async function check(name) {
  assert.ok(await evaluate(cdp,"document.documentElement.scrollWidth <= innerWidth + 1"), "Page overflow");
  await audit.check(cdp,name,selector);
}
try {
  await wait(async()=>(await fetch(base)).ok,"Next did not start");
  let debugPort;
  await wait(async()=>{debugPort=(await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0];return !!debugPort;},"Chrome did not start");
  const target=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());
  cdp=new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable"); await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown",({exceptionDetails})=>exceptions.push(exceptionDetails.exception?.description || exceptionDetails.text));
  cdp.on("Fetch.requestPaused",async({requestId,request})=>{
    const path=new URL(request.url).pathname; let code=200,body={};
    if(path==="/api/auth/session") body={authenticated:true,user:{id:user,name:user,email:`${user}@example.invalid`,locale},organization:{id:"qa-org",name:"Counts QA"},role:"organization_admin",platform_admin:false,onboarding_required:false};
    else if(path==="/api/health") body={status:"ok",database:"synthetic",apertus:{configured:false},firecrawl:{configured:false}};
    else if(path==="/api/jobs") body=[];
    else if(path==="/api/monitoring-centre/today-counts") {reads++;code=status;body=code===200?counts():{code:"unavailable"};if(hold){held.push({requestId,body,code});return;}}
    else if(path==="/api/river-watch/today") body={items:[river()],unreviewed_count:Number(!reviewed),next:null};
    else if(path.startsWith("/api/river-watch/monitors/")&&path.endsWith("/review")) {mutations.push(JSON.parse(request.postData));reviewed=true;body=river();}
    else if(path==="/api/interest-feed") body={items:[],next_cursor:null,has_more:false,scanned_event_count:0};
    else if(path.endsWith("/today")) body={items:[],next_cursor:null,next:null};
    else {code=503;body={code:"unavailable"};}
    await respond(requestId,body,code);
  });
  await cdp.send("Fetch.enable",{patterns:[{urlPattern:`${base}/api/*`,requestStage:"Request"}]});
  for (const language of Object.keys(todayCountsCopy)) {
    locale=language; mode="full"; status=200; reviewed=false;
    await cdp.send("Emulation.setDeviceMetricsOverride",{width:locale==="en-CH"?1280:390,height:950,deviceScaleFactor:1,mobile:false});
    await cdp.send("Page.navigate",{url:base+"/"}); await ready();
    const copy=todayCountsCopy[locale];
    assert.ok((await text()).includes(copy.title));assert.ok((await text()).includes(copy.total+": 55"));
    assert.equal(await evaluate(cdp,`document.querySelectorAll(${JSON.stringify(selector + " [data-domain]")}).length`),10);
    const links=await evaluate(cdp,`[...document.querySelectorAll(${JSON.stringify(selector + " [data-domain]")})].map(e=>({id:e.dataset.domain,href:e.getAttribute('href')}))`);
    assert.deepEqual(new Set(links.map(l=>l.id)),new Set(domains));
    assert.ok(links.every(l=>l.href.startsWith('/') && !l.href.includes('undefined')));
    await check(`populated-${locale}`);
    mode="incomplete";await refresh();assert.ok((await text()).includes(copy.incomplete));
    assert.equal(await evaluate(cdp,"document.querySelector('[data-testid=today-review-total]')"),null);
    assert.ok((await text()).includes(copy.unavailable));await check(`incomplete-${locale}`);
    mode="empty";await refresh();assert.ok((await text()).includes(copy.empty));await check(`empty-${locale}`);
    status=503;await refresh();assert.ok((await text()).includes(copy.error));
    assert.equal(await evaluate(cdp,"document.querySelector('[data-testid=today-review-total]')"),null);
    await check(`failed-${locale}`);
  }
  locale="en-CH";status=200;mode="full";reviewed=false;
  await cdp.send("Page.navigate",{url:base+"/"});await ready();
  await refresh(true);assert.ok((await text()).includes("Total: 55"));
  const before=reads;
  await wait(()=>evaluate(cdp,`[...document.querySelectorAll('[data-river-today] button')].some(b=>b.textContent.trim()===${JSON.stringify(riverCopy[locale].reviewed)}&&!b.disabled)`),"Review button missing");
  await evaluate(cdp,`[...document.querySelectorAll('[data-river-today] button')].find(b=>b.textContent.trim()===${JSON.stringify(riverCopy[locale].reviewed)}&&!b.disabled).click()`);
  await wait(()=>reads>before,"Successful real review did not invalidate counts");await ready();
  assert.ok((await text()).includes("Total: 54"));assert.equal(mutations.length,1);await check("review-refresh");
  await evaluate(cdp, `document.querySelector(${JSON.stringify(selector + ' [data-domain="legal"]')}).click()`);
  await wait(()=>evaluate(cdp,"location.search === '?state=unread' && location.hash === '#legal-feed'"),"Legal queue link did not apply the unread filter");
  assert.ok((await text()).includes("Total: 54"));
  await evaluate(cdp,"scrollTo(0,0)");
  await writeFile(join(root,"test-results/today-counts-mobile.png"),Buffer.from((await cdp.send("Page.captureScreenshot",{format:"png"})).data,"base64"));
  await cdp.send("Emulation.setDeviceMetricsOverride",{width:1280,height:950,deviceScaleFactor:1,mobile:false});
  await evaluate(cdp,"scrollTo(0,0)");await writeFile(join(root,"test-results/today-counts-desktop.png"),Buffer.from((await cdp.send("Page.captureScreenshot",{format:"png"})).data,"base64"));
  // Abort a private old response before another account/page-return can render it.
  hold=true;const oldReads=reads;
  await evaluate(cdp,`document.querySelector(${JSON.stringify(selector + " button")}).click()`);
  await wait(()=>reads>oldReads,"Held refresh missing");
  assert.ok(!(await text()).includes("Total: 54"));
  await evaluate(cdp,"window.dispatchEvent(new PageTransitionEvent('pagehide'))");
  assert.equal(await text(),"");
  hold=false;user="qa-b";mode="empty";
  await cdp.send("Page.navigate",{url:base+"/"});await ready();
  for(const item of held) await respond(item.requestId,item.body,item.code);
  assert.ok((await text()).includes(todayCountsCopy[locale].empty));assert.ok(!(await text()).includes("Total: 54"));
  await check("private-return");
  assert.deepEqual(exceptions,[]);audit.finish(22);
  console.log("Today counts: 22 built-browser/axe checks passed. Five locales, all ten queues, incomplete/zero/error, keyboard, actual review refresh and stale private response suppression. Synthetic API evidence only.");
} catch(error) {
  console.error({locale,reads,status,mode,exceptions,text:cdp?await text().catch(()=>""):""});throw error;
} finally {
  cdp?.close();for(const child of [browser,server]){const stopped=new Promise(done=>child.once("exit",done));child.kill();await Promise.race([stopped,sleep(2000)]);}
  assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith("helvetic-today-counts-"));
  await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
