// Isolated built-product journey. Synthetic API responses; no production writes.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { sourceAttentionCopy } from "../apps/web/lib/source-attention-copy.ts";
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-source-attention-qa-"));
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
  readCount = 0;
const exceptions = [],
  mutations = [];
const audit = new AccessibilityAudit("monitoring-source-attention");
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
}
async function reload() {
  await evaluate(
    cdp,
    "document.querySelector('[data-monitoring-source-operations] header button').click()",
  );
}
const pathAttention = "/api/admin/monitoring-sources/attention";
let rows = [],
  attentionStatus = 200,
  mode = "ready",
  held = null;
function seedAttention() {
  rows = data.items.flatMap((source) =>
    (source.channels || [source]).map((channel) => ({
      key: source.id + ":" + channel.id + ":renewal_7_days",
      domain: source.id,
      channel: channel.id,
      code: "renewal_7_days",
      severity: "urgent",
      fingerprint: "a".repeat(64),
      expires_at: "2026-09-20T06:00:00Z",
      latest_success_at: null,
      next_request_at: null,
      acknowledged_at: null,
    })),
  );
}
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
async function button(name) {
  await wait(
    () =>
      evaluate(
        cdp,
        '(()=>{const b=[...document.querySelectorAll("[data-source-attention] button")].find(b=>b.textContent.trim()===' +
          JSON.stringify(name) +
          "&&!b.disabled);if(!b)return false;b.click();return true;})()",
      ),
    "Missing attention button " + name,
  );
}
async function ready(count = 10) {
  await wait(
    () =>
      evaluate(
        cdp,
        'document.querySelectorAll("[data-source-issue]").length===' + count,
      ),
    "Attention rows missing",
  );
}
async function filter(value) {
  await evaluate(
    cdp,
    '(()=>{const el=document.querySelector("[data-source-attention] select");Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,"value").set.call(el,' +
      JSON.stringify(value) +
      ');el.dispatchEvent(new Event("change",{bubbles:true}));})()',
  );
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
      } else if (path === pathAttention) {
        code = attentionStatus;
        result =
          code === 200
            ? {
                checked_at: "2026-09-15T06:00:00Z",
                items: structuredClone(rows),
                unacknowledged: rows.filter((r) => !r.acknowledged_at).length,
              }
            : {
                code: code === 403 ? "platform_admin_required" : "unavailable",
              };
      } else if (path === pathAttention + "/acknowledge") {
        const body = JSON.parse(request.postData);
        assert.deepEqual(Object.keys(body).sort(), ["fingerprint", "key"]);
        const row = rows.find((r) => r.key === body.key);
        assert.ok(row);
        assert.equal(body.fingerprint, row.fingerprint);
        if (mode === "conflict") {
          code = 409;
          result = { code: "source_attention_changed" };
        } else if (mode === "denied") {
          code = 403;
          result = { code: "platform_admin_required" };
        } else {
          row.acknowledged_at = "2026-09-15T06:00:00Z";
          result = {
            key: row.key,
            fingerprint: row.fingerprint,
            acknowledged_at: row.acknowledged_at,
          };
        }
        if (mode === "delayed") {
          held = { requestId, result };
          return;
        }
      } else if (path === "/api/jobs") result = [];
      else {
        code = 503;
        result = { code: "unavailable" };
      }
      await fulfilled(requestId, result, code);
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
  for (const language of Object.keys(sourceAttentionCopy))
    for (const width of [390, 1440]) {
      locale = language;
      seedAttention();
      mode = "ready";
      attentionStatus = 200;
      admin = true;
      status = 200;
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: width === 390,
      });
      await navigate();
      await ready();
      const c = sourceAttentionCopy[locale];
      assert.equal(
        await evaluate(
          cdp,
          "document.documentElement.scrollWidth<=innerWidth+1",
        ),
        true,
      );
      assert.ok((await body()).includes(c.renewal7));
      const links = await evaluate(
        cdp,
        '[...document.querySelectorAll("[data-source-issue] a")].map(a=>a.getAttribute("href"))',
      );
      assert.equal(new Set(links).size, 9);
      assert.ok(
        links.every((h) => h.startsWith("/monitoring/settings?category=")),
      );
      await audit.check(
        cdp,
        locale + "-" + width + "-pending",
        "[data-source-attention]",
      );
      await button(c.acknowledge);
      await ready(9);
      await filter("all");
      await ready();
      assert.ok((await body()).includes(c.acknowledged));
      await audit.check(
        cdp,
        locale + "-" + width + "-acknowledged",
        "[data-source-attention]",
      );
      rows[0].fingerprint = "b".repeat(64);
      rows[0].acknowledged_at = null;
      await button(sourceOperationsCopy[locale].refresh);
      await ready();
      assert.equal(
        await evaluate(
          cdp,
          'document.querySelectorAll("[data-source-issue] button").length',
        ),
        10,
      );
      if (locale === "en-CH") {
        await evaluate(
          cdp,
          'document.querySelector("[data-source-attention]").scrollIntoView({block:"start"})',
        );
        await writeFile(
          join(root, "test-results/source-attention-" + width + ".png"),
          Buffer.from(
            (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
            "base64",
          ),
        );
      }
    }
  locale = "en-CH";
  seedAttention();
  await navigate();
  await ready();
  for (const fault of ["conflict", "denied"]) {
    mode = fault;
    await button(sourceAttentionCopy[locale].acknowledge);
    await wait(
      () =>
        evaluate(
          cdp,
          'document.querySelectorAll("[data-source-issue]").length===0',
        ),
      "Failure retained issue actions",
    );
    assert.ok(
      (await body()).includes(
        fault === "denied"
          ? sourceOperationsCopy[locale].failed
          : sourceAttentionCopy[locale].failed,
      ),
    );
    await audit.check(cdp, fault, "[data-monitoring-source-operations]");
    mode = "ready";
    await navigate();
    await ready();
  }
  mode = "delayed";
  await button(sourceAttentionCopy[locale].acknowledge);
  await wait(() => held !== null, "Delayed acknowledgement missing");
  await evaluate(cdp, 'window.dispatchEvent(new Event("pagehide"))');
  await fulfilled(held.requestId, held.result);
  await sleep(300);
  assert.equal(
    await evaluate(
      cdp,
      'document.querySelectorAll("[data-source-issue]").length',
    ),
    0,
  );
  mode = "ready";
  seedAttention();
  await navigate();
  await ready();
  attentionStatus = 503;
  await button(sourceOperationsCopy[locale].refresh);
  await wait(
    async () => (await body()).includes(sourceAttentionCopy[locale].failed),
    "Read error missing",
  );
  await audit.check(cdp, "read-failure", "[data-source-attention]");
  attentionStatus = 200;
  await button(sourceOperationsCopy[locale].refresh);
  await ready();
  admin = false;
  await navigate();
  await wait(
    async () => (await body()).includes(sourceOperationsCopy[locale].denied),
    "Non-admin denial missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      'document.querySelectorAll("[data-source-issue]").length',
    ),
    0,
  );
  await wait(
    () =>
      evaluate(
        cdp,
        `[...document.querySelectorAll('[role=alert]')].some(e=>e.getClientRects().length)`,
      ),
    "Visible non-admin denial missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      'document.querySelectorAll("[data-source-issue]").length',
    ),
    0,
  );
  await audit.check(cdp, "non-admin", '[role="alert"]');
  assert.ok(
    mutations.every(
      (p) =>
        p === pathAttention + "/acknowledge" || p.startsWith("/api/assistant/"),
    ),
  );
  assert.deepEqual(exceptions, []);
  audit.finish(24);
  console.log(
    "Source attention: 24 full-document axe checkpoints; nine categories, two transport channels, five locales/two widths, acknowledge/reopen, stale/denied/failed reads, pagehide late response and metadata isolation. Synthetic browser API.",
  );
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const stopped = new Promise((done) => child.once("exit", done));
    child.kill();
    await Promise.race([stopped, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-source-attention-qa-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
