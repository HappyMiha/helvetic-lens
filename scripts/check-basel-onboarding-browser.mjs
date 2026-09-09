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
const accessibility = new AccessibilityAudit("basel-onboarding");

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
const profile = await mkdtemp(join(tmpdir(), "helvetic-basel-browser-"));
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

let locale = "en-CH", role = "organization_admin", enabled = false, failPreview = false, failSave = false, empty = false, duplicate = false;
const localized = value => Object.fromEntries(["en-CH","de-CH","fr-CH","it-CH","rm-CH"].map(key => [key,value]));
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
    const path = new URL(request.url).pathname;
    const payload = request.postData ? JSON.parse(request.postData) : null;
    requests.push({path, method:request.method, body:payload});
    let body = {}, code = 200;
    if (path === "/api/auth/session") body = {authenticated:true,user:{id:"basel-qa",email:"qa@example.invalid",name:"QA",locale},organization:{id:"basel-qa",name:"QA"},role};
    else if (path === "/api/health") body = {status:"ok",database:"postgresql",apertus:{configured:false},firecrawl:{configured:false}};
    else if (path === "/api/source-packs") body = {items:[{id:"basel-stadt-legislation",description:localized("German official OGD legislation only. No court decisions, parliament or annex contents. Kantonsblatt is authoritative."),expected_first_data:localized("Collection proceeds gradually; this does not establish complete coverage."),subscription:{enabled}}]};
    else if (path === "/api/source-packs/basel-stadt-legislation/activate") {enabled=true;code=202;body={jobs:[]};}
    else if (path === "/api/onboarding/basel-stadt/collect") {code=202;body={state:"queued"};}
    else if (path === "/api/monitoring-topics/preview") {
      if (failPreview) {code=503;body={detail:"Synthetic preview unavailable"};}
      else body={items:empty?[]:[{event_id:"event-privacy",title:"Synthetic Datenschutz Gesetz",reason_signals:[{type:"concept",value:"Datenschutz"}],evidence_url:"/corpus-evidence/basel-qa-version",source_url:"https://www.gesetzessammlung.bs.ch/app/de/texts_of_law/153.260/versions/6649"}],matching_topics:{items:duplicate?[{id:"existing"}]:[],count_is_complete:true,scanned_count:1,scan_limit:500,match_count:duplicate?1:0,display_truncated:false,basis:"same_matching_rules_v1"}};
    } else if (path === "/api/monitoring-topics") {
      if (request.method === "POST") {code=failSave?503:201;body=failSave?{detail:"Synthetic save unavailable"}:{id:"saved-topic"};}
      else body=[];
    } else if (["/api/jobs","/api/scans","/api/sources","/api/laws"].includes(path)) body=[];
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

  const writes = () => requests.filter(r => !["GET","HEAD"].includes(r.method) && !r.path.startsWith("/api/assistant/"));
  async function open() {
    await cdp.send("Page.navigate", {url:`${base}/onboarding/basel-stadt?locale=${locale}`});
    await waitFor(()=>evaluate(cdp,`document.querySelector('[data-basel-preview]') && document.documentElement.lang === ${JSON.stringify(locale)}`),"Basel guide did not load");
    assert.ok(await evaluate(cdp,`document.documentElement.scrollWidth <= innerWidth + 1`),"Horizontal overflow");
  }
  for (const language of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]) for (const width of [390,1440]) for (const permission of ["organization_admin","viewer"]) {
    locale=language;role=permission;enabled=permission==="viewer";empty=false;duplicate=false;failPreview=false;failSave=false;
    await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:900,deviceScaleFactor:1,mobile:width<500});
    const before=writes().length;
    await open();
    assert.equal(writes().length,before,"Passive guide entry wrote data");
    await accessibility.check(cdp,`basel-${locale}-${width}-${role}`,"[data-basel-guide]");
    if (permission === "organization_admin") {
      assert.equal(await evaluate(cdp,`document.querySelector('[data-basel-preview]').disabled`),true);
      await click('[data-basel-enable]');
      await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-basel-collect]') && !document.querySelector('[data-basel-collect]').disabled`),"Activation did not refresh package");
      assert.deepEqual(writes().at(-1),{path:"/api/source-packs/basel-stadt-legislation/activate",method:"POST",body:null});
      await click('[data-basel-collect]');
      await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-basel-notice]') && !document.querySelector('[data-basel-preview]').disabled`),"Collection acknowledgement missing");
      assert.deepEqual(writes().at(-1),{path:"/api/onboarding/basel-stadt/collect",method:"POST",body:null});
    } else assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-basel-enable],[data-basel-collect]').length`),0);
    failPreview=true;
    await click('[data-basel-preview]');
    await waitFor(()=>evaluate(cdp,`document.body.innerText.includes('Synthetic preview unavailable') && !document.querySelector('[data-basel-preview]').disabled`),"Preview failure not recoverable");
    assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-basel-results]').length`),0);
    failPreview=false;empty=true;
    await click('[data-basel-preview]');
    await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-basel-results]') && !document.querySelector('[data-basel-preview]').disabled`),"Empty preview missing");
    assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-basel-evidence]').length`),0);
    assert.ok(await evaluate(cdp,`!document.querySelector('[data-basel-save]') || document.querySelector('[data-basel-save]').disabled`));
    empty=false;
    await click('[data-basel-preview]');
    await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-basel-evidence]') && !document.querySelector('[data-basel-preview]').disabled`),"Relevant evidence link missing");
    const plan=writes().at(-1).body;
    assert.deepEqual(plan.jurisdictions,["CH-BS"]);assert.deepEqual(plan.languages,["de"]);assert.deepEqual(plan.source_pack_ids,["basel-stadt-legislation"]);
    assert.equal(await evaluate(cdp,`document.querySelector('[data-basel-evidence]').getAttribute('href')`),"/corpus-evidence/basel-qa-version");
    assert.ok(await evaluate(cdp,`document.querySelector('[data-basel-results]').innerText.includes('Datenschutz')`));
    await accessibility.check(cdp,`basel-results-${locale}-${width}-${role}`,"[data-basel-guide]");
    if (permission === "organization_admin") {
      failSave=true;
      await click('[data-basel-save]');
      await waitFor(()=>evaluate(cdp,`document.body.innerText.includes('Synthetic save unavailable') && !document.querySelector('[data-basel-save]').disabled`),"Save failure not recoverable");
      const failed=writes().at(-1).body;
      failSave=false;
      await click('[data-basel-save]');
      await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-basel-guide] a[href="/digests"]') && !document.querySelector('[data-basel-save]')`),"Successful save did not expose next steps");
      assert.deepEqual(writes().at(-1).body,failed,"Retry changed the idempotency key or plan");
      duplicate=true;
      await open();await click('[data-basel-preview]');
      await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-basel-results]') && !document.querySelector('[data-basel-preview]').disabled`),"Duplicate preview missing");
      assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-basel-save]').length`),0);
      duplicate=false;
    } else assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-basel-save]').length`),0);
    if (locale === "en-CH" && permission === "viewer") {
      await mkdir(join(root,".tmp"),{recursive:true});
      await evaluate(cdp,`document.querySelector('[data-basel-guide]').scrollIntoView({block:'start'})`);
      const shot=await cdp.send("Page.captureScreenshot",{format:"png"});
      await writeFile(join(root,".tmp",`basel-${width}.png`),Buffer.from(shot.data,"base64"));
    }
  }
  assert.deepEqual(exceptions,[]);
  accessibility.finish(40);
  console.log("Basel onboarding: 20 five-locale desktop/mobile admin/viewer journeys; passive entry, explicit activation/collection, preview error/empty/retry, evidence destination, matching terms, idempotent save retry, existing-topic handling and 40 accessibility checks passed. Synthetic API interception; live source acceptance is checked separately.");
} catch (error) {
  console.error({locale,role,requests:requests.slice(-12),exceptions,text:cdp?await evaluate(cdp,'document.body.innerText.slice(-2400)').catch(()=>"unavailable"):"none"});
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const ended = new Promise(resolve => child.once("exit", resolve));
    child.kill();
    await Promise.race([ended, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-basel-browser-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
