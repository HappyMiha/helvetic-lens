// Compiled UI with synthetic native review contracts; real readers have API tests.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { monitoringSettingsCopy as copy } from "../apps/web/lib/monitoring-settings-copy.ts";

import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";

const root = resolve(import.meta.dirname, "..");
const chrome = [
  process.env.CHROME_BIN,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/google-chrome",
]
  .filter(Boolean)
  .find(existsSync);
assert.ok(chrome);
const reserve = createServer();
await new Promise((r) => reserve.listen(0, "127.0.0.1", r));
const port = reserve.address().port;
await new Promise((r) => reserve.close(r));
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-connector-check-"));
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
const audit = new AccessibilityAudit("monitoring-settings");
const domains = [
  "pollen",
  "river",
  "air",
  "warnings",
  "commute",
  "traffic",
  "tenders",
  "ip",
  "auctions",
];
const panel = "[data-connector-settings]";
let cdp,
  locale = "en-CH",
  domain = "pollen",
  isAdmin = true,
  revision = 0,
  mode = "ready",
  checks = 0;
const traffic = [],
  exceptions = [];
const fields = () =>
  ({
    pollen: [],
    river: [],
    air: [],
    warnings: [{ id: "hazard_source_enabled", kind: "boolean", value: true }],
    commute: [
      { id: "commute_source_enabled", kind: "boolean", value: true },
      { id: "commute_gtfs_rt_key", kind: "secret", configured: true },
      { id: "commute_gtfs_sa_key", kind: "secret", configured: false },
    ],
    traffic: [{ id: "road_source_key", kind: "secret", configured: true }],
    tenders: [
      { id: "simap_public_source_enabled", kind: "boolean", value: true },
      {
        id: "tender_monitor_max_versions",
        kind: "integer",
        value: 10000,
        minimum: 1,
        maximum: 1000000,
      },
    ],
    ip: [
      { id: "ipi_source_enabled", kind: "boolean", value: true },
      { id: "ipi_username", kind: "login", configured: true },
      { id: "ipi_password", kind: "password", configured: true },
      {
        id: "ipi_source_permission_id",
        kind: "permission",
        value: "",
        choices: [],
      },
    ],
    auctions: [{ id: "aste_source_enabled", kind: "boolean", value: true }],
  })[domain];
const state = () => ({ domain, revision, fields: fields(), check: null });
async function wait(fn, message) {
  for (let n = 0; n < 200; n++) {
    if (
      await Promise.resolve()
        .then(fn)
        .catch(() => false)
    )
      return;
    await sleep(75);
  }
  throw Error(message);
}
const text = (selector) =>
  evaluate(
    cdp,
    `document.querySelector(${JSON.stringify(selector)})?.innerText||''`,
  );
async function button(label) {
  await wait(
    () =>
      evaluate(
        cdp,
        `[...document.querySelectorAll('${panel} button')].some(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled)`,
      ),
    `Missing button ${label}`,
  );
  await evaluate(
    cdp,
    `[...document.querySelectorAll('${panel} button')].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled).click()`,
  );
}
async function navigate() {
  await evaluate(cdp, "window.__oldSettingsDocument=true");
  await cdp.send("Page.navigate", {
    url: `${base}/monitoring/settings?category=${domain}&qa=${Date.now()}`,
  });
  await wait(
    () =>
      evaluate(
        cdp,
        `!window.__oldSettingsDocument&&document.documentElement.lang===${JSON.stringify(locale)}&&document.querySelector('[data-native-settings]')&&[...document.querySelectorAll('button[title]')].some(b=>b.title.includes('Connector QA'))`,
      ),
    "Settings not ready",
  );
  await wait(
    () =>
      text(panel).then((t) =>
        t.includes(isAdmin ? copy[locale].check : copy[locale].admin),
      ),
    "Connection missing",
  );
}
async function check(name) {
  assert.ok(
    await evaluate(cdp, "document.documentElement.scrollWidth<=innerWidth+1"),
    "Horizontal overflow",
  );
  await audit.check(cdp, name, panel);
  checks++;
}
try {
  await wait(async () => (await fetch(base)).ok, "Next did not start");
  let debugPort, target;
  await wait(async () => {
    debugPort = (
      await readFile(join(profile, "DevToolsActivePort"), "utf8")
    ).split("\n")[0];
    return !!debugPort;
  }, "Chrome not ready");
  await wait(async () => {
    target = await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, {
      method: "PUT",
    }).then((r) => r.json());
    return !!target.webSocketDebuggerUrl;
  }, "Debugger unavailable");
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    exceptions.push(
      exceptionDetails.exception?.description || exceptionDetails.text,
    ),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const path = new URL(request.url).pathname;
    traffic.push({
      path,
      method: request.method,
      body: request.postData,
      domain,
    });
    let code = 200,
      body = {};
    if (path === "/api/auth/session")
      body = {
        authenticated: true,
        user: {
          id: "00000000-0000-4000-8000-000000000001",
          name: "Connector QA",
          email: "connector@example.invalid",
          locale,
        },
        organization: {
          id: "00000000-0000-4000-8000-000000000002",
          name: "Connector QA",
        },
        role: isAdmin ? "organization_admin" : "viewer",
        platform_admin: isAdmin,
        onboarding_required: false,
      };
    else if (path === "/api/health")
      body = {
        status: "ok",
        database: "synthetic",
        apertus: { configured: false },
        firecrawl: { configured: false },
      };
    else if (path === "/api/jobs") body = [];
    else if (path === "/api/monitoring-settings")
      body = {
        can_configure_connectors: isAdmin,
        items: domains.map((id) => ({
          id,
          collector: "configured",
          access: "public_contract",
          acquisition: "unobserved",
        })),
      };
    else if (path.startsWith("/api/admin/monitoring-connectors/")) {
      if (mode === "denied") {
        code = 403;
        body = { code: "platform_admin_required" };
      } else if (request.method === "PATCH") {
        if (mode === "conflict") {
          code = 409;
          body = { code: "connector_revision_conflict" };
        } else {
          assert.equal(JSON.parse(request.postData).revision, revision);
          revision++;
          body = state();
        }
      } else if (path.endsWith("/check"))
        body = {
          checked_at: "2026-09-14T12:00:00Z",
          coverage_verified: false,
          channels: [{ id: "public", state: "http_accessible" }],
        };
      else body = state();
    } else if (path === "/api/monitoring-centre/today-counts")
      body = {
        items: domains.map((domain) => ({ domain, count: 0, state: "ready" })),
        total: 0,
      };
    else if (path.includes("/monitors") || path.includes("monitoring-drafts"))
      body = { items: [], next_cursor: null };
    else if (path.endsWith("/stations")) body = { stations: [] };
    else if (path.includes("-watch")) {
      code = 503;
      body = {
        code: "source_unavailable",
        detail: "Synthetic source access is unavailable",
      };
    } else { code = 503; body = { code: "unavailable" }; }
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
  for (const language of Object.keys(copy))
    for (const width of [390, 1440])
      for (const category of domains) {
        locale = language;
        domain = category;
        revision = 0;
        mode = "ready";
        isAdmin = true;
        await cdp.send("Emulation.setDeviceMetricsOverride", {
          width,
          height: 1000,
          deviceScaleFactor: 1,
          mobile: false,
        });
        const writes = traffic.filter((r) => r.method !== "GET" && !r.path.startsWith("/api/assistant/")).length;
        await navigate();
        assert.equal(
          await evaluate(
            cdp,
            "document.querySelectorAll('[data-monitoring-settings] nav a').length",
          ),
          9,
        );
        assert.equal(
          await evaluate(cdp, "document.querySelectorAll('main').length"),
          1,
          "Nested shell",
        );
        assert.equal(
          traffic.filter((r) => r.method !== "GET" && !r.path.startsWith("/api/assistant/")).length,
          writes,
          "Opening settings wrote data",
        );
        await check(`settings-${domain}-${locale}-${width}`);
        await button(copy[locale].check);
        await wait(
          () => text(panel).then((t) => t.includes(copy[locale].ready)),
          "Access result missing",
        );
        if (locale === "en-CH" && domain === "ip")
          await writeFile(
            join(root, `test-results/monitoring-settings-${width}.png`),
            Buffer.from(
              (await cdp.send("Page.captureScreenshot", { format: "png" }))
                .data,
              "base64",
            ),
          );
      }
  locale = "en-CH";
  domain = "ip";
  revision = 0;
  await navigate();
  await evaluate(
    cdp,
    `[...document.querySelectorAll('${panel} select')].filter(s=>s.querySelector('option[value=replace]')).forEach(s=>{s.value='replace';s.dispatchEvent(new Event('change',{bubbles:true}));})`,
  );
  await wait(
    () =>
      evaluate(
        cdp,
        "document.querySelectorAll('[data-credential]').length===2",
      ),
    "Credential inputs missing",
  );
  await evaluate(
    cdp,
    "document.querySelectorAll('[data-credential]').forEach(i=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(i,'synthetic-secret');i.dispatchEvent(new Event('input',{bubbles:true}));})",
  );
  assert.ok(
    await evaluate(
      cdp,
      `[...document.querySelectorAll('${panel} button')].find(b=>b.textContent===${JSON.stringify(copy[locale].check)}).disabled`,
    ),
  );
  await button(copy[locale].save);
  await wait(
    () => text(panel).then((t) => t.includes(copy[locale].saved)),
    "Save missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelectorAll('[data-credential]').length",
    ),
    0,
  );
  const saved = traffic.filter((r) => r.method === "PATCH").at(-1);
  assert.deepEqual(JSON.parse(saved.body).secrets, {
    ipi_username: "synthetic-secret",
    ipi_password: "synthetic-secret",
  });
  await check("saved-credentials-cleared");
  mode = "conflict";
  await evaluate(
    cdp,
    `const s=document.querySelector('${panel} select');s.value='clear';s.dispatchEvent(new Event('change',{bubbles:true}));`,
  );
  await button(copy[locale].save);
  await wait(
    () => text(panel).then((t) => t.includes(copy[locale].failed)),
    "Conflict missing",
  );
  assert.equal(
    await evaluate(cdp, `document.querySelectorAll('${panel} input').length`),
    0,
  );
  await check("conflict-clears-form");
  mode = "ready";
  isAdmin = false;
  await navigate();
  assert.equal(
    await evaluate(
      cdp,
      `document.querySelectorAll('${panel} input,${panel} select').length`,
    ),
    0,
  );
  await check("viewer-native-settings-visible");
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelectorAll('[data-monitoring-settings] nav a').length",
    ),
    9,
  );
  assert.deepEqual(exceptions, []);
  audit.finish(checks);
  console.log(
    `Monitoring settings: ${checks} browser/axe checks, nine categories, five locales, two widths, secrets/save/conflict and viewer boundaries.`,
  );
} catch (error) {
  console.error({
    locale,
    domain,
    mode,
    exceptions,
    recent: traffic.slice(-8),
    text: cdp ? await text("body").catch(() => "") : "",
  });
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const stopped = new Promise((r) => child.once("exit", r));
    child.kill();
    await Promise.race([stopped, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-connector-check-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
