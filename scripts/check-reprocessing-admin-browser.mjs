// Production UI, intercepted synthetic APIs. No maintenance reaches a backend.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { createServer } from "node:net";
import { Cdp, evaluate, pollJson, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";

const root = resolve(import.meta.dirname, ".."),
  audit = new AccessibilityAudit("reprocessing-admin");
const chrome = [
  process.env.CHROME_BIN,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
]
  .filter(Boolean)
  .find(existsSync);
assert.ok(chrome, "A real Chrome executable is required");
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-reprocessing-browser-"));
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
  platformAdmin = true,
  currentRule = "synthetic-rule-2",
  loseNextApply = false,
  unavailable = false;
let saved = [],
  intentions = new Map();
let organizationRole = "organization_admin";
const requests = [],
  exceptions = [];
async function waitFor(check, message) {
  for (let i = 0; i < 160; i++) {
    if (await check().catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}
const visible = (selector) =>
  evaluate(
    cdp,
    `!!document.querySelector(${JSON.stringify(selector)})?.getClientRects().length`,
  );
const writes = () =>
  requests.filter(
    (r) => r.method === "POST" && !r.path.startsWith("/api/assistant/"),
  );
function data(pending = false) {
  return {
    status: pending ? "pending" : "complete",
    has_more: pending,
    dry_run: true,
    rule_revision: currentRule,
    captured_at: "2026-09-06T10:00:00Z",
    processed: pending ? 25 : 61,
    eligible: 61,
    changed: pending ? 1 : 3,
    retained: pending ? 24 : 58,
    rejected: pending ? 1 : 3,
    skipped: 0,
    batches: pending ? 1 : 3,
    ai_calls: 0,
    examples: [
      {
        candidate_id: "synthetic-candidate",
        event_id: "synthetic-event",
        target_work_id: "synthetic-target",
        source_title:
          "Bundesgesetz über den Schutz personenbezogener Daten — synthetic public source",
        target_title:
          "Federal Data Protection Retention Act — saved synthetic target",
        outcome: "rejected",
        old_score: 0.8,
        new_score: 0,
        reason: [
          "Saved synthetic retrieval reason. This is not a legal no-impact judgment.",
        ],
      },
    ],
  };
}
function makeJob(input) {
  const id = `11111111-2222-4333-8444-${String(saved.length + 1).padStart(12, "0")}`;
  const result = { ...data(!input.dry_run), dry_run: input.dry_run };
  return {
    id,
    type: "relation_candidate_reprocess",
    target_type: "relation_candidate_rules",
    target_id: currentRule,
    queue: "maintenance",
    priority: 5,
    state: input.dry_run ? "succeeded" : "running",
    progress: { current: result.processed, total: 61 },
    attempts: 1,
    max_attempts: 3,
    queue_position: null,
    cancel_requested: false,
    request: null,
    error: null,
    maintenance: {
      dry_run: input.dry_run,
      rule_revision: input.rule_revision,
      captured_at: result.captured_at,
    },
    result: {
      type: "relation_candidate_rules",
      id: currentRule,
      url: "/activity",
      data: result,
    },
    steps: [],
    created_at: "2026-09-06T10:00:00Z",
    updated_at: "2026-09-06T10:00:01Z",
    started_at: "2026-09-06T10:00:00Z",
    finished_at: input.dry_run ? "2026-09-06T10:00:01Z" : null,
  };
}
async function key(key, code = key) {
  const virtual = { Enter: 13, Tab: 9, " ": 32 }[key];
  for (const type of ["keyDown", "keyUp"])
    await cdp.send("Input.dispatchKeyEvent", {
      type,
      key,
      code,
      windowsVirtualKeyCode: virtual,
      ...(type === "keyDown" && ["Enter", " "].includes(key)
        ? { text: key === "Enter" ? "\r" : " " }
        : {}),
    });
}
async function click(selector) {
  await waitFor(() => visible(selector), `Missing ${selector}`);
  await evaluate(
    cdp,
    `document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center'})`,
  );
  await sleep(100);
  const p = await evaluate(
    cdp,
    `(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`,
  );
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", ...p });
  await cdp.send("Input.dispatchMouseEvent", {
    type: "mousePressed",
    button: "left",
    clickCount: 1,
    ...p,
  });
  await cdp.send("Input.dispatchMouseEvent", {
    type: "mouseReleased",
    button: "left",
    clickCount: 1,
    ...p,
  });
}
async function open(job = "") {
  await cdp.send("Page.navigate", {
    url: `${base}/admin/relation-reprocessing?locale=${locale}${job ? `&job=${job}` : ""}`,
  });
  await waitFor(
    () =>
      evaluate(
        cdp,
        `document.documentElement.lang===${JSON.stringify(locale)} && !!document.querySelector('h1') && ${platformAdmin ? "!!document.querySelector('[data-reprocessing]')" : "!document.querySelector('[data-reprocessing]')"}`,
      ),
    "Maintenance page missing",
  );
  if (platformAdmin)
    await waitFor(
      () => visible(unavailable ? "[role=alert]" : "[data-current-rule]"),
      "Options not loaded",
    );
}
try {
  await waitFor(
    async () => (await fetch(base)).ok,
    "Isolated production server failed to start",
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
  ).then((r) => r.json());
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
      input = request.postData ? JSON.parse(request.postData) : null;
    requests.push({
      path: url.pathname,
      query: url.search,
      method: request.method,
      body: input,
    });
    let body = {},
      code = 200;
    if (url.pathname === "/api/auth/session")
      body = {
        authenticated: true,
        user: {
          id: "qa-user",
          name: "QA",
          email: "qa@example.invalid",
          locale,
        },
        organization: { id: "qa-org", name: "QA" },
        role: organizationRole,
        platform_admin: platformAdmin,
      };
    else if (url.pathname === "/api/health")
      body = {
        status: "ok",
        database: "postgresql",
        apertus: { configured: true },
        firecrawl: { configured: false },
      };
    else if (url.pathname === "/api/profile")
      body = { name: "Synthetic organization", business_areas: [] };
    else if (url.pathname === "/api/admin/relation-reprocessing") {
      if (!platformAdmin) {
        code = 403;
        body = { detail: "Platform admin required" };
      } else if (unavailable) {
        code = 503;
        body = { detail: "Synthetic maintenance unavailable" };
      } else if (request.method === "GET")
        body = { rule_revision: currentRule, batch_size: 25 };
      else {
        const identity = `${input.rule_revision}:${input.dry_run}:${input.request_id}`;
        if (!intentions.has(identity)) {
          if (input.rule_revision !== currentRule) {
            code = 409;
            body = {
              code: "relation_reprocess_rule_changed",
              detail: "Rule changed",
            };
          } else {
            const job = makeJob(input);
            intentions.set(identity, job);
            saved.unshift(job);
          }
        }
        if (code === 200) body = intentions.get(identity);
        if (loseNextApply && input.dry_run === false) {
          loseNextApply = false;
          await cdp.send("Fetch.failRequest", {
            requestId,
            errorReason: "ConnectionClosed",
          });
          return;
        }
      }
    } else if (url.pathname === "/api/jobs")
      body = url.searchParams.has("job_type") ? saved : [];
    else if (
      url.pathname.startsWith("/api/jobs/") ||
      url.pathname.startsWith("/api/admin/relation-reprocessing/jobs/")
    ) {
      const [, id, action] =
        url.pathname.split("/jobs/")[1].match(/^([^/]+)(?:\/(.*))?$/) || [];
      const job = saved.find((j) => j.id === id);
      if (!job) {
        code = 404;
        body = { detail: "Synthetic job missing" };
      } else {
        if (request.method === "POST" && action === "cancel")
          job.state = "cancelled";
        if (request.method === "POST" && action === "retry") {
          job.state = "succeeded";
          job.progress.current = 61;
          job.result.data = { ...data(), dry_run: job.maintenance.dry_run };
        }
        body = job;
      }
    } else if (
      [
        "/api/scans",
        "/api/sources",
        "/api/laws",
        "/api/monitoring-topics",
      ].includes(url.pathname)
    )
      body = [];
    else {
      code = 503;
      body = { detail: "Synthetic endpoint unavailable" };
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
  for (const language of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"])
    for (const width of [390, 1440]) {
      locale = language;
      organizationRole =
        locale === "en-CH" && width === 1440 ? "viewer" : "organization_admin";
      saved = [];
      intentions = new Map();
      currentRule = "synthetic-rule-2";
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: width < 500,
      });
      const start = writes().length;
      await open();
      assert.equal(writes().length, start, "Opening maintenance mutated data");
      await audit.check(cdp, `${locale}-${width}-empty`, "[data-reprocessing]");
      const origin = await evaluate(cdp, "performance.timeOrigin");
      await click("[data-reprocess-preview]");
      await waitFor(
        () => visible("[data-review-apply]"),
        "Preview did not finish",
      );
      assert.equal(writes().length, start + 1);
      assert.equal(writes().at(-1).body.dry_run, true);
      assert.equal(
        await evaluate(cdp, "performance.timeOrigin"),
        origin,
        "Preview reloaded the page",
      );
      await click("[data-reprocess-result] details summary");
      assert.ok(
        await evaluate(
          cdp,
          "document.documentElement.scrollWidth<=innerWidth+1",
        ),
        "Result overflows viewport",
      );
      await audit.check(
        cdp,
        `${locale}-${width}-preview`,
        "[data-reprocess-counts]",
      );
      await evaluate(
        cdp,
        "window.__maintenanceKeys=[]; ['keydown','keyup','click'].forEach(type=>document.addEventListener(type,e=>window.__maintenanceKeys.push({type:e.type,key:e.key,target:e.target.tagName,review:e.target.hasAttribute?.('data-review-apply')}))); document.querySelector('[data-review-apply]').focus()",
      );
      await key("Enter");
      await waitFor(
        () => visible("[data-apply-confirmation]"),
        "Apply confirmation missing",
      );
      assert.ok(
        await evaluate(
          cdp,
          "document.activeElement.matches('[data-apply-confirmation] h3')",
        ),
        "Confirmation heading did not receive focus",
      );
      assert.ok(
        await evaluate(
          cdp,
          "document.querySelector('[data-confirm-apply]').disabled",
        ),
      );
      await audit.check(
        cdp,
        `${locale}-${width}-confirmation`,
        "[data-apply-confirmation]",
      );
      await evaluate(
        cdp,
        "document.querySelector('[data-apply-acknowledge]').focus()",
      );
      await key(" ", "Space");
      assert.ok(
        await evaluate(
          cdp,
          "document.querySelector('[data-apply-acknowledge]').checked",
        ),
      );
      loseNextApply = true;
      await click("[data-confirm-apply]");
      await waitFor(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('[data-recover-request]') && !document.querySelector('[data-recover-request]').disabled",
          ),
        "Lost response was not recoverable",
      );
      const lost = writes().at(-1).body;
      assert.equal(lost.dry_run, false);
      assert.equal(saved.length, 2);
      await open(saved.find((j) => j.maintenance.dry_run).id);
      await waitFor(
        () => visible("[data-recover-request]"),
        "Reload lost the request identity",
      );
      assert.equal(
        writes().at(-1).body.request_id,
        lost.request_id,
        "Reload issued a mutation",
      );
      await click("[data-recover-request]");
      await waitFor(
        () => visible("[data-reprocess-cancel]"),
        "Original running job not recovered",
      );
      assert.equal(saved.length, 2);
      assert.equal(writes().at(-1).body.request_id, lost.request_id);
      assert.equal(writes().at(-1).body.rule_revision, lost.rule_revision);
      assert.ok(
        await evaluate(
          cdp,
          "document.querySelector('[data-reprocess-progress]').textContent.includes('25')",
        ),
      );
      await audit.check(
        cdp,
        `${locale}-${width}-running`,
        "[data-reprocess-cancel]",
      );
      await click("[data-reprocess-cancel]");
      await waitFor(
        () => visible("[data-reprocess-resume]"),
        "Cancelled run has no resume control",
      );
      await click("[data-reprocess-resume]");
      await waitFor(
        () =>
          evaluate(
            cdp,
            "document.querySelector('[data-reprocess-progress]')?.textContent.includes('61') && !document.querySelector('[data-reprocess-resume]')",
          ),
        "Resume did not finish saved run",
      );
      assert.equal(saved.length, 2);
      assert.equal(
        writes().length,
        start + 5,
        "Unexpected mutation outside preview, apply/recovery, cancel and resume",
      );
      assert.ok(
        writes()
          .slice(start)
          .slice(-2)
          .every((request) =>
            request.path.startsWith("/api/admin/relation-reprocessing/jobs/"),
          ),
        "Maintenance actions must use platform authorization even in a read-only organization",
      );
      assert.ok(
        await evaluate(
          cdp,
          "[...document.querySelectorAll('[data-job-time]')].every(e=>e.textContent.includes(':00:00'))",
        ),
        "Run history omits exact times",
      );
      await audit.check(
        cdp,
        `${locale}-${width}-completed`,
        "[data-reprocess-result]",
      );
      assert.ok(
        await evaluate(
          cdp,
          "document.documentElement.scrollWidth<=innerWidth+1",
        ),
      );
      if (locale === "en-CH" && width === 390) {
        const shot = await cdp.send("Page.captureScreenshot", {
          format: "png",
          captureBeyondViewport: false,
        });
        await mkdir(join(root, "test-results"), { recursive: true });
        await writeFile(
          join(root, "test-results/reprocessing-admin-mobile.png"),
          Buffer.from(shot.data, "base64"),
        );
      }
    }
  // Old-rule previews and superseded zero-batch results must never expose apply.
  currentRule = "synthetic-rule-3";
  await open(saved.find((j) => j.maintenance.dry_run).id);
  await waitFor(
    () => visible("[data-obsolete]"),
    "Old-rule preview was not identified",
  );
  assert.equal(await visible("[data-review-apply]"), false);
  const old = saved.find((j) => j.maintenance.dry_run);
  old.result.data = {
    ...old.result.data,
    status: "superseded",
    eligible: null,
    processed: 0,
    changed: 0,
    retained: 0,
    rejected: 0,
    skipped: 0,
    batches: 0,
  };
  await open(old.id);
  await waitFor(
    () => visible("[data-superseded]"),
    "Early superseded result was hidden",
  );
  assert.equal(await visible("[data-review-apply]"), false);
  old.maintenance.rule_revision = currentRule;
  old.result.data = { ...data(), changed: 0, retained: 61, rejected: 0 };
  await open(old.id);
  await waitFor(
    () => visible("[data-no-changes]"),
    "No-change preview was not explained",
  );
  assert.equal(await visible("[data-review-apply]"), false);
  await audit.check(cdp, "en-CH-1440-no-changes", "[data-no-changes]");
  old.result.data = { ...data(), examples: [{ reason: "malformed result" }] };
  await open(old.id);
  await waitFor(
    () => visible("[data-reprocess-result]"),
    "Malformed result page missing",
  );
  assert.equal(await visible("[data-review-apply]"), false);
  await audit.check(cdp, "en-CH-1440-malformed", "[data-reprocess-result]");
  unavailable = true;
  await open();
  assert.ok(
    await evaluate(
      cdp,
      "document.querySelector('[data-reprocess-preview]').disabled",
    ),
  );
  await audit.check(cdp, "en-CH-1440-unavailable", "[data-reprocessing]");
  unavailable = false;
  const beforeNavigation = writes().length;
  await cdp.send("Page.navigate", { url: `${base}/admin?locale=${locale}` });
  await waitFor(
    () => visible('a[href="/admin/relation-reprocessing"]'),
    "Platform admin has no maintenance entry",
  );
  await click('a[href="/admin/relation-reprocessing"]');
  await waitFor(
    () => visible("[data-reprocessing]"),
    "Admin entry did not open maintenance",
  );
  assert.equal(
    writes().length,
    beforeNavigation,
    "Navigating to maintenance caused a mutation",
  );
  platformAdmin = false;
  const before = requests.length;
  await open(old.id);
  await sleep(300);
  assert.equal(await visible("[data-reprocessing]"), false);
  assert.equal(
    requests
      .slice(before)
      .filter(
        (r) =>
          r.path === "/api/admin/relation-reprocessing" ||
          r.query?.includes("job_type="),
      ).length,
    0,
    "Ordinary organization admin fetched platform maintenance",
  );
  await audit.check(cdp, "en-CH-1440-denied", "h1");
  assert.deepEqual(exceptions, []);
  audit.finish(54);
  console.log(
    "Maintenance UI: preview, keyboard confirmation, lost apply response and reload recovery with the same UUID/rule, progress, cancel/resume, no page reload, old-rule/superseded/denied states; five locales, 390/1440px, synthetic APIs only.",
  );
} catch (error) {
  console.error({
    locale,
    currentRule,
    requests: requests.slice(-12),
    exceptions,
    focus: cdp
      ? await evaluate(
          cdp,
          "({active:document.activeElement?.outerHTML.slice(0,400),keys:window.__maintenanceKeys})",
        ).catch(() => null)
      : null,
    text: cdp
      ? await evaluate(cdp, "document.body.innerText.slice(-2200)").catch(
          () => "unavailable",
        )
      : "none",
  });
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const ended = new Promise((r) => child.once("exit", r));
    child.kill();
    await Promise.race([ended, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-reprocessing-browser-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
