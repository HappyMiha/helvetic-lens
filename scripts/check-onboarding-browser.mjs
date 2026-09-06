// Real production UI with intercepted synthetic API responses. No live backend.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { createServer } from "node:net";
import { Cdp, evaluate, pollJson, sleep } from "./browser-cdp.mjs";

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
const profile = await mkdtemp(join(tmpdir(), "helvetic-onboarding-browser-"));
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
let locale = "en-CH", role = "organization_admin", user = "qa", state, failSave = false;
function fresh(available = false) { return {state: "new", intent: null, started_at: null, deferred_at: null, updated_at: null, visibility: "personal", completion_verified: false, milestones: [], organization_setup: {source_package_enabled: available, active_document_watch: available, active_topic: false}}; }
try {
  await waitFor(async () => (await fetch(base)).ok, "Isolated production UI failed to start");
  let debugPort;
  await waitFor(async () => { debugPort = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]; return !!debugPort; }, "Browser failed to start");
  await pollJson(`http://127.0.0.1:${debugPort}/json/version`);
  const target = await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: "PUT" }).then(response => response.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) => exceptions.push(exceptionDetails.exception?.description || exceptionDetails.text));

  cdp.on("Fetch.requestPaused", async ({requestId, request}) => {
    const url = new URL(request.url);
    const payload = request.postData ? JSON.parse(request.postData) : null;
    requests.push({path: url.pathname, method: request.method, body: payload});
    let body = {}, code = 200;
    if (url.pathname === "/api/auth/session") body = {authenticated:true, user:{id:user,email:"qa@example.invalid",name:"QA",locale}, organization:{id:"qa-org",name:"QA"},role};
    else if (url.pathname === "/api/health") body = {status:"ok",database:"postgresql",apertus:{configured:false},firecrawl:{configured:false}};
    else if (url.pathname === "/api/onboarding") {
      if (request.method === "PATCH") {
        if (failSave) {code=503; body={detail:"Synthetic save unavailable"};}
        else { const {action} = payload; assert.deepEqual(Object.keys(payload), ["action"]);
          state = {...state,state: action === "later" ? "deferred" : "started",intent: action === "later" ? state.intent : action}; body=state; }
      } else body=state;
    } else if (["/api/jobs","/api/scans","/api/sources","/api/laws","/api/monitoring-topics"].includes(url.pathname)) body=[];
    else {code=503;body={detail:"Synthetic endpoint unavailable"};}
    await cdp.send("Fetch.fulfillRequest", {requestId,responseCode:code,responseHeaders:[{name:"Content-Type",value:"application/json"}],body:Buffer.from(JSON.stringify(body)).toString("base64")}).catch(()=>{});
  });
  await cdp.send("Fetch.enable", {patterns:[{urlPattern:`${base}/api/*`,requestStage:"Request"}]});
  const click = async selector => {
    await evaluate(cdp, `new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))`);
    const point = await evaluate(cdp, `(()=>{const el=document.querySelector(${JSON.stringify(selector)});el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect(), x=r.x+r.width/2,y=r.y+r.height/2;return {x,y,visible:el.contains(document.elementFromPoint(x,y))};})()`);
    assert.ok(point.visible, `Control not reachable by pointer: ${selector}`);
    for (const type of ["mousePressed", "mouseReleased"]) await cdp.send("Input.dispatchMouseEvent", {type, x:point.x, y:point.y, button: "left", clickCount: 1});
  };
  const changes = () => requests.filter(r => !["GET", "HEAD"].includes(r.method) && !r.path.startsWith("/api/assistant/"));
  async function open() {
    await cdp.send("Page.navigate", {url:`${base}/onboarding?locale=${locale}`});
    await waitFor(()=>evaluate(cdp, `document.querySelectorAll('[data-onboarding-choice]').length === 3 && document.documentElement.lang === ${JSON.stringify(locale)}`), "Guide not loaded");
    assert.ok(await evaluate(cdp, `document.documentElement.scrollWidth <= innerWidth + 1`), "Guide overflows viewport");
    assert.ok(await evaluate(cdp, `!document.querySelector('[data-onboarding-guide]').innerText.includes('gettingStarted.')`), "Untranslated guide key");
  }
  for (const language of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]) for (const width of [390,1440]) for (const permission of ["organization_admin","viewer"]) {
    locale=language;role=permission;user=`${language}-${width}-${permission}`;state=fresh(permission === "viewer");
    await cdp.send("Emulation.setDeviceMetricsOverride", {width,height:900,deviceScaleFactor:1,mobile:width<500});
    let before=changes().length;
    await open();
    assert.equal(changes().length,before,"Opening guide mutated shared or personal data");
    assert.ok(await evaluate(cdp, `document.querySelector('[data-onboarding-guide] a[href="/sources#source-packs"]') !== null`));
    assert.equal(await evaluate(cdp, `document.querySelectorAll('[data-milestone-recorded]').length`),0);
    state={...state,milestones:["interest_saved","notifications_saved","evidence_displayed"].map(kind=>({kind,object_kind:"test",recorded_at:"2026-09-06T10:00:00Z"}))};
    await open();
    assert.equal(await evaluate(cdp, `document.querySelectorAll('[data-milestone-recorded]').length`),3);
    assert.ok(await evaluate(cdp, `!document.querySelector('[data-onboarding-milestones]').innerText.includes('onboardingProgress.')`));
    assert.equal(changes().length,before,"Reading recorded milestones wrote data");
    const availableText = await evaluate(cdp, `document.querySelector('[data-organization-availability="sources"]').textContent`);
    state = {...state, organization_setup:{source_package_enabled:!state.organization_setup.source_package_enabled,active_document_watch:false,active_topic:false}};
    await open();
    assert.notEqual(await evaluate(cdp, `document.querySelector('[data-organization-availability="sources"]').textContent`),availableText,"Organization availability not refreshed");
    if (locale === "en-CH" && permission === "viewer") {
      await mkdir(join(root,".tmp"),{recursive:true});
      await evaluate(cdp, `document.querySelector('[data-onboarding-milestones]').scrollIntoView({block:'start'})`);
      await sleep(100);
      const shot=await cdp.send("Page.captureScreenshot",{format:"png"});
      await writeFile(join(root,".tmp",`onboarding-${width}.png`),Buffer.from(shot.data,"base64"));
    }
    failSave=true;
    await click('[data-onboarding-choice="topic"]');
    await waitFor(()=>evaluate(cdp, `document.body.innerText.includes('Synthetic save unavailable') && !document.querySelector('[data-onboarding-choice="topic"]').disabled`),"Save failure not recoverable");
    assert.equal(await evaluate(cdp,'location.pathname'),'/onboarding');
    assert.equal(state.state,"new");
    failSave=false;
    for (const [action, destination] of [["topic","/topics"],["law","/discover"],["explore","/"],["later","/"]]) {
      before=changes().length;
      await click(action === "later" ? '[data-onboarding-later]' : `[data-onboarding-choice="${action}"]`);
      await waitFor(()=>evaluate(cdp, `location.pathname === ${JSON.stringify(destination)}`),"Choice did not navigate after save");
      assert.equal(changes().length,before+1,"Choice caused extra mutation");
      assert.deepEqual(changes().at(-1),{path:"/api/onboarding",method:"PATCH",body:{action}});
      await open();
      assert.equal(state.state,action === "later" ? "deferred" : "started");
      assert.ok(await evaluate(cdp, `document.querySelector('[data-onboarding-status]').textContent.length > 20`));
    }
    assert.equal(state.intent,"explore","Deferral lost prior intent");
  }
  assert.deepEqual(exceptions,[]);
  console.log("Personal onboarding production UI: 20 five-language 390/1440px admin/viewer journeys pass passive entry, organization availability, all three choices, defer/resume, failed-save retry, exact personal PATCH and no hidden shared activation. API interception only; no live model/source/email calls.");
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
  assert.ok(basename(profile).startsWith("helvetic-onboarding-browser-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
