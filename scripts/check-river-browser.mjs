// Built frontend with intercepted synthetic sources/accounts; no production mutations.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { riverCopy } from "../apps/web/lib/river-copy.ts";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";

const root = resolve(import.meta.dirname, "..");
const chrome = [process.env.CHROME_BIN, "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "/usr/bin/google-chrome"].filter(Boolean).find(existsSync);
assert.ok(chrome);
const reserve = createServer();
await new Promise(done => reserve.listen(0, "127.0.0.1", done));
const port = reserve.address().port;
await new Promise(done => reserve.close(done));
const base = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, [join(root, "node_modules/next/dist/bin/next"), "start", "-H", "127.0.0.1", "-p", String(port)], { cwd: join(root, "apps/web"), stdio: "ignore", windowsHide: true });
const profile = await mkdtemp(join(tmpdir(), "helvetic-river-qa-"));
const browser = spawn(chrome, ["--headless=new", "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore", windowsHide: true });
let cdp, locale = "en-CH", manager = true, monitor = null, previewReady = true;
const exceptions = [], mutations = [];
const audit = new AccessibilityAudit("river-watch");
const station = { id: "2289", name: "Basel, Rheinhalle", waterbody: "Rhein", source_url: "https://data.bafu.admin.ch/dataproduct-water-observations" };
const sample = { metric: "W", timestamp: new Date().toISOString(), value: "244.9", unit: "m", quality: "provisional", datum: "FOEN:2289:m ü.M.", aggregation: "live_observation", source_url: station.source_url };
const coverage = { W: { status: "current", sample }, WT: { status: "unknown", sample: null } };
let changes = [];
async function wait(check, message) { for (let i = 0; i < 200; i++) { if (await Promise.resolve().then(check).catch(() => false)) return; await sleep(100); } throw new Error(message); }
const text = () => evaluate(cdp, "document.querySelector('[data-river-watch]')?.innerText || ''");
async function button(name) { await wait(() => evaluate(cdp, `!!Array.from(document.querySelectorAll('[data-river-watch] button')).find(b=>b.textContent.trim()===${JSON.stringify(name)}&&!b.disabled)`), `Missing enabled button ${name}`); await evaluate(cdp, `Array.from(document.querySelectorAll('[data-river-watch] button')).find(b=>b.textContent.trim()===${JSON.stringify(name)}&&!b.disabled).click()`); }
async function field(label, value, select = false) { await evaluate(cdp, `(()=>{const l=Array.from(document.querySelectorAll('form label')).find(l=>l.firstChild.textContent.trim()===${JSON.stringify(label)}&&l.querySelector(${JSON.stringify(select ? "select" : "input")}));const e=l.querySelector(${JSON.stringify(select ? "select" : "input")});Object.getOwnPropertyDescriptor(${select ? "HTMLSelectElement" : "HTMLInputElement"}.prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event(${JSON.stringify(select ? "change" : "input")},{bubbles:true}));})()`); }
async function navigate() { await cdp.send("Page.navigate", { url: `${base}/river-watch?qa=${Date.now()}` }); await wait(async () => (await text()).includes(riverCopy[locale].title), "River page did not load"); }
try {
  await wait(async () => (await fetch(base)).ok, "Next did not start");
  let debugPort;
  await wait(async () => { debugPort = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]; return !!debugPort; }, "Chrome did not start");
  const target = await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: "PUT" }).then(r => r.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable"); await cdp.send("Runtime.enable");
  await cdp.send("Network.setCookie", { name: "helvetic_lens_csrf", value: "synthetic-river", url: base });
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) => exceptions.push(exceptionDetails.text));
  cdp.on("Page.javascriptDialogOpening", () => cdp.send("Page.handleJavaScriptDialog", { accept: true }));
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url), payload = request.postData ? JSON.parse(request.postData) : null;
    let code = 200, body = {};
    if (url.pathname === "/api/auth/session") body = { authenticated: true, user: { id: "qa", name: "River QA", email: "river@example.invalid", locale }, organization: { id: "private-qa", name: "Private QA" }, role: manager ? "organization_admin" : "viewer", platform_admin: false, onboarding_required: false };
    else if (url.pathname === "/api/health") body = { status: "ok", database: "synthetic", apertus: { configured: false }, firecrawl: { configured: false } };
    else if (url.pathname === "/api/jobs") body = [];
    else if (url.pathname.startsWith("/api/river-watch")) {
      if (request.method !== "GET") mutations.push({ path: url.pathname, method: request.method, payload });
      if (url.pathname.endsWith("/stations")) body = { stations: [station], health: "ready" };
      else if (url.pathname.endsWith("/preview")) body = { station, coverage, start_available: previewReady };
      else if (url.pathname.endsWith("/monitors") && request.method === "POST") { monitor = { id: "river-qa", configuration: payload.configuration, status: "draft", version: 1, revision: 1, health: "waiting", state: {}, last_poll_at: null }; body = monitor; code = 201; }
      else if (url.pathname.endsWith("/monitors")) body = { items: monitor ? [monitor] : [] };
      else if (url.pathname.endsWith("/command")) { assert.equal(payload.expected_version, monitor.version); monitor.version++; monitor.status = { start: "active", pause: "paused", resume: "active", archive: "archived" }[payload.action]; monitor.state = { coverage }; monitor.health = "partial_unknown"; body = monitor; }
      else if (url.pathname.endsWith("/changes")) body = { items: changes, next_before: null };
      else if (url.pathname.endsWith("/review")) { changes[0].decision = payload.decision; changes[0].review_version++; body = changes[0]; }
      else if (url.pathname.endsWith("/measurements")) body = { items: [sample], next: null };
      else if (url.pathname.endsWith("/revisions")) body = { items: [{ revision: monitor.revision, configuration: monitor.configuration }], next_before: null };
      else if (request.method === "PATCH") { assert.equal(monitor.status, "paused"); monitor.configuration = payload.configuration; monitor.version++; monitor.revision++; body = monitor; }
      else if (request.method === "DELETE") { monitor = null; code = 204; }
      else body = monitor;
    } else { code = 503; body = { code: "unavailable" }; }
    await cdp.send("Fetch.fulfillRequest", { requestId, responseCode: code, responseHeaders: [{ name: "Content-Type", value: "application/json" }, { name: "Cache-Control", value: "no-store" }], body: code === 204 ? "" : Buffer.from(JSON.stringify(body)).toString("base64") }).catch(() => {});
  });
  await cdp.send("Fetch.enable", { patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }] });
  await navigate(); const c = riverCopy[locale];
  await button(c.create); await field(c.name, "Basel river"); await field(c.search, "Basel"); await field(c.station, "2289", true); await button(c.add); await field(c.threshold, "245");
  await button(c.preview); await wait(async () => (await text()).includes("244.9"), "Realistic source preview missing");
  assert.ok((await text()).includes(c.unknown));
  await audit.check(cdp, "configuration-preview", "form");
  await button(c.save); await wait(() => monitor?.status === "draft", "Draft not saved");
  await button(c.preview); await button(c.start); await wait(() => monitor?.status === "active", "Monitor did not start");
  changes = [{ id: "change-1", development_id: "a".repeat(64), sequence: 1, revision: 1, kind: "danger_escalation", priority: 1, review_version: 0, decision: null, evidence: { sample: { ...sample, metric: "danger", value: "3", unit: "official_level", datum: null }, baseline: null, rule: null, evaluated_value: "3", recovered: false } }];
  await button(c.refresh); await wait(async () => (await text()).includes(c.danger_escalation), "Danger development missing");
  await button(c.reviewed); await wait(() => changes[0].decision === "reviewed", "Review not saved");
  await button(c.measurements); await button(c.settings);
  await audit.check(cdp, "active-history-review", "[data-river-watch]");
  await button(c.pause); await button(c.edit); await field(c.name, "Basel updated"); await button(c.preview); await button(c.saveEdit);
  await wait(() => monitor?.revision === 2, "Edit did not create revision");
  previewReady = false; await button(c.preview);
  assert.equal(await evaluate(cdp, `Array.from(document.querySelectorAll('[data-river-watch] button')).find(b=>b.textContent.trim()===${JSON.stringify(c.resume)}).disabled`), true);
  previewReady = true; await button(c.preview); await button(c.resume); await button(c.archive);
  for (const language of Object.keys(riverCopy)) {
    locale = language; await cdp.send("Emulation.setDeviceMetricsOverride", { width: language === "en-CH" ? 1280 : 390, height: 900, deviceScaleFactor: 1, mobile: false });
    await navigate(); await wait(async () => (await text()).includes("Basel updated"), "Saved monitor missing");
    await evaluate(cdp, "Array.from(document.querySelectorAll('[data-river-watch] nav button')).find(b=>b.textContent.includes('Basel updated')).click()");
    await wait(async () => (await text()).includes(riverCopy[locale].changes), "Localized detail missing");
    assert.equal(await evaluate(cdp, "document.documentElement.scrollWidth <= innerWidth + 1"), true, `Overflow ${locale}`);
    await audit.check(cdp, `reader-${locale}`, "[data-river-watch]");
  }
  manager = false; await navigate(); await wait(async () => (await text()).includes(riverCopy[locale].readonly), "Viewer explanation missing");
  assert.equal(await evaluate(cdp, `Array.from(document.querySelectorAll('[data-river-watch] button')).some(b=>b.textContent===${JSON.stringify(riverCopy[locale].create)})`), false);
  assert.ok(mutations.every(r => !JSON.stringify(r.payload).includes("email_consent")));
  assert.deepEqual(exceptions, []); audit.finish(7);
  console.log("River browser: preview/save/start/priority/review/history/pause/edit/resume/archive, five locales, mobile and viewer gates passed.");
} catch (error) {
  console.error(JSON.stringify({ text: cdp ? await text().catch(() => "") : "", mutations, exceptions }));
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) { const stopped = new Promise(done => child.once("exit", done)); child.kill(); await Promise.race([stopped, sleep(2000)]); }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir())); assert.ok(basename(profile).startsWith("helvetic-river-qa-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
