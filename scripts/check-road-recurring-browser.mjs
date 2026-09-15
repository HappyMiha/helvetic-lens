// Built Road Watch, synthetic private recurring closure; no live source or accounts.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { roadCopy } from "../apps/web/lib/road-copy.ts";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-road-recurring-qa-"));
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
const id = "00000000-0000-4000-8000-000000000001",
  eventId = "00000000-0000-4000-8000-000000000002",
  ref = "00000000-0000-4000-8000-000000000003";
const corridor = {
  id: ref,
  name: "Synthetic corridor northbound",
  flow: "north",
  attribution: "Synthetic topology",
};
const monitor = {
  id,
  version: 2,
  revision: 1,
  status: "active",
  health: "ready",
  last_check_at: "2026-09-13T10:00:00Z",
  configuration: {
    template_id: "road-watch",
    template_version: 1,
    name: "Synthetic recurring road",
    corridor_reference_ids: [ref],
    materiality: {
      event_kinds: ["road_closure"],
      minimum_delay_seconds: 900,
      include_planned: true,
    },
  },
};
let locale = "en-CH",
  denied = false,
  phase = "planned",
  cdp;
const payload = () => ({
  state: phase,
  corridors: {
    [ref]: {
      state: phase,
      coverage: "verified",
      facts: [
        {
          kind: "road_closure",
          phase,
          probability: "certain",
          recurring: true,
          valid_from: "2026-09-13T22:00:00Z",
          valid_until: "2026-09-14T06:00:00Z",
        },
      ],
    },
  },
});
const version = (sequence) => ({
  sequence,
  payload: denied ? null : payload(),
  availability: denied ? "unavailable" : "available",
  attribution: "Synthetic traffic evidence",
  detected_at: "2026-09-13T10:00:00Z",
});
const event = () => ({
  id: eventId,
  monitor_id: id,
  version: 3,
  sequence: 2,
  reviewed_sequence: 1,
  muted: false,
  updated_at: "2026-09-13T10:00:00Z",
  ...version(2),
});
const audit = new AccessibilityAudit("road-recurring");
const exceptions = [];
async function wait(check, label) {
  for (let i = 0; i < 150; i++) {
    if (await check()) return;
    await sleep(100);
  }
  throw Error(label);
}
const text = () => evaluate(cdp, "document.body.innerText");
async function navigate() {
  await cdp.send("Page.navigate", {
    url: `${base}/road-watch?monitor=${id}&event=${eventId}&sequence=2`,
  });
  await wait(
    async () =>
      (await text()).includes(
        denied ? roadCopy[locale].unavailable : roadCopy[locale].recurring,
      ),
    "Recurring detail did not render",
  );
}
try {
  await wait(async () => {
    try {
      return (await fetch(base)).ok;
    } catch {
      return false;
    }
  }, "Next failed to start");
  let debugPort;
  await wait(async () => {
    try {
      debugPort = Number(
        (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split(
          "\n",
        )[0],
      );
      return !!debugPort;
    } catch {
      return false;
    }
  }, "Chrome failed to start");
  const tabs = await (
    await fetch(`http://127.0.0.1:${debugPort}/json/list`)
  ).json();
  cdp = new Cdp(tabs.find((tab) => tab.type === "page").webSocketDebuggerUrl);
  await cdp.ready;
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    exceptions.push(exceptionDetails.text),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url);
    let body = { code: "unavailable" },
      status = 503;
    if (url.pathname === "/api/auth/session") {
      body = {
        authenticated: true,
        user: {
          id: "road-qa",
          name: "Road QA",
          email: "qa@example.invalid",
          locale,
        },
        organization: { id: "road-org", name: "Synthetic QA" },
        role: "organization_admin",
        platform_admin: false,
        onboarding_required: false,
      };
      status = 200;
    } else if (url.pathname === "/api/health") {
      body = {
        status: "ok",
        database: "synthetic",
        apertus: { configured: false },
        firecrawl: { configured: false },
      };
      status = 200;
    } else if (url.pathname.startsWith("/api/road-watch")) {
      status = 200;
      const path = url.pathname.slice("/api/road-watch".length);
      if (denied) {
        status = 404;
        body = { code: "road_event_unavailable" };
      } else if (path === "/capabilities")
        body = { drafts_available: true, start_available: true };
      else if (path === "/catalog")
        body = { items: [corridor], next_cursor: null };
      else if (path === "/monitors")
        body = { items: [monitor], next_cursor: null };
      else if (path === `/monitors/${id}`) body = monitor;
      else if (path.endsWith("/corridors"))
        body = { items: [corridor], next_cursor: null };
      else if (path === `/events/${eventId}`)
        body = {
          event: event(),
          snapshot: version(2),
          previous: version(1),
          corridors: [corridor],
          current_configuration: true,
          newer_available: false,
        };
      else if (path.endsWith("/history"))
        body = { items: [version(1), version(2)], next_cursor: null };
      else if (path.endsWith("/events"))
        body = { items: [event()], next_cursor: null };
      else if (path.endsWith("/email"))
        body = {
          revision: 0,
          configuration: {
            timezone: "Europe/Zurich",
            delivery: { email: "off", digest_at: null, quiet_hours: null },
          },
          consent_active: false,
          email_verified: true,
          uncertain_deliveries: 0,
          monitor_version: 2,
          delivery_service_available: true,
        };
      else if (path.endsWith("/email-preview"))
        body = { status: "ready", items: [], more_available: false };
      else body = { items: [], next_cursor: null };
    }
    await cdp
      .send("Fetch.fulfillRequest", {
        requestId,
        responseCode: status,
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
  for (locale of ["en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"]) {
    for (const width of [390, 1440]) {
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: false,
      });
      await navigate();
      assert.equal(
        await evaluate(
          cdp,
          "document.documentElement.scrollWidth <= innerWidth + 1",
        ),
        true,
        `Overflow ${locale}`,
      );
      for (const sourceTime of [
        "2026-09-13T22:00:00Z",
        "2026-09-14T06:00:00Z",
      ]) {
        const expected = await evaluate(
          cdp,
          `new Intl.DateTimeFormat(${JSON.stringify(locale)}, {dateStyle:"medium", timeStyle:"short", timeZone:"Europe/Zurich"}).format(new Date(${JSON.stringify(sourceTime)}))`,
        );
        assert.ok(
          (await text()).includes(expected),
          `Missing Swiss interval time: ${expected}`,
        );
      }
      await audit.check(cdp, `${locale}-${width}`, "main");
      if (locale === "en-CH" && width === 390) {
        await evaluate(
          cdp,
          `document.querySelectorAll('p').values().find(p => p.textContent === ${JSON.stringify(roadCopy[locale].recurring)}).scrollIntoView({block:'center'}); new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))`,
        );
        await writeFile(
          join(root, "test-results/road-recurring-mobile.png"),
          Buffer.from(
            (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
            "base64",
          ),
        );
      }
    }
  }
  locale = "en-CH";
  phase = "active";
  await navigate();
  await audit.check(cdp, "active", "main");
  denied = true;
  await cdp.send("Page.navigate", {
    url: `${base}/road-watch?monitor=${id}&event=${eventId}&sequence=2`,
  });
  await wait(
    async () =>
      !(await text()).includes(roadCopy[locale].recurring) &&
      (await evaluate(cdp, "!!document.querySelector('[role=alert]')")),
    "Denied source retained recurrence evidence",
  );
  assert.ok(!(await text()).includes("Synthetic corridor northbound"));
  await audit.check(cdp, "denied", "main");
  assert.deepEqual(exceptions, []);
  audit.finish(12);
  console.log(
    "Road recurring: five locales/two widths, Swiss interval display, active/planned and denied-source redaction passed. Synthetic API.",
  );
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const stopped = new Promise((done) => child.once("exit", done));
    child.kill();
    await Promise.race([stopped, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-road-recurring-qa-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
