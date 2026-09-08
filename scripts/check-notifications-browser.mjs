// Real production UI with intercepted synthetic API responses. No live backend.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { createServer } from "node:net";
import { Cdp, evaluate, pollJson, sleep } from "./browser-cdp.mjs";

import { AccessibilityAudit } from "./browser-accessibility.mjs";
const accessibility = new AccessibilityAudit("notifications");
const root = resolve(import.meta.dirname, "..");
const chrome = [process.env.CHROME_BIN, "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "/usr/bin/google-chrome", "/usr/bin/chromium"].filter(Boolean).find(existsSync);
assert.ok(chrome, "A real Chrome executable is required.");
const reserve = createServer();
await new Promise(resolve => reserve.listen(0, "127.0.0.1", resolve));
const port = reserve.address().port;
await new Promise(resolve => reserve.close(resolve));
const base = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, [join(root, "node_modules/next/dist/bin/next"), "start", "-H", "127.0.0.1", "-p", String(port)], {
  cwd: join(root, "apps/web"), stdio: "ignore", windowsHide: true,
});
const profile = await mkdtemp(join(tmpdir(), "helvetic-notifications-browser-"));
const browser = spawn(chrome, ["--headless=new", "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore", windowsHide: true });
let cdp;
const requests = [], exceptions = [];
async function waitFor(check, message) {
  for (let i = 0; i < 150; i++) {
    if (await check().catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}
let locale="en-CH",role="viewer",user="qa",failure="",stateFailure=false;
const readStates=new Map();
const event = id => ({event_id:id,title:`Synthetic development ${id} — ${"A long multilingual regulatory heading ".repeat(3)}`,source:"Official synthetic source",detected_at:"2026-09-08T08:00:00Z"});
try {
  await waitFor(async () => (await fetch(base)).ok, "Isolated production UI failed to start");
  let debugPort;
  await waitFor(async () => { debugPort = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]; return !!debugPort; }, "Browser failed to start");
  await pollJson(`http://127.0.0.1:${debugPort}/json/version`);
  const target = await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: "PUT" }).then(response => response.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Page.addScriptToEvaluateOnNewDocument",{source:"window.__qaNotificationDocument = new URL(location.href).searchParams.get('qa');"});
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) => exceptions.push(exceptionDetails.exception?.description || exceptionDetails.text));

  cdp.on("Fetch.requestPaused", async ({requestId,request}) => {
    const url=new URL(request.url),path=url.pathname;
    requests.push({path,query:url.search,method:request.method,body:request.postData});
    let body={},code=200;
    if(path==="/api/auth/session") body={authenticated:true,user:{id:user,email:"qa@example.invalid",name:"QA",locale},organization:{id:"qa-org",name:"QA"},role};
    else if(path==="/api/health") body={status:"ok",database:"postgresql",apertus:{configured:false},firecrawl:{configured:false}};
    else if(["/api/laws","/api/scans","/api/jobs"].includes(path)) body=[];
    else if(path==="/api/interest-feed") {
      assert.equal(url.searchParams.get("limit"),"5");
      assert.equal(url.searchParams.get("state"),"unread");
      const cursor=url.searchParams.get("cursor")||"";
      if(failure===cursor || (failure==="first" && !cursor)) { failure="none";code=503;body={detail:"Synthetic notification read failure"}; }
      else {
        const ids=cursor==="older" ? ["old-event"] : cursor==="empty-batch" ? [] : cursor==="last" ? ["last-event"] : ["event-one","event-two"];
        body={items:ids.filter(id=>!readStates.has(user+id)).map(event),next_cursor:cursor==="older" ? "empty-batch" : cursor==="empty-batch" ? "last" : cursor==="last" ? null : "older"};
      }
    } else if(path.startsWith("/api/interest-feed/events/")) {
      assert.equal(request.method,"PATCH");
      const value=JSON.parse(request.postData);assert.ok(["read","dismissed"].includes(value.state));
      if(stateFailure){stateFailure=false;code=503;body={detail:"Synthetic state save failure"};}
      else {readStates.set(user+path.split('/').at(-2),value.state);body={state:value.state};}
    } else {code=503;body={detail:"Synthetic unrelated endpoint unavailable"};}
    await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"Content-Type",value:"application/json"}],body:Buffer.from(JSON.stringify(body)).toString("base64")}).catch(()=>{});
  });
  await cdp.send("Fetch.enable",{patterns:[{urlPattern:`${base}/api/*`,requestStage:"Request"}]});
  const click = async selector => {
    await evaluate(cdp, `new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))`);
    let point;
    await waitFor(async () => {
      point = await evaluate(cdp, `(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el || el.disabled)return null;el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect(), x=r.x+r.width/2,y=r.y+r.height/2;return {x,y,visible:el.contains(document.elementFromPoint(x,y))};})()`);
      return point?.visible;
    }, `Control not reachable by pointer: ${selector}`);
    for (const type of ["mousePressed", "mouseReleased"]) await cdp.send("Input.dispatchMouseEvent", {type, x:point.x, y:point.y, button: "left", clickCount: 1});
  };
  for(const language of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]) for(const width of [390,1440]) for(const viewerRole of ["viewer","organization_admin"]) {
    locale=language;role=viewerRole;user=`${locale}-${width}-${role}`;failure="first";
    await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:900,deviceScaleFactor:1,mobile:width<500});
    const before=requests.length;
    await cdp.send("Page.navigate",{url:`${base}/overview?locale=${locale}&qa=${user}`});
    await waitFor(()=>evaluate(cdp,`window.__qaNotificationDocument===${JSON.stringify(user)} && document.documentElement.lang===${JSON.stringify(locale)} && !!document.querySelector('[data-notifications-trigger]')`),"Notification entry missing");
    assert.equal(requests.slice(before).filter(r=>r.path==='/api/interest-feed').length,0,'Closed centre fetched feed');
    await click('[data-notifications-trigger]');
    await waitFor(()=>evaluate(cdp,`document.querySelector('[data-notification-centre]').innerText.includes('Synthetic notification read failure')`),'First-load error missing');
    await click('[data-notification-retry]');
    await waitFor(()=>evaluate(cdp,`document.querySelectorAll('[data-notification-event]').length===2`),'First page missing');
    assert.ok(await evaluate(cdp,`Array.from(document.querySelectorAll('[data-notification-centre] button')).every(b=>b.getBoundingClientRect().height>=44)`),'Small notification targets');
    assert.equal(await evaluate(cdp,`document.querySelector('[data-notification-event] a').getAttribute('href')`),'/?event=event-one');
    await evaluate(cdp,`document.querySelector('[data-notification-centre] button[data-slot=dialog-close]').focus()`);
    await cdp.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
    await cdp.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
    assert.ok(await evaluate(cdp,`!!document.activeElement.closest('[data-notification-centre]')`),'Dialog keyboard focus escaped');
    assert.ok(await evaluate(cdp,`!document.querySelector('.marvin-companion') || getComputedStyle(document.querySelector('.marvin-companion')).visibility==='hidden'`),'Marvin overlays notifications');
    if(width===390) assert.ok(await evaluate(cdp,`Number(getComputedStyle(document.querySelector('.mobile-nav')).zIndex)<Number(getComputedStyle(document.querySelector('[data-notification-centre]')).zIndex)`),'Mobile navigation overlays notifications');
    await accessibility.check(cdp,`notifications-${user}-first`,'[data-notification-centre]');
    failure="older";
    await click('[data-notification-next]');
    await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-notification-retry]')`),'Next-page failure missing');
    assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-notification-event]').length`),2,'Failed page erased records');
    await accessibility.check(cdp,`notifications-${user}-retry`,'[data-notification-centre]');
    await click('[data-notification-retry]');
    await waitFor(()=>evaluate(cdp,`document.querySelector('[data-notification-event] a')?.getAttribute('href')==='/?event=old-event'`),'Wrong retry page');
    const writesBefore=requests.filter(r=>r.method==='PATCH').length;
    await click('[data-notification-read]');
    await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-notification-empty]')`),'Read event did not leave unread list');
    assert.ok(await evaluate(cdp,`document.activeElement===document.querySelector('[data-notification-list] p[tabindex]')`),'Successful state change lost keyboard focus');
    assert.equal(requests.filter(r=>r.method==='PATCH').length,writesBefore+1,'Reading wrote more than once');
    await click('[data-notification-next]');
    await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-notification-empty]') && !document.querySelector('[data-notification-back]').disabled && document.querySelector('[data-notification-list]').getAttribute('aria-busy')==='false'`),'Sparse page missing');
    assert.ok(await evaluate(cdp,`!document.querySelector('[data-notification-next]').disabled`),'Sparse batch falsely ended notifications');
    await click('[data-notification-next]');
    await waitFor(()=>evaluate(cdp,`document.querySelector('[data-notification-event] a')?.getAttribute('href')==='/?event=last-event'`),'Continuation skipped older event');
    assert.ok(await evaluate(cdp,`document.querySelector('[data-notification-next]').disabled`));
    await click('[data-notification-back]');
    await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-notification-empty]') && document.querySelector('[data-notification-list]').getAttribute('aria-busy')==='false'`),'Back did not restore sparse page');
    await click('[data-notification-next]');
    await waitFor(()=>evaluate(cdp,`document.querySelector('[data-notification-event] a')?.getAttribute('href')==='/?event=last-event'`),'Forward after Back lost cursor');
    await accessibility.check(cdp,`notifications-${user}-last`,'[data-notification-centre]');
    stateFailure=true;
    await click('[data-notification-dismiss]');
    await waitFor(()=>evaluate(cdp,`document.querySelector('[data-notification-centre]').innerText.includes('Synthetic state save failure')`),'State error hidden');
    assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-notification-event]').length`),1,'Failed mutation hid record');
    await click('[data-notification-retry]');
    await waitFor(()=>evaluate(cdp,`!document.querySelector('[data-notification-retry]')`),'State recovery failed');
    await click('[data-notification-dismiss]');
    await waitFor(()=>evaluate(cdp,`document.querySelectorAll('[data-notification-event]').length===0`),'Dismissal not reflected');
    await accessibility.check(cdp,`notifications-${user}-empty`,'[data-notification-centre]');
    assert.ok(await evaluate(cdp,`document.documentElement.scrollWidth<=innerWidth+1`),'Header/dialog overflow');
    await cdp.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await cdp.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await waitFor(()=>evaluate(cdp,`!document.querySelector('[data-notification-centre]') && document.activeElement.matches('[data-notifications-trigger]')`),'Close did not return focus');
    await click('[data-notifications-trigger]');
    await waitFor(()=>evaluate(cdp,`document.querySelectorAll('[data-notification-event]').length===2`),'Reopen failed');
    await click('[data-notification-next]');
    await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-notification-empty]')`),'Saved read state did not persist after reopen');
    if(locale==='en-CH' && role==='viewer') {
      await click('[data-notification-latest]');
      await waitFor(()=>evaluate(cdp,`document.querySelectorAll('[data-notification-event]').length===2`),'Latest page missing');
      await mkdir(join(root,'test-results/notifications'),{recursive:true});
      const shot=await cdp.send('Page.captureScreenshot',{format:'png'});
      await writeFile(join(root,'test-results/notifications',`${width}.png`),Buffer.from(shot.data,'base64'));
    }
  }
  assert.deepEqual(requests.filter(r=>r.method!=='GET' && !r.path.startsWith('/api/assistant/') && !r.path.startsWith('/api/interest-feed/events/')),[]);
  assert.deepEqual(exceptions,[]);
  await accessibility.finish(80);
  console.log('20 notification journeys pass: five languages, mobile/desktop, viewer/admin, errors/retry, sparse continuation, personal read/dismiss state, pointer targets and close focus. APIs intercepted; no inference or real data writes.');
} catch (error) {
  console.error({locale,role,user,requests:requests.slice(-12),exceptions,text:cdp ? await evaluate(cdp,'document.body.innerText.slice(-2400)').catch(()=> 'unavailable') : 'none'});
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const ended = new Promise(resolve => child.once("exit", resolve));
    child.kill();
    await Promise.race([ended, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-notifications-browser-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
