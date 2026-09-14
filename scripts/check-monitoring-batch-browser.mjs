// Compiled UI with synthetic native review contracts; real readers have API tests.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { monitoringBatchCopy } from "../apps/web/lib/monitoring-batch-copy.ts";
import { monitoringNotificationsCopy } from "../apps/web/lib/monitoring-notifications-copy.ts";
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-batch-review-"));
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
const auditName = process.env.BATCH_CHECK_KEYBOARD_ONLY
  ? "monitoring-batch-keyboard"
  : process.env.BATCH_CHECK_LOCALE
    ? "monitoring-batch-locale"
    : "monitoring-batch";
const audit = new AccessibilityAudit(auditName),
  exceptions = [],
  requests = [];
const domains = [
  "pollen",
  "air",
  "river",
  "tenders",
  "commute",
  "traffic",
  "warnings",
  "ip",
  "auctions",
];
const uuid = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const clock = "2026-09-14T12:00:00Z",
  modal = "[data-notification-centre]",
  queue = "[data-monitoring-notification-queue]",
  panel = "[data-monitoring-batch]";
const actions = (domain) =>
  ({
    tenders: ["bid", "no_bid", "monitor"],
    ip: ["reviewed", "relevant", "not_relevant", "monitor", "counsel"],
    auctions: ["inspect", "bid", "no_bid", "monitor"],
  })[domain] || ["reviewed"];
let cdp,
  locale = "en-CH",
  role = "organization_admin",
  domain = "pollen",
  mode = "ready",
  applied = false,
  held,
  navigation = 0,
  checks = 0;
const rows = () =>
  Array.from({ length: mode === "many" ? 21 : 2 }, (_, n) => ({
    id: uuid(n + 10),
    domain,
    monitor_name: `Selected ${domain} ${n + 1}`,
    allergen: null,
    detected_at: clock,
    href: `/${domain}-watch?monitor=${uuid(1)}&item=${uuid(n + 10)}`,
    record: {
      domain,
      monitor_id: uuid(1),
      item_id: uuid(n + 10),
      sequence: ["warnings", "commute", "traffic"].includes(domain) ? 1 : null,
    },
  }));
async function wait(fn, message) {
  for (let n = 0; n < 250; n++) {
    if (
      await Promise.resolve()
        .then(fn)
        .catch(() => false)
    )
      return;
    await sleep(100);
  }
  throw new Error(message);
}
const text = (selector) =>
  evaluate(
    cdp,
    `document.querySelector(${JSON.stringify(selector)})?.innerText || ''`,
  );
async function click(selector) {
  await wait(
    () =>
      evaluate(
        cdp,
        `!!document.querySelector(${JSON.stringify(selector)})&&!document.querySelector(${JSON.stringify(selector)}).disabled`,
      ),
    `Missing ${selector}`,
  );
  await evaluate(
    cdp,
    `document.querySelector(${JSON.stringify(selector)}).click()`,
  );
}
async function button(label) {
  await wait(
    () =>
      evaluate(
        cdp,
        `[...document.querySelectorAll(${JSON.stringify(modal + " button")})].some(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled)`,
      ),
    `Missing button ${label}`,
  );
  await evaluate(
    cdp,
    `[...document.querySelectorAll(${JSON.stringify(modal + " button")})].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled).click()`,
  );
}
async function check(name) {
  await evaluate(
    cdp,
    "Promise.all(document.getAnimations().filter(a=>a.effect?.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})))",
  );
  assert.ok(
    await evaluate(cdp, "document.documentElement.scrollWidth<=innerWidth+1"),
  );
  await audit.check(cdp, name, queue);
  checks++;
}
async function navigate() {
  await evaluate(cdp, "window.__oldBatchDocument=true");
  await cdp.send("Page.navigate", {
    url: `${base}/overview?qa=${++navigation}`,
  });
  await wait(
    () =>
      evaluate(
        cdp,
        `!window.__oldBatchDocument&&document.documentElement.lang===${JSON.stringify(locale)}&&[...document.querySelectorAll('button[title]')].some(b=>b.title.includes('Batch QA'))`,
      ),
    "Page not ready",
  );
  await click("[data-notifications-trigger]");
  await click(`${modal} [data-domain="${domain}"]`);
  await wait(
    () =>
      evaluate(
        cdp,
        `document.querySelector(${JSON.stringify(queue)})?.getAttribute('aria-busy')==='false'`,
      ),
    "Queue not ready",
  );
}
async function select() {
  await evaluate(
    cdp,
    `[...document.querySelectorAll(${JSON.stringify(queue + " input[type=checkbox]")})].slice(0,2).forEach(input=>input.click())`,
  );
  await wait(
    () =>
      evaluate(
        cdp,
        `document.querySelector(${JSON.stringify(panel)})?.innerText.includes('(2/20)')`,
      ),
    "Selection missing",
  );
}
async function preview() {
  await button(monitoringBatchCopy[locale].preview);
  await wait(
    () =>
      evaluate(
        cdp,
        `document.querySelectorAll(${JSON.stringify(panel + " select")}).length===2`,
      ),
    "Preview missing",
  );
}
async function choices() {
  const action =
    domain === "tenders"
      ? "no_bid"
      : domain === "auctions"
        ? "inspect"
        : "reviewed";
  await evaluate(
    cdp,
    `[...document.querySelectorAll(${JSON.stringify(panel + " select")})].forEach(input=>{input.value=${JSON.stringify(action)};input.dispatchEvent(new Event('change',{bubbles:true}));})`,
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
  let target;
  await wait(async () => {
    target = await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, {
      method: "PUT",
    }).then((r) => r.json());
    return !!target.webSocketDebuggerUrl;
  }, "Chrome debugger did not become available");
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    exceptions.push(
      exceptionDetails.exception?.description || exceptionDetails.text,
    ),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url),
      path = url.pathname;
    requests.push({
      path,
      method: request.method,
      body: request.postData,
      domain,
      locale,
    });
    let code = 200,
      body = {};
    if (path === "/api/auth/session")
      body = {
        authenticated: true,
        user: {
          id: uuid(100),
          name: "Batch QA",
          email: "batch@example.invalid",
          locale,
        },
        organization: { id: uuid(101), name: "Batch QA" },
        role,
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
    else if (path === "/api/monitoring-centre/today-counts")
      body = {
        items: [...domains, "legal"].map((domain) => ({
          domain,
          count: applied ? 0 : 2,
          state: "complete",
        })),
        total: applied ? 0 : 20,
        state: "complete",
        evaluated_at: clock,
      };
    else if (path === "/api/monitoring-centre/notifications")
      body = {
        domain,
        state: "available",
        items: applied ? [] : rows(),
        next_cursor: null,
      };
    else if (path === "/api/monitoring-centre/review/preview") {
      const data = JSON.parse(request.postData);
      assert.equal(data.locale, locale);
      assert.equal(request.method, "POST");
      body = {
        locale,
        applied: false,
        checked_at: clock,
        items: data.records.map((record, n) => ({
          record: mode === "wrong" ? { ...record, item_id: uuid(999) } : record,
          binding: String(n + 1).repeat(64),
          actions: actions(domain),
          more_extracts: true,
          reference_url: `/api/monitoring-centre/evidence/reference?domain=${domain}&monitor_id=${record.monitor_id}&item_id=${record.item_id}&expected_binding=${String(n + 1).repeat(64)}`,
          extracts: [
            {
              pointer: "/facts/title",
              quote: `Exact ${domain} <script>window.injected=true</script>`,
              context: { unit: "m", station_id: "Synthetic" },
            },
            {
              pointer: "/facts/instruction",
              quote: "Original instruction\nUnmodified second line",
              context: {},
            },
          ],
        })),
      };
      if (mode === "late") {
        held = { requestId, body };
        return;
      }
      if (mode === "denied") {
        code = 404;
        body = { code: "monitoring_batch_not_found" };
      }
    } else if (path === "/api/monitoring-centre/review/apply") {
      const data = JSON.parse(request.postData);
      assert.equal(data.locale, locale);
      assert.equal(data.selections.length, 2);
      assert.ok(
        data.selections.every(
          (row, n) =>
            row.expected_binding === String(n + 1).repeat(64) &&
            actions(domain).includes(row.action),
        ),
      );
      if (mode === "conflict") {
        code = 409;
        body = { code: "monitoring_batch_changed" };
      } else {
        applied = true;
        body = { applied: true, count: 2 };
      }
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
        body: Buffer.from(JSON.stringify(body)).toString("base64"),
      })
      .catch(() => {});
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }],
  });
  const languages = process.env.BATCH_CHECK_KEYBOARD_ONLY
    ? []
    : process.env.BATCH_CHECK_LOCALE
      ? [process.env.BATCH_CHECK_LOCALE]
      : Object.keys(monitoringBatchCopy);
  assert.ok(languages.every((language) => monitoringBatchCopy[language]));
  for (const language of languages)
    for (const width of [390, 1440])
      for (const area of domains) {
        locale = language;
        domain = area;
        mode = "ready";
        applied = false;
        await cdp.send("Emulation.setDeviceMetricsOverride", {
          width,
          height: 950,
          deviceScaleFactor: 1,
          mobile: false,
        });
        await navigate();
        const before = requests.filter((r) =>
          r.path.endsWith("/review/apply"),
        ).length;
        await select();
        assert.equal(
          requests.filter((r) => r.path.endsWith("/review/apply")).length,
          before,
        );
        await preview();
        assert.ok(
          (await text(panel)).includes(`<script>window.injected=true</script>`),
        );
        assert.equal(await evaluate(cdp, "!!window.injected"), false);
        assert.equal(
          await evaluate(
            cdp,
            `[...document.querySelectorAll(${JSON.stringify(panel + " a")})].every(a=>a.origin===location.origin&&a.pathname==='/api/monitoring-centre/evidence/reference')`,
          ),
          true,
        );
        if (actions(domain).length > 1)
          assert.equal(
            await evaluate(
              cdp,
              `[...document.querySelectorAll(${JSON.stringify(panel + " button")})].find(b=>b.textContent===${JSON.stringify(monitoringBatchCopy[locale].apply)}).disabled`,
            ),
            true,
          );
        await choices();
        await check(`preview-${domain}-${locale}-${width}`);
        if (locale === "en-CH" && domain === "tenders") {
          await evaluate(
            cdp,
            `document.querySelector(${JSON.stringify(panel)}).scrollIntoView({block:'start'})`,
          );
          await writeFile(
            join(root, `test-results/monitoring-batch-${width}.png`),
            Buffer.from(
              (await cdp.send("Page.captureScreenshot", { format: "png" }))
                .data,
              "base64",
            ),
          );
        }
        await button(monitoringBatchCopy[locale].apply);
        await wait(
          () =>
            text(queue).then((value) =>
              value.includes(monitoringBatchCopy[locale].saved),
            ),
          "Success not shown",
        );
        assert.equal(await text(panel), "");
        await check(`applied-${domain}-${locale}-${width}`);
      }
  locale = "en-CH";
  domain = "tenders";
  for (const scenario of ["conflict", "denied", "wrong"]) {
    mode = scenario;
    applied = false;
    await navigate();
    await select();
    if (scenario === "conflict") {
      await preview();
      await choices();
      await button(monitoringBatchCopy[locale].apply);
    } else await button(monitoringBatchCopy[locale].preview);
    await wait(
      () =>
        text(queue).then((value) =>
          value.includes(monitoringBatchCopy[locale].failed),
        ),
      "Failure not shown",
    );
    assert.equal(await text(panel), "");
    assert.equal(
      await evaluate(
        cdp,
        `document.querySelectorAll(${JSON.stringify(queue + " input:checked")}).length`,
      ),
      0,
    );
    await check(scenario);
  }
  mode = "many";
  applied = false;
  await navigate();
  await evaluate(
    cdp,
    `[...document.querySelectorAll(${JSON.stringify(queue + " input[type=checkbox]")})].slice(0,20).forEach(input=>input.click())`,
  );
  await wait(
    () =>
      evaluate(
        cdp,
        `document.querySelector(${JSON.stringify(panel)})?.innerText.includes('(20/20)')`,
      ),
    "Twenty selections missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      `[...document.querySelectorAll(${JSON.stringify(queue + " input[type=checkbox]")})][20].disabled`,
    ),
    true,
  );
  await check("bounded-selection");
  mode = "late";
  applied = false;
  await navigate();
  await select();
  await button(monitoringBatchCopy[locale].preview);
  await wait(() => !!held, "No held preview");
  await evaluate(
    cdp,
    "window.dispatchEvent(new PageTransitionEvent('pagehide'))",
  );
  await cdp
    .send("Fetch.fulfillRequest", {
      requestId: held.requestId,
      responseCode: 200,
      responseHeaders: [{ name: "Content-Type", value: "application/json" }],
      body: Buffer.from(JSON.stringify(held.body)).toString("base64"),
    })
    .catch(() => {});
  held = null;
  assert.equal(await text(panel), "");
  mode = "ready";
  applied = false;
  await navigate();
  for (let index = 0; index < 2; index++) {
    await evaluate(
      cdp,
      `[...document.querySelectorAll(${JSON.stringify(queue + " input[type=checkbox]")})][${index}].focus()`,
    );
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: " ",
      code: "Space",
      windowsVirtualKeyCode: 32,
    });
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: " ",
      code: "Space",
      windowsVirtualKeyCode: 32,
    });
  }
  await wait(
    () =>
      evaluate(
        cdp,
        `document.querySelectorAll(${JSON.stringify(queue + " input:checked")}).length===2 && document.querySelector(${JSON.stringify(panel)})?.innerText.includes('(2/20)')`,
      ),
    "Keyboard selection failed",
  );
  await evaluate(
    cdp,
    `[...document.querySelectorAll(${JSON.stringify(panel + " button")})].find(b=>b.textContent===${JSON.stringify(monitoringBatchCopy[locale].preview)}).focus()`,
  );
  assert.equal(
    await evaluate(cdp, `document.activeElement?.textContent`),
    monitoringBatchCopy[locale].preview,
  );
  await cdp.send("Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "Enter",
    code: "Enter",
    windowsVirtualKeyCode: 13,
    text: "\r",
    unmodifiedText: "\r",
  });
  await cdp.send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Enter",
    code: "Enter",
    windowsVirtualKeyCode: 13,
  });
  await wait(
    () =>
      evaluate(
        cdp,
        `document.querySelectorAll(${JSON.stringify(panel + " select")}).length===2`,
      ),
    "Keyboard preview failed",
  );
  await check("keyboard-preview");
  role = "viewer";
  mode = "ready";
  await navigate();
  assert.equal(
    await evaluate(
      cdp,
      `document.querySelectorAll(${JSON.stringify(queue + " input[type=checkbox]")}).length`,
    ),
    0,
  );
  await check("viewer");
  assert.deepEqual(exceptions, []);
  assert.ok(
    requests
      .filter((r) => r.method === "POST")
      .every(
        (r) =>
          r.path.startsWith("/api/monitoring-centre/review/") ||
          r.path.startsWith("/api/assistant/"),
      ),
  );
  await writeFile(
    join(root, `test-results/${auditName}-requests.json`),
    JSON.stringify(requests, null, 2),
  );
  audit.finish(checks);
  console.log(
    `Batch review: ${checks} full-document browser/axe checkpoints; ${languages.length ? `nine directions, ${languages.length} locales, two widths` : "focused keyboard/failure checks"}, explicit decisions, conflicts, access, bound selections, viewer and late response.`,
  );
} catch (error) {
  console.error({
    locale,
    domain,
    mode,
    exceptions,
    recent: requests.slice(-6),
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
  assert.ok(basename(profile).startsWith("helvetic-batch-review-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
