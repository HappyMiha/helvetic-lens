// Built frontend with intercepted synthetic sources/accounts; no production mutations.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { stripTypeScriptTypes } from "node:module";
import { pathToFileURL } from "node:url";
const copyPath = resolve(import.meta.dirname, "../apps/web/lib/air-copy.ts");
const copySource = (await readFile(copyPath, "utf8")).replace(
  '"./river-copy"',
  JSON.stringify(
    pathToFileURL(resolve(import.meta.dirname, "../apps/web/lib/river-copy.ts"))
      .href,
  ),
);
const { airCopy } = await import(
  "data:text/javascript;base64," +
    Buffer.from(stripTypeScriptTypes(copySource)).toString("base64")
);
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-air-qa-"));
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
  monitor = null,
  previewReady = true;
const exceptions = [],
  mutations = [];
const audit = new AccessibilityAudit("air-watch");
const station = {
  id: "BAS",
  name: "Basel-Binningen",
  area: "Basel / Binningen",
};
const sample = {
  metric: "O3",
  timestamp: new Date().toISOString(),
  value: "60",
  unit: "µg/m³",
  quality: "provisional",
  period: "hourly_mean",
  source_url: "https://data.bs.ch/explore/dataset/100051/",
  license_url: "https://creativecommons.org/licenses/by/4.0/",
  revision: 1,
};
const coverage = {
  "O3:hourly_mean": { status: "current", sample },
  "PM25:hourly_mean": { status: "unknown", sample: null },
};
let changes = [];
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
  evaluate(cdp, "document.querySelector('[data-air-watch]')?.innerText || ''");
async function button(name) {
  await wait(
    () =>
      evaluate(
        cdp,
        `!!Array.from(document.querySelectorAll('[data-air-watch] button')).find(b=>b.textContent.trim()===${JSON.stringify(name)}&&!b.disabled)`,
      ),
    `Missing enabled button ${name}`,
  );
  await evaluate(
    cdp,
    `Array.from(document.querySelectorAll('[data-air-watch] button')).find(b=>b.textContent.trim()===${JSON.stringify(name)}&&!b.disabled).click()`,
  );
}
async function field(label, value, select = false) {
  await evaluate(
    cdp,
    `(()=>{const l=Array.from(document.querySelectorAll('form label')).find(l=>l.firstChild.textContent.trim()===${JSON.stringify(label)}&&l.querySelector(${JSON.stringify(select ? "select" : "input")}));const e=l.querySelector(${JSON.stringify(select ? "select" : "input")});Object.getOwnPropertyDescriptor(${select ? "HTMLSelectElement" : "HTMLInputElement"}.prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event(${JSON.stringify(select ? "change" : "input")},{bubbles:true}));})()`,
  );
}
async function navigate() {
  await cdp.send("Page.navigate", {
    url: `${base}/air-watch?qa=${Date.now()}`,
  });
  await wait(
    async () => (await text()).includes(airCopy[locale].title),
    "Air page did not load",
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
  await cdp.send("Network.setCookie", {
    name: "helvetic_lens_csrf",
    value: "synthetic-air",
    url: base,
  });
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    exceptions.push(exceptionDetails.text),
  );
  cdp.on("Page.javascriptDialogOpening", () =>
    cdp.send("Page.handleJavaScriptDialog", { accept: true }),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url),
      payload = request.postData ? JSON.parse(request.postData) : null;
    let code = 200,
      body = {};
    if (url.pathname === "/api/auth/session")
      body = {
        authenticated: true,
        user: {
          id: "qa",
          name: "Air QA",
          email: "air@example.invalid",
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
    else if (url.pathname.startsWith("/api/air-watch")) {
      if (request.method !== "GET")
        mutations.push({ path: url.pathname, method: request.method, payload });
      if (url.pathname.endsWith("/stations"))
        body = { stations: [station], health: "ready" };
      else if (url.pathname.endsWith("/today"))
        body = {
          items: changes.slice(0, 1).map((e) => ({
            ...e,
            monitor_id: monitor.id,
            monitor_name: monitor.configuration.name,
            monitor_status: monitor.status,
            health: monitor.health,
            muted: false,
          })),
          next: null,
        };
      else if (url.pathname.endsWith("/mute")) {
        monitor.configuration.muted_metrics = payload.muted
          ? [payload.metric]
          : [];
        monitor.version++;
        monitor.revision++;
        body = monitor;
      } else if (url.pathname.endsWith("/preview"))
        body = { station, coverage, start_available: previewReady };
      else if (
        url.pathname.endsWith("/monitors") &&
        request.method === "POST"
      ) {
        monitor = {
          id: "air-qa",
          configuration: payload.configuration,
          status: "draft",
          version: 1,
          revision: 1,
          health: "waiting",
          state: {},
          last_poll_at: null,
        };
        body = monitor;
        code = 201;
      } else if (url.pathname.endsWith("/monitors"))
        body = { items: monitor ? [monitor] : [] };
      else if (url.pathname.endsWith("/command")) {
        assert.equal(payload.expected_version, monitor.version);
        monitor.version++;
        monitor.status = {
          start: "active",
          pause: "paused",
          resume: "active",
          archive: "archived",
        }[payload.action];
        monitor.state = { coverage };
        monitor.health = "partial_unknown";
        body = monitor;
      } else if (url.pathname.endsWith("/changes"))
        body = { items: changes, next_before: null };
      else if (url.pathname.endsWith("/review")) {
        changes[0].decision = payload.decision;
        changes[0].review_version++;
        body = changes[0];
      } else if (url.pathname.endsWith("/measurements"))
        body = { items: [sample], next: null };
      else if (url.pathname.endsWith("/revisions"))
        body = {
          items: [
            {
              revision: monitor.revision,
              configuration: monitor.configuration,
            },
          ],
          next_before: null,
        };
      else if (request.method === "PATCH") {
        assert.equal(monitor.status, "paused");
        monitor.configuration = payload.configuration;
        monitor.version++;
        monitor.revision++;
        body = monitor;
      } else if (request.method === "DELETE") {
        monitor = null;
        code = 204;
      } else body = monitor;
    } else {
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
        body:
          code === 204
            ? ""
            : Buffer.from(JSON.stringify(body)).toString("base64"),
      })
      .catch(() => {});
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }],
  });
  await navigate();
  const c = airCopy[locale];
  await button(c.create);
  await field(c.name, "Basel air");
  await field(c.search, "Basel");
  await field(c.station, "BAS", true);
  await button(c.add);
  await field(c.threshold, "50");
  await button(c.preview);
  await wait(
    async () => (await text()).includes("60"),
    "Realistic source preview missing",
  );
  assert.ok((await text()).includes(c.unknown));
  await audit.check(cdp, "configuration-preview", "form");
  await button(c.save);
  await wait(() => monitor?.status === "draft", "Draft not saved");
  await button(c.preview);
  await button(c.start);
  await wait(() => monitor?.status === "active", "Monitor did not start");
  changes = [
    {
      id: "change-1",
      development_id: "a".repeat(64),
      sequence: 1,
      revision: 1,
      kind: "threshold_crossed",
      priority: 2,
      review_version: 0,
      decision: null,
      evidence: {
        sample,
        baseline: { ...sample, value: "40" },
        rule: monitor.configuration.rules[0],
        corrected: false,
        recovered: false,
      },
    },
  ];
  await button(c.refresh);
  await wait(
    async () => (await text()).includes(c.threshold_crossed),
    "Pollution change missing",
  );
  await button(c.reviewed);
  await wait(() => changes[0].decision === "reviewed", "Review not saved");
  await button(c.measurements);
  await button(c.settings);
  await audit.check(cdp, "active-history-review", "[data-air-watch]");
  await button(`${c.mute}: ${c.O3}`);
  await wait(
    () => monitor.configuration.muted_metrics.includes("O3"),
    "Mute was not saved",
  );
  await button(`${c.unmute}: ${c.O3}`);
  await wait(
    () => !monitor.configuration.muted_metrics.length,
    "Unmute was not saved",
  );
  await cdp.send("Page.navigate", { url: base });
  await wait(
    () => evaluate(cdp, "!!document.querySelector('[data-air-today]')"),
    "Air change missing in Today",
  );
  assert.ok(
    await evaluate(
      cdp,
      "document.querySelector('[data-air-today]').innerText.includes('Basel air')",
    ),
  );
  await audit.check(cdp, "today-change", "[data-air-today]");
  await navigate();
  await wait(
    () =>
      evaluate(
        cdp,
        "!!document.querySelector('[data-air-watch] aside button')",
      ),
    "Monitor list missing",
  );
  await evaluate(
    cdp,
    "document.querySelector('[data-air-watch] aside button').click()",
  );
  await button(c.pause);
  await button(c.edit);
  await field(c.name, "Basel updated");
  await button(c.preview);
  await button(c.saveEdit);
  await wait(() => monitor?.revision === 4, "Edit did not create revision");
  previewReady = false;
  await button(c.preview);
  assert.equal(
    await evaluate(
      cdp,
      `Array.from(document.querySelectorAll('[data-air-watch] button')).find(b=>b.textContent.trim()===${JSON.stringify(c.resume)}).disabled`,
    ),
    true,
  );
  previewReady = true;
  await button(c.preview);
  await button(c.resume);
  await button(c.archive);
  for (const language of Object.keys(airCopy)) {
    locale = language;
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: language === "en-CH" ? 1280 : 390,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await navigate();
    await wait(
      async () => (await text()).includes("Basel updated"),
      "Saved monitor missing",
    );
    await evaluate(
      cdp,
      "Array.from(document.querySelectorAll('[data-air-watch] aside button')).find(b=>b.textContent.includes('Basel updated')).click()",
    );
    await wait(
      async () => (await text()).includes(airCopy[locale].changes),
      "Localized detail missing",
    );
    assert.equal(
      await evaluate(
        cdp,
        "document.documentElement.scrollWidth <= innerWidth + 1",
      ),
      true,
      `Overflow ${locale}`,
    );
    await audit.check(cdp, `reader-${locale}`, "[data-air-watch]");
  }
  manager = false;
  await navigate();
  await wait(
    async () => (await text()).includes(airCopy[locale].readonly),
    "Viewer explanation missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      `Array.from(document.querySelectorAll('[data-air-watch] button')).some(b=>b.textContent===${JSON.stringify(airCopy[locale].create)})`,
    ),
    false,
  );
  assert.ok(
    mutations.every(
      (r) => !JSON.stringify(r.payload).includes("email_consent"),
    ),
  );
  assert.deepEqual(exceptions, []);
  audit.finish(8);
  console.log(
    "Air browser: preview/save/start/threshold/review/history/mute/unmute/Today/pause/edit/resume/archive, five locales, mobile and viewer gates passed.",
  );
} catch (error) {
  console.error(
    JSON.stringify({
      text: cdp ? await text().catch(() => "") : "",
      mutations,
      exceptions,
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
  assert.ok(basename(profile).startsWith("helvetic-air-qa-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
