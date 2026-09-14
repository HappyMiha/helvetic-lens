// Actual JSON downloads in all nine built native readers and selected business histories.
// Synthetic browser transport; native API/source permissions have separate integration tests.
import { personalFixture } from "./evidence-personal-browser-fixtures.mjs";
import { EvidenceExportFixture } from "./evidence-export-browser-fixture.mjs";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { evidenceExportCopy } from "../apps/web/lib/monitoring-evidence-export-copy.ts";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";

const downloads = new EvidenceExportFixture();
const root = resolve(import.meta.dirname, "..");
const fixtures = JSON.parse(
  await readFile(
    join(root, ".tmp/business-item-browser-fixtures.json"),
    "utf8",
  ),
);
for (const domain of [
  "pollen",
  "air",
  "river",
  "warnings",
  "commute",
  "traffic",
])
  fixtures[domain] = personalFixture(domain);
const chrome = [
  process.env.CHROME_BIN,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
]
  .filter(Boolean)
  .find(existsSync);
assert.ok(chrome);
const socket = createServer();
await new Promise((r) => socket.listen(0, "127.0.0.1", r));
const port = socket.address().port;
await new Promise((r) => socket.close(r));
const base = `http://127.0.0.1:${port}`;
function localSources(value) {
  if (typeof value === "string" && /^https?:/.test(value))
    return base + "/synthetic-source";
  if (Array.isArray(value)) return value.map(localSources);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value).map(([k, v]) => [k, localSources(v)]),
    );
  return value;
}
for (const key of ["tenders", "ip", "auctions"])
  fixtures[key] = localSources(fixtures[key]);
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-evidence-file-"));
const browser = spawn(
  chrome,
  [
    "--headless=new",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-extensions",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: "ignore", windowsHide: true },
);
const routes = {
  tenders: "tender-watch",
  ip: "trademark-watch",
  auctions: "auction-watch",
  pollen: "pollen-watch",
  air: "air-watch",
  river: "river-watch",
  warnings: "hazard-watch",
  commute: "commute-watch",
  traffic: "road-watch",
};
const historyId = "00000000-0000-4000-8000-000000000099";
const panel = "[data-monitoring-evidence-export]";
const audit = new AccessibilityAudit("monitoring-evidence-file");
let cdp,
  domain = "tenders",
  locale = "en-CH",
  state,
  nav = 0,
  role = "organization_admin",
  historical = false;
const requests = [],
  errors = [];
async function wait(check, message) {
  for (let i = 0; i < 250; i++) {
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
async function response(id, body, code = 200) {
  await cdp
    .send("Fetch.fulfillRequest", {
      requestId: id,
      responseCode: code,
      responseHeaders: [
        { name: "Content-Type", value: "application/json" },
        { name: "Cache-Control", value: "no-store" },
      ],
      body: Buffer.from(JSON.stringify(body)).toString("base64"),
    })
    .catch(() => {});
}
async function navigate() {
  await evaluate(cdp, "window.__evidencePrevious=true");
  const suffix =
    domain === "tenders"
      ? `&dossier=${state.detail.id}`
      : domain === "ip"
        ? `&candidate=${state.detail.id}${historical ? "&event=" + historyId : ""}`
        : historical
          ? "&event=" + historyId
          : "";
  await cdp.send("Page.navigate", {
    url: state.query
      ? `${base}/${routes[domain]}?${state.query}&qa=${++nav}${domain === "pollen" ? `#draft=${state.monitor.id}` : ""}`
      : `${base}/${routes[domain]}?monitor=${state.monitor.id}${suffix}&qa=${++nav}`,
  });
  await wait(
    () =>
      evaluate(
        cdp,
        `!window.__evidencePrevious&&document.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector(${JSON.stringify(panel)})`,
      ),
    "Reader did not open",
  );
}
try {
  await wait(async () => (await fetch(base)).ok, "Next did not start");
  let debug;
  await wait(async () => {
    debug = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split(
      "\n",
    )[0];
    return !!debug;
  }, "Chrome did not start");
  const target = await fetch(`http://127.0.0.1:${debug}/json/new?about:blank`, {
    method: "PUT",
  }).then((r) => r.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await downloads.setup(cdp, root);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");

  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    errors.push(
      exceptionDetails.exception?.description || exceptionDetails.text,
    ),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    if (
      new URL(request.url).origin !== base ||
      new URL(request.url).pathname === "/synthetic-source"
    ) {
      await cdp.send("Fetch.fulfillRequest", {
        requestId,
        responseCode: 200,
        responseHeaders: [{ name: "Content-Type", value: "text/html" }],
        body: Buffer.from(
          "<!doctype html><html lang='en'><title>Synthetic source</title><body>Local browser fixture</body></html>",
        ).toString("base64"),
      });
      return;
    }
    if (!new URL(request.url).pathname.startsWith("/api/")) {
      await cdp.send("Fetch.continueRequest", { requestId });
      return;
    }
    if (await downloads.handle({ requestId, request })) return;
    try {
      const url = new URL(request.url),
        path = url.pathname,
        body = request.postData ? JSON.parse(request.postData) : null;
      requests.push({
        path,
        method: request.method,
        domain,
        mode: downloads.mode,
      });
      let data = {},
        code = 200;
      if (path === "/api/auth/session")
        data = {
          authenticated: true,
          user: {
            id: "owner",
            name: "Owner",
            email: "fixture@example.invalid",
            locale,
          },
          organization: {
            id: downloads.mode === "wrong-identity" ? "foreign" : "org-a",
            name: "Synthetic workspace",
          },
          role,
          platform_admin: false,
          onboarding_required: false,
        };
      else if (path === "/api/health")
        data = {
          status: "ok",
          database: "synthetic",
          apertus: { configured: false },
          firecrawl: { configured: false },
        };
      else if (path === "/api/assistant/context")
        data = { context: { entity: null }, persona: { quip_allowed: false } };
      else if (path === "/api/jobs") data = [];
      else if (state.response && path.startsWith(state.api)) {
        data = state.response(path);
      } else if (path.startsWith(`/api/${routes[domain]}`)) {
        if (historical && path.endsWith("/versions"))
          data = {
            items: [
              {
                id: historyId,
                sequence: 1,
                kind: "material_update",
                profile_revision: 1,
                summary: { deadline: null },
              },
            ],
            next_cursor: null,
          };
        else if (historical && path.endsWith("/events/" + historyId))
          data = {
            id: historyId,
            item_id: state.detail.id,
            sequence: 1,
            profile_revision: 1,
            detected_at: "2026-09-14T08:00:00Z",
            change_codes: [],
            newer_available: true,
            current_configuration: false,
            previous: null,
            snapshot: { state: "available", facts: state.detail.facts },
            assessment: state.detail.assessment,
            current: state.detail,
          };
        else if (path.endsWith("/capabilities"))
          data = {
            drafts_available: true,
            public_source_available: true,
            lookback_days: 90,
            cycle_hours: 6,
          };
        else if (path.endsWith("/source-status"))
          data = {
            state: "permission_required",
            traversal: null,
            source: null,
          };
        else if (path.endsWith(`/monitors/${state.monitor.id}`))
          data = state.monitor;
        else if (path.endsWith("/monitors"))
          data = { items: [state.monitor], next_cursor: null };
        else if (path.endsWith(`/${state.detail.id}`)) data = state.detail;
        else if (
          ["/dossiers", "/candidates", "/items"].some((end) =>
            path.endsWith(end),
          )
        )
          data = {
            ...state.page,
            items: state.page.items.map((item) => ({
              ...item,
              ...state.detail,
            })),
          };
        else
          data = {
            items: [],
            next_cursor: null,
            health: "waiting",
            coverage_verified: false,
          };
      }
      await response(requestId, data, code);
    } catch (error) {
      errors.push(String(error));
      await response(requestId, { code: "fixture_failed" }, 500);
    }
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: "*", requestStage: "Request" }],
  });
  await cdp.send("Network.setCookie", {
    name: "helvetic_lens_csrf",
    value: "synthetic",
    url: base,
  });
  for (const kind of Object.keys(routes))
    for (const language of Object.keys(evidenceExportCopy))
      for (const width of [390, 1440]) {
        domain = kind;
        locale = language;
        state = fixtures[kind].response
          ? fixtures[kind]
          : structuredClone(fixtures[kind]);
        role = "organization_admin";
        await cdp.send("Emulation.setDeviceMetricsOverride", {
          width,
          height: 1000,
          deviceScaleFactor: 1,
          mobile: width === 390,
        });
        await navigate();
        await downloads.check({
          domain,
          locale,
          monitor: state.monitor.id,
          item: state.detail.id,
          sequence: state.sequence,
          audit,
          restore: navigate,
          name: domain + "-" + locale + "-" + width,
          negative: locale === "en-CH" && width === 1440,
        });
        if (locale === "en-CH") {
          await evaluate(
            cdp,
            'document.querySelector("[data-monitoring-evidence-export]").scrollIntoView({block:"center"})',
          );
          await writeFile(
            join(
              root,
              "test-results/evidence-file-" + domain + "-" + width + ".png",
            ),
            Buffer.from(
              (await cdp.send("Page.captureScreenshot", { format: "png" }))
                .data,
              "base64",
            ),
          );
        }
      }
  locale = "en-CH";
  for (const kind of Object.keys(routes)) {
    domain = kind;
    state = fixtures[kind].response
      ? fixtures[kind]
      : structuredClone(fixtures[kind]);
    role = "viewer";
    await navigate();
    await downloads.check({
      domain,
      locale,
      monitor: state.monitor.id,
      item: state.detail.id,
      sequence: state.sequence,
      audit,
      name: domain + "-viewer",
    });
  }
  historical = true;
  for (const kind of ["tenders", "ip", "auctions"])
    for (const language of Object.keys(evidenceExportCopy))
      for (const width of [390, 1440]) {
        domain = kind;
        locale = language;
        state = structuredClone(fixtures[kind]);
        role = "organization_admin";
        downloads.mode = "ready";
        await cdp.send("Emulation.setDeviceMetricsOverride", {
          width,
          height: 1000,
          deviceScaleFactor: 1,
          mobile: width === 390,
        });
        await navigate();
        const selector =
          domain === "tenders"
            ? '[data-tender-version="' +
              historyId +
              '"] [data-monitoring-evidence-export]'
            : domain === "ip"
              ? "[data-trademark-change] [data-monitoring-evidence-export]"
              : "[data-auction-change] > [data-monitoring-evidence-export]";
        await downloads.check({
          domain,
          locale,
          monitor: state.monitor.id,
          item: state.detail.id,
          revision: historyId,
          selector,
          audit,
          name: domain + "-history-" + locale + "-" + width,
        });
      }
  assert.deepEqual(errors, []);
  assert.deepEqual(downloads.failures, []);
  await writeFile(
    join(root, "test-results/evidence-file-requests.json"),
    JSON.stringify(downloads.requests, null, 2),
  );
  audit.finish(129);
  assert.equal(downloads.files, 129);
  console.log(
    "129 actual native downloads across nine categories and three selected business histories passed; five locales, desktop/mobile, viewer, corrupt bytes/manifests, revoked access, expiry, cancellation and late responses. Synthetic browser API; source rights covered separately.",
  );
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const ended = new Promise((r) => child.once("exit", r));
    child.kill();
    await Promise.race([ended, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-evidence-file-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 8,
    retryDelay: 250,
  });
}
