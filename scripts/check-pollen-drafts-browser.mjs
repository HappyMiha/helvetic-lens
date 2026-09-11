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
import { pollenEditCopy } from "../apps/web/lib/pollen-edit-copy.ts";
import { pollenDeliveryCopy } from "../apps/web/lib/pollen-delivery-copy.ts";
import { pollenRecoveryCopy } from "../apps/web/lib/pollen-recovery-copy.ts";
import { pollenBackupCopy } from "../apps/web/lib/pollen-backup-copy.ts";
import { pollenStationCopy } from "../apps/web/lib/pollen-station-copy.ts";
import { pollenRuntimeCopy } from "../apps/web/lib/pollen-runtime-copy.ts";
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
let editMode = "success", editFixture = false, unsupportedEdit = false;
let live = false, liveLost = false, liveReady = true;
let liveRuntime = { version: 0, run_id: null, health: "waiting", email_consent: false, muted: false };
let liveEntries = [];
const liveCommands = new Map();
const liveSample = (value, forecast = false) => ({ series: { source_id: "synthetic-browser-source", method_version: "synthetic-browser-v1", station_id: "PBS", allergen: "birch", period: forecast ? "forecast_instant" : "observation_hourly", unit: "number/m3", forecast: forecast ? { issue_at: "2026-09-11T00:00:00Z", model: "synthetic" } : null }, value, valid_at: forecast ? "2026-09-12T08:00:00Z" : "2026-09-11T08:00:00Z", fetched_at: "2026-09-11T08:10:00Z", fresh_until: "2026-09-12T10:00:00Z", quality: value === null ? "missing" : "usable", source_revision: 1, artifact_hashes: ["a".repeat(64)], policy_version: "synthetic" });
const updated = new Map(), editHistory = new Map();
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
async function navigateDocument(url) {
  await evaluate(cdp, "window.__pollenOldDocument = true");
  await cdp.send("Page.navigate", { url });
  await wait(() => evaluate(cdp, `!window.__pollenOldDocument && location.search === ${JSON.stringify(new URL(url).search)}`), "New document did not replace the previous page");
}
async function reloadDocument() {
  await evaluate(cdp, "window.__pollenOldDocument = true");
  await cdp.send("Page.reload");
  await wait(() => evaluate(cdp, "!window.__pollenOldDocument"), "Reload did not replace the previous document");
}
async function navigate() {
  await navigateDocument(`${base}/pollen-watch?case=${Date.now()}`);
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
      } else if (url.pathname === "/api/monitoring-subjects/today") {
        body = { items: live ? liveEntries.filter(entry => !entry.review || ["continue", "action_required"].includes(entry.review.decision)).map(entry => ({ id: entry.id, subject_id: "a", station_id: "PBS", allergen: "birch", reasons: entry.reasons })) : [], next_cursor: null };
      } else if (live && url.pathname.endsWith("/commands")) {
        if (liveCommands.has(payload.request_key)) body = liveCommands.get(payload.request_key);
        else {
          assert.equal(payload.expected_version, liveRuntime.version);
          liveRuntime = { ...liveRuntime, version: liveRuntime.version + 1, email_consent: payload.email_consent || false };
          if (["start", "resume"].includes(payload.action)) { selectedStatus = "active"; liveRuntime.run_id = `run-${liveRuntime.version}`; }
          if (payload.action === "pause") selectedStatus = "paused";
          if (payload.action === "archive") selectedStatus = "archived";
          if (payload.action === "mute") liveRuntime.muted = true;
          if (payload.action === "unmute") liveRuntime.muted = false;
          body = { ...draft("a", "PBS"), status: selectedStatus, runtime: liveRuntime };
          liveCommands.set(payload.request_key, body);
          if (liveLost) { liveLost = false; code = 503; body = { code: "unavailable" }; }
        }
      } else if (live && url.pathname.endsWith("/review")) {
        const entry = liveEntries.find(entry => entry.id === url.pathname.split("/")[5]);
        assert.equal(payload.expected_version, entry.review?.version || 0);
        entry.review = { decision: payload.decision, version: payload.expected_version + 1 };
        body = entry.review;
      } else if (live && url.pathname.endsWith("/reviews")) {
        body = { items: [{ version: 1, decision: "reviewed", created_at: "2026-09-11T09:00:00Z" }], next_before_version: null };
      } else if (request.method === "PATCH") {
        await sleep(200);
        const id = url.pathname.split("/")[3];
        if (editMode === "conflict") { revisions.set(id, 13); code = 409; body = { code: "subject_revision_conflict" }; }
        else if (editMode === "revoked") { code = 403; body = { code: "membership_required" }; }
        else if (editMode === "unchanged") { code = 503; body = { code: "unavailable" }; }
        else {
          const revision = { ...draft(id, "PBS"), revision: payload.expected_revision + 1, configuration: payload.configuration, configuration_hash: "c".repeat(64) };
          updated.set(id, revision); editHistory.set(id, [revision]);
          body = revision;
          if (editMode === "lost" || editMode === "later") {
            code = 503; body = { code: "unavailable" };
            if (editMode === "later") updated.set(id, { ...revision, revision: revision.revision + 1, configuration: config("PGE"), configuration_hash: "d".repeat(64) });
          }
        }
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
        const id = url.pathname.split("/")[3];
        const selected = structuredClone(updated.get(id) || [...created.values()].find(d => d.id === id) || draft(isA ? "a" : "b", isA ? "PBS" : "PZH"));
        if (editFixture && !updated.has(id)) {
          Object.assign(selected.configuration, { contract_version: 1, template_version: 1, template_id: "pollen-watch" });
          selected.configuration.delivery = { email: "daily_digest", digest_at: "08:30", quiet_hours: { start: "22:00", end: "07:00" } };
          if (unsupportedEdit) selected.configuration.selections[0].rules[0].future_rule_setting = true;
        }
        selected.revision = revisions.get(selected.id) || selected.revision;
        selected.status = selectedStatus;
        if (live) { selected.runtime_version = liveRuntime.version; selected.configuration.delivery = { email: "immediate", digest_at: null, quiet_hours: null }; }
        body = url.pathname.endsWith("/history") ? { items: [{ revision: url.searchParams.has("before_revision") ? 11 : 12,
          configuration: config("PGE"), configuration_hash: "b".repeat(64) }], next_before_revision: url.searchParams.has("before_revision") ? null : 12 } : selected;
        if (url.pathname.endsWith("/state")) body = { ...selected, runtime: { version: 0, run_id: null, health: "not_started", email_consent: false, muted: false },
          start_available: false, blocking_reasons: ["source_acceptance_pending"], current: [], coverage: [] };
        if (url.pathname.endsWith("/activity")) body = { items: [], next_cursor: null };
        if (live && url.pathname.endsWith("/state")) body = { ...selected, runtime: liveRuntime, start_available: liveReady, blocking_reasons: liveReady ? [] : ["pollen_source_not_ready"], coverage: [], current: liveRuntime.run_id ? [{ stream_id: "measured", entry_id: "initial", sample: liveSample(liveReady ? "12.500001" : null), availability: liveReady ? "usable" : "unverified", category: null }, { stream_id: "forecast", entry_id: "forecast", sample: liveSample("3.8125", true), availability: "usable", category: null }] : [] };
        if (live && url.pathname.endsWith("/activity")) body = { items: structuredClone(liveEntries), next_cursor: null };
        if (url.pathname.endsWith("/history") && editHistory.has(id)) {
          const before = Number(url.searchParams.get("before_revision") || Infinity);
          body = { items: editHistory.get(id).filter(r => r.revision < before).slice(0, Number(url.searchParams.get("limit") || 10)), next_before_revision: null };
        }
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
    assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-edit-open]')"), false, "Viewer was offered editing");
    await wait(() => evaluate(cdp, "document.activeElement?.tagName === 'H2'"), "Selection did not focus its settings heading");
    if (locale !== "en-CH") assert.ok(await evaluate(cdp, "document.activeElement.getBoundingClientRect().top >= 72"), "Focused heading is hidden by the mobile header");
    assert.ok((await text()).includes(pollenDraftCopy[locale].blocked));
    assert.equal(await evaluate(cdp, "document.querySelector('[aria-describedby=\"pollen-start-blocked\"]').disabled"), true);
    await audit.check(cdp, locale, "[data-pollen-revision]");
    assert.equal(await evaluate(cdp, "document.documentElement.scrollWidth <= innerWidth"), true);
  }
  locale = "en-CH"; await navigate();
  await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-drafts] ul button')"), "List not ready");
  await click('[data-pollen-drafts] section[aria-label="Pollen Watch"] > button');
  await wait(() => evaluate(cdp, "document.querySelectorAll('[data-pollen-drafts] ul button').length === 2"), "List continuation failed");
  delayFirst = true;
  await click('[data-pollen-drafts] li:first-child button');
  await click('[data-pollen-drafts] li:last-child button');
  await wait(() => evaluate(cdp, "document.querySelector('[data-pollen-drafts] button[aria-pressed=true]')?.innerText.includes('PZH')"), "Newest selection failed");
  await sleep(1000);
  assert.ok(await evaluate(cdp, "document.querySelector('[data-pollen-drafts] button[aria-pressed=true]').innerText.includes('PZH')"));
  await click('[data-pollen-drafts] section[aria-label="Saved settings"] > button:last-child');
  await wait(() => evaluate(cdp, "document.querySelectorAll('[data-pollen-revision]').length === 2"), "History continuation failed");
  await click('[data-pollen-revision]:last-of-type summary');
  assert.ok((await text()).includes("PGE"));
  await audit.check(cdp, "expanded-history", "[data-pollen-revision][open]");
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
  const fill = (name, value) => evaluate(cdp, `(() => { const input=document.querySelector(${JSON.stringify(`[name="${name}"]`)}); const select=input instanceof HTMLSelectElement; Object.getOwnPropertyDescriptor(select ? HTMLSelectElement.prototype : HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(value)}); input.dispatchEvent(new Event(select ? 'change' : 'input',{bubbles:true})); })()`);
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
    assert.equal(await evaluate(cdp, "document.querySelectorAll('[data-pollen-revision]').length"), 0);
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
  assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-edit-open]')"), false, "Active monitor was offered draft editing");
  selectedStatus = "draft"; editFixture = true;
  const patches = () => requests.filter(r => r.method === "PATCH");
  async function beginEdit() {
    mode = "ready"; deleted.clear(); revisions.clear(); updated.clear(); editHistory.clear();
    await selectForDelete(); await button(pollenEditCopy[locale].edit);
    await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-edit] input')"), "Editor did not open");
    assert.equal(await evaluate(cdp, "document.querySelector('[name=\"trigger-birch-observation_hourly\"]').value"), "12.500001");
    assert.ok((await text()).includes("08:30") && (await text()).includes("22:00"));
    await fill("trigger-birch-observation_hourly", "13.500001");
    await button(pollenCreateCopy[locale].preview);
    await wait(async () => (await text()).includes(pollenCreateCopy[locale].checked), "Edit preview missing");
  }
  for (const language of Object.keys(pollenEditCopy)) {
    locale = language; editMode = "success"; await beginEdit();
    await audit.check(cdp, `edit-${locale}`, "[data-pollen-edit] form");
    if (locale === "en-CH") {
      await evaluate(cdp, "document.querySelector('[data-pollen-edit] h2').scrollIntoView({block:'center'})");
      const editImage = await cdp.send("Page.captureScreenshot", { format: "png" });
      await writeFile(join(root, "test-results/pollen-edit-mobile.png"), Buffer.from(editImage.data, "base64"));
    }
    assert.equal(await evaluate(cdp, "document.documentElement.scrollWidth <= innerWidth"), true);
    const count = patches().length;
    await evaluate(cdp, `(() => {const b=Array.from(document.querySelectorAll('[data-pollen-edit] button')).find(b => b.textContent === ${JSON.stringify(pollenCreateCopy[locale].save)}); b.click(); b.click();})()`);
    await wait(async () => (await text()).includes(pollenEditCopy[locale].saved), "Edit save not confirmed");
    assert.equal(patches().length, count + 1);
    const patch = patches().at(-1);
    assert.equal(patch.payload.expected_revision, 12);
    assert.equal(patch.payload.configuration.selections[0].rules[0].threshold.trigger_at_or_above, "13.500001");
    assert.equal(patch.payload.configuration.contract_version, 1);
    assert.equal(patch.payload.configuration.template_version, 1);
    assert.equal(patch.payload.configuration.template_id, "pollen-watch");
    assert.deepEqual(patch.payload.configuration.delivery, { email: "daily_digest", digest_at: "08:30", quiet_hours: { start: "22:00", end: "07:00" } });
    assert.ok(!("request_key" in patch.payload));
    assert.equal(Object.entries(patch.headers).find(([key]) => key.toLowerCase() === "x-csrf-token")?.[1], "synthetic-pollen-csrf");
    await button(pollenCreateCopy[locale].view);
    await wait(async () => (await text()).includes("13.500001"), "Edited saved draft not shown");
  }
  locale = "en-CH";
  for (const lost of ["lost", "later"]) {
    editMode = lost; await beginEdit(); await button(pollenCreateCopy[locale].save);
    await wait(async () => (await text()).includes(pollenEditCopy[locale].uncertain), "Uncertain edit not shown");
    assert.equal(await evaluate(cdp, "document.querySelector('[data-pollen-edit] form > fieldset').disabled"), true);
    const count = patches().length; await button(pollenEditCopy[locale].recover);
    await wait(async () => (await text()).includes(pollenEditCopy[locale].recorded), "Exact next historical revision not recovered");
    assert.equal(patches().length, count, "Recovery wrote an extra revision");
    assert.ok(requests.some(r => r.path.endsWith('/a/history') && r.query === '?limit=1&before_revision=14'));
    await button(pollenCreateCopy[locale].view);
    await wait(() => evaluate(cdp, `document.querySelector('[data-pollen-drafts] section[aria-label="Saved settings"] h3')?.textContent.includes('${lost === "later" ? 14 : 13}')`), "Recovery did not read current revision");
  }
  editMode = "unchanged"; await beginEdit(); await button(pollenCreateCopy[locale].save);
  await wait(async () => (await text()).includes(pollenEditCopy[locale].uncertain), "Failed edit not held");
  const retryCount = patches().length; await button(pollenEditCopy[locale].recover);
  await wait(async () => (await text()).includes(pollenEditCopy[locale].unchanged), "Unchanged revision not distinguished");
  assert.equal(patches().length, retryCount);
  editMode = "success"; await button(pollenCreateCopy[locale].save);
  await wait(async () => (await text()).includes(pollenEditCopy[locale].saved), "Explicit same-revision retry failed");
  assert.deepEqual(patches().at(-1).payload, patches().at(-2).payload);
  editMode = "conflict"; await beginEdit(); await button(pollenCreateCopy[locale].save);
  await wait(async () => (await text()).includes(pollenEditCopy[locale].conflict), "Edit conflict not shown");
  assert.ok(!(await text()).includes(pollenCreateCopy[locale].save));
  dialogAccept = false; await button(pollenEditCopy[locale].reload);
  assert.ok(await evaluate(cdp, "!!document.querySelector('[data-pollen-edit]')"));
  dialogAccept = true; await button(pollenEditCopy[locale].reload);
  await wait(() => evaluate(cdp, "document.querySelector('[data-pollen-drafts] section[aria-label=\"Saved settings\"] h3')?.textContent.includes('13')"), "Conflict did not require rereading new revision");
  editMode = "unchanged"; await beginEdit(); await button(pollenCreateCopy[locale].save);
  await wait(async () => (await text()).includes(pollenEditCopy[locale].uncertain), "Uncertain conflict fixture failed");
  revisions.set("a", 13); await button(pollenEditCopy[locale].recover);
  await wait(async () => (await text()).includes(pollenEditCopy[locale].conflict), "Different historical settings incorrectly accepted");
  dialogAccept = true; await button(pollenEditCopy[locale].cancel);
  editMode = "revoked"; await beginEdit(); await button(pollenCreateCopy[locale].save);
  await wait(async () => (await text()).includes(pollenDraftCopy[locale].access), "Edit revocation not cleared");
  assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-edit]')"), false);
  assert.ok(!(await text()).includes("13.500001"));
  editMode = "unchanged";
  await beginEdit(); dialogAccept = true; await button(pollenEditCopy[locale].cancel);
  await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-edit-open]')"), "Read after edit cancellation missing");
  await button(pollenEditCopy[locale].edit); await button(pollenCreateCopy[locale].preview);
  await wait(async () => (await text()).includes(pollenCreateCopy[locale].checked), "Unchanged settings preview missing");
  await button(pollenCreateCopy[locale].save);
  await wait(async () => (await text()).includes(pollenEditCopy[locale].uncertain), "Unchanged settings save fixture failed");
  const dialogCount = dialogs.length; dialogAccept = false; await button(pollenEditCopy[locale].cancel);
  assert.equal(dialogs.length, dialogCount + 1, "Uncertain unchanged write lacked departure protection");
  assert.ok(await evaluate(cdp, "!!document.querySelector('[data-pollen-edit]')"));
  dialogAccept = true; await button(pollenEditCopy[locale].cancel);
  mode = "ready"; unsupportedEdit = true; await selectForDelete();
  assert.ok((await text()).includes(pollenEditCopy[locale].unsupported));
  assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-edit-open]')"), false);
  unsupportedEdit = false; editFixture = false; editMode = "success";
  const chooseEmail = value => evaluate(cdp, `(() => {const s=document.querySelector('[name="pollen-email"]'); s.value=${JSON.stringify(value)}; s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  for (const language of Object.keys(pollenDeliveryCopy)) {
    locale = language; await navigate();
    await wait(async () => (await text()).includes(pollenCreateCopy[locale].create), "Delivery creator entry missing");
    await button(pollenCreateCopy[locale].create);
    await fill("pollen-station", "PBS"); await click('[name="allergen-birch"]');
    await click('[name="rule-birch-observation_hourly"]');
    await fill("trigger-birch-observation_hourly", "12.500001"); await fill("reset-birch-observation_hourly", "5");
    assert.equal(await evaluate(cdp, "document.querySelector('[name=\"pollen-email\"]').value"), "off");
    assert.ok((await text()).includes(pollenDeliveryCopy[locale].note));
    const previewCount = posts('/api/monitoring-subjects/preview').length;
    await chooseEmail("daily_digest"); await button(pollenCreateCopy[locale].preview);
    assert.equal(posts('/api/monitoring-subjects/preview').length, previewCount, "Empty digest time passed native validation");
    assert.equal(await evaluate(cdp, "document.querySelector('[name=\"pollen-digest\"]').validity.valueMissing"), true);
    await fill("pollen-digest", "23:59"); await click('[name="pollen-quiet"]');
    await button(pollenCreateCopy[locale].preview);
    assert.equal(posts('/api/monitoring-subjects/preview').length, previewCount, "Empty quiet hours passed validation");
    await fill("pollen-quiet-start", "22:00"); await fill("pollen-quiet-end", "22:00");
    await button(pollenCreateCopy[locale].preview);
    await wait(async () => (await text()).includes(pollenDeliveryCopy[locale].invalidQuiet), "Equal quiet endpoints not explained");
    assert.equal(posts('/api/monitoring-subjects/preview').length, previewCount);
    await fill("pollen-quiet-end", "07:00"); await button(pollenCreateCopy[locale].preview);
    await wait(async () => (await text()).includes(pollenCreateCopy[locale].checked), "Delivery preview missing");
    await chooseEmail("immediate"); assert.ok(!(await text()).includes(pollenCreateCopy[locale].checked));
    assert.equal(await evaluate(cdp, "!!document.querySelector('[name=\"pollen-digest\"]')"), false);
    await button(pollenCreateCopy[locale].preview);
    await wait(async () => (await text()).includes(pollenCreateCopy[locale].checked), "Immediate preview missing");
    assert.deepEqual(posts('/api/monitoring-subjects/preview').at(-1).payload.configuration.delivery,
      { email: "immediate", digest_at: null, quiet_hours: { start: "22:00", end: "07:00" } });
    await chooseEmail("off"); await click('[name="pollen-quiet"]'); await button(pollenCreateCopy[locale].preview);
    await wait(async () => (await text()).includes(pollenCreateCopy[locale].checked), "Cleared preferences preview missing");
    assert.deepEqual(posts('/api/monitoring-subjects/preview').at(-1).payload.configuration.delivery,
      { email: "off", digest_at: null, quiet_hours: null });
    await chooseEmail("daily_digest");
    assert.equal(await evaluate(cdp, "document.querySelector('[name=\"pollen-digest\"]').value"), "", "Old digest time silently restored");
    await fill("pollen-digest", "00:00"); await click('[name="pollen-quiet"]');
    await fill("pollen-quiet-start", "22:00"); await fill("pollen-quiet-end", "07:00");
    await fill("pollen-timezone", "Europe/London");
    assert.ok((await text()).includes(pollenDeliveryCopy[locale].clock.replace('{timezone}', 'Europe/London')));
    await button(pollenCreateCopy[locale].preview);
    await wait(async () => (await text()).includes(pollenCreateCopy[locale].checked), "Final delivery preview missing");
    await audit.check(cdp, `delivery-${locale}`, "[data-pollen-delivery]");
    assert.equal(await evaluate(cdp, "document.documentElement.scrollWidth <= innerWidth"), true);
    if (locale === "en-CH") {
      await evaluate(cdp, "document.querySelector('[data-pollen-delivery]').scrollIntoView({block:'start'})");
      const deliveryImage = await cdp.send("Page.captureScreenshot", { format: "png" });
      await writeFile(join(root, "test-results/pollen-delivery-mobile.png"), Buffer.from(deliveryImage.data, "base64"));
    }
    await button(pollenCreateCopy[locale].save);
    await wait(async () => (await text()).includes(pollenCreateCopy[locale].saved), "Delivery draft not saved");
    const createdDelivery = posts('/api/monitoring-subjects').at(-1).payload.configuration;
    assert.deepEqual(createdDelivery.delivery, { email: "daily_digest", digest_at: "00:00", quiet_hours: { start: "22:00", end: "07:00" } });
    assert.equal(createdDelivery.timezone, "Europe/London");
    await button(pollenCreateCopy[locale].view);
    await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-edit-open]')"), "Saved delivery edit entry missing");
    await button(pollenEditCopy[locale].edit);
    assert.equal(await evaluate(cdp, "document.querySelector('[name=\"pollen-digest\"]').value"), "00:00");
    await chooseEmail("immediate"); await fill("pollen-quiet-end", "08:00");
    await button(pollenCreateCopy[locale].preview);
    await wait(async () => (await text()).includes(pollenCreateCopy[locale].checked), "Delivery revision preview missing");
    editMode = locale === "en-CH" ? "lost" : "success";
    await button(pollenCreateCopy[locale].save);
    if (editMode === "lost") {
      await wait(async () => (await text()).includes(pollenEditCopy[locale].uncertain), "Uncertain delivery edit not retained");
      assert.equal(await evaluate(cdp, "document.querySelector('[name=\"pollen-email\"]').matches(':disabled')"), true);
      const count = patches().length; await button(pollenEditCopy[locale].recover);
      await wait(async () => (await text()).includes(pollenEditCopy[locale].recorded), "Delivery history recovery failed");
      assert.equal(patches().length, count);
    } else await wait(async () => (await text()).includes(pollenEditCopy[locale].saved), "Delivery revision not saved");
    assert.equal(patches().at(-1).payload.expected_revision, 1);
    assert.deepEqual(patches().at(-1).payload.configuration.delivery,
      { email: "immediate", digest_at: null, quiet_hours: { start: "22:00", end: "08:00" } });
    assert.deepEqual(patches().at(-1).payload.configuration.selections, createdDelivery.selections);
  }
  editFixture = false; unsupportedEdit = false; updated.clear(); editHistory.clear();
  const writes = () => requests.filter(r => r.path.startsWith('/api/monitoring-subjects') && r.method !== 'GET');
  const originalWrites = writes().length;
  for (const language of Object.keys(pollenRecoveryCopy)) {
    locale = language; revisions.clear(); await selectForDelete();
    assert.equal(await evaluate(cdp, "location.hash"), "#draft=a");
    assert.ok((await text()).includes(pollenRecoveryCopy[locale].saved));
    assert.equal(await evaluate(cdp, "document.querySelector('[data-pollen-saved-link]').getAttribute('href')"), "/pollen-watch#draft=a");
    revisions.set("a", 13); await reloadDocument();
    await wait(() => evaluate(cdp, "document.querySelector('[data-pollen-drafts] section[aria-label] h3')?.textContent.includes('13')"), "Reload did not read current saved revision");
    await audit.check(cdp, `recovery-${locale}`, "[data-pollen-saved-link]");
  }
  assert.equal(writes().length, originalWrites, "Saved-state recovery issued a write");
  locale = "en-CH";
  for (const denied of ['revoked', 'disabled', 'missing']) {
    mode = denied;
    await navigateDocument(`${base}/pollen-watch?recovery=${denied}#draft=a`);
    await wait(async () => (await text()).includes(pollenDraftCopy[locale][denied === 'revoked' ? 'access' : denied]) && await evaluate(cdp, "location.hash === ''"), 'Recovery did not report access failure and clear its locator');
    assert.equal(await evaluate(cdp, "location.hash"), "");
    assert.ok(!(await text()).includes('12.500001'));
  }
  mode = 'ready'; revisions.clear(); await selectForDelete();
  const savedUrl = await evaluate(cdp, 'location.href');
  await navigateDocument(`${base}/pollen-watch?away=1`);
  await wait(() => evaluate(cdp, "location.search === '?away=1' && !!document.querySelector('[data-pollen-drafts] li')"), 'Away document not ready');
  const historyBeforeBack = await cdp.send('Page.getNavigationHistory');
  revisions.set('a', 14);
  await cdp.send('Page.navigateToHistoryEntry', {entryId: historyBeforeBack.entries[historyBeforeBack.currentIndex - 1].id});
  await wait(() => evaluate(cdp, "document.querySelector('[data-pollen-drafts] section[aria-label] h3')?.textContent.includes('14')"), 'Back did not revalidate saved settings');
  assert.equal(await evaluate(cdp, 'location.href'), savedUrl);
  const historyBeforeForward = await cdp.send('Page.getNavigationHistory');
  await cdp.send('Page.navigateToHistoryEntry', {entryId: historyBeforeForward.entries[historyBeforeForward.currentIndex + 1].id});
  await wait(() => evaluate(cdp, "location.search === '?away=1' && !document.querySelector('[data-pollen-saved-link]')"), 'Forward retained stale selected settings');
  await selectForDelete();
  await evaluate(cdp, "window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted:true}))");
  assert.ok(!(await text()).includes('12.500001'), 'Cached page retained private settings');
  mode = 'revoked';
  const authReads = requests.filter(r => r.path === '/api/auth/session').length;
  await evaluate(cdp, "window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}))");
  await wait(async () => (await text()).includes(pollenDraftCopy[locale].access) && requests.filter(r => r.path === '/api/auth/session').length > authReads, 'Cached restore did not recheck session and authorization');
  assert.ok(requests.filter(r => r.path === '/api/auth/session').length > authReads);
  mode = 'ready'; await navigate();
  await wait(async () => (await text()).includes(pollenCreateCopy[locale].create), 'Navigation creator not ready');
  await button(pollenCreateCopy[locale].create); await fill('pollen-station', 'PBS');
  assert.equal(await evaluate(cdp, 'location.hash'), '');
  assert.ok((await text()).includes(pollenRecoveryCopy[locale].unsaved));
  const dialogsBeforeProbes = dialogs.length;
  for (const variant of ['anchor','modified','blank','download']) {
    await evaluate(cdp, `(() => { const a=document.createElement('a'); a.href=${JSON.stringify(variant === 'anchor' ? '#form-section' : '/pollen-watch?elsewhere=1')};
      ${variant === 'blank' ? "a.target='_blank';" : ''} ${variant === 'download' ? "a.download='fixture';" : ''}
      a.addEventListener('click', e => e.preventDefault()); document.body.append(a);
      a.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,ctrlKey:${variant === 'modified'}})); a.remove(); })()`);
  }
  assert.equal(dialogs.length, dialogsBeforeProbes, 'A non-departing link prompted discard');
  dialogAccept = false;
  assert.equal(await evaluate(cdp, "window.dispatchEvent(new CustomEvent('helvetic:before-navigation',{cancelable:true}))"), false);
  assert.equal(await evaluate(cdp, "window.dispatchEvent(new Event('beforeunload',{cancelable:true}))"), false);
  dialogAccept = true;
  assert.equal(await evaluate(cdp, "window.dispatchEvent(new CustomEvent('helvetic:before-navigation',{cancelable:true}))"), true);
  // Approval alone is not a commit: a failed workspace switch must still protect the form.
  assert.equal(await evaluate(cdp, "window.dispatchEvent(new Event('beforeunload',{cancelable:true}))"), false);
  await evaluate(cdp, "window.dispatchEvent(new CustomEvent('helvetic:navigation-committed'))");
  assert.equal(await evaluate(cdp, "window.dispatchEvent(new Event('beforeunload',{cancelable:true}))"), true);
  await reloadDocument();
  await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-drafts] li') && !document.querySelector('[data-pollen-create]')"), 'Reload invented unsaved form recovery');
  assert.equal(writes().length, originalWrites, 'Navigation recovery wrote private records');

  const downloadDirectory = join(profile, "downloads");
  await mkdir(downloadDirectory);
  await cdp.send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: downloadDirectory });
  const backupPath = join(downloadDirectory, "pollen-watch-settings.json");
  async function chooseBackup(path) {
    await evaluate(cdp, "document.querySelector('[data-pollen-import]').open = true");
    const { root: documentRoot } = await cdp.send("DOM.getDocument");
    const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: documentRoot.nodeId, selector: "[data-pollen-import] input" });
    await cdp.send("DOM.setFileInputFiles", { nodeId, files: [path] });
  }
  const writesBeforeBackup = writes().length;
  for (const language of Object.keys(pollenBackupCopy)) {
    locale = language; mode = "ready"; manager = true; organization = "org-a";
    updated.clear(); revisions.clear(); editFixture = false;
    await selectForDelete();
    const fresh = config("PGE");
    Object.assign(fresh, { contract_version: 1, template_version: 1, template_id: "pollen-watch" });
    fresh.selections[0].rules[0].threshold = { trigger_at_or_above: "999999.999999", reset_at_or_below: "0.000001" };
    fresh.selections[0].rules[0].rapid_increase.minimum_increase = "3.000001";
    fresh.delivery = { email: "daily_digest", digest_at: "08:30", quiet_hours: { start: "22:00", end: "07:00" } };
    updated.set("a", { ...draft("a", "PGE"), revision: 15, configuration: fresh });
    const readCount = requests.filter(r => r.path === '/api/monitoring-subjects/a' && r.method === 'GET').length;
    // Actual keyboard-initiated download and an actual file input round trip.
    await evaluate(cdp, "document.querySelector('[data-pollen-export]').focus()");
    await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, text: "\r", unmodifiedText: "\r" });
    await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
    let backup;
    await wait(async () => { backup = JSON.parse(await readFile(backupPath, 'utf8')); return true; }, 'Settings backup download missing');
    assert.deepEqual(backup, { format: 'helvetic-lens.pollen-draft', version: 1, configuration: fresh });
    assert.equal(requests.filter(r => r.path === '/api/monitoring-subjects/a' && r.method === 'GET').length, readCount + 1);
    assert.ok((await text()).includes(pollenBackupCopy[locale].downloaded));
    const beforeImport = writes().length;
    await chooseBackup(backupPath);
    await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-import-review]')"), 'Imported review missing');
    assert.equal(writes().length, beforeImport, 'Selecting backup sent configuration before explicit preview');
    assert.equal(await evaluate(cdp, "document.activeElement?.tagName"), 'H2');
    assert.equal(await evaluate(cdp, "document.querySelector('[name=pollen-station]').value"), 'PGE');
    assert.equal(await evaluate(cdp, "document.querySelector('[name=trigger-birch-observation_hourly]').value"), '999999.999999');
    assert.equal(await evaluate(cdp, "document.querySelector('[name=pollen-email]').value"), 'daily_digest');
    assert.equal(await evaluate(cdp, "document.querySelector('[name=pollen-digest]').value"), '08:30');
    dialogAccept = false;
    await button(pollenCreateCopy[locale].cancel);
    assert.ok(await evaluate(cdp, "!!document.querySelector('[data-pollen-import-review]')"), 'Imported settings lacked discard protection');
    dialogAccept = true;
    await button(pollenCreateCopy[locale].preview);
    await wait(async () => (await text()).includes(pollenCreateCopy[locale].checked), 'Restored preview missing');
    assert.deepEqual(posts('/api/monitoring-subjects/preview').at(-1).payload, { configuration: fresh });
    await audit.check(cdp, `backup-${locale}`, '[data-pollen-import-review]');
    assert.equal(await evaluate(cdp, 'document.documentElement.scrollWidth <= innerWidth'), true);
    if (language === 'en-CH') {
      await evaluate(cdp, "document.querySelector('[data-pollen-import-review]').scrollIntoView({block:'center'})");
      const backupImage = await cdp.send('Page.captureScreenshot', { format: 'png' });
      await writeFile(join(root, 'test-results/pollen-backup-mobile.png'), Buffer.from(backupImage.data, 'base64'));
    }
    const oldCreated = created.size;
    loseFirstSave = true;
    await button(pollenCreateCopy[locale].save);
    await wait(async () => (await text()).includes(pollenCreateCopy[locale].uncertain), 'Restore lost-response fixture missing');
    await button(pollenCreateCopy[locale].save);
    await wait(async () => (await text()).includes(pollenCreateCopy[locale].saved), 'Restore retry missing');
    const [firstSave, retrySave] = posts('/api/monitoring-subjects').slice(-2);
    assert.deepEqual(firstSave.payload, retrySave.payload);
    assert.deepEqual(firstSave.payload.configuration, fresh);
    assert.deepEqual(Object.keys(firstSave.payload).sort(), ['configuration', 'request_key']);
    assert.equal(created.size, oldCreated + 1);
    assert.equal(updated.get('a').revision, 15, 'Restore overwrote original');
    assert.equal(Object.entries(firstSave.headers).find(([key]) => key.toLowerCase() === 'x-csrf-token')?.[1], 'synthetic-pollen-csrf');
    await button(pollenCreateCopy[locale].view);
    await wait(() => evaluate(cdp, "location.hash.startsWith('#draft=created-')"), 'Restored draft not opened');
    await rm(backupPath);
  }
  assert.equal(writes().length - writesBeforeBackup, 15, 'Backup workflow performed unexpected writes');
  locale = 'en-CH'; updated.clear(); revisions.clear();
  await selectForDelete();
  const fixturePath = join(profile, 'import-fixture.json');
  const noUnexpectedWrites = writes().length;
  for (const [contents, error] of [['{bad', 'invalid'], ['x'.repeat(65537), 'invalid'], [JSON.stringify({format:'other',version:1,configuration:config('PBS')}), 'unsupported']]) {
    await writeFile(fixturePath, contents);
    await chooseBackup(fixturePath);
    await wait(async () => (await text()).includes(pollenBackupCopy[locale][error]), 'Invalid import not explained');
    assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-create]')"), false);
    assert.ok((await text()).includes('12.500001'), 'Invalid import cleared saved reader');
  }
  for (const failureMode of ['revoked', 'disabled', 'missing', 'error']) {
    mode = 'ready'; await selectForDelete(); mode = failureMode;
    await click('[data-pollen-export]');
    await wait(async () => (await text()).includes(failureMode === 'error' ? pollenBackupCopy[locale].failed : pollenDraftCopy[locale][failureMode === 'revoked' ? 'access' : failureMode]), 'Failed export not explained');
    assert.equal(existsSync(backupPath), false, 'Failed export downloaded stale private settings');
    if (failureMode !== 'error') assert.ok(!(await text()).includes('12.500001'), 'Revoked export retained private settings');
  }
  mode = 'ready'; await selectForDelete(); delayFirst = true;
  await click('[data-pollen-export]');
  await button(pollenCreateCopy[locale].create);
  await sleep(900);
  assert.equal(existsSync(backupPath), false, 'Late export survived leaving its selected draft');
  delayFirst = false; await button(pollenCreateCopy[locale].cancel);
  await writeFile(fixturePath, JSON.stringify({format:'helvetic-lens.pollen-draft',version:1,configuration:config('PBS')}));
  await evaluate(cdp, "window.__originalPollenRead = File.prototype.arrayBuffer; File.prototype.arrayBuffer = function() { const file = this; return new Promise(resolve => setTimeout(() => resolve(window.__originalPollenRead.call(file)), 500)); }");
  await chooseBackup(fixturePath);
  await button(pollenCreateCopy[locale].create);
  await sleep(600);
  assert.equal(await evaluate(cdp, "document.querySelector('[name=pollen-station]').value"), '', 'Late import replaced a different form');
  assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-import-review]')"), false);
  await evaluate(cdp, "File.prototype.arrayBuffer = window.__originalPollenRead");
  await button(pollenCreateCopy[locale].cancel);
  await chooseBackup(fixturePath);
  await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-import-review]')"), 'Revoked restore review missing');
  mode = 'revoked'; await button(pollenCreateCopy[locale].preview);
  await wait(async () => (await text()).includes(pollenDraftCopy[locale].access), 'Imported preview bypassed access recheck');
  assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-create]')"), false);
  assert.equal(writes().length, noUnexpectedWrites + 1);
  mode = 'ready'; manager = false; await selectForDelete();
  assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-import]')"), false, 'Viewer can import');
  await click('[data-pollen-export]');
  await wait(() => existsSync(backupPath), 'Authorized owner viewer cannot export own configuration');
  await rm(backupPath);
  manager = true; mode = 'ready'; updated.clear(); revisions.clear();
  const deviceLocation = {latitude:47.56181234, longitude:7.58394321};
  await cdp.send('Page.addScriptToEvaluateOnNewDocument', {source: "window.__pollenLocationCalls = 0; const locate = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation); navigator.geolocation.getCurrentPosition = (...args) => { window.__pollenLocationCalls++; return locate(...args); };"});
  await cdp.send('Browser.grantPermissions', {origin:base, permissions:['geolocation']});
  await cdp.send('Emulation.setGeolocationOverride', {...deviceLocation, accuracy:50});
  for (const language of Object.keys(pollenStationCopy)) {
    locale = language; const stationCopy = pollenStationCopy[locale], createCopy = pollenCreateCopy[locale];
    await navigate();
    await wait(async () => (await text()).includes(createCopy.create), 'Station creator not ready');
    await button(createCopy.create);
    assert.equal(await evaluate(cdp, "document.querySelector('[name=pollen-station]').value"), '');
    assert.equal(await evaluate(cdp, "document.querySelectorAll('[name=pollen-station] option').length"), 16);
    assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-distance]')"), false);
    assert.equal(await evaluate(cdp, 'window.__pollenLocationCalls'), 0, 'Location was requested without a user action');
    await click('[data-pollen-nearby] summary');
    const beforeLocation = writes().length;
    await click('[data-pollen-locate]');
    await wait(async () => (await text()).includes(stationCopy.ordered), 'Browser location did not rank stations');
    assert.equal(await evaluate(cdp, 'window.__pollenLocationCalls'), 1);
    assert.equal(await evaluate(cdp, "document.querySelectorAll('[name=pollen-station] option')[1].value"), 'PBS');
    assert.equal(await evaluate(cdp, "document.querySelector('[name=pollen-station]').value"), '', 'Location silently selected a station');
    assert.equal(writes().length, beforeLocation, 'Location caused a write');
    await evaluate(cdp, "document.querySelector('[name=pollen-station]').focus()");
    await cdp.send('Input.dispatchKeyEvent', {type:'keyDown', key:'ArrowDown', code:'ArrowDown', windowsVirtualKeyCode:40});
    await cdp.send('Input.dispatchKeyEvent', {type:'keyUp', key:'ArrowDown', code:'ArrowDown', windowsVirtualKeyCode:40});
    await wait(() => evaluate(cdp, "document.querySelector('[name=pollen-station]').value === 'PBS'"), 'Keyboard station selection failed');
    assert.ok(await evaluate(cdp, "!!document.querySelector('[data-pollen-distance]')"));
    await click('[name=allergen-birch]'); await click('[name=allergen-grasses]');
    await click('[name=allergen-beech]'); await click('[name=allergen-ragweed]');
    const rows = await evaluate(cdp, "Array.from(document.querySelectorAll('[data-pollen-channels] tbody tr')).map(r => r.innerText)");
    assert.equal(rows.length, 4);
    assert.ok(rows[0].includes(stationCopy.documentedObservation) && rows[0].includes(stationCopy.documentedForecast));
    assert.ok(rows[2].includes(stationCopy.documentedObservation) && rows[2].includes(stationCopy.notEstablished));
    assert.ok(rows[3].includes(stationCopy.notEstablished) && rows[3].includes(stationCopy.documentedForecast));
    assert.ok((await text()).includes(stationCopy.unverified));
    await button(createCopy.preview);
    await wait(async () => (await text()).includes(createCopy.checked), 'Station configuration check missing');
    await fill('pollen-station', 'PGE');
    assert.ok(!(await text()).includes(createCopy.checked), 'Changed station kept old preview');
    await click('[data-pollen-location-clear]');
    assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-distance]')"), false);
    assert.equal(await evaluate(cdp, "document.querySelector('[name=pollen-station]').value"), 'PGE', 'Clearing coordinates changed the station');
    await button(createCopy.preview);
    await wait(async () => (await text()).includes(createCopy.checked), 'Changed station check missing');
    await audit.check(cdp, `station-${locale}`, '[data-pollen-station-picker]');
    assert.equal(await evaluate(cdp, 'document.documentElement.scrollWidth <= innerWidth'), true);
    if (language === 'en-CH') {
      await evaluate(cdp, "document.querySelector('[data-pollen-station-picker]').scrollIntoView({block:'start'})");
      await writeFile(join(root, 'test-results/pollen-station-mobile.png'), Buffer.from((await cdp.send('Page.captureScreenshot', {format:'png'})).data, 'base64'));
    }
    await button(createCopy.save);
    await wait(async () => (await text()).includes(createCopy.saved), 'Station save failed');
    const payload = posts('/api/monitoring-subjects').at(-1).payload.configuration;
    assert.equal(payload.station_id, 'PGE'); assert.equal(payload.selections.length, 4);
    assert.equal(Object.hasOwn(payload, 'latitude'), false); assert.equal(Object.hasOwn(payload, 'longitude'), false);
    await button(createCopy.view);
    await wait(async () => (await text()).includes('Genève') && (await text()).includes(stationCopy.coverage), 'Saved station name/channel overview missing');
    const browserStorage = await evaluate(cdp, 'JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage), document.cookie])');
    for (const coordinate of Object.values(deviceLocation)) assert.ok(!browserStorage.includes(String(coordinate)), 'Device coordinates reached browser persistence');
  }
  for (const coordinate of Object.values(deviceLocation)) assert.ok(!JSON.stringify(requests).includes(String(coordinate)), 'Device coordinates reached an API request');
  locale = 'en-CH';
  await navigate(); await wait(async () => (await text()).includes(pollenCreateCopy[locale].create), 'Location error fixture not ready');
  await button(pollenCreateCopy[locale].create); await click('[data-pollen-nearby] summary');
  await evaluate(cdp, "window.__savedLocation = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation)");
  for (const [code, key] of [[1,'denied'], [2,'unavailable'], [3,'timeout']]) {
    await evaluate(cdp, `navigator.geolocation.getCurrentPosition = (ok, fail) => fail({code:${code}})`);
    await click('[data-pollen-locate]');
    await wait(async () => (await text()).includes(pollenStationCopy[locale][key]), 'Location error not explained');
    assert.equal(await evaluate(cdp, "document.querySelector('[name=pollen-station]').disabled"), false);
  }
  await evaluate(cdp, "navigator.geolocation.getCurrentPosition = ok => { window.__latePollenLocation = ok; }");
  await click('[data-pollen-locate]'); await click('[data-pollen-location-clear]');
  await evaluate(cdp, `window.__latePollenLocation({coords:${JSON.stringify(deviceLocation)}})`);
  assert.ok(!(await text()).includes(pollenStationCopy[locale].ordered), 'Cancelled location callback returned');
  await click('[data-pollen-locate]'); await button(pollenCreateCopy[locale].cancel);
  await button(pollenCreateCopy[locale].create);
  await evaluate(cdp, `window.__latePollenLocation({coords:${JSON.stringify(deviceLocation)}})`);
  assert.equal(await evaluate(cdp, "document.querySelector('[name=pollen-station]').value"), '');
  assert.ok(!(await text()).includes(pollenStationCopy[locale].ordered), 'Old form location reached new form');
  await button(pollenCreateCopy[locale].cancel);
  updated.set('a', {...draft('a','XYZ'), configuration:config('XYZ')});
  await navigate(); await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-drafts] li button')"), 'Unknown station list missing');
  await click('[data-pollen-drafts] li button');
  await wait(async () => (await text()).includes(pollenStationCopy[locale].unknown), 'Unknown saved station not explained');
  await click('[data-pollen-edit-open]');
  assert.equal(await evaluate(cdp, "document.querySelector('[name=pollen-station]').value"), 'XYZ');
  await button(pollenCreateCopy[locale].preview);
  await wait(async () => (await text()).includes(pollenCreateCopy[locale].checked), 'Unknown station configuration check failed');
  assert.equal(posts('/api/monitoring-subjects/preview').at(-1).payload.configuration.station_id, 'XYZ');
  assert.ok((await text()).includes(pollenStationCopy[locale].unknown));
  await button(pollenEditCopy[locale].cancel);
  assert.equal(requests.filter(r => r.path.endsWith("/start")).length, 0);
  assert.deepEqual(exceptions, []);
  live = true; manager = true; mode = "ready"; updated.clear(); revisions.clear(); deleted.clear(); editFixture = false;
  for (const language of Object.keys(pollenRuntimeCopy)) {
    locale = language; selectedStatus = "draft"; liveEntries = []; liveCommands.clear(); liveReady = true;
    liveRuntime = { version: 0, run_id: null, health: "waiting", email_consent: false, muted: false };
    const copy = pollenRuntimeCopy[locale];
    await navigate(); await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-drafts] li button')"), "Live monitor list missing");
    await click('[data-pollen-drafts] li button');
    await wait(() => evaluate(cdp, "document.querySelector('[data-pollen-start]')?.disabled === false"), "Approved live Start unavailable");
    assert.equal(await evaluate(cdp, "document.querySelector('[data-pollen-runtime] fieldset input[type=checkbox]').checked"), false);
    liveLost = true;
    await button(copy.start); await wait(async () => (await text()).includes(copy.uncertain), "Lost Start response not explained");
    const firstKey = requests.filter(r => r.path.endsWith('/commands')).at(-1).payload.request_key;
    await button(copy.retry); await wait(async () => (await text()).includes(copy.active), "Start retry did not recover active monitor");
    assert.equal(requests.filter(r => r.path.endsWith('/commands')).at(-1).payload.request_key, firstKey);
    assert.equal(liveRuntime.version, 1); assert.equal(liveRuntime.email_consent, false);
    assert.ok((await text()).includes(copy.measured) && (await text()).includes(copy.forecast));
    assert.ok((await text()).includes('12.500001') && (await text()).includes('3.8125'));
    liveEntries = [{ id: 'material-1', sequence: 2, kind: 'material', material_id: 'synthetic-material', current: liveSample('20'), previous: liveSample('5'), baseline: liveSample('2'), reasons: ['threshold_triggered'], binding: { rule: config('PBS').selections[0].rules[0] }, configuration_revision: 12, review: null }];
    await button(copy.load); await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-activity]')"), "Material change not rendered");
    assert.ok((await text()).includes(copy.threshold_triggered));
    await click('[data-pollen-activity] details > summary');
    assert.ok((await text()).includes(copy.previous));
    await audit.check(cdp, `runtime-${locale}`, '[data-pollen-runtime]');
    if (locale === 'en-CH') {
      await evaluate(cdp, "document.querySelector('[data-pollen-runtime]').scrollIntoView({block:'start'})");
      await writeFile(join(root, 'test-results/pollen-runtime-mobile.png'), Buffer.from((await cdp.send('Page.captureScreenshot', {format:'png'})).data, 'base64'));
    }
    assert.equal(await evaluate(cdp, 'document.documentElement.scrollWidth <= innerWidth'), true);
    for (const decision of ['action_required', 'not_relevant', 'continue', 'reviewed']) {
      await button(copy[decision]); await wait(() => evaluate(cdp, `document.querySelector('[data-pollen-activity] button[aria-pressed=true]')?.textContent === ${JSON.stringify(copy[decision])}`), 'Review was not retained');
    }
    liveRuntime.health = 'source_unavailable'; await button(copy.load);
    await wait(async () => (await text()).includes(copy.source_unavailable), 'Failed source refresh not explained');
    assert.ok((await text()).includes('12.500001'));
    liveEntries.unshift({ ...liveEntries[0], id: 'material-2', material_id: 'synthetic-reopened', review: null, reasons: ['threshold_reset'] });
    await button(copy.load); await wait(() => evaluate(cdp, "document.querySelectorAll('[data-pollen-activity]').length === 2"), 'Later change did not reopen separately');
    assert.ok((await text()).includes(copy.new));
    await button(copy.pause); await wait(async () => (await text()).includes(copy.paused), 'Pause state missing');
    await button(copy.resume); await wait(async () => (await text()).includes(copy.active), 'Resume state missing');
    assert.equal(liveRuntime.email_consent, false);
    liveReady = false; await button(copy.load); await wait(async () => (await text()).includes(copy.unverified), 'Source revocation not visible');
    mode = 'revoked'; await button(copy.load); await wait(async () => (await text()).includes(pollenDraftCopy[locale].access), 'Membership revocation not cleared');
    assert.equal(await evaluate(cdp, "!!document.querySelector('[data-pollen-runtime]')"), false);
    mode = 'ready';
  }
  locale = 'en-CH'; mode = 'ready'; liveReady = true;
  await navigateDocument(`${base}/?case=pollen-today`);
  await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-today] a')"), 'Pollen changes did not appear in Today');
  assert.ok(await evaluate(cdp, "document.querySelector('[data-pollen-today] a').getAttribute('href').includes('/pollen-watch#draft=a')"));
  await audit.check(cdp, 'pollen-today', '[data-pollen-today]');
  await click('[data-pollen-today] a');
  await wait(() => evaluate(cdp, "!!document.querySelector('[data-pollen-runtime]')"), 'Today link did not open its private monitor');
  assert.deepEqual(exceptions, []);
  audit.finish(47);
  console.log('Pollen runtime: five locales, measured/forecast separation, exact values, lost Start same-key recovery, no implicit email consent, why/previous evidence, review and new change reopening, pause/resume, source/membership revocation and Today navigation passed with synthetic APIs.');
  console.log("Pollen reader: five locales, desktop/mobile, keyboard activation, exact decimals, list/history pagination, obsolete responses, revoked/default-off/missing/error/empty/anonymous/workspace isolation passed. Synthetic APIs only; no live acceptance.");
  console.log("Pollen creation: five locales, keyboard entry, multi-allergen observation/forecast rules, invalid preview, preview invalidation, CSRF, busy guard, lost-response same-key retry, saved navigation, confirmed/cancelled discard and revoked access passed. Draft creation phase: email off and no Start requests.");
  console.log("Pollen deletion: five localized exact station/revision confirmations, cancel/success, duplicate clicks, CSRF, private-history removal, conflict requiring fresh revision, uncertain response then missing, revoked access and active/viewer denial passed.");
  console.log("Pollen editing: five locales, exact decimals, preserved contract/delivery fields, CSRF, revision CAS, duplicate guard, history recovery without writes including newer current revision, explicit unchanged retry, conflicting history, discard/reload, revoked access and unsupported future configuration read-only passed.");
  console.log("Pollen delivery preferences: five locales, email-off defaults, required clock fields, equal/overnight quiet hours, all mode transitions, digest/quiet clearing, timezone labels, preview invalidation, exact create/edit payloads, numeric preservation and uncertain-write history recovery passed. Draft preference phase: no Start or delivery activation.");
  console.log("Pollen saved recovery: five locales, identifier-only links, reload/current revisions, denied/missing/default-off clearing, real Back/Forward document restoration, cached-page privacy/session revalidation, non-departing links and committed-only unload bypass passed without writes. Unsaved crash recovery and same-document traversal cancellation remain open.");
  console.log("Private backup and restore: five locales, real keyboard downloads and local file inputs, fresh authorized snapshots, lossless settings, separate preview/new-copy Save, same-key retry, dirty review, malformed/oversized/unsupported files, revoked/default-off/missing/failed export, cancelled late download and viewer read-only export passed. No history/identity/source/consent restoration.");
  console.log("Station selection: five locales, 15 named source stations, real browser geolocation and keyboard choice, local distances without automatic selection, separate allergen channels, preview invalidation, saved names, unknown-code retention, location errors/cancellation/late callbacks, and no coordinate persistence/API transmission passed. Dated metadata is not live coverage.");
} catch (error) {
  console.error({ locale, mode, requests: requests.slice(-12), exceptions,
    page: cdp ? await text().catch(() => "unavailable") : null,
    active: cdp ? await evaluate(cdp, "document.activeElement?.outerHTML.slice(0,600)").catch(() => null) : null });
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) { const stopped = new Promise(done => child.once("exit", done)); child.kill(); await Promise.race([stopped, sleep(2000)]); }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-pollen-reader-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
