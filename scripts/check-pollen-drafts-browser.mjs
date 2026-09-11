// Production UI with synthetic intercepted API responses; no live source or user data.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { pollenDraftCopy } from "../apps/web/lib/pollen-draft-copy.ts";
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
const server = spawn(process.execPath, [join(root, "node_modules/next/dist/bin/next"), "start", "-H", "127.0.0.1", "-p", String(port)],
  { cwd: join(root, "apps/web"), stdio: "ignore", windowsHide: true });
const profile = await mkdtemp(join(tmpdir(), "helvetic-pollen-reader-"));
const browser = spawn(chrome, ["--headless=new", "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"],
  { stdio: "ignore", windowsHide: true });
let cdp, locale = "en-CH", mode = "ready", organization = "org-a", delayFirst = false;
const requests = [], exceptions = [];
const audit = new AccessibilityAudit("pollen-drafts");
const config = station => ({ station_id: station, selections: [{ allergen: "birch", rules: [{ period: "observation_hourly", unit: "number/m3",
  threshold: { trigger_at_or_above: "12.500001", reset_at_or_below: "5" }, rapid_increase: { minimum_increase: "3", window_hours: 2 }, category_change: false }] },
  { allergen: "grasses", rules: [] }], timezone: "Europe/Zurich", delivery: { email: "off", digest_at: null, quiet_hours: null } });
const draft = (id, station) => ({ id, status: "draft", revision: 12, configuration: config(station), configuration_hash: "a".repeat(64) });
async function wait(check, message) {
  for (let n = 0; n < 150; n++) {
    if (await Promise.resolve().then(check).catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}
const text = () => evaluate(cdp, "document.querySelector('[data-pollen-drafts]')?.innerText || ''");
const click = selector => evaluate(cdp, `document.querySelector(${JSON.stringify(selector)}).click()`);
async function navigate() {
  await cdp.send("Page.navigate", { url: `${base}/pollen-watch?case=${Date.now()}` });
  await wait(async () => (await text()).includes(pollenDraftCopy[locale].title), "Reader not rendered");
}
try {
  await wait(async () => (await fetch(base)).ok, "Next production server did not start");
  let debugPort;
  await wait(async () => { debugPort = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]; return !!debugPort; }, "Chrome did not start");
  const target = await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: "PUT" }).then(r => r.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable"); await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) => exceptions.push(exceptionDetails.text));
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url); requests.push({ path: url.pathname, query: url.search, method: request.method });
    let code = 200, body = {};
    if (url.pathname === "/api/auth/session") body = { authenticated: mode !== "anonymous", anonymous_development: mode === "anonymous",
      user: mode === "anonymous" ? undefined : { id: "qa", email: "qa@example.invalid", name: "QA", locale },
      organization: { id: organization, name: organization }, role: "viewer", platform_admin: false };
    else if (url.pathname === "/api/health") body = { status: "ok", database: "synthetic", apertus: { configured: false }, firecrawl: { configured: false } };
    else if (url.pathname.startsWith("/api/monitoring-subjects")) {
      if (["disabled", "revoked", "error", "missing"].includes(mode)) {
        code = mode === "revoked" ? 403 : mode === "error" ? 503 : 404;
        body = { code: { disabled: "monitoring_not_enabled", revoked: "membership_required", error: "unavailable", missing: "subject_not_found" }[mode] };
      } else if (url.pathname === "/api/monitoring-subjects") body = mode === "empty" || organization === "org-b" ? { items: [], next_cursor: null }
        : url.searchParams.has("cursor") ? { items: [draft("b", "PZH")], next_cursor: null } : { items: [draft("a", "PBS")], next_cursor: "a" };
      else {
        const isA = url.pathname.split("/")[3] === "a";
        if (delayFirst && isA) await sleep(800);
        const selected = draft(isA ? "a" : "b", isA ? "PBS" : "PZH");
        body = url.pathname.endsWith("/history") ? { items: [{ revision: url.searchParams.has("before_revision") ? 11 : 12,
          configuration: config("PGE"), configuration_hash: "b".repeat(64) }], next_before_revision: url.searchParams.has("before_revision") ? null : 12 } : selected;
      }
    } else if (url.pathname === "/api/jobs") body = [];
    else { code = 503; body = { detail: "Synthetic endpoint unavailable" }; }
    await cdp.send("Fetch.fulfillRequest", { requestId, responseCode: code,
      responseHeaders: [{ name: "Content-Type", value: "application/json" }, { name: "Cache-Control", value: "private, no-store" }],
      body: Buffer.from(JSON.stringify(body)).toString("base64") }).catch(() => {});
  });
  await cdp.send("Fetch.enable", { patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }] });
  for (const language of Object.keys(pollenDraftCopy)) {
    locale = language;
    await cdp.send("Emulation.setDeviceMetricsOverride", { width: locale === "en-CH" ? 1280 : 390, height: 900, deviceScaleFactor: 1, mobile: false });
    await navigate();
    await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-drafts] button[aria-pressed]')"), "Draft list missing");
    // A real keyboard activation, not a synthetic click event.
    await evaluate(cdp, "document.querySelector('[data-pollen-drafts] button[aria-pressed]').focus()");
    await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, text: "\r", unmodifiedText: "\r" });
    await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
    await wait(async () => (await text()).includes("12.500001"), "Exact saved threshold missing");
    await wait(() => evaluate(cdp, "document.activeElement?.tagName === 'H2'"), "Selection did not focus its settings heading");
    if (locale !== "en-CH") assert.ok(await evaluate(cdp, "document.activeElement.getBoundingClientRect().top >= 72"), "Focused heading is hidden by the mobile header");
    assert.ok((await text()).includes(pollenDraftCopy[locale].blocked));
    assert.equal(await evaluate(cdp, "document.querySelector('[aria-describedby=\"pollen-start-blocked\"]').disabled"), true);
    await audit.check(cdp, locale, "[data-pollen-drafts] details");
    assert.equal(await evaluate(cdp, "document.documentElement.scrollWidth <= innerWidth"), true);
  }
  locale = "en-CH"; await navigate();
  await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-drafts] ul button')"), "List not ready");
  await click('[data-pollen-drafts] section[aria-label="Pollen Watch drafts"] > button');
  await wait(() => evaluate(cdp, "document.querySelectorAll('[data-pollen-drafts] ul button').length === 2"), "List continuation failed");
  delayFirst = true;
  await click('[data-pollen-drafts] li:first-child button');
  await click('[data-pollen-drafts] li:last-child button');
  await wait(() => evaluate(cdp, "document.querySelector('[data-pollen-drafts] button[aria-pressed=true]')?.innerText.includes('PZH')"), "Newest selection failed");
  await sleep(1000);
  assert.ok(await evaluate(cdp, "document.querySelector('[data-pollen-drafts] button[aria-pressed=true]').innerText.includes('PZH')"));
  await click('[data-pollen-drafts] section[aria-label="Saved settings"] > button:last-child');
  await wait(() => evaluate(cdp, "document.querySelectorAll('[data-pollen-drafts] details').length === 2"), "History continuation failed");
  await click('[data-pollen-drafts] details:last-of-type summary');
  assert.ok((await text()).includes("PGE"));
  await audit.check(cdp, "expanded-history", "[data-pollen-drafts] details[open]");
  await mkdir(join(root, "test-results"), { recursive: true });
  const screenshot = await cdp.send("Page.captureScreenshot", { format: "png" });
  await writeFile(join(root, "test-results/pollen-drafts-mobile.png"), Buffer.from(screenshot.data, "base64"));
  mode = "revoked";
  await click('[data-pollen-drafts] > button');
  await wait(async () => (await text()).includes(pollenDraftCopy[locale].access), "Revocation not shown");
  assert.ok(!(await text()).includes("12.500001"));
  for (const state of ["disabled", "missing", "error", "empty"]) {
    mode = state; await navigate();
    await wait(async () => (await text()).includes(pollenDraftCopy[locale][state === "error" ? "failed" : state]), `Missing ${state} state`);
    assert.ok(!(await text()).includes("12.500001"));
  }
  mode = "ready"; organization = "org-b"; await navigate();
  await wait(async () => (await text()).includes(pollenDraftCopy[locale].empty), "Workspace changed but old list remained");
  mode = "anonymous"; const requestStart = requests.length; await navigate();
  await wait(async () => (await text()).includes(pollenDraftCopy[locale].access), "Anonymous state missing");
  assert.equal(requests.slice(requestStart).filter(r => r.path.startsWith("/api/monitoring-subjects")).length, 0);
  assert.equal(requests.filter(r => r.path.startsWith("/api/monitoring-subjects") && r.method !== "GET").length, 0);
  assert.deepEqual(exceptions, []);
  audit.finish(6);
  console.log("Pollen reader: five locales, desktop/mobile, keyboard activation, exact decimals, list/history pagination, obsolete responses, revoked/default-off/missing/error/empty/anonymous/workspace isolation passed. Synthetic APIs only; no live acceptance.");
} catch (error) {
  console.error({ locale, mode, requests: requests.slice(-12), exceptions,
    page: cdp ? await text().catch(() => "unavailable") : null,
    active: cdp ? await evaluate(cdp, "document.activeElement?.outerHTML").catch(() => null) : null });
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) { const stopped = new Promise(done => child.once("exit", done)); child.kill(); await Promise.race([stopped, sleep(2000)]); }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-pollen-reader-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
