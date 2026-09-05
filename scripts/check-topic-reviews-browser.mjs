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
const profile = await mkdtemp(join(tmpdir(), "helvetic-topic-reviews-browser-"));
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
let locale = "en-CH", role = "organization_admin", fingerprint = "a".repeat(64), reviewId = null;
let savedReviews = [], failNext = false;
const posts = [];
const evidence = { work_title: "Synthetic citizenship development", source_url: "https://www.fedlex.admin.ch/eli/cc/synthetic", detected_at: "2026-09-05T08:00:00Z" };
const reasons = [{ type: "concept", value: "citizenship" }];
const currentMatch = () => ({ id: "synthetic-match", topic_id: "topic-a", is_current: true, validity: "matching", confidence: "high",
  evaluation_fingerprint: fingerprint, review_id: reviewId, decision: savedReviews[0]?.decision || "pending", decision_is_current: !!reviewId,
  matched_at: "2026-09-05T08:00:00Z", evidence, reasons });
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
    if (url.pathname === "/api/auth/session") body = { authenticated: true, user: { id: "qa", email: "qa@example.invalid", name: "QA", locale }, organization: { id: "qa-org", name: "Isolated QA" }, role };
    else if (url.pathname === "/api/health") body = { status: "ok", database: "sqlite", apertus: { configured: false, model: "qa" }, firecrawl: { configured: false }, private_sources_enabled: false };
    else if (url.pathname === "/api/jobs") body = [];
    else if (url.pathname === "/api/topic-matches/synthetic-match/reviews") {
      if (request.method === "POST") {
        const values = JSON.parse(request.postData); posts.push(values);
        if (role === "viewer") { code = 403; body = { detail: "Read only" }; }
        else if (failNext) { failNext = false; code = 503; body = { detail: "Synthetic temporary save failure" }; }
        else if (values.expected_evaluation_fingerprint !== fingerprint || values.expected_review_id !== reviewId) { code = 409; body = { detail: "Synthetic evidence changed. Reload evidence." }; }
        else {
          reviewId = `review-${savedReviews.length + 1}`;
          const review = { id: reviewId, decision: values.decision, note: values.note, actor_name: "Synthetic reviewer", created_at: "2026-09-05T08:30:00Z",
            snapshot: { evidence, reasons, confidence: "high", matched_at: "2026-09-05T08:00:00Z" } };
          savedReviews.unshift(review); body = { review, reused: false }; code = 201;
        }
      } else {
        const later = url.searchParams.has("cursor");
        body = { match: currentMatch(), items: later ? savedReviews.slice(2) : savedReviews.slice(0, 2), has_more: !later && savedReviews.length > 2,
          next_cursor: !later && savedReviews.length > 2 ? "older-reviews" : null };
      }
    } else { code = 503; body = { detail: "Unconfigured synthetic QA endpoint" }; }
    await cdp.send("Fetch.fulfillRequest", { requestId, responseCode: code, responseHeaders: [{ name: "Content-Type", value: "application/json" }], body: Buffer.from(JSON.stringify(body)).toString("base64") }).catch(() => {});
  });
  // Intercept every application API request before it can reach Next's proxy.
  await cdp.send("Fetch.enable", { patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }] });
  await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: "window.__reviewDocument = Math.random();" });
  const navigate = async () => {
    const navigation = await cdp.send("Page.navigate", { url: `${base}/topic-review?match=synthetic-match&locale=${locale}` });
    assert.ok(!navigation.errorText, JSON.stringify(navigation));
    await waitFor(() => evaluate(cdp, `!!document.querySelector('[data-topic-review-evidence]')`), "Review evidence failed to render");
  };
  const enterNote = async () => {
    await evaluate(cdp, `(() => { const input = document.querySelector('[data-topic-review-form] textarea'); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(input, 'Synthetic review rationale'); input.dispatchEvent(new Event('input', { bubbles: true })); })()`);
    await waitFor(() => evaluate(cdp, `!document.querySelectorAll('[data-topic-review-form] button')[1].disabled`), "Review actions did not enable with a rationale");
  };
  const clickDecision = async index => evaluate(cdp, `document.querySelectorAll('[data-topic-review-form] button')[${index}].click()`);
  for (locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    for (const width of [390, 1440]) {
      role = "organization_admin"; fingerprint = "a".repeat(64); reviewId = null; savedReviews = [];
      await cdp.send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 500 });
      await navigate();
      assert.ok(await evaluate(cdp, `document.documentElement.scrollWidth <= innerWidth + 1`), `Overflow: ${locale}/${width}`);
      assert.ok(await evaluate(cdp, `document.querySelectorAll('[data-topic-review-form] button')[1].disabled`), "Blank rationale allowed decision");
      const marker = await evaluate(cdp, "window.__reviewDocument");
      await enterNote(); failNext = true;
      const start = posts.length;
      await clickDecision(1);
      await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Synthetic temporary save failure')`), "Retry error missing");
      await clickDecision(1);
      await waitFor(() => evaluate(cdp, `document.querySelector('[data-topic-review-history]')?.innerText.includes('Synthetic review rationale') && !document.querySelectorAll('[data-topic-review-form] button')[0].disabled`), "Successful decision did not reach history");
      assert.equal(posts[start].request_key, posts[start + 1].request_key, "Unchanged retry created a second request identity");
      assert.equal(await evaluate(cdp, "window.__reviewDocument"), marker, "Saving a decision reloaded the document");
      await enterNote(); fingerprint = "b".repeat(64);
      await clickDecision(2);
      await waitFor(() => evaluate(cdp, `document.body.innerText.includes('Synthetic evidence changed')`), "Stale evidence was not rejected");
      await clickDecision(0);
      await waitFor(() => evaluate(cdp, `!document.querySelectorAll('[data-topic-review-form] button')[1].disabled`), "Evidence refresh did not restore deliberate review");
      await clickDecision(2);
      await waitFor(() => Promise.resolve(savedReviews.length === 2), "New-evidence rejection missing");
      assert.equal(posts.at(-1).expected_evaluation_fingerprint, fingerprint);
      assert.ok(await evaluate(cdp, `!document.body.innerText.match(/topicReview\.|\{(?:date|reasons)\}/)`), "Untranslated review key/placeholder");
      if (locale === "en-CH") {
        await mkdir(join(root, ".tmp"), { recursive: true });
        await writeFile(join(root, ".tmp", `topic-review-${width}.png`), Buffer.from((await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false })).data, "base64"));
      }
      await waitFor(() => evaluate(cdp, `!document.querySelectorAll('[data-topic-review-form] button')[0].disabled`), "Save did not settle");
      await enterNote();
      await clickDecision(1);
      await waitFor(() => evaluate(cdp, `document.querySelectorAll('[data-topic-review-history] article').length === 2 && !!document.querySelector('[data-topic-review-history] button')`), "History did not expose a bounded next page");
      await evaluate(cdp, `document.querySelector('[data-topic-review-history] button').click()`);
      await waitFor(() => evaluate(cdp, `document.querySelectorAll('[data-topic-review-history] article').length === 1`), "Older review page missing");
      await evaluate(cdp, `document.querySelector('[data-topic-review-history] button').click()`);
      await waitFor(() => evaluate(cdp, `document.querySelectorAll('[data-topic-review-history] article').length === 2`), "First history page did not restore");
      role = "viewer";
      await navigate();
      assert.equal(await evaluate(cdp, `document.querySelectorAll('[data-topic-review-form]').length`), 0, "Viewer received shared review controls");
      assert.ok(await evaluate(cdp, `document.querySelector('[data-topic-review-history]').innerText.includes('Synthetic review rationale')`), "Viewer cannot inspect retained history");
    }
  }
  assert.deepEqual(exceptions, [], "Runtime exceptions in the real page");
  console.log("Topic review production UI: 10 journeys (5 locales x 390/1440px), required rationale, same-key retry, append-only paginated history, no document reload, stale evidence conflict/reload and viewer history without write controls passed. Every API call intercepted; no real data/provider/mail.");
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
  assert.ok(basename(profile).startsWith("helvetic-topic-reviews-browser-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
