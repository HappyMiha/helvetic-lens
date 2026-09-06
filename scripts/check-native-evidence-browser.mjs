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
const profile = await mkdtemp(join(tmpdir(), "helvetic-native-evidence-browser-"));
const browser = spawn(chrome, ["--headless=new", "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore", windowsHide: true });
let cdp;
const requests = [], exceptions = [], milestones = [];
async function waitFor(check, message) {
  for (let i = 0; i < 150; i++) {
    if (await check().catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}
let locale = "en-CH", mode = "passages";
const passages = Array.from({ length: 125 }, (_, index) => ({ id: `p${index + 1}`, text: `Synthetic saved passage ${index + 1}`, page: Math.floor(index / 25) + 1 }));
function evidence(native) {
  return { id: "synthetic-version", law_id: native ? null : "synthetic-law", law_name: "Synthetic saved connector document", native,
    origin: native ? "official_connector" : "live", created_at: "2026-09-05T08:00:00Z", source_url: mode === "empty" ? "javascript:alert(1)" : "https://example.invalid/official-source",
    content_type: "application/pdf", artifact_url: mode === "passages" ? `/api/${native ? "regulatory-versions" : "versions"}/synthetic-version/artifact` : null,
    declared_date: null, synthetic: mode === "sample", identity_json: { language: "de" }, passages: ["passages", "sample"].includes(mode) ? passages : [], passage_count: mode === "passages" ? 125 : 0,
    plain_text: mode === "text" ? "Saved text without passage identifiers" : null };
}
try {
  await waitFor(async () => (await fetch(base)).ok, "Isolated production UI failed to start");
  let debugPort;
  await waitFor(async () => { debugPort = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]; return !!debugPort; }, "Browser failed to start");
  await pollJson(`http://127.0.0.1:${debugPort}/json/version`);
  const target = await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: "PUT" }).then(response => response.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  // Controlled visibility isolates the visibilitychange contract from headless tab policy.
  await cdp.send("Page.addScriptToEvaluateOnNewDocument", {source:`Object.defineProperty(document, 'visibilityState', {get: () => sessionStorage.getItem('qa-hidden') === '1' ? 'hidden' : 'visible'});`});
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) => exceptions.push(exceptionDetails.text));
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url);
    requests.push(url.pathname + url.search);
    let body = {}, code = 200;
    if (url.pathname === "/api/auth/session") body = { authenticated: true, user: { id: "qa", email: "qa@example.invalid", name: "QA", locale }, organization: { id: "qa-org", name: "Isolated QA" }, role: "viewer" };
    else if (url.pathname === "/api/health") body = { status: "ok", database: "sqlite", apertus: { configured: false }, firecrawl: { configured: false } };
    else if (url.pathname === "/api/onboarding/evidence-displayed") {
      assert.equal(request.method, "POST"); milestones.push(JSON.parse(request.postData)); body={recorded:true};
    }
    else if (url.pathname === "/api/jobs") body = [];
    else if (/^\/api\/(regulatory-versions|versions)\/synthetic-version$/.test(url.pathname)) body = evidence(url.pathname.includes("regulatory-versions"));
    else { code = 503; body = { detail: "Unconfigured synthetic QA endpoint" }; }
    await cdp.send("Fetch.fulfillRequest", { requestId, responseCode: code, responseHeaders: [{ name: "Content-Type", value: "application/json" }], body: Buffer.from(JSON.stringify(body)).toString("base64") }).catch(() => {});
  });
  // Intercept every application API request before it can reach Next's proxy.
  await cdp.send("Fetch.enable", { patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }] });
  const navigate = async (path) => {
    await cdp.send("Page.navigate", { url: `${base}${path}${path.includes("?") ? "&" : "?"}locale=${locale}` });
    await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Synthetic saved connector document')`), "Saved document did not open");
  };
  await cdp.send("Page.navigate", {url:base});
  await waitFor(() => evaluate(cdp, `location.origin === ${JSON.stringify(base)}`), "Initial local origin missing");
  for (locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    for (const width of [390, 1440]) {
      mode = "passages";
      await cdp.send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 500 });
      await evaluate(cdp, `sessionStorage.setItem('qa-hidden','1')`);
      const before = milestones.length;
      await navigate("/corpus-evidence/synthetic-version?passage=p100");
      await waitFor(() => evaluate(cdp, `!!document.querySelector('#passage-p100.evidence-target')`), "Deep-linked passage on later page missing");
      assert.ok(await evaluate(cdp, `document.querySelector('.evidence-target').innerText.includes('Synthetic saved passage 100')`));
      assert.ok(await evaluate(cdp, `!!document.querySelector('a[href="/api/regulatory-versions/synthetic-version/artifact#page=4"]')`), "Native PDF page link missing");
      assert.ok(await evaluate(cdp, `!!document.querySelector('a[href="/corpus-evidence/synthetic-version?passage=p100"]')`), "Passage permalink uses wrong namespace");
      await sleep(300);
      assert.equal(milestones.length, before, "Background text recorded as displayed");
      await evaluate(cdp, `sessionStorage.removeItem('qa-hidden'); document.dispatchEvent(new Event('visibilitychange'))`);
      await waitFor(() => Promise.resolve(milestones.length === before + 1), "Visible evidence not recorded");
      assert.deepEqual(milestones.at(-1), {kind:"native_version",id:"synthetic-version"});
      await evaluate(cdp, `document.querySelectorAll('.pagination button')[1].click()`);
      await waitFor(() => evaluate(cdp, `!!document.querySelector('#passage-p125')`), "Next evidence page missing");
      await evaluate(cdp, `document.querySelectorAll('.pagination button')[0].click()`);
      await waitFor(() => evaluate(cdp, `!!document.querySelector('#passage-p100')`), "Previous evidence page missing");
      assert.ok(await evaluate(cdp, `document.documentElement.scrollWidth <= innerWidth + 1`), `Overflow: ${locale}/${width}`);
      if (locale === "en-CH") {
        await mkdir(join(root, ".tmp"), { recursive: true });
        await writeFile(join(root, ".tmp", `native-evidence-${width}.png`), Buffer.from((await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false })).data, "base64"));
      }
      await sleep(200);
      assert.equal(milestones.length, before + 1, "Pagination repeated completed display write");
      await navigate("/corpus-evidence/synthetic-version?passage=missing");
      await waitFor(() => evaluate(cdp, `!!document.querySelector('a[href="/corpus-evidence/synthetic-version"]')`), "Missing passage recovery link missing");
      await sleep(200);
      assert.equal(milestones.length, before + 1, "Missing citation recorded as viewed");
      mode = "sample";
      await navigate("/corpus-evidence/synthetic-version?passage=p100");
      await sleep(200);
      assert.equal(milestones.length, before + 1, "Demo source recorded as real evidence");
      mode = "text";
      await navigate("/corpus-evidence/synthetic-version");
      await waitFor(() => evaluate(cdp, `document.querySelector('[data-native-text]')?.innerText.includes('Saved text without passage identifiers')`), "Saved unnumbered text missing");
      assert.equal(await evaluate(cdp, `document.querySelectorAll('a[href*="/artifact"]').length`), 0, "Missing original has a fake download link");
      await evaluate(cdp, `document.querySelector('[data-evidence-display-text]').scrollIntoView({block:'center'})`);
      await waitFor(() => Promise.resolve(milestones.length === before + 2), "Saved unnumbered text display not recorded");
      mode = "empty";
      await navigate("/corpus-evidence/synthetic-version");
      await waitFor(() => evaluate(cdp, `!!document.querySelector('[data-native-text]')`), "Metadata-only state missing");
      assert.equal(await evaluate(cdp, `document.querySelectorAll('a[href^="javascript:"]').length`), 0, "Unsafe publisher URL rendered");
      await sleep(200);
      assert.equal(milestones.length, before + 2, "Metadata only recorded as text evidence");
      assert.ok(await evaluate(cdp, `!document.body.innerText.match(/nativeEvidence\.|\{(?:date|type|passages)\}/)`), "Untranslated evidence key");
    }
  }
  const beforeLegacy = milestones.length;
  mode = "passages";
  await navigate("/evidence/synthetic-version?passage=p100");
  await waitFor(() => evaluate(cdp, `!!document.querySelector('#passage-p100.evidence-target')`), "Legacy evidence regression");
  assert.ok(await evaluate(cdp, `!!document.querySelector('a[href="/laws/synthetic-law"]') && !!document.querySelector('a[href="/api/versions/synthetic-version/artifact#page=4"]')`));
  await waitFor(() => Promise.resolve(milestones.length === beforeLegacy + 1), "Legacy display not recorded");
  assert.deepEqual(milestones.at(-1), {kind:"version",id:"synthetic-version"});
  assert.deepEqual(exceptions, [], "Runtime exceptions in the real page");
  console.log("Native evidence production UI: 10 five-locale 390/1440px journeys pass later-page citations, PDF links, next/back, missing-passage recovery, text-only/metadata-only states, unavailable original and unsafe-source omission; legacy viewer smoke also passes. Milestones exclude controlled-background visibility, missing targets, demos and empty evidence, resume on visible text and avoid pagination duplicates. All APIs intercepted; no source/model/mail calls.");
} catch (error) {
  console.error({ requests, exceptions, page: cdp ? await evaluate(cdp, "JSON.stringify({url:location.href,ready:document.readyState,html:document.documentElement.outerHTML.slice(0,1800)})").catch(() => "unavailable") : "no browser" });
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const ended = new Promise(resolve => child.once("exit", resolve));
    child.kill();
    await Promise.race([ended, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-native-evidence-browser-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
