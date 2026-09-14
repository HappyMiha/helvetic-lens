// Isolated built-product journey. Synthetic API responses; no production writes.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { sourceHistoryCopy } from "../apps/web/lib/source-history-copy.ts";
import { sourceOperationsCopy } from "../apps/web/lib/source-operations-copy.ts";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";

const root = resolve(import.meta.dirname, "..");
const chrome = [
  process.env.CHROME_BIN,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "/usr/bin/google-chrome",
]
  .filter(Boolean)
  .find(existsSync);
assert.ok(chrome);
const reserve = createServer();
await new Promise((done) => reserve.listen(0, "127.0.0.1", done));
const port = reserve.address().port;
await new Promise((done) => reserve.close(done));
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
  { cwd: join(root, "apps/web"), stdio: "ignore", windowsHide: true },
);
const profile = await mkdtemp(join(tmpdir(), "helvetic-source-history-qa-"));
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
let cdp,
  locale = "en-CH",
  admin = true,
  status = 200,
  readCount = 0,
  authReads = 0;
const exceptions = [],
  mutations = [];
const audit = new AccessibilityAudit("monitoring-source-history");
const packIds = [
  "safety_environment",
  "mobility",
  "business_opportunities",
  "intellectual_property",
];
const sourceDefs = [
  ["pollen", 0, "pollen"],
  ["river", 0, "river"],
  ["air", 0, "air"],
  ["warnings", 0, "hazard"],
  ["commute", 1, "commute"],
  ["traffic", 1, "road"],
  ["tenders", 2, "tender"],
  ["auctions", 2, "auction"],
  ["ip", 3, "trademark"],
];
const data = {
  checked_at: "2026-09-14T06:00:00Z",
  release: "fixture-release",
  packs: packIds,
  items: sourceDefs.map(([id, pack, path], i) => ({
    id,
    pack: packIds[pack],
    href: `/${path}-watch`,
    section_enabled: true,
    collector:
      id === "warnings"
        ? "channel_required"
        : id === "traffic"
          ? "credentials_required"
          : "configured",
    access: {
      state:
        i === 7
          ? "expired"
          : i === 8
            ? "revoked"
            : i < 3
              ? "public_contract"
              : "missing",
      expires_at: i === 7 ? "2026-09-13T00:00:00Z" : null,
    },
    acquisition: {
      state:
        i === 2
          ? "errors"
          : i === 0
            ? "invalid_clock"
            : i < 3
              ? "recorded"
              : "unobserved",
      record_count: i < 3 ? 2 : 0,
      never_succeeded_count: i === 2 ? 1 : null,
      error_count: i === 2 ? 1 : null,
      oldest_success_at: i < 3 ? "2026-09-14T03:00:00Z" : null,
      latest_success_at: i < 3 ? "2026-09-14T05:55:00Z" : null,
      source_published_at: null,
      next_request_at: "2026-09-14T06:05:00Z",
    },
  })),
};
data.items.find((i) => i.id === "commute").channels = [
  "trip_updates",
  "service_alerts",
].map((id) => ({
  id,
  collector: "credentials_required",
  access: { state: "missing", expires_at: null },
  acquisition: { ...data.items[6].acquisition },
}));
async function wait(check, message) {
  for (let i = 0; i < 200; i++) {
    if (
      await Promise.resolve()
        .then(check)
        .catch(() => false)
    )
      return;
    await sleep(100);
  }
  throw Error(message);
}
const body = () => evaluate(cdp, "document.body.innerText");
async function navigate(path = "/admin/monitoring-sources") {
  const previousAuth = authReads;
  await evaluate(cdp, "window.__previousAttention=true");
  await cdp.send("Page.navigate", { url: base + path });
  await wait(
    () =>
      evaluate(
        cdp,
        "!window.__previousAttention && document.documentElement.lang === " +
          JSON.stringify(locale),
      ),
    "New locale document missing",
  );
  await wait(() => authReads > previousAuth, "Fresh session response missing");
}
const pathAttention = "/api/admin/monitoring-sources/attention";
async function fulfilled(id, result, code = 200) {
  await cdp
    .send("Fetch.fulfillRequest", {
      requestId: id,
      responseCode: code,
      responseHeaders: [
        { name: "Content-Type", value: "application/json" },
        { name: "Cache-Control", value: "no-store" },
      ],
      body: Buffer.from(JSON.stringify(result)).toString("base64"),
    })
    .catch(() => {});
}
let historyMode = "ready",
  historyHeld = null;
function historyData(channel, days) {
  const checked = "2026-09-15T06:59:00Z",
    end = Date.parse("2026-09-15T06:00:00Z");
  const points = Array.from({ length: days * 24 }, (_, i) => {
    const missing = historyMode === "empty" || i % 5 === 0,
      value = (i + 1) * 60;
    const metric = {
      min_seconds: missing ? null : value / 2,
      max_seconds: missing ? null : value,
      known_samples: missing ? 0 : 12,
    };
    return {
      at: new Date(end - (days * 24 - 1 - i) * 3600000).toISOString(),
      samples: missing ? 0 : 12,
      expected_samples: 12,
      missing_samples: missing ? 12 : 0,
      states: missing ? {} : { [i % 7 === 0 ? "errors" : "recorded"]: 12 },
      access_states: missing ? {} : { record_current: 11, revoked: 1 },
      collector_states: missing ? {} : { configured: 11, disabled: 1 },
      disabled_samples: missing ? 0 : 1,
      binding_changed: i === days * 24 - 2,
      metrics: {
        latest_acquisition_age: metric,
        oldest_acquisition_age: {
          ...metric,
          max_seconds: missing ? null : value * 2,
        },
        publication_age: {
          min_seconds: null,
          max_seconds: null,
          known_samples: 0,
        },
      },
      last_state: missing
        ? null
        : {
            state: "recorded",
            access: "record_current",
            collector: "configured",
            section_enabled: true,
          },
    };
  });
  return {
    channel,
    days,
    checked_at: checked,
    first_sample_at: historyMode === "empty" ? null : points[1].at,
    last_sample_at: historyMode === "empty" ? null : points.at(-1).at,
    points,
  };
}
async function choose(selector, value) {
  await evaluate(
    cdp,
    "(()=>{const el=document.querySelector(" +
      JSON.stringify(selector) +
      ');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,"value").set.call(el,' +
      JSON.stringify(String(value)) +
      ');el.dispatchEvent(new Event("change",{bubbles:true}));})()',
  );
}
async function historyReady() {
  await wait(
    () =>
      evaluate(cdp, '!!document.querySelector("[data-source-history] svg")'),
    "Source history graph missing",
  );
}
async function refreshHistory() {
  await evaluate(
    cdp,
    'document.querySelector("[data-source-history] button").click()',
  );
  await historyReady();
}
try {
  await wait(async () => (await fetch(base)).ok, "Next did not start");
  let debugPort;
  await wait(async () => {
    debugPort = (
      await readFile(join(profile, "DevToolsActivePort"), "utf8")
    ).split("\n")[0];
    return !!debugPort;
  }, "Chrome did not start");
  const target = await fetch(
    `http://127.0.0.1:${debugPort}/json/new?about:blank`,
    { method: "PUT" },
  ).then((r) => r.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    exceptions.push(exceptionDetails.text),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    try {
      const path = new URL(request.url).pathname;
      let result = {},
        code = 200;
      if (request.method !== "GET") mutations.push(path);
      if (path === "/api/auth/session")
        result = {
          authenticated: true,
          user: {
            id: "ops-user",
            name: "Source QA",
            email: "qa@example.invalid",
            locale,
          },
          organization: { id: "qa-org", name: "Source QA" },
          role: "organization_admin",
          platform_admin: admin,
          onboarding_required: false,
        };
      else if (path === "/api/health")
        result = {
          status: "ok",
          database: "synthetic",
          apertus: { configured: false },
          firecrawl: { configured: false },
        };
      else if (path === "/api/admin/monitoring-sources") {
        readCount++;
        code = status;
        result =
          status === 200
            ? data
            : {
                code:
                  status === 403 ? "platform_admin_required" : "unavailable",
              };
      } else if (path === "/api/admin/monitoring-sources/history") {
        const query = new URL(request.url).searchParams;
        result = historyData(query.get("channel"), Number(query.get("days")));
        if (historyMode === "error") {
          code = 503;
          result = { code: "unavailable" };
        }
        if (historyMode === "denied") {
          code = 403;
          result = { code: "platform_admin_required" };
        }
        if (historyMode === "delayed") {
          historyHeld = { requestId, result };
          return;
        }
      } else if (path === pathAttention) {
        result = {
          checked_at: "2026-09-15T06:00:00Z",
          items: [],
          unacknowledged: 0,
        };
      } else if (path === "/api/jobs") result = [];
      else {
        code = 503;
        result = { code: "unavailable" };
      }
      await fulfilled(requestId, result, code);
      if (path === "/api/auth/session") authReads++;
    } catch (error) {
      exceptions.push(String(error));
      await fulfilled(requestId, { code: "fixture_failure" }, 500);
    }
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }],
  });
  await cdp.send("Network.setCookie", {
    name: "helvetic_lens_csrf",
    value: "synthetic",
    url: base,
  });

  for (const language of Object.keys(sourceHistoryCopy))
    for (const width of [390, 1440]) {
      locale = language;
      admin = true;
      status = 200;
      historyMode = "ready";
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: width === 390,
      });
      await navigate();
      await historyReady();
      const c = sourceHistoryCopy[locale];
      assert.equal(
        await evaluate(
          cdp,
          "document.documentElement.scrollWidth<=innerWidth+1",
        ),
        true,
      );
      const options = await evaluate(
        cdp,
        '[...document.querySelector("[data-history-channel]").options].map(o=>o.value)',
      );
      assert.equal(options.length, 10);
      assert.equal(new Set(options.map((k) => k.split(":")[0])).size, 9);
      for (const source of options) {
        await choose("[data-history-channel]", source);
        await historyReady();
        assert.ok((await body()).includes(c.boundary));
      }
      await audit.check(
        cdp,
        locale + "-" + width + "-chart",
        "[data-source-history] svg",
      );
      await choose("[data-history-period]", 30);
      await historyReady();
      await evaluate(
        cdp,
        'document.querySelector("[data-source-history] details").open=true',
      );
      await wait(
        () =>
          evaluate(
            cdp,
            'document.querySelectorAll("[data-history-hour]").length===24',
          ),
        "Hourly table missing",
      );
      await wait(
        async () => (await body()).includes(c.page + " 1 / 30"),
        "Thirty-day response missing",
      );
      await choose("[data-history-metric]", "publication_age");
      assert.equal(
        await evaluate(
          cdp,
          'document.querySelectorAll("[data-source-history] svg rect[fill=currentColor]").length',
        ),
        0,
      );
      assert.ok((await body()).includes(sourceOperationsCopy[locale].unknown));
      await choose("[data-history-metric]", "oldest_acquisition_age");
      await evaluate(
        cdp,
        '[...document.querySelectorAll("[data-source-history] button")].at(-1).click()',
      );
      await wait(
        async () => (await body()).includes(c.page + " 2 / 30"),
        "Next history page missing",
      );
      assert.equal(
        await evaluate(
          cdp,
          "document.documentElement.scrollWidth<=innerWidth+1",
        ),
        true,
      );
      await audit.check(
        cdp,
        locale + "-" + width + "-detail",
        "[data-history-hour]",
      );
      if (locale === "en-CH") {
        await evaluate(
          cdp,
          'document.querySelector("[data-source-history]").scrollIntoView({block:"start"})',
        );
        await writeFile(
          join(root, "test-results/source-history-" + width + ".png"),
          Buffer.from(
            (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
            "base64",
          ),
        );
      }
    }
  locale = "en-CH";
  historyMode = "ready";
  await navigate();
  await historyReady();
  historyMode = "error";
  await evaluate(
    cdp,
    'document.querySelector("[data-source-history] button").click()',
  );
  await wait(
    async () => (await body()).includes(sourceHistoryCopy[locale].failed),
    "History error missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      'document.querySelectorAll("[data-source-history] svg").length',
    ),
    0,
  );
  await audit.check(cdp, "read-failure", "[data-source-history]");
  historyMode = "empty";
  await refreshHistory();
  assert.ok((await body()).includes(sourceHistoryCopy[locale].empty));
  await audit.check(cdp, "empty", "[data-source-history]");
  historyMode = "ready";
  await refreshHistory();
  historyMode = "delayed";
  historyHeld = null;
  await choose("[data-history-channel]", "air");
  await wait(() => historyHeld !== null, "Delayed history missing");
  await evaluate(cdp, 'window.dispatchEvent(new Event("pagehide"))');
  await fulfilled(historyHeld.requestId, historyHeld.result);
  await sleep(250);
  assert.equal(
    await evaluate(
      cdp,
      'document.querySelectorAll("[data-source-history] svg").length',
    ),
    0,
  );
  historyMode = "ready";
  await navigate();
  await historyReady();
  historyMode = "denied";
  await evaluate(
    cdp,
    'document.querySelector("[data-source-history] button").click()',
  );
  await wait(
    async () => (await body()).includes(sourceOperationsCopy[locale].failed),
    "Parent denial missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      'document.querySelectorAll("[data-source-history] svg,[data-source-direction]").length',
    ),
    0,
  );
  await audit.check(cdp, "revoked", "[data-monitoring-source-operations]");
  admin = false;
  historyMode = "ready";
  await navigate();
  await wait(
    () =>
      evaluate(
        cdp,
        '!!document.querySelector("[role=alert]")?.getClientRects().length',
      ),
    "Visible non-admin denial missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      'document.querySelectorAll("[data-source-history]").length',
    ),
    0,
  );
  await audit.check(cdp, "non-admin", "[role=alert]");
  assert.deepEqual(exceptions, []);
  assert.ok(mutations.every((p) => p.startsWith("/api/assistant/")));
  audit.finish(24);
  console.log(
    "Source history: nine categories/two transport channels, five locales/two widths, chart metrics, 30-day paginated detail, unknown/gaps, error/empty/revoked/late response and 24 full-document axe checkpoints. Synthetic API.",
  );
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const stopped = new Promise((done) => child.once("exit", done));
    child.kill();
    await Promise.race([stopped, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-source-history-qa-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
