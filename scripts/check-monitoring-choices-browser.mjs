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
const profile = await mkdtemp(join(tmpdir(), "helvetic-monitor-choice-browser-"));
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
let locale = "en-CH", role = "organization_admin", user = "qa", confirmAccept = true, confirmCount = 0, packEnabled = false, packPending = false;
let review = null, failReview = false, packRevision="v1";
const title = "Synthetic retention policy", documentUrl = "https://example.invalid/retention";
const text = value => ({"en-CH": value});
const pack = () => ({id: "fedlex-legislation", revision:packRevision, name: text("Synthetic official legislation"), description: text("Saved official sources"), expected_first_data: text("Data arrives after a successful scheduled sync."),
  capabilities: [], authorities: ["fedlex"], document_kinds: ["act"], languages: ["de", "fr"], cadences: ["scheduled"], last_success_at: null, partial: true, pending_request: packPending,
  subscription: {enabled: packEnabled, state: packEnabled ? "queued" : "inactive", included_event_count: 0, progress_current: 0, progress_total: 1}});
const law = {id: "qa-created-law", name: title, url: documentUrl, source_id: null, active: true, current_version_id: null, current_version: null, created_at: "2026-09-06T08:00:00Z", last_checked: null, last_result: "baseline", last_error: null, comparison_id: null, comparison_mode: null, change_counts: null, analysis: null};

try {
  await waitFor(async () => (await fetch(base)).ok, "Isolated production UI failed to start");
  let debugPort;
  await waitFor(async () => { debugPort = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]; return !!debugPort; }, "Browser failed to start");
  await pollJson(`http://127.0.0.1:${debugPort}/json/version`);
  const target = await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: "PUT" }).then(response => response.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) => exceptions.push(exceptionDetails.text));

  cdp.on("Page.javascriptDialogOpening", ({type}) => { if (type === "confirm") confirmCount++; void cdp.send("Page.handleJavaScriptDialog", {accept: type === "confirm" ? confirmAccept : true}); });
  cdp.on("Fetch.requestPaused", async ({requestId, request}) => {
    const url = new URL(request.url);
    requests.push({path: url.pathname, method: request.method, body: request.postData ? JSON.parse(request.postData) : null});
    let body = {}, code = 200;
    if (url.pathname === "/api/auth/session") body = {authenticated: true, user: {id: user, email: "qa@example.invalid", name: "QA", locale}, organization: {id: "qa-org", name: "QA"}, role};
    else if (url.pathname === "/api/health") body = {status: "ok", database: "sqlite", apertus: {configured: false}, firecrawl: {configured: false}};
    else if (["/api/jobs", "/api/scans", "/api/sources"].includes(url.pathname)) body = [];
    else if (url.pathname === "/api/laws" && request.method === "GET") body = [];
    else if (url.pathname === "/api/monitoring-context") body = {kind: "event", id: url.searchParams.get("id"), title, source_url: documentUrl, requires_confirmation: true, ai_calls: 0,
      more_watches: false, watches: url.searchParams.get("id") === "watched" ? [{law_id: law.id, name: title, active: false, url: `/laws/${law.id}`}] : []};
    else if (url.pathname === "/api/monitoring-topics") body = [];
    else if (url.pathname === "/api/source-capabilities") body = {catalogue_revision: "synthetic", items: []};
    else if (url.pathname === "/api/source-packs") {await sleep(100); body = {catalogue_revision:"synthetic", starter: {id: "starter", name: text("Synthetic starter package"), description: text("Review before activation."), expected_first_data: text("No complete coverage promised."), state: "inactive"}, items: [pack()]};}
    else if (url.pathname === "/api/onboarding") body={state:"new",intent:null,milestones:[],source_review:review ? {...review,current:review.snapshot.packs[0].revision===packRevision && review.snapshot.packs[0].enabled===packEnabled} : null,organization_setup:{}};
    else if (url.pathname === "/api/onboarding/source-review") {
      assert.equal(request.method,"POST");
      if(failReview){code=409;body={detail:"Synthetic source selection changed"};}
      else {const snapshot=JSON.parse(request.postData);assert.deepEqual(snapshot,{catalogue_revision:"synthetic",packs:[{id:"fedlex-legislation",revision:packRevision,enabled:packEnabled}]});
        // Reordered fields reproduce PostgreSQL JSONB object ordering.
        review={snapshot:{packs:snapshot.packs.map(p=>({enabled:p.enabled,revision:p.revision,id:p.id})),catalogue_revision:snapshot.catalogue_revision},current:true,reviewed_at:"2026-09-06T10:00:00Z",first_reviewed_at:"2026-09-06T10:00:00Z"};body=review;}
    }
    else if (url.pathname === "/api/preview") {
      assert.equal(request.method, "POST"); assert.equal(JSON.parse(request.postData).url, documentUrl);
      body = {title, content_type: "text/html", characters: 120, passage_count: 1, page_count: 0, excerpt: "Synthetic saved text for review.", url: documentUrl};
    } else if (url.pathname === "/api/laws" && request.method === "POST") {
      assert.equal(role, "organization_admin"); const payload = JSON.parse(request.postData);
      assert.equal(payload.url, documentUrl); assert.equal(payload.name, title); assert.equal(payload.provider, "native");
      body = law; code = 201;
    } else if (url.pathname === "/api/source-packs/fedlex-legislation/activate") {assert.equal(role, "organization_admin"); packEnabled = true; code = 202;}
    else if (url.pathname === "/api/source-pack-requests") {assert.equal(role, "viewer"); assert.deepEqual(JSON.parse(request.postData), {pack_id: "fedlex-legislation", action: "activate"}); packPending = true; code = 201;}
    else {code = 503; body = {detail: "Unconfigured synthetic endpoint"};}
    await cdp.send("Fetch.fulfillRequest", {requestId, responseCode: code, responseHeaders: [{name: "Content-Type", value: "application/json"}], body: Buffer.from(JSON.stringify(body)).toString("base64")}).catch(() => {});
  });
  await cdp.send("Fetch.enable", {patterns: [{urlPattern: `${base}/api/*`, requestStage: "Request"}]});
  const click = async selector => {
    await evaluate(cdp, `new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))`);
    const point = await evaluate(cdp, `(()=>{const el=document.querySelector(${JSON.stringify(selector)});el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect(), x=r.x+r.width/2,y=r.y+r.height/2;return {x,y,visible:el.contains(document.elementFromPoint(x,y))};})()`);
    assert.ok(point.visible, `Control not reachable by pointer: ${selector}`);
    for (const type of ["mousePressed", "mouseReleased"]) await cdp.send("Input.dispatchMouseEvent", {type, x:point.x, y:point.y, button: "left", clickCount: 1});
  };
  const changes = () => requests.filter(r => r.method !== "GET" && !r.path.startsWith('/api/assistant/'));
  for (const language of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) for (const width of [390,1280,1440]) for (const permission of ["organization_admin", "viewer"]) {
    locale = language; role = permission; user = `${language}-${width}-${permission}`; packEnabled = false; packPending = false; review=null; failReview=false; packRevision="v1";
    const before = changes().length;
    await cdp.send("Emulation.setDeviceMetricsOverride", {width, height: 900, deviceScaleFactor: 1, mobile: width < 500});
    await cdp.send("Page.navigate", {url: `${base}/topics?from=event&record=unwatched&locale=${locale}`});
    await waitFor(() => evaluate(cdp, `document.querySelectorAll('[data-monitor-choice]').length === 3 && !document.querySelector('[data-monitor-use]').disabled && document.documentElement.lang === ${JSON.stringify(locale)}`), "Choice screen not ready");
    assert.equal(changes().length, before, "Merely opening choices changed monitoring");
    assert.equal(await evaluate(cdp, `document.body.innerText.includes('monitorChoice.')`), false);
    assert.ok(await evaluate(cdp, `document.documentElement.scrollWidth <= innerWidth + 1`), "Choice cards overflowed");
    if (language === "en-CH" && role === "organization_admin") {
      await mkdir(join(root, ".tmp"), {recursive:true});
      await evaluate(cdp, `document.querySelector('[data-monitor-choices]').scrollIntoView({block:'center'})`);
      const shot = await cdp.send("Page.captureScreenshot", {format:"png"});
      await writeFile(join(root, ".tmp", `monitor-choice-${width}.png`),Buffer.from(shot.data,"base64"));
    }
    if (role === "organization_admin") {
      await click('[data-monitor-document]');
      await waitFor(() => evaluate(cdp, `!!document.querySelector('[role="dialog"] input[type="url"]')`), "Document setup missing");
      assert.equal(await evaluate(cdp, `document.querySelector('[role="dialog"] input[type="url"]').value`), documentUrl);
      assert.equal(changes().length, before, "Opening document setup fetched/saved without preview action");
      assert.ok(await evaluate(cdp, `document.querySelector('[role="dialog"] button[type="submit"]').disabled`), "Save should require preview");
      await click('[role="dialog"] .form-actions button[type="button"]');
      await waitFor(() => evaluate(cdp, `!!document.querySelector('.extraction-preview') && !document.querySelector('[role="dialog"] button[type="submit"]').disabled`), "Explicit preview failed");
      assert.deepEqual(changes().slice(before).map(r=>r.path), ['/api/preview']);
      await click('[role="dialog"] button[type="submit"]');
      await waitFor(() => evaluate(cdp, `location.pathname === '/laws/qa-created-law'`), "Saved document did not open its direct page");
      assert.deepEqual(changes().slice(before).map(r=>r.path), ['/api/preview', '/api/laws']);
    } else {
      assert.ok(await evaluate(cdp, `document.querySelector('[data-monitor-document]').disabled`), "Viewer could add shared document");
    }
    await cdp.send("Page.navigate", {url: `${base}/topics?from=event&record=watched&locale=${locale}`});
    await waitFor(() => evaluate(cdp, `!!document.querySelector('[data-monitor-existing]')`), "Existing watch not offered");
    assert.equal(await evaluate(cdp, `document.querySelector('[data-monitor-existing]').getAttribute('href')`), '/laws/qa-created-law');
    assert.equal(await evaluate(cdp, `!!document.querySelector('[data-monitor-document]')`), false, "Existing paused watch offered duplicate creation");
    // Editing a topic does not consent to abandoning it for another setup route.
    await click('[data-monitor-use]');
    await waitFor(() => evaluate(cdp, `document.querySelector('[name="topic-name"]').value === 'Synthetic retention policy'`), "Topic copy failed");
    confirmAccept = false; const oldConfirm = confirmCount;
    await click('[data-monitor-packs]');
    await waitFor(() => Promise.resolve(confirmCount === oldConfirm + 1), "Leaving dirty topic did not request confirmation");
    assert.equal(await evaluate(cdp, `location.pathname`), '/topics');
    const beforePack = changes().length;
    confirmAccept = true;
    await click('[data-monitor-packs]');
    await waitFor(() => evaluate(cdp, `location.pathname === '/sources' && location.hash === '#source-packs' && document.activeElement?.id === 'source-packs'`), "Source packages deep link did not focus asynchronously loaded section");
    assert.equal(changes().length, beforePack, "Selecting source packages activated them");
    assert.ok(await evaluate(cdp, `document.getElementById('source-packs').getBoundingClientRect().top >= (document.querySelector('.topbar')?.getBoundingClientRect().bottom || 0)`), "Sticky header hid selected packages");
    await click('[data-pack-id="fedlex-legislation"] button');
    await waitFor(() => Promise.resolve(changes().length === beforePack + 1), "Explicit package action not sent");
    assert.equal(changes().at(-1).path, role === 'viewer' ? '/api/source-pack-requests' : '/api/source-packs/fedlex-legislation/activate');
    await waitFor(()=>evaluate(cdp, `!!document.querySelector('[data-save-source-review]') && !document.querySelector('[data-save-source-review]').disabled`),"Personal review unavailable");
    const beforeReview=changes().length;
    failReview=true;
    await click('[data-save-source-review]');
    await waitFor(()=>evaluate(cdp, `document.querySelector('[data-source-review]').textContent.includes('Synthetic source selection changed') && !document.querySelector('[data-save-source-review]').disabled`),"Conflict not recoverable");
    assert.equal(review,null);
    failReview=false;
    await click('[data-save-source-review]');
    await waitFor(()=>evaluate(cdp, `!!document.querySelector('[data-source-review-status]') && document.querySelector('[data-save-source-review]').disabled`),"Review not saved or JSON field order affected equality");
    assert.deepEqual(changes().slice(beforeReview).map(r=>r.path),['/api/onboarding/source-review','/api/onboarding/source-review']);
    assert.ok(await evaluate(cdp, `!document.querySelector('[data-source-review]').innerText.includes('sourceReview.')`));
    if(language==='en-CH' && width!==1280 && permission==='viewer'){
      await evaluate(cdp, `document.querySelector('[data-source-review]').scrollIntoView({block:'center'})`);
      await writeFile(join(root,'.tmp',`source-review-${width}.png`),Buffer.from((await cdp.send('Page.captureScreenshot',{format:'png'})).data,'base64'));
    }
    packRevision="v2";
    await cdp.send('Page.navigate',{url:`${base}/sources?locale=${locale}`});
    await waitFor(()=>evaluate(cdp, `!!document.querySelector('[data-source-review-status]') && !document.querySelector('[data-save-source-review]').disabled`),"Changed revision still treated as reviewed");
    await click('[data-save-source-review]');
    await waitFor(()=>evaluate(cdp, `document.querySelector('[data-save-source-review]').disabled`),"Re-review failed");
    await cdp.send('Page.navigate',{url:`${base}/onboarding?locale=${locale}`});
    await waitFor(()=>evaluate(cdp, `!!document.querySelector('[data-onboarding-source-review]')`),"Guide lost source review");
    assert.ok(await evaluate(cdp, `document.documentElement.scrollWidth <= innerWidth + 1`), "Source packages overflowed");
  }
  assert.deepEqual(exceptions, []);
  console.log('Monitoring choices production UI: 30 five-locale 390/1280/1440px admin/viewer journeys pass explicit law/topic/package choice, no action on entry, preview-before-document-save and exact success link, existing paused-watch reuse, viewer document restriction, dirty-draft leave confirmation, asynchronous source-package focus and explicit activation/admin request. Personal source review also passes zero-mutation entry, admin/viewer save, rejected stale-state retry, JSONB field-order equality, revision invalidation and guide persistence. All APIs intercepted; no live source or shared data changes.');
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
  assert.ok(basename(profile).startsWith("helvetic-monitor-choice-browser-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
