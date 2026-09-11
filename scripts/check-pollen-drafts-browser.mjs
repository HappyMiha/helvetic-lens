// Production UI with synthetic intercepted API responses; no live source or user data.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { pollenDraftCopy } from "../apps/web/lib/pollen-draft-copy.ts";
import { pollenCreateCopy } from "../apps/web/lib/pollen-create-copy.ts";
import { pollenDeleteCopy } from "../apps/web/lib/pollen-delete-copy.ts";
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
let manager = false, previewError = false, loseFirstSave = false, dialogAccept = false;
const created = new Map();
const deleted = new Set(), revisions = new Map(), dialogs = [];
let deleteMode = "success", selectedStatus = "draft";
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
  await cdp.send("Network.setCookie", { name: "helvetic_lens_csrf", value: "synthetic-pollen-csrf", url: base });
  cdp.on("Page.javascriptDialogOpening", async ({ message }) => {
    dialogs.push(message);
    await cdp.send("Page.handleJavaScriptDialog", { accept: dialogAccept });
  });
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) => exceptions.push(exceptionDetails.text));
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url); const payload = request.postData ? JSON.parse(request.postData) : null;
    requests.push({ path: url.pathname, query: url.search, method: request.method, payload, headers: request.headers });
    let code = 200, body = {};
    if (url.pathname === "/api/auth/session") body = { authenticated: mode !== "anonymous", anonymous_development: mode === "anonymous",
      user: mode === "anonymous" ? undefined : { id: "qa", email: "qa@example.invalid", name: "QA", locale },
      organization: { id: organization, name: organization }, role: manager ? "organization_admin" : "viewer", platform_admin: false };
    else if (url.pathname === "/api/health") body = { status: "ok", database: "synthetic", apertus: { configured: false }, firecrawl: { configured: false } };
    else if (url.pathname.startsWith("/api/monitoring-subjects")) {
      if (["disabled", "revoked", "error", "missing"].includes(mode)) {
        code = mode === "revoked" ? 403 : mode === "error" ? 503 : 404;
        body = { code: { disabled: "monitoring_not_enabled", revoked: "membership_required", error: "unavailable", missing: "subject_not_found" }[mode] };
      } else if (deleted.has(url.pathname.split("/")[3])) {
        code = 404; body = { code: "subject_not_found" };
      } else if (request.method === "DELETE") {
        await sleep(200);
        const id = url.pathname.split("/")[3];
        if (deleteMode === "conflict") { revisions.set(id, 13); code = 409; body = { code: "subject_revision_conflict" }; }
        else if (deleteMode === "revoked") { code = 403; body = { code: "membership_required" }; }
        else { deleted.add(id); code = deleteMode === "uncertain" ? 503 : 204; body = { code: "unavailable" }; }
      } else if (url.pathname === "/api/monitoring-subjects/preview") {
        if (previewError) { code = 422; body = { code: "invalid_input" }; }
        else body = { configuration: payload.configuration, configuration_hash: "c".repeat(64), preview_kind: "configuration_only", start_available: false,
          coverage: "unverified", observations: [], forecasts: [] };
      } else if (url.pathname === "/api/monitoring-subjects" && request.method === "POST") {
        if (!created.has(payload.request_key)) created.set(payload.request_key, { ...draft(`created-${created.size}`, payload.configuration.station_id),
          revision: 1, configuration: payload.configuration });
        if (loseFirstSave) { loseFirstSave = false; code = 503; body = { code: "unavailable" }; }
        else { code = 201; body = created.get(payload.request_key); }
      } else if (url.pathname === "/api/monitoring-subjects") {
        const remaining = [draft("a", "PBS"), draft("b", "PZH")].filter(d => !deleted.has(d.id));
        body = mode === "empty" || organization === "org-b" ? { items: [], next_cursor: null }
          : url.searchParams.has("cursor") ? { items: remaining.slice(1), next_cursor: null } : { items: remaining.slice(0, 1), next_cursor: remaining.length > 1 ? remaining[0].id : null };
      }
      else {
        const isA = url.pathname.split("/")[3] === "a";
        if (delayFirst && isA) await sleep(800);
        const selected = [...created.values()].find(d => d.id === url.pathname.split("/")[3]) || draft(isA ? "a" : "b", isA ? "PBS" : "PZH");
        selected.revision = revisions.get(selected.id) || selected.revision;
        selected.status = selectedStatus;
        body = url.pathname.endsWith("/history") ? { items: [{ revision: url.searchParams.has("before_revision") ? 11 : 12,
          configuration: config("PGE"), configuration_hash: "b".repeat(64) }], next_before_revision: url.searchParams.has("before_revision") ? null : 12 } : selected;
      }
    } else if (url.pathname === "/api/jobs") body = [];
    else { code = 503; body = { detail: "Synthetic endpoint unavailable" }; }
    await cdp.send("Fetch.fulfillRequest", { requestId, responseCode: code,
      responseHeaders: [{ name: "Content-Type", value: "application/json" }, { name: "Cache-Control", value: "private, no-store" }],
      body: code === 204 ? "" : Buffer.from(JSON.stringify(body)).toString("base64") }).catch(() => {});
  });
  await cdp.send("Fetch.enable", { patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }] });
  for (const language of Object.keys(pollenDraftCopy)) {
    locale = language;
    await cdp.send("Emulation.setDeviceMetricsOverride", { width: locale === "en-CH" ? 1280 : 390, height: 900, deviceScaleFactor: 1, mobile: false });
    await navigate();
    await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-drafts] button[aria-pressed]')"), "Draft list missing");
    assert.ok(!(await text()).includes(pollenCreateCopy[locale].create), "Viewer was offered creation");
    // A real keyboard activation, not a synthetic click event.
    await evaluate(cdp, "document.querySelector('[data-pollen-drafts] button[aria-pressed]').focus()");
    await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, text: "\r", unmodifiedText: "\r" });
    await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
    await wait(async () => (await text()).includes("12.500001"), "Exact saved threshold missing");
    assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-delete]')"), false, "Viewer was offered deletion");
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
  const fill = (name, value) => evaluate(cdp, `(() => { const input=document.querySelector(${JSON.stringify(`[name="${name}"]`)}); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(value)}); input.dispatchEvent(new Event('input',{bubbles:true})); })()`);
  const button = label => evaluate(cdp, `Array.from(document.querySelectorAll('[data-pollen-drafts] button')).find(b => b.textContent === ${JSON.stringify(label)}).click()`);
  const posts = path => requests.filter(r => r.path === path && r.method === "POST");
  mode = "ready"; organization = "org-a"; manager = true; delayFirst = false;
  for (const language of Object.keys(pollenCreateCopy)) {
    locale = language; const copy = pollenCreateCopy[locale];
    await navigate();
    await wait(async () => (await text()).includes(copy.create), "Manager creation entry missing");
    await button(copy.create);
    await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-create] input')"), "Creation form missing");
    await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 });
    await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 });
    assert.equal(await evaluate(cdp, "document.activeElement?.getAttribute('name')"), "pollen-station");
    await fill("pollen-station", "PBS");
    await click('[name="allergen-birch"]'); await click('[name="allergen-grasses"]');
    await click('[name="rule-birch-observation_hourly"]');
    await fill("trigger-birch-observation_hourly", "12.500001");
    await fill("reset-birch-observation_hourly", "5");
    await click('[name="rapid-birch-observation_hourly"]');
    await fill("increase-birch-observation_hourly", "3.000001");
    await fill("window-birch-observation_hourly", "2");
    await click('[name="rule-birch-forecast_instant"]');
    await fill("trigger-birch-forecast_instant", "20"); await fill("reset-birch-forecast_instant", "4");
    previewError = true; await button(copy.preview);
    await wait(async () => (await text()).includes(copy.invalid), "Server validation was not shown");
    previewError = false; await button(copy.preview);
    await wait(async () => (await text()).includes(copy.checked), "Configuration-only preview missing");
    assert.equal(posts("/api/monitoring-subjects").length, created.size * 2);
    await fill("trigger-birch-observation_hourly", "13.500001");
    assert.ok(!(await text()).includes(copy.checked));
    await button(copy.preview);
    await wait(async () => (await text()).includes(copy.checked), "Edited configuration not checked");
    await audit.check(cdp, `create-${locale}`, "[data-pollen-create] form");
    if (locale === "en-CH") {
      await evaluate(cdp, "document.querySelector('[name=\"trigger-birch-observation_hourly\"]').scrollIntoView({block:'center'})");
      const formImage = await cdp.send("Page.captureScreenshot", { format: "png" });
      await writeFile(join(root, "test-results/pollen-create-mobile.png"), Buffer.from(formImage.data, "base64"));
    }
    assert.equal(await evaluate(cdp, "document.documentElement.scrollWidth <= innerWidth"), true);
    loseFirstSave = true;
    const oldPosts = posts("/api/monitoring-subjects").length;
    await evaluate(cdp, `(() => {const b=Array.from(document.querySelectorAll('[data-pollen-create] button')).find(b => b.textContent === ${JSON.stringify(copy.save)}); b.click(); b.click();})()`);
    await wait(async () => (await text()).includes(copy.uncertain), "Lost save response was not retained");
    assert.equal(posts("/api/monitoring-subjects").length, oldPosts + 1);
    assert.equal(await evaluate(cdp, "document.querySelector('[data-pollen-create] form > fieldset').disabled"), true);
    await button(copy.save);
    await wait(async () => (await text()).includes(copy.saved), "Idempotent save retry failed");
    const [first, retry] = posts("/api/monitoring-subjects").slice(-2);
    assert.deepEqual(first.payload, retry.payload);
    assert.equal(first.payload.configuration.selections[0].rules[0].threshold.trigger_at_or_above, "13.500001");
    assert.equal(first.payload.configuration.selections[0].rules[0].rapid_increase.minimum_increase, "3.000001");
    assert.equal(first.payload.configuration.selections[0].rules[1].period, "forecast_instant");
    assert.equal(first.payload.configuration.delivery.email, "off");
    assert.equal(Object.entries(first.headers).find(([key]) => key.toLowerCase() === "x-csrf-token")?.[1], "synthetic-pollen-csrf");
    await button(copy.view);
    await wait(async () => (await text()).includes("13.500001"), "Saved draft navigation failed");
  }
  assert.equal(created.size, 5);
  const copy = pollenCreateCopy[locale];
  await button(copy.create); await fill("pollen-station", "PBS");
  dialogAccept = false; await button(copy.cancel); assert.ok(await evaluate(cdp, "!!document.querySelector('[data-pollen-create]')"));
  dialogAccept = true; await button(copy.cancel);
  await wait(() => evaluate(cdp, "!document.querySelector('[data-pollen-create]')"), "Confirmed discard failed");
  await button(copy.create); await fill("pollen-station", "PBS"); await click('[name="allergen-birch"]');
  mode = "revoked"; await button(copy.preview);
  await wait(async () => (await text()).includes(pollenDraftCopy[locale].access), "Creation access revocation was not shown");
  assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-create]')"), false);
  const deletes = () => requests.filter(r => r.method === "DELETE");
  async function selectForDelete() {
    await navigate();
    await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-drafts] li:first-child button')"), "Deletion fixture list missing");
    await click('[data-pollen-drafts] li:first-child button');
    await wait(async () => (await text()).includes("12.500001"), "Deletion fixture settings missing");
  }
  mode = "ready";
  for (const language of Object.keys(pollenDeleteCopy)) {
    locale = language; deleted.clear(); revisions.clear(); deleteMode = "success";
    await selectForDelete(); const removal = pollenDeleteCopy[locale];
    const count = deletes().length; dialogAccept = false; await button(removal.remove);
    assert.equal(deletes().length, count);
    assert.equal(dialogs.at(-1), removal.confirm.replace("{station}", "PBS").replace("{revision}", "12"));
    dialogAccept = true;
    await evaluate(cdp, "(() => {const button=document.querySelector('[data-pollen-delete]'); button.click(); button.click();})()");
    await wait(async () => (await text()).includes(removal.deleted), "Deletion success was not shown");
    assert.equal(deletes().length, count + 1);
    assert.deepEqual(deletes().at(-1).payload, { expected_revision: 12 });
    assert.equal(Object.entries(deletes().at(-1).headers).find(([key]) => key.toLowerCase() === "x-csrf-token")?.[1], "synthetic-pollen-csrf");
    assert.ok(!(await text()).includes("12.500001"));
    assert.equal(await evaluate(cdp, "document.querySelectorAll('[data-pollen-drafts] details').length"), 0);
    await audit.check(cdp, `deleted-${locale}`, "[data-pollen-drafts] p[role=status]");
  }
  locale = "en-CH"; deleted.clear(); revisions.clear(); deleteMode = "conflict";
  await selectForDelete(); const removal = pollenDeleteCopy[locale];
  await button(removal.remove);
  await wait(async () => (await text()).includes(removal.conflict), "Revision conflict missing");
  assert.equal(await evaluate(cdp, "document.querySelector('[data-pollen-delete]').disabled"), true);
  const conflictCount = deletes().length; await button(removal.remove); assert.equal(deletes().length, conflictCount);
  deleteMode = "success"; await button(removal.reload);
  await wait(() => evaluate(cdp, "document.querySelector('[data-pollen-drafts] section[aria-label=\"Saved settings\"] h3')?.textContent.includes('13')"), "Changed revision was not read");
  await button(removal.remove);
  await wait(async () => (await text()).includes(removal.deleted), "Fresh-revision deletion failed");
  assert.equal(deletes().at(-1).payload.expected_revision, 13);
  assert.equal(dialogs.at(-1), removal.confirm.replace("{station}", "PBS").replace("{revision}", "13"));
  deleted.clear(); revisions.clear(); deleteMode = "uncertain"; await selectForDelete(); await button(removal.remove);
  await wait(async () => (await text()).includes(removal.uncertain), "Uncertain deletion was treated as success");
  await button(removal.remove);
  await wait(async () => (await text()).includes(pollenDraftCopy[locale].missing), "Missing after uncertain deletion was not distinguished");
  assert.ok(!(await text()).includes(removal.deleted));
  assert.ok(!(await text()).includes("12.500001"));
  assert.deepEqual(deletes().at(-1).payload, deletes().at(-2).payload);
  deleted.clear(); deleteMode = "revoked"; await selectForDelete(); await button(removal.remove);
  await wait(async () => (await text()).includes(pollenDraftCopy[locale].access), "Deletion revocation was not shown");
  assert.ok(!(await text()).includes("12.500001"));
  selectedStatus = "active"; deleteMode = "success"; await selectForDelete();
  assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-delete]')"), false, "Active monitor was offered draft deletion");
  assert.equal(requests.filter(r => r.path.endsWith("/start")).length, 0);
  assert.deepEqual(exceptions, []);
  audit.finish(16);
  console.log("Pollen reader: five locales, desktop/mobile, keyboard activation, exact decimals, list/history pagination, obsolete responses, revoked/default-off/missing/error/empty/anonymous/workspace isolation passed. Synthetic APIs only; no live acceptance.");
  console.log("Pollen creation: five locales, keyboard entry, multi-allergen observation/forecast rules, invalid preview, preview invalidation, CSRF, busy guard, lost-response same-key retry, saved navigation, confirmed/cancelled discard and revoked access passed. Email off; no Start requests.");
  console.log("Pollen deletion: five localized exact station/revision confirmations, cancel/success, duplicate clicks, CSRF, private-history removal, conflict requiring fresh revision, uncertain response then missing, revoked access and active/viewer denial passed.");
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
