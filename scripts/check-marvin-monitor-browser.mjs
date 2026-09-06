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
const profile = await mkdtemp(join(tmpdir(), "helvetic-marvin-monitor-browser-"));
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
let locale = "en-CH", role = "organization_admin", user = "qa", confirmAccept = true, confirmCount = 0;
const title = "Monitor privacy updates";
const messages = [{id: "qa-message", role: "user", content: title, created_at: "2026-09-06T08:00:00Z"},
  {id: "qa-reply", role: "assistant", content: "Synthetic assistant reply, not legal evidence.", created_at: "2026-09-06T08:00:00Z"},
  {id: "qa-message-two", role: "user", content: "Monitor workplace changes", created_at: "2026-09-06T09:00:00Z"}];

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
    else if (url.pathname === "/api/jobs") body = [];
    else if (url.pathname === "/api/assistant/context") body = {context: {entity: null}, persona: {quip_allowed: false}};
    else if (url.pathname === "/api/assistant/runtime") body = {display_name: "Local QA", ready: false, state: "stopped", selected_model: {display_name: "Synthetic"}, policy: {cloud_fallback: false, single_runtime: true}};
    else if (url.pathname === "/api/assistant/conversations") body = {id: "qa-conversation", draft: "", handoffs: [], messages, visibility: "personal"};
    else if (url.pathname === "/api/monitoring-context") {
      assert.equal(url.searchParams.get("kind"), "assistant");
      assert.equal(url.searchParams.get("id"), "qa-conversation");
      const message = messages.find(item => item.id === url.searchParams.get("message") && item.role === "user");
      assert.ok(message, "Message identifier was not preserved");
      body = {kind: "assistant", id: "qa-conversation", message_id: message.id, question: message.content, title: message.content,
        message_created_at: message.created_at, visibility: "personal", requires_confirmation: true, ai_calls: 0,
        source_url: null, evidence_url: null, reference_url: null, watches: [], more_watches: false};
    } else if (url.pathname === "/api/source-packs") body = {items: [{id: "fedlex-legislation", name: {en: "Synthetic enabled sources"}, subscription: {enabled: true}}]};
    else if (url.pathname === "/api/monitoring-topics" && request.method === "GET") body = [];
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
  for (const language of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) for (const width of [390,1440]) for (const permission of ["organization_admin", "viewer"]) {
    locale = language; role = permission; user = `${language}-${width}-${permission}`;
    await cdp.send("Emulation.setDeviceMetricsOverride", {width, height: 900, deviceScaleFactor: 1, mobile: width < 500});
    await cdp.send("Page.navigate", {url: `${base}/topics?locale=${locale}`});
    await waitFor(() => evaluate(cdp, `!!document.querySelector('.marvin-trigger') && !!document.querySelector('[name="topic-name"]') && document.documentElement.lang === ${JSON.stringify(locale)}`), "Topic screen not ready");
    await click('.marvin-trigger');
    await waitFor(() => evaluate(cdp, `document.querySelectorAll('[data-marvin-monitor]').length === 2`), "Saved user messages missing monitoring action while model is stopped");
    assert.equal(await evaluate(cdp, `document.querySelectorAll('.is-assistant [data-marvin-monitor]').length`), 0, "Assistant replies must not be proposed as monitoring goals");
    const selector = '[data-marvin-monitor] a';
    if (locale === "en-CH" && role === "organization_admin") {
      await mkdir(join(root, ".tmp"), {recursive: true});
      await evaluate(cdp, `document.querySelector('${selector}').scrollIntoView({block:'center'})`);
      const shot = await cdp.send("Page.captureScreenshot", {format: "png"});
      await writeFile(join(root, ".tmp", `marvin-monitor-${width}.png`), Buffer.from(shot.data, "base64"));
    }
    await click(selector);
    await waitFor(() => evaluate(cdp, `!!document.querySelector('[data-monitor-saved-question]') && !document.querySelector('.marvin-panel')`), "Personal message context did not open or companion blocked it");
    assert.ok(await evaluate(cdp, `location.search.includes('message=qa-message') && !location.search.includes('privacy') && !location.search.includes('workplace')`));
    assert.equal(await evaluate(cdp, `document.querySelector('[name="topic-name"]').value`), "", "Navigation silently copied private text");
    assert.ok(await evaluate(cdp, `document.querySelector('[data-monitor-saved-question]').innerText.includes('Monitor privacy updates') && !document.querySelector('[data-monitor-context]').innerText.includes('Synthetic assistant reply')`));
    assert.equal(await evaluate(cdp, `document.body.innerText.includes('monitorThis.')`), false);
    await click('[data-monitor-use]');
    await waitFor(() => evaluate(cdp, `document.querySelector('[name="topic-goal"]').value === 'Monitor privacy updates'`), "User explicitly selected message but goal was changed");
    assert.equal(await evaluate(cdp, `document.querySelector('[name="topic-concepts"]').value`), "", "Assistant invented matching terms");
    assert.ok(await evaluate(cdp, `document.documentElement.scrollWidth <= innerWidth + 1`), "Context overflowed");
    assert.equal(await evaluate(cdp, `!!document.querySelector('[data-topic-personal-note]')`), role === "viewer");
    // Same conversation, different message must not reuse the first message's cache.
    await click('.marvin-trigger');
    await waitFor(() => evaluate(cdp, `document.querySelectorAll('[data-marvin-monitor]').length === 2`), "Companion did not reopen");
    await click('[data-marvin-monitor] a[href*="message=qa-message-two"]');
    await waitFor(() => evaluate(cdp, `document.querySelector('[data-monitor-saved-question]')?.innerText.includes('Monitor workplace changes')`), "Second message reused the first private cache entry");
    assert.equal(await evaluate(cdp, `document.querySelector('[name="topic-goal"]').value`), "Monitor privacy updates", "New context overwrote existing unsaved goal");
    const beforeConfirm = confirmCount;
    confirmAccept = false;
    await click('[data-monitor-use]');
    await waitFor(() => Promise.resolve(confirmCount === beforeConfirm + 1), "Replacing a dirty draft did not require confirmation");
    assert.equal(await evaluate(cdp, `document.querySelector('[name="topic-goal"]').value`), "Monitor privacy updates", "Declined replacement discarded original draft");
    confirmAccept = true;
    await click('[data-monitor-use]');
    await waitFor(() => evaluate(cdp, `document.querySelector('[name="topic-goal"]').value === 'Monitor workplace changes'`), "Explicitly approved replacement failed");
  }
  assert.equal(requests.some(r => r.path.includes('/messages') || r.path.includes('/remark') || r.path.includes('/preview') || r.path.includes('/draft') || (r.path === '/api/monitoring-topics' && r.method !== 'GET')), false, "Navigation spent inference or changed monitoring");
  assert.deepEqual(exceptions, []);
  console.log("Marvin monitoring production UI: 20 five-locale mobile/desktop admin/viewer journeys pass explicit personal-user-message entry with local AI stopped, no assistant-reply CTA, drawer closure, private-text-free URLs, manual editable goal copy, empty matching terms, different-message cache isolation and dirty-draft protection. All APIs intercepted; no live model or shared monitoring writes.");
} catch (error) {
  console.error({locale, role, user, requests: requests.slice(-10), exceptions, text: cdp ? await evaluate(cdp, "document.body.innerText.slice(-2500)").catch(()=>"unavailable") : "none"});
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const ended = new Promise(resolve => child.once("exit", resolve));
    child.kill();
    await Promise.race([ended, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-marvin-monitor-browser-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
