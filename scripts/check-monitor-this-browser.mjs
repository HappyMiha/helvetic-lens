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
const profile = await mkdtemp(join(tmpdir(), "helvetic-monitor-this-browser-"));
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
let locale = "en-CH", role = "organization_admin", user = "qa", saved = null;
const title = "Synthetic privacy development";
const coverageStream = {connector: "fedlex", stream: "rss-de", publisher: "Synthetic official publisher", localized_copy: {"en-CH": {summary: "Saved source metadata", boundary: "Bounded official source evidence."}}, catalogue_state: "partial", configured: true, enabled: true, interval_seconds: 7200, jitter_seconds: 120, window_start: "07:00", window_end: "20:00", next_run_at: "2026-09-05T08:00:00Z", next_attempt_past_due: true, last_reported_health: "degraded", last_success_at: "2026-09-04T08:00:00Z", last_run_status: "partial"};
const existing = {id: "qa-existing-topic", status: "paused", current_revision: 1, created_at: "2026-09-06T08:00:00Z", updated_at: "2026-09-06T08:00:00Z", revisions: [],
  plan: {name: "Synthetic existing topic with a deliberately long descriptive name for narrow screens", goal: "Privacy", concepts: ["privacy"], synonyms: [], exclusions: [], jurisdictions: ["CH"], languages: ["en"], source_pack_ids: ["fedlex-legislation"], document_kinds: ["act"], event_kinds: ["amended"], importance_floor: "low"}};

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

  cdp.on("Page.javascriptDialogOpening", () => { void cdp.send("Page.handleJavaScriptDialog", {accept: true}); });
  cdp.on("Fetch.requestPaused", async ({requestId, request}) => {
    const url = new URL(request.url);
    requests.push({path: url.pathname, method: request.method, body: request.postData ? JSON.parse(request.postData) : null});
    let body = {}, code = 200;
    if (url.pathname === "/api/auth/session") body = {authenticated: true, user: {id: user, email: "qa@example.invalid", name: "QA", locale}, organization: {id: "qa-org", name: "QA"}, role};
    else if (url.pathname === "/api/health") body = {status: "ok", database: "sqlite", apertus: {configured: false}, firecrawl: {configured: false}};
    else if (url.pathname === "/api/jobs") body = [];
    else if (url.pathname === "/api/monitoring-context") {
      if (url.searchParams.get("id") === "unavailable") {code = 404; body = {detail: "Synthetic unavailable context"};}
      else body = {kind: url.searchParams.get("kind"), id: "qa-event", title: title, requires_confirmation: true, ai_calls: 0,
        ...(url.searchParams.get("kind") === "answer" ? {question: "Which privacy obligations changed?", answer_created_at: "2026-09-06T08:00:00Z", comparison_id: "qa-comparison"} : {}),
        source_url: "https://example.invalid/official-source", evidence_url: "/corpus-evidence/qa-native", watches: [{law_id: "qa-law", name: "Already monitored document", active: false, url: "/laws/qa-law"}], more_watches: false};
    } else if (url.pathname === "/api/source-packs") body = {items: [{id: "fedlex-legislation", name: {en: "Synthetic enabled sources"}, subscription: {enabled: true}}]};
    else if (url.pathname === "/api/monitoring-topics/preview") body = {candidate_count: 0, scanned_event_count: 0, scanned_event_limit: 500, items: [], count_is_complete: true, sample_captured_at: "2026-09-06T08:00:00Z",
      source_coverage: {captured_at: "2026-09-06T08:00:00Z", timezone: "Europe/Zurich", scope: "selected_packs_saved_operational_state", enabled_pack_count: role === "viewer" ? 0 : 1, items: [{id: "fedlex-legislation", name: {"en-CH": "Synthetic official sources"}, subscription_enabled: role !== "viewer", subscription_state: role === "viewer" ? "inactive" : "partial", unknown_stream_count: 0, streams: [coverageStream, {...coverageStream, stream: "rss-fr", enabled: false, next_attempt_past_due: false, last_reported_health: "healthy"}, {...coverageStream, stream: "missing", configured: false, enabled: false, interval_seconds: null, jitter_seconds: null, next_run_at: null, next_attempt_past_due: false, last_success_at: null, last_reported_health: "unknown", last_run_status: null, window_start: null, window_end: null}]}]},
      matching_topics: {items: [{id: existing.id, name: existing.plan.name, status: existing.status, current_revision: 1}], match_count: 12, scanned_count: 500, scan_limit: 500, count_is_complete: false, display_truncated: true, basis: "same_matching_rules_v1"}};
    else if (url.pathname === "/api/monitoring-topics" && request.method === "POST") {
      assert.equal(role, "organization_admin", "Viewer must not activate monitoring");
      saved = {id: "qa-topic", status: "active", current_revision: 1, plan: JSON.parse(request.postData), revisions: [], created_at: "2026-09-06T08:00:00Z", updated_at: "2026-09-06T08:00:00Z"};
      code = 201; body = saved;
    } else if (url.pathname === "/api/monitoring-topics") body = saved ? [saved, existing] : [existing];
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
  const creates = () => requests.filter(r => r.path === "/api/monitoring-topics" && r.method === "POST");
  const previews = () => requests.filter(r => r.path === "/api/monitoring-topics/preview");
  for (const language of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) for (const width of [390,1440]) for (const permission of ["organization_admin", "viewer"]) {
    locale = language; role = permission; user = `${language}-${width}-${permission}`; saved = null;
    const before = creates().length, previewBefore = previews().length;
    await cdp.send("Emulation.setDeviceMetricsOverride", {width, height: 900, deviceScaleFactor: 1, mobile: width < 500});
    await cdp.send("Page.navigate", {url: `${base}/topics?from=${width === 1440 ? "answer" : "event"}&record=${width === 1440 ? "qa-answer" : "qa-event"}&locale=${locale}`});
    await waitFor(() => evaluate(cdp, `!!document.querySelector('[data-monitor-use]') && !document.querySelector('[data-monitor-use]').disabled && document.documentElement.lang === ${JSON.stringify(locale)}`), "Context not ready");
    assert.equal(await evaluate(cdp, `document.querySelector('[name="topic-name"]').value`), "", "Context silently replaced draft");
    assert.equal(creates().length, before);
    assert.equal(previews().length, previewBefore);
    if (locale === "en-CH" && role === "organization_admin") {
      await mkdir(join(root, ".tmp"), {recursive: true});
      const shot = await cdp.send("Page.captureScreenshot", {format: "png"});
      await writeFile(join(root, ".tmp", `monitor-this-${width}.png`), Buffer.from(shot.data, "base64"));
    }
    assert.ok(await evaluate(cdp, `!!document.querySelector('[data-monitor-context] a[href="/laws/qa-law"]') && !!document.querySelector('a[href="/corpus-evidence/qa-native"]')`));
    await click('[data-monitor-use]');
    await waitFor(() => evaluate(cdp, `document.querySelector('[name="topic-name"]').value === ${JSON.stringify(title)}`), "Explicit context copy failed");
    assert.equal(await evaluate(cdp, `document.querySelector('[name="topic-concepts"]').value`), "", "Guessed search terms were added");
    if (width === 1440) {
      assert.ok(await evaluate(cdp, `document.querySelector('[data-monitor-saved-question]').innerText.includes('Which privacy obligations changed?')`));
      assert.ok(await evaluate(cdp, `document.querySelector('[name="topic-goal"]').value.includes('Which privacy obligations changed?')`));
      assert.equal(await evaluate(cdp, `location.search.includes('privacy')`), false, "Question leaked into URL");
    }
    await evaluate(cdp, `(()=>{const el=document.querySelector('[name="topic-concepts"]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,'privacy');el.dispatchEvent(new Event('input',{bubbles:true}));})()`);
    await click('.monitoring-topic-builder button[type="submit"]');
    await waitFor(() => evaluate(cdp, `!!document.querySelector('[data-topic-preview]') && !document.querySelector('.monitoring-topic-builder fieldset').disabled`), "Preview failed");
    assert.equal(creates().length, before, "Preview activated monitoring");
    assert.equal(previews().at(-1).body.concepts[0], "privacy");
    assert.deepEqual(previews().at(-1).body.source_pack_ids, ["fedlex-legislation"]);
    assert.ok(await evaluate(cdp, `!!document.querySelector('[data-topic-source-readiness]') && !!document.querySelector('[data-topic-source-attention]')`), "Source readiness missing before activation");
    assert.equal(await evaluate(cdp, `!!document.querySelector('[data-topic-sources-inactive]')`), role === "viewer");
    assert.equal(await evaluate(cdp, `document.body.innerText.includes('topicSources.')`), false);
    await click('[data-topic-source-pack] summary');
    assert.equal(await evaluate(cdp, `document.querySelectorAll('[data-topic-source-stream]').length`), 3);
    assert.ok(await evaluate(cdp, `document.querySelector('[data-topic-source-readiness]').innerText.includes('Europe/Zurich') && document.querySelector('[data-topic-source-readiness]').innerText.includes('120')`), "Saved custom interval/window missing");
    assert.ok(await evaluate(cdp, `document.querySelector('[data-topic-source-next]').textContent.includes('10:00')`), "Scheduled attempt must include its Zurich time, not only date");
    if (locale === "en-CH" && role === "organization_admin") {
      await evaluate(cdp, `document.querySelector('[data-topic-source-readiness]').scrollIntoView({block:'start'})`);
      await sleep(200);
      const shot = await cdp.send("Page.captureScreenshot", {format: "png"});
      await writeFile(join(root, ".tmp", `topic-source-readiness-${width}.png`), Buffer.from(shot.data, "base64"));
    }
    await click('[data-topic-source-pack] summary');
    assert.ok(await evaluate(cdp, `!!document.querySelector('[data-topic-duplicates] a[href="#topic-qa-existing-topic"]') && !!document.getElementById('topic-qa-existing-topic')`), "Existing topic warning/target missing");
    assert.ok(await evaluate(cdp, `document.querySelector('[data-topic-duplicates]').innerText.includes('500')`), "Limited check must be disclosed");
    assert.equal(await evaluate(cdp, `document.body.innerText.includes('topicDuplicates.')`), false);
    if (locale === "en-CH" && role === "organization_admin") {
      await evaluate(cdp, `document.querySelector('[data-topic-duplicates]').scrollIntoView({block:'center'})`);
      await sleep(200);
      const shot = await cdp.send("Page.captureScreenshot", {format: "png"});
      await writeFile(join(root, ".tmp", `topic-duplicates-${width}.png`), Buffer.from(shot.data, "base64"));
    }
    if (role === "organization_admin") {
      assert.ok(await evaluate(cdp, `document.querySelector('[data-topic-save]').disabled`), "Duplicate bypassed review");
      await click('[data-topic-duplicate-confirm]');
      assert.ok(await evaluate(cdp, `!document.querySelector('[data-topic-save]').disabled`));
      // A newly computed preview always needs its own explicit review.
      await click('.monitoring-topic-builder button[type="submit"]');
      await waitFor(() => evaluate(cdp, `!document.querySelector('.monitoring-topic-builder fieldset').disabled && !document.querySelector('[data-topic-duplicate-confirm]').checked`), "Repeated preview retained obsolete acknowledgement");
      assert.ok(await evaluate(cdp, `document.querySelector('[data-topic-save]').disabled`));
      await evaluate(cdp, `document.querySelector('[data-topic-duplicate-confirm]').focus()`);
      await cdp.send("Input.dispatchKeyEvent", {type: "keyDown", key: " ", code: "Space", windowsVirtualKeyCode: 32});
      await cdp.send("Input.dispatchKeyEvent", {type: "keyUp", key: " ", code: "Space", windowsVirtualKeyCode: 32});
      await waitFor(() => evaluate(cdp, `!document.querySelector('[data-topic-save]').disabled`), "Keyboard acknowledgement failed");
      await click('[data-topic-save]');
      await waitFor(() => evaluate(cdp, `!!document.querySelector('[data-topic-open-saved]')`), "Saved topic link missing");
      assert.equal(creates().length, before + 1);
      assert.ok(creates().at(-1).body.idempotency_key.length >= 8);
      assert.equal(await evaluate(cdp, `document.querySelector('[data-topic-open-saved]').getAttribute('href')`), "/topics#topic-qa-topic");
    } else {
      assert.ok(await evaluate(cdp, `!document.querySelector('[data-topic-save]') && !document.querySelector('[data-topic-duplicate-confirm]') && !!document.querySelector('[data-topic-personal-note]') && !document.querySelector('[data-topic-edit]')`));
      await cdp.send("Page.reload");
      await waitFor(() => evaluate(cdp, `!!document.querySelector('[data-topic-restore]')`), "Viewer personal draft not recoverable");
      assert.ok(await evaluate(cdp, `document.querySelector('[data-monitor-use]').disabled`), "Context can overwrite recovery");
      await click('[data-topic-restore]');
      await waitFor(() => evaluate(cdp, `document.querySelector('[name="topic-concepts"]').value === 'privacy'`), "Viewer personal draft restore failed");
      assert.ok(await evaluate(cdp, `!document.querySelector('[data-topic-preview]')`), "Restored stale preview");
      assert.equal(creates().length, before);
    }
    assert.ok(await evaluate(cdp, `document.documentElement.scrollWidth <= innerWidth+1`), `Overflow ${locale} ${width} ${role}`);
    assert.equal(await evaluate(cdp, `document.body.innerText.includes('monitorThis.')`), false);
  }
  user = "qa-unavailable";
  await cdp.send("Page.navigate", {url: `${base}/topics?from=event&record=unavailable&locale=en-CH`});
  await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Synthetic unavailable context')`), "Missing context error");
  assert.ok(await evaluate(cdp, `!document.querySelector('[data-monitor-use]')`));
  assert.equal(requests.some(r => r.path.includes('/draft') || (r.path === '/api/source-packs' && r.method !== 'GET')), false);
  assert.deepEqual(exceptions, []);
  console.log("Monitor-this production UI: 20 five-locale mobile/desktop admin/viewer journeys pass explicit context copy, existing-watch/evidence links, manual concepts, enabled-pack scope, preview without activation, saved source schedules/health/subscription boundaries and disclosure controls, duplicate links and bounded-check disclosure, required pointer/keyboard review reset on repeated preview, explicit authorized save/direct link, viewer read-only duplicate warning and reload/restore without activation and unavailable-context recovery. All APIs intercepted; no real monitoring or inference.");
} catch (error) {
  console.error({ locale, role, user, requests: requests.slice(-10), exceptions, form: cdp ? await evaluate(cdp, `JSON.stringify({inputs: Array.from(document.querySelectorAll(".monitoring-topic-builder input")).map(el=>({name:el.name,value:el.value,valid:el.checkValidity()})),text:document.body.innerText.slice(-1800)})`).catch(()=>"unavailable") : "none", page: cdp ? await evaluate(cdp, "JSON.stringify({url:location.href,ready:document.readyState,html:document.documentElement.outerHTML.slice(0,1800)})").catch(() => "unavailable") : "no browser" });
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const ended = new Promise(resolve => child.once("exit", resolve));
    child.kill();
    await Promise.race([ended, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-monitor-this-browser-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
