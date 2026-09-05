// Real production UI with intercepted synthetic API responses. No live backend.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-inbox-browser-"));
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
const law = { organization_candidate_id: "candidate-old", candidate_id: "shared", watch_id: "watch", law_id: "law", law_title: "Synthetic monitored law",
  status: "awaiting_analysis", severity: "unknown", why: ["Saved official reference"], potential_effect: "Awaiting evidence review", suggested_next_step: "Inspect the saved evidence", coverage: {}, analysis_history_count: 0, review_history_count: 0, links: { timeline: "/laws/law", analysis_history: "/api/test" } };
const event = title => ({ event_id: title, title, source: "fedlex", authority: "Fedlex", type: "amended", document_kind: "law", detected_at: "2026-09-05T08:00:00Z", read_state: "unread", severity: "unknown", coverage: { analysed: 0, total: 1 }, items: [law] });
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
    if (url.pathname === "/api/auth/session") body = { authenticated: true, user: { id: "qa", email: "qa@example.invalid", name: "QA", locale: "en-CH" }, organization: { id: "qa-org", name: "Isolated QA" }, role: "viewer" };
    else if (url.pathname === "/api/health") body = { status: "ok", database: "sqlite", apertus: { configured: false, model: "qa" }, firecrawl: { configured: false }, private_sources_enabled: false };
    else if (url.pathname === "/api/jobs") body = [];
    else if (url.pathname === "/api/impact-inbox/law-options") body = { items: [{ id: "law", watch_id: "watch", title: "Synthetic monitored law" }, { id: "other", watch_id: "other-watch", title: "Law from another page" }], selected: null, has_more: true };
    else if (url.pathname === "/api/impact-inbox/page") {
      if (url.searchParams.get("cursor") === "bad") { code = 422; body = { code: "invalid_inbox_cursor", detail: "Invalid cursor. Open the first page." }; }
      else {
        const later = url.searchParams.has("cursor"), linked = url.searchParams.has("candidate"), sparse = !later && url.searchParams.get("severity") === "high";
        body = { items: sparse ? [] : [event(linked ? "Linked historical event" : later ? "Older saved event" : "Newest saved event")], total_events: sparse ? 0 : 1, total_impacts: sparse ? 0 : 1, unread: sparse ? 0 : 1,
          counts_scope: "page", scanned_event_count: linked ? 1 : 50, has_more: !later && !linked, next_cursor: !later && !linked ? "next" : null };
      }
    } else { code = 503; body = { detail: "Unconfigured synthetic QA endpoint" }; }
    await cdp.send("Fetch.fulfillRequest", { requestId, responseCode: code, responseHeaders: [{ name: "Content-Type", value: "application/json" }], body: Buffer.from(JSON.stringify(body)).toString("base64") }).catch(() => {});
  });
  // Intercept every application API request before it can reach Next's proxy.
  await cdp.send("Fetch.enable", { patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }] });
  const navigate = async query => {
    const navigation = await cdp.send("Page.navigate", { url: `${base}/impact${query}` });
    assert.ok(!navigation.errorText, JSON.stringify(navigation));
    await waitFor(() => evaluate(cdp, `!!document.querySelector('[data-inbox-navigation]') && document.body.innerText.includes('On this page')`), "Inbox failed to render");
  };
  await navigate("");
  await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Newest saved event')`), "Initial event missing");
  await evaluate(cdp, `document.querySelector('[data-inbox-navigation] a[href*="cursor=next"]').click()`);
  await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Older saved event')`), "Next-page click failed");
  assert.ok(await evaluate(cdp, `document.body.innerText.includes('On this page') && !!document.querySelector('option[value="other"]')`));
  await evaluate(cdp, `history.back()`);
  await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Newest saved event')`), "Browser back failed");
  await navigate("?severity=high");
  await waitFor(() => evaluate(cdp, `document.body.innerText.includes('No events on this page match')`), "Sparse page was mistaken for exhaustion");
  assert.ok(await evaluate(cdp, `!!document.querySelector('[data-inbox-navigation] a[href*="cursor=next"]')`));
  await navigate("?candidate=candidate-old");
  await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Linked historical event')`), "Notification deep link lost its event");
  await evaluate(cdp, `(() => { const select = document.querySelector('option[value="other"]').parentElement; select.value = 'other'; select.dispatchEvent(new Event('change', { bubbles: true })); })()`);
  await waitFor(() => evaluate(cdp, `location.search.includes('watched_law=other') && !location.search.includes('candidate=') && !location.search.includes('cursor=')`), "Filter change retained a stale cursor/target");
  await navigate("?cursor=bad&state=unread");
  await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Invalid cursor')`), "Cursor recovery error missing");
  await evaluate(cdp, `document.querySelector('[data-inbox-navigation] a').click()`);
  await waitFor(() => evaluate(cdp, `!location.search.includes('cursor=') && location.search.includes('state=unread') && document.body.innerText.includes('Newest saved event')`), "Cursor recovery discarded filters");
  for (const width of [390, 768, 1024, 1440]) {
    await cdp.send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 500 });
    await sleep(150);
    assert.ok(await evaluate(cdp, `document.documentElement.scrollWidth <= innerWidth + 1`), `Page overflows at ${width}px`);
    assert.equal(await evaluate(cdp, `Array.from(document.querySelectorAll('[data-inbox-navigation] a')).filter(el => el.getBoundingClientRect().height < 44).length`), 0);
  }
  assert.equal(requests.some(path => path.split("?")[0] === "/api/impact-inbox"), false, "The UI must never fetch the legacy full-history inbox");
  assert.deepEqual(exceptions, [], "Runtime exceptions in the real page");
  console.log("Inbox production UI: next/back navigation, independent law options, sparse pages, candidate deep links, filter reset, invalid-cursor recovery, 390/768/1024/1440px layout passed. Every API call was intercepted; no live backend/model or data mutation.");
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
  assert.ok(basename(profile).startsWith("helvetic-inbox-browser-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
