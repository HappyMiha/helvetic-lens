// Built frontend, synthetic private accounts and API. No live source or production mutation.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { centreCopy } from "../apps/web/lib/monitoring-centre-copy.ts";
import { riverCopy } from "../apps/web/lib/river-copy.ts";
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-centre-qa-"));
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
  manager = true,
  denied = false,
  disabled = false;
const exceptions = [],
  requests = [],
  mutations = [];
const audit = new AccessibilityAudit("monitoring-centre");
const templates = [
  "warnings",
  "commute",
  "traffic",
  "pollen",
  "river",
  "air",
  "tenders",
  "ip",
  "auctions",
].map((id, index) => ({
  id,
  group: index < 6 ? "personal" : "business",
  availability: ["pollen", "river", "air"].includes(id)
    ? "available"
    : "blocked",
  href: ["pollen", "river", "air"].includes(id) ? `/${id}-watch` : null,
}));
const rows = ["air", "river", "pollen"].map((domain, index) => ({
  id: `${domain}-qa`,
  domain,
  name: domain === "pollen" ? null : `Private ${domain}`,
  station_id: domain === "pollen" ? "PBS" : domain === "air" ? "BAS" : "2289",
  status: index === 1 ? "paused" : "active",
  health: index === 0 ? "partial_unknown" : "waiting",
  href:
    domain === "pollen"
      ? "/pollen-watch#draft=pollen-qa"
      : `/${domain}-watch?monitor=${domain}-qa`,
  metrics: [domain === "pollen" ? "birch" : domain === "air" ? "O3" : "W"],
  last_observation_at: null,
  last_check_at: new Date().toISOString(),
  next_check_at:
    index === 1 ? null : new Date(Date.now() + 600000).toISOString(),
}));
const river = {
  id: "river-qa",
  configuration: {
    name: "Private river",
    station_id: "2289",
    metrics: ["W"],
    rules: [],
    official_danger: false,
  },
  status: "paused",
  health: "waiting",
  version: 1,
  revision: 1,
  state: {},
  last_poll_at: null,
};
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
  throw new Error(message);
}
const text = () =>
  evaluate(
    cdp,
    "document.querySelector('[data-monitoring-centre]')?.innerText || ''",
  );
async function click(selector) {
  await evaluate(
    cdp,
    `document.querySelector(${JSON.stringify(selector)}).click()`,
  );
}
async function button(name) {
  await evaluate(
    cdp,
    `Array.from(document.querySelectorAll('[data-monitoring-centre] button')).find(b=>b.textContent.trim()===${JSON.stringify(name)}&&!b.disabled).click()`,
  );
}
async function filter(index, value) {
  await evaluate(
    cdp,
    `(()=>{const e=document.querySelectorAll('[data-monitoring-centre] select')[${index}];Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('change',{bubbles:true}));})()`,
  );
}
async function navigate(path = "/monitoring") {
  await cdp.send("Page.navigate", {
    url: `${base}${path}${path.includes("?") ? "&" : "?"}qa=${Date.now()}`,
  });
  await wait(
    async () => (await text()).includes(centreCopy[locale].saved),
    "Centre did not load",
  );
  await wait(
    () => evaluate(cdp, "!!document.querySelector('[data-template]')"),
    "Templates did not load",
  );
}
try {
  await wait(async () => (await fetch(base)).ok, "Next server did not start");
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
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    exceptions.push(exceptionDetails.text),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url);
    let code = 200,
      body = {};
    requests.push(url.pathname + url.search);
    if (
      request.method !== "GET" &&
      /^\/api\/(monitoring-centre|monitoring-subjects|river-watch|air-watch)/.test(
        url.pathname,
      )
    )
      mutations.push(request.url);
    if (url.pathname === "/api/auth/session")
      body = {
        authenticated: true,
        user: {
          id: "qa",
          name: "Centre QA",
          email: "qa@example.invalid",
          locale,
        },
        organization: { id: "private-qa", name: "Private QA" },
        role: manager ? "organization_admin" : "viewer",
        platform_admin: false,
        onboarding_required: false,
      };
    else if (url.pathname === "/api/health")
      body = {
        status: "ok",
        database: "synthetic",
        apertus: { configured: false },
        firecrawl: { configured: false },
      };
    else if (url.pathname === "/api/jobs") body = [];
    else if (url.pathname === "/api/monitoring-centre") {
      if (denied) {
        code = 403;
        body = { code: "membership_required", detail: "Access removed" };
      } else {
        const filtered = rows.filter(
          (r) =>
            (!url.searchParams.get("domain") ||
              r.domain === url.searchParams.get("domain")) &&
            (!url.searchParams.get("status") ||
              r.status === url.searchParams.get("status")),
        );
        const offset = url.searchParams.has("cursor") ? 2 : 0;
        body = {
          templates: templates.map((t) =>
            disabled && t.href
              ? { ...t, availability: "disabled", href: null }
              : t,
          ),
          items: filtered.slice(offset, offset + 2).map((r) =>
            disabled
              ? {
                  ...r,
                  health: "disabled",
                  href: null,
                  last_observation_at: null,
                  last_check_at: null,
                  next_check_at: null,
                }
              : r,
          ),
          next_cursor: filtered.length > offset + 2 ? "next-page" : null,
        };
      }
    } else if (url.pathname === "/api/river-watch/stations")
      body = {
        stations: [
          {
            id: "2289",
            name: "Rhein – Basel",
            waterbody: "Rhein",
            metrics: ["W"],
          },
        ],
      };
    else if (url.pathname === "/api/river-watch/monitors")
      body = { items: [] }; // Exact link works beyond the first domain page.
    else if (url.pathname === "/api/river-watch/monitors/river-qa")
      body = river;
    else if (url.pathname.startsWith("/api/river-watch/monitors/river-qa/"))
      body = { items: [], next: null, next_before: null };
    else {
      code = 503;
      body = { code: "unavailable" };
    }
    await cdp
      .send("Fetch.fulfillRequest", {
        requestId,
        responseCode: code,
        responseHeaders: [
          { name: "Content-Type", value: "application/json" },
          { name: "Cache-Control", value: "no-store" },
        ],
        body: Buffer.from(JSON.stringify(body)).toString("base64"),
      })
      .catch(() => {});
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }],
  });
  await navigate();
  assert.equal(
    await evaluate(cdp, "document.querySelectorAll('[data-template]').length"),
    9,
  );
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelectorAll('[data-template] a').length",
    ),
    3,
  );
  assert.equal(
    await evaluate(cdp, "document.querySelectorAll('[data-monitor]').length"),
    2,
  );
  await button(riverCopy[locale].more);
  await wait(
    () =>
      evaluate(cdp, "document.querySelectorAll('[data-monitor]').length===3"),
    "Pagination lost a domain",
  );
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelector('[data-monitor=\"pollen-qa\"] a').getAttribute('href')",
    ),
    "/pollen-watch#draft=pollen-qa",
  );
  await audit.check(cdp, "three-domain-inventory", "[data-monitor]");
  const screenshot = await cdp.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
  });
  await writeFile(
    join(root, ".tmp/centre-desktop.png"),
    Buffer.from(screenshot.data, "base64"),
  );
  await click('a[href="#choose-monitor"]');
  await wait(
    () => evaluate(cdp, "document.activeElement?.id === 'choose-monitor'"),
    "Template jump did not move keyboard focus",
  );
  await cdp.send("Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "Tab",
    code: "Tab",
    windowsVirtualKeyCode: 9,
  });
  await cdp.send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Tab",
    code: "Tab",
    windowsVirtualKeyCode: 9,
  });
  assert.equal(
    await evaluate(cdp, "document.activeElement?.getAttribute('href')"),
    "/pollen-watch",
  );
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelector('[aria-labelledby=legacy-monitoring] a[href=\"/registry\"]') !== null && document.querySelector('[aria-labelledby=legacy-monitoring] a[href=\"/topics\"]') !== null",
    ),
    true,
  );
  await filter(1, "paused");
  await wait(
    () =>
      evaluate(
        cdp,
        "document.querySelectorAll('[data-monitor]').length===1 && !!document.querySelector('[data-monitor=\"river-qa\"]')",
      ),
    "Lifecycle filter failed",
  );
  await click('[data-monitor="river-qa"] a');
  await wait(
    () =>
      evaluate(
        cdp,
        "document.querySelector('[data-river-watch]')?.innerText.includes('Private river')",
      ),
    "River deep link did not open detail",
  );
  assert.ok(requests.includes("/api/river-watch/monitors/river-qa"));
  await navigate();
  await filter(0, "pollen");
  await wait(
    () =>
      evaluate(
        cdp,
        "document.querySelectorAll('[data-monitor]').length===1 && !!document.querySelector('[data-monitor=\"pollen-qa\"]')",
      ),
    "Domain filter failed",
  );
  await filter(1, "archived");
  await wait(
    async () => (await text()).includes(centreCopy[locale].empty),
    "Empty filters unclear",
  );
  denied = true;
  await button(riverCopy[locale].refresh);
  await wait(
    () =>
      evaluate(
        cdp,
        "!!document.querySelector('[data-monitoring-centre] [role=alert]')",
      ),
    "Revocation error missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelectorAll('[data-monitor], [data-template]').length",
    ),
    0,
  );
  await audit.check(cdp, "revoked-read", "[role=alert]");
  denied = false;
  await button(riverCopy[locale].refresh);
  await wait(
    () => evaluate(cdp, "!!document.querySelector('[data-template]')"),
    "Retry did not restore permitted results",
  );
  disabled = true;
  await navigate();
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelectorAll('[data-template] a, [data-monitor] a').length",
    ),
    0,
  );
  await audit.check(cdp, "disabled-scenarios", "[data-template]");
  disabled = false;
  for (const language of Object.keys(centreCopy)) {
    locale = language;
    manager = false;
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 390,
      height: 844,
      deviceScaleFactor: 1,
      mobile: true,
    });
    await navigate();
    assert.ok((await text()).includes(riverCopy[locale].readonly));
    assert.equal(
      await evaluate(cdp, "document.documentElement.scrollWidth<=innerWidth"),
      true,
    );
    await audit.check(
      cdp,
      `mobile-viewer-${locale}`,
      "[data-monitoring-centre]",
    );
  }
  assert.deepEqual(mutations, []);
  assert.deepEqual(exceptions, []);
  audit.finish(8);
  console.log(
    "Centre browser passed: nine choices, three-domain pagination, filters, exact River link, error/revocation recovery, disabled gates, five locales and mobile viewers; no mutations.",
  );
} catch (error) {
  console.error(
    JSON.stringify({
      text: cdp ? await text().catch(() => "") : "",
      exceptions,
      requests: requests.slice(-15),
    }),
  );
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const stopped = new Promise((done) => child.once("exit", done));
    child.kill();
    await Promise.race([stopped, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-centre-qa-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
