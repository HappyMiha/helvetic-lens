// Real production UI with intercepted synthetic API responses. No live backend.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { createServer } from "node:net";
import { Cdp, evaluate, pollJson, sleep } from "./browser-cdp.mjs";

const root = resolve(import.meta.dirname, "..");
const chrome = [
  process.env.CHROME_BIN,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
]
  .filter(Boolean)
  .find(existsSync);
assert.ok(chrome, "A real Chrome executable is required.");
const reserve = createServer();
await new Promise((resolve) => reserve.listen(0, "127.0.0.1", resolve));
const port = reserve.address().port;
await new Promise((resolve) => reserve.close(resolve));
const base = `http://127.0.0.1:${port}`;
const server = spawn(
  process.execPath,
  [
    join(root, "node_modules/next/dist/bin/next"),
    "start",
    "-H",
    "127.0.0.1",
    "-p",
    String(port),
  ],
  {
    cwd: join(root, "apps/web"),
    stdio: "ignore",
    windowsHide: true,
  },
);
const profile = await mkdtemp(join(tmpdir(), "helvetic-digests-browser-"));
const browser = spawn(
  chrome,
  [
    "--headless=new",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: "ignore", windowsHide: true },
);
let cdp;
const requests = [],
  exceptions = [];
async function waitFor(check, message) {
  for (let i = 0; i < 150; i++) {
    if (await check().catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}

let locale = "en-CH",
  revision = 1,
  invalid = false;
let preference;
const defaultPreference = () => ({
  enabled: false,
  frequency: "weekly",
  severities: ["high"],
  sources: [],
  next_delivery_at: null,
  last_sent_at: null,
});
function response(cursor = "") {
  const index = cursor ? Number(cursor.split(":")[1]) : 0;
  const stamp = `2026-09-05T${String(8 + revision).padStart(2, "0")}:00:00Z`;
  return {
    preference,
    source_options: ["fedlex"],
    delivery_mode: "disabled",
    deliveries: [],
    preview: {
      events:
        index < 2
          ? []
          : [
              {
                event_id: "synthetic-match",
                title: "Synthetic matching event",
                source: "fedlex",
                severity: "high",
                detected_at: "2026-09-05T08:00:00Z",
                source_url: null,
                impacts: [],
              },
            ],
      truncated: false,
      counts_scope: "page",
      scanned_event_count: index < 2 ? 50 : 21,
      period_start: "2026-08-29T08:00:00Z",
      period_end: stamp,
      has_more: index < 2,
      current_cursor: `${revision}:${index}`,
      next_cursor: index < 2 ? `${revision}:${index + 1}` : null,
    },
  };
}
try {
  await waitFor(
    async () => (await fetch(base)).ok,
    "Isolated production UI failed to start",
  );
  let debugPort;
  await waitFor(async () => {
    debugPort = (
      await readFile(join(profile, "DevToolsActivePort"), "utf8")
    ).split("\n")[0];
    return !!debugPort;
  }, "Browser failed to start");
  await pollJson(`http://127.0.0.1:${debugPort}/json/version`);
  const target = await fetch(
    `http://127.0.0.1:${debugPort}/json/new?about:blank`,
    { method: "PUT" },
  ).then((response) => response.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    exceptions.push(exceptionDetails.text),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url);
    requests.push({
      method: request.method,
      path: url.pathname + url.search,
      body: request.postData,
    });
    let body = {},
      code = 200;
    if (url.pathname === "/api/auth/session")
      body = {
        authenticated: true,
        user: { id: "qa", email: "qa@example.invalid", name: "QA", locale },
        organization: { id: "qa-org", name: "Isolated QA" },
        role: "viewer",
      };
    else if (url.pathname === "/api/health")
      body = {
        status: "ok",
        database: "sqlite",
        apertus: { configured: false, model: "qa" },
        firecrawl: { configured: false },
        private_sources_enabled: false,
      };
    else if (url.pathname === "/api/jobs") body = [];
    else if (
      url.pathname === "/api/digests" ||
      url.pathname === "/api/digests/preferences"
    ) {
      const cursor = url.searchParams.get("cursor") || "";
      if (url.searchParams.get("preview_page") !== "true") {
        code = 500;
        body = { detail: "Unbounded preview used" };
      } else if (request.method === "PUT") {
        preference = { ...preference, ...JSON.parse(request.postData) };
        revision++;
        body = response();
      } else if (
        cursor &&
        (invalid || Number(cursor.split(":")[0]) !== revision)
      ) {
        code = 422;
        body = { code: "invalid_digest_cursor", detail: "Restart preview" };
      } else body = response(cursor);
      await sleep(100); // Exercise a real pending page/save, including disabled controls.
    } else {
      code = 503;
      body = { detail: "Unconfigured synthetic QA endpoint" };
    }
    await cdp
      .send("Fetch.fulfillRequest", {
        requestId,
        responseCode: code,
        responseHeaders: [{ name: "Content-Type", value: "application/json" }],
        body: Buffer.from(JSON.stringify(body)).toString("base64"),
      })
      .catch(() => {});
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }],
  });
  async function click(selector) {
    await evaluate(
      cdp,
      `document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center',inline:'nearest'})`,
    );
    await evaluate(
      cdp,
      `new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`,
    );
    const point = await evaluate(
      cdp,
      `(() => { const el=document.querySelector(${JSON.stringify(selector)}); const r=el.getBoundingClientRect(); const x=r.left+r.width/2,y=r.top+r.height/2; return {x,y,hit:el.contains(document.elementFromPoint(x,y)),disabled:el.disabled}; })()`,
    );
    assert.ok(point.hit && !point.disabled, `Unreachable control: ${selector}`);
    await cdp.send("Input.dispatchMouseEvent", {
      type: "mousePressed",
      x: point.x,
      y: point.y,
      button: "left",
      clickCount: 1,
    });
    await cdp.send("Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x: point.x,
      y: point.y,
      button: "left",
      clickCount: 1,
    });
  }
  const ready = () =>
    evaluate(
      cdp,
      `!!document.querySelector('[data-digest-navigation]') && !document.querySelector('[data-digest-preview]').matches('[aria-busy="true"]')`,
    );
  const form = () =>
    evaluate(
      cdp,
      `(() => { const f=document.querySelector('main fieldset'); return {enabled:f.querySelector('input[type=checkbox]').checked, frequency:f.querySelector('select').value}; })()`,
    );
  for (locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    for (const width of [390, 1440]) {
      revision = 1;
      invalid = false;
      preference = defaultPreference();
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: width < 500,
      });
      const start = requests.length;
      await cdp.send("Page.navigate", {
        url: `${base}/digests?locale=${locale}`,
      });
      await waitFor(ready, "Digest preview failed to render");
      assert.equal(
        await evaluate(cdp, `document.documentElement.lang`),
        locale,
      );
      const firstText = await evaluate(
        cdp,
        `document.querySelector('[data-digest-navigation]').innerText`,
      );
      assert.ok(
        firstText.includes("0") &&
          firstText.includes("50") &&
          !firstText.includes("digestPage."),
      );
      await sleep(350);
      assert.equal(
        requests.slice(start).filter((r) => r.path.startsWith("/api/digests"))
          .length,
        1,
        "A sparse page must not automatically exhaust the period",
      );
      await click("main fieldset input[type=checkbox]");
      assert.equal((await form()).enabled, true);
      await click("[data-digest-next]");
      await waitFor(
        async () =>
          (await ready()) &&
          requests.slice(start).some((r) => r.path.includes("cursor=1%3A1")),
        "First continuation missing",
      );
      assert.equal(
        (await form()).enabled,
        true,
        "Paging overwrote unsaved preference",
      );
      assert.equal(
        await evaluate(
          cdp,
          `document.activeElement === document.querySelector('[data-digest-preview] h2')`,
        ),
        true,
        "Paging lost keyboard focus",
      );
      await click("[data-digest-next]");
      await waitFor(
        async () =>
          (await ready()) &&
          (await evaluate(
            cdp,
            `document.body.innerText.includes('Synthetic matching event')`,
          )),
        "Sparse continuation never reached its match",
      );
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('[data-digest-next]').disabled`,
        ),
        true,
      );
      await click("[data-digest-back]");
      await waitFor(ready, "Back to middle page failed");
      await click("[data-digest-back]");
      await waitFor(ready, "Back to pinned first page failed");
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('[data-digest-navigation]').innerText`,
        ),
        firstText,
      );
      await click("main fieldset button");
      await waitFor(
        async () =>
          (await ready()) &&
          requests.slice(start).some((r) => r.method === "PUT") &&
          (await evaluate(
            cdp,
            `!document.querySelector('main fieldset').disabled`,
          )),
        "Saved preferences did not produce a new bounded preview",
      );
      assert.equal((await form()).enabled, true);
      const saved = requests.slice(start).find((r) => r.method === "PUT");
      assert.deepEqual(JSON.parse(saved.body), {
        enabled: true,
        frequency: "weekly",
        severities: ["high"],
        sources: [],
      });
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('[data-digest-back]').disabled`,
        ),
        true,
      );
      invalid = true;
      await click("[data-digest-next]");
      await waitFor(
        () =>
          evaluate(
            cdp,
            `!document.querySelector('[data-digest-navigation]') && !!document.querySelector('[data-digest-recovery]') && !document.body.innerText.includes('error.invalid_digest_cursor')`,
          ),
        "Stale cursor error did not offer recovery",
      );
      invalid = false;
      await click("[data-digest-recovery]");
      await waitFor(ready, "Restart failed");
      assert.equal(
        (await form()).enabled,
        true,
        "Recovery overwrote current choices",
      );
      assert.ok(
        await evaluate(
          cdp,
          `document.documentElement.scrollWidth <= innerWidth + 1`,
        ),
        `${locale} overflow at ${width}px`,
      );
      assert.equal(
        await evaluate(
          cdp,
          `Array.from(document.querySelectorAll('[data-digest-navigation] button')).filter(el=>el.getBoundingClientRect().height<44).length`,
        ),
        0,
        "Small touch controls",
      );
      const calls = requests
        .slice(start)
        .filter((r) => r.path.startsWith("/api/digests"));
      assert.ok(calls.every((r) => r.path.includes("preview_page=true")));
      assert.equal(
        calls.filter((r) => r.method !== "GET" && r.method !== "PUT").length,
        0,
      );
      if (locale === "en-CH") {
        await evaluate(
          cdp,
          `document.querySelector('[data-digest-navigation]').scrollIntoView({block:'center'})`,
        );
        await mkdir(join(root, "test-results/digest-preview"), {
          recursive: true,
        });
        const shot = await cdp.send("Page.captureScreenshot", {
          format: "png",
        });
        await writeFile(
          join(root, `test-results/digest-preview/preview-${width}.png`),
          Buffer.from(shot.data, "base64"),
        );
      }
    }
  }
  assert.equal(
    requests.some((r) => r.path.startsWith("/api/digests/send")),
    false,
  );
  assert.deepEqual(exceptions, []);
  console.log(
    "Digest production UI: 10 journeys (DE/FR/IT/RM/EN x 390/1440px); bounded sparse next/back, captured period, focus, unsaved choices, explicit save, stale-cursor recovery and touch targets pass. All API calls intercepted; no mail, inference or production data touched.",
  );
} catch (error) {
  console.error({
    requests,
    exceptions,
    page: cdp
      ? await evaluate(
          cdp,
          "JSON.stringify({url:location.href,ready:document.readyState,html:document.documentElement.outerHTML.slice(0,1800)})",
        ).catch(() => "unavailable")
      : "no browser",
  });
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const ended = new Promise((resolve) => child.once("exit", resolve));
    child.kill();
    await Promise.race([ended, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-digests-browser-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
