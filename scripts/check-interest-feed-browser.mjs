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
const profile = await mkdtemp(join(tmpdir(), "helvetic-feed-browser-"));
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
let locale = "en-CH", readingState = "unread";
const event = title => ({ event_id: title, title, source: "fedlex", type: "amended", document_kind: "act", lifecycle_status: null,
  detected_at: "2026-09-05T08:00:00Z", official_dates: [{ kind: "effective_from", value: "2027", precision: "year", provenance: "official_metadata", source_url: "https://example.invalid/date-source" }], read_state: readingState, severity: "unknown",
  source_url: "https://www.fedlex.admin.ch/eli/cc/synthetic", source_artifact_url: "/evidence/synthetic-version",
  jurisdictions: ["CH", "CH-ZH"], document_language: "de", provenance_method: "official_metadata", connector_health_at_detection: "degraded",
  monitored_documents: [{ watch_id: "own-watch", name: "Direct monitored document", url: "/laws/own-law" }], topic_matches: [
    { id: "topic-a", name: "Synthetic citizenship interest", url: "/topics#topic-a", confidence: "high", reasons: [{ type: "concept", value: "citizenship" }] },
    { id: "topic-b", name: "Synthetic naturalisation interest", url: "/topics#topic-b", confidence: "medium", reasons: [{ type: "concept", value: "naturalisation" }] },
  ], law_impacts: [{ organization_candidate_id: "candidate-a", law_title: "Synthetic citizenship act", status: "awaiting_analysis", severity: "unknown",
    potential_effect: "Waiting for a cited assessment, not a low-impact conclusion.", suggested_next_step: "Inspect saved evidence", links: { timeline: "/laws/law-a" } }] });
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
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url);
    requests.push(url.pathname + url.search);
    let body = {}, code = 200;
    if (url.pathname === "/api/auth/session") body = { authenticated: true, user: { id: "qa", email: "qa@example.invalid", name: "QA", locale }, organization: { id: "qa-org", name: "Isolated QA" }, role: "viewer" };
    else if (url.pathname === "/api/health") body = { status: "ok", database: "sqlite", apertus: { configured: false, model: "qa" }, firecrawl: { configured: false }, private_sources_enabled: false };
    else if (url.pathname === "/api/jobs") body = [];
    else if (url.pathname.startsWith("/api/interest-feed/events/") && request.method === "PATCH") {
      readingState = JSON.parse(request.postData).state; body = { state: readingState };
    } else if (url.pathname === "/api/interest-feed") {
      if (url.searchParams.get("cursor") === "bad") { code = 422; body = { detail: "Invalid cursor. Open the first page." }; }
      else {
        const later = url.searchParams.has("cursor"), sparse = !later && url.searchParams.get("period") === "yesterday";
        body = { items: sparse ? [] : [event(later ? "Older saved event" : "Newest saved event")],
          counts_scope: "page", scanned_event_count: 20, has_more: !later, next_cursor: !later ? "next" : null };
      }
    } else { code = 503; body = { detail: "Unconfigured synthetic QA endpoint" }; }
    await cdp.send("Fetch.fulfillRequest", { requestId, responseCode: code, responseHeaders: [{ name: "Content-Type", value: "application/json" }], body: Buffer.from(JSON.stringify(body)).toString("base64") }).catch(() => {});
  });
  // Intercept every application API request before it can reach Next's proxy.
  await cdp.send("Fetch.enable", { patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }] });
  await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: "window.__feedDocument = Math.random();" });
  const navigate = async query => {
    const navigation = await cdp.send("Page.navigate", { url: `${base}/${query}` });
    assert.ok(!navigation.errorText, JSON.stringify(navigation));
    await waitFor(() => evaluate(cdp, `!!document.querySelector('[data-inbox-navigation]')`), "Feed failed to render");
  };
  for (locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    for (const width of [390, 1440]) {
      readingState = "unread";
      await cdp.send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 500 });
      await navigate(`?locale=${locale}`);
      await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Newest saved event')`), "Initial event missing");
      assert.equal(await evaluate(cdp, `document.querySelectorAll('[data-feed-event]').length`), 1);
      assert.ok(await evaluate(cdp, `document.body.innerText.includes('Synthetic citizenship interest') && document.body.innerText.includes('Synthetic naturalisation interest') && document.body.innerText.includes('Synthetic citizenship act') && document.body.innerText.includes('Direct monitored document')`));
      assert.ok(await evaluate(cdp, `!!document.querySelector('a[href="/topics#topic-a"]') && !!document.querySelector('a[href="/impact?candidate=candidate-a"]')`));
      await evaluate(cdp, `document.querySelector('[data-feed-evidence] summary').click()`);
      assert.ok(await evaluate(cdp, `document.querySelector('[data-feed-evidence]').innerText.includes('CH-ZH') && document.querySelector('[data-feed-date] time').innerText === '2027'`), "Recorded scope/date precision missing");
      assert.ok(await evaluate(cdp, `!!document.querySelector('[data-feed-evidence] a[href="/evidence/synthetic-version"]') && !!document.querySelector('[data-feed-date] a[href="https://example.invalid/date-source"]')`), "Exact evidence links missing");
      assert.ok(await evaluate(cdp, `!document.querySelector('[data-feed-evidence]').innerText.includes('feedEvidence.')`), "Evidence translation key leaked");
      assert.ok(await evaluate(cdp, `document.documentElement.scrollWidth <= innerWidth + 1`), `Overflow: ${locale}/${width}`);
      assert.equal(await evaluate(cdp, `Array.from(document.querySelectorAll('[data-feed-event] select')).filter(el => el.getBoundingClientRect().height < 44).length`), 0);
      if (locale === "en-CH") {
        await evaluate(cdp, `document.querySelector('[data-feed-evidence]').scrollIntoView({ block: "start" })`);
        await mkdir(join(root, ".tmp"), { recursive: true });
        const shot = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
        await writeFile(join(root, ".tmp", `interest-feed-${width}.png`), Buffer.from(shot.data, "base64"));
      }
      const marker = await evaluate(cdp, "window.__feedDocument");
      await evaluate(cdp, `(() => { const select = document.querySelector('[data-feed-event] select'); select.value = 'read'; select.dispatchEvent(new Event('change', { bubbles: true })); })()`);
      await waitFor(() => evaluate(cdp, `document.querySelector('[data-feed-event] select')?.value === 'read' && !document.querySelector('[data-feed-event] select')?.disabled`), "Reading-state mutation did not settle");
      assert.equal(await evaluate(cdp, "window.__feedDocument"), marker, "Personal state reloaded the document");
      await evaluate(cdp, `document.querySelector('[data-inbox-navigation] a[href*="cursor=next"]').click()`);
      await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Older saved event')`), "Next page failed");
      await evaluate(cdp, "history.back()");
      await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Newest saved event')`), "Browser back failed");
      assert.ok(await evaluate(cdp, `!document.body.innerText.match(/feed\.(title|body|empty)|topics\.kind\.|\{(?:date|reasons)\}/)`), "Untranslated UI key");
    }
  }
  await evaluate(cdp, `document.querySelector('[data-feed-permalink]').click()`);
  await waitFor(() => evaluate(cdp, `location.search.includes('event=') && !!document.querySelector('[data-feed-all]')`), "Exact event route missing");
  await evaluate(cdp, `document.querySelector('[data-feed-all]').click()`);
  await waitFor(() => evaluate(cdp, `!location.search.includes('event=')`), "Return to all developments failed");
  await navigate("?period=yesterday");
  await waitFor(() => evaluate(cdp, `document.querySelectorAll('[data-feed-event]').length === 0 && !!document.querySelector('[data-inbox-navigation] a[href*="cursor=next"]')`), "Sparse page lost continuation");
  await evaluate(cdp, `document.querySelector('[data-inbox-navigation] a[href*="cursor=next"]').click()`);
  await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Older saved event')`), "Sparse continuation failed");
  await evaluate(cdp, `(() => { const select = document.querySelector('option[value="today"]').parentElement; select.value = 'today'; select.dispatchEvent(new Event('change', { bubbles: true })); })()`);
  await waitFor(() => evaluate(cdp, `location.search.includes('period=today') && !location.search.includes('cursor=')`), "Filter retained stale cursor");
  await navigate("?cursor=bad&state=unread");
  await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Invalid cursor')`), "Cursor recovery error missing");
  await evaluate(cdp, `document.querySelector('[data-inbox-navigation] a').click()`);
  await waitFor(() => evaluate(cdp, `!location.search.includes('cursor=') && location.search.includes('state=unread') && document.body.innerText.includes('Newest saved event')`), "Recovery discarded filters");
  assert.equal(requests.some(path => /\/(analyse|ask|model)($|[/?-])/.test(path)), false, "Viewing the feed started AI work");
  assert.deepEqual(exceptions, [], "Runtime exceptions in the real page");
  console.log("Interest feed production UI: 10 journeys (5 locales x 390/1440px), one card/two topics/one law, recorded scope/date precision and exact saved evidence links, event permalink/recovery, private read state without reload, next/back, sparse continuation, filter reset and cursor recovery passed. All API calls intercepted; no live provider or data mutation.");
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
  assert.ok(basename(profile).startsWith("helvetic-feed-browser-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
