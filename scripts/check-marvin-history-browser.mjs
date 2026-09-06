// Actual production UI; disposable Chrome profile, synthetic APIs, no live data.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { createServer } from "node:net";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";

const root = resolve(import.meta.dirname, ".."),
  audit = new AccessibilityAudit("marvin-history");
const chrome = [
  process.env.CHROME_BIN,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-marvin-history-"));
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
  role = "viewer",
  user = "qa-owner",
  organization = "qa-organization",
  init,
  failure = "",
  empty = false,
  deleted = false,
  holdDetail = false;
const requests = [],
  exceptions = [],
  held = [];
const date = "2026-09-06T09:00:00Z";
const entry = (index) => ({
  id: `personal-${index}`,
  title: `${user}: saved context ${index}`,
  route: "/compare",
  entity_kind: "comparison",
  entity_id: `comparison-${index}`,
  locale,
  created_at: date,
  updated_at: date,
  message_count: 2,
  handoff_count: 1,
  has_draft: true,
});
const detail = (index) => ({
  ...entry(index),
  entity: { kind: "comparison", id: `comparison-${index}` },
  draft: "PRIVATE DRAFT TO REMOVE",
  messages: [
    { id: "m1", role: "user", content: "Explain this page", created_at: date },
    {
      id: "m2",
      role: "assistant",
      content: `${user}: private answer. <img src=x onerror=alert(1)> ${"A long saved thought. ".repeat(65)}`,
      created_at: date,
    },
  ],
  handoffs: [
    { id: "h1", question: "What changed in the document?", created_at: date },
  ],
  visibility: "personal",
});
async function waitFor(check, description) {
  for (let i = 0; i < 180; i++) {
    if (await check().catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(description);
}
async function respond(requestId, body, status = 200) {
  await cdp.send("Fetch.fulfillRequest", {
    requestId,
    responseCode: status,
    responseHeaders: [{ name: "Content-Type", value: "application/json" }],
    body: Buffer.from(JSON.stringify(body)).toString("base64"),
  });
}
async function press(selector, key = "Enter") {
  assert.ok(
    await evaluate(
      cdp,
      `(() => { const el = document.querySelector(${JSON.stringify(selector)}); if (!el || el.disabled) return false; el.focus(); return document.activeElement === el; })()`,
    ),
    `Cannot focus ${selector}`,
  );
  await cdp.send("Input.dispatchKeyEvent", {
    type: "keyDown",
    text: "\r",
    key,
    code: key,
    windowsVirtualKeyCode: 13,
  });
  await cdp.send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code: key,
    windowsVirtualKeyCode: 13,
  });
}
async function checkpoint(name, selector = "[data-marvin-history]") {
  // Wait for finite dialog/button transitions; do not exclude any axe rules.
  await evaluate(
    cdp,
    `Promise.all(document.getAnimations().filter(a =>
    Number.isFinite(a.effect?.getComputedTiming().endTime) && a.effect.getComputedTiming().endTime < 2000
  ).map(a => a.finished.catch(() => {})))`,
  );
  await audit.check(cdp, name, selector);
  assert.ok(
    await evaluate(
      cdp,
      "document.documentElement.scrollWidth <= innerWidth + 1",
    ),
    `${name}: page overflow`,
  );
}
async function install() {
  if (init)
    await cdp.send("Page.removeScriptToEvaluateOnNewDocument", {
      identifier: init,
    });
  init = (
    await cdp.send("Page.addScriptToEvaluateOnNewDocument", {
      source: `
    localStorage.setItem('helvetic_lens_locale', ${JSON.stringify(locale)});
    localStorage.setItem('helvetic_lens_companion_v1', JSON.stringify({enabled:true,contextAttached:true,voice:false,spontaneous:false}));
    sessionStorage.setItem('helvetic_lens_companion_draft_v1:' + JSON.stringify([${JSON.stringify(organization)},${JSON.stringify(user)},'comparison-0']), 'PRIVATE DRAFT TO REMOVE');
    const realNow = Date.now; window.qaOffset = 0; Date.now = () => realNow() + window.qaOffset;
  `,
    })
  ).identifier;
}
async function navigate() {
  await cdp.send("Page.navigate", { url: `${base}/assistant-history` });
  await waitFor(
    () => evaluate(cdp, "!!document.querySelector('[data-marvin-history]')"),
    "Missing history page",
  );
}
try {
  await waitFor(
    async () => (await fetch(base)).ok,
    "Production UI did not start",
  );
  let debugPort;
  await waitFor(async () => {
    debugPort = (
      await readFile(join(profile, "DevToolsActivePort"), "utf8")
    ).split(/\r?\n/)[0];
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
    exceptions.push(
      exceptionDetails.exception?.description || exceptionDetails.text,
    ),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    try {
      const url = new URL(request.url),
        path = url.pathname;
      requests.push({
        path,
        query: url.search,
        method: request.method,
        user,
        organization,
      });
      let body = {},
        status = 200;
      if (path === "/api/auth/session")
        body = {
          authenticated: true,
          user: {
            id: user,
            name: user,
            email: `${user}@example.invalid`,
            locale,
          },
          organization: { id: organization, name: organization },
          role,
        };
      else if (path === "/api/health")
        body = {
          status: "ok",
          database: "sqlite",
          apertus: { configured: false },
          firecrawl: { configured: false },
        };
      else if (
        path === "/api/assistant/conversations" &&
        request.method === "GET"
      ) {
        if (failure === "list") {
          body = { detail: "Synthetic offline" };
          status = 503;
        } else
          body = {
            items: empty
              ? []
              : url.searchParams.get("cursor")
                ? [entry(20)]
                : Array.from({ length: 20 }, (_, i) => entry(i)).filter(
                    (v) => !deleted || v.id !== "personal-0",
                  ),
            next_cursor:
              empty || url.searchParams.get("cursor") ? null : "page-two",
            visibility: "personal",
          };
      } else if (/^\/api\/assistant\/conversations\/personal-\d+$/.test(path)) {
        if (request.method === "DELETE") {
          if (failure === "delete") {
            body = { detail: "Synthetic delete failed" };
            status = 503;
          } else {
            deleted = true;
            body = { deleted: true, id: "personal-0", visibility: "personal" };
          }
        } else if (failure === "detail") {
          body = { detail: "Synthetic missing" };
          status = 404;
        } else body = detail(Number(path.split("-").at(-1)));
      } else {
        body = { detail: "Unexpected synthetic API" };
        status = 503;
      }
      if (
        holdDetail &&
        /\/personal-\d+$/.test(path) &&
        request.method === "GET"
      )
        held.push({ requestId, body });
      else await respond(requestId, body, status);
    } catch (error) {
      exceptions.push(String(error));
    }
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*` }],
  });
  for (locale of ["en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"])
    for (const width of [390, 1440]) {
      const prefix = `${locale}-${width}`;
      role = width === 390 ? "viewer" : "organization_admin";
      failure = "";
      deleted = false;
      empty = false;
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: false,
      });
      await install();
      await navigate();
      await waitFor(
        () =>
          evaluate(
            cdp,
            "document.querySelectorAll('[data-history-view]').length === 20",
          ),
        "Metadata list missing",
      );
      await checkpoint(`${prefix}-list`);
      assert.ok(
        await evaluate(
          cdp,
          "!document.body.innerText.includes('PRIVATE DRAFT') && !document.querySelector('.marvin-trigger')",
        ),
      );
      await press(".marvin-history-pager button:last-child");
      await waitFor(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('[data-history-view=personal-20]')",
          ),
        "Older page missing",
      );
      await checkpoint(`${prefix}-older`);
      await press(".marvin-history-pager button:first-child");
      await waitFor(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('[data-history-view=personal-0]')",
          ),
        "Newer page missing",
      );
      await press("[data-history-view=personal-0]");
      await waitFor(
        () =>
          evaluate(cdp, "!!document.querySelector('[data-history-delete]')"),
        "Conversation not loaded",
      );
      assert.ok(
        await evaluate(
          cdp,
          "document.activeElement === document.querySelector('.marvin-history-detail h2') && !document.querySelector('.marvin-history-detail img')",
        ),
      );
      await checkpoint(`${prefix}-detail`);
      if (locale === "en-CH") {
        const screenshot = await cdp.send("Page.captureScreenshot", {
          format: "png",
        });
        await writeFile(
          join(root, `test-results/marvin-history-${width}.png`),
          Buffer.from(screenshot.data, "base64"),
        );
      }
      await press("[data-history-delete]");
      await waitFor(
        () => evaluate(cdp, "!!document.querySelector('[role=dialog]')"),
        "Delete confirmation missing",
      );
      await checkpoint(`${prefix}-confirm`, "[role=dialog]");
      await cdp.send("Input.dispatchKeyEvent", {
        type: "keyDown",
        key: "Escape",
        code: "Escape",
        windowsVirtualKeyCode: 27,
      });
      await cdp.send("Input.dispatchKeyEvent", {
        type: "keyUp",
        key: "Escape",
        code: "Escape",
        windowsVirtualKeyCode: 27,
      });
      await waitFor(
        () => evaluate(cdp, "!document.querySelector('[role=dialog]')"),
        "Escape did not cancel deletion",
      );
      assert.equal(deleted, false);
      failure = "delete";
      await press("[data-history-delete]");
      await press('[role="dialog"] button[data-variant="destructive"]');
      await waitFor(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('[role=dialog] [role=alert]')",
          ),
        "Delete failure not shown",
      );
      await checkpoint(`${prefix}-delete-error`, "[role=dialog]");
      failure = "";
      await press('[role="dialog"] button[data-variant="destructive"]');
      await waitFor(
        () =>
          evaluate(
            cdp,
            "document.querySelectorAll('[data-history-view]').length === 19 && !document.querySelector('[role=dialog]')",
          ),
        "Deletion not reflected",
      );
      assert.equal(
        await evaluate(
          cdp,
          `sessionStorage.getItem('helvetic_lens_companion_draft_v1:' + JSON.stringify([${JSON.stringify(organization)},${JSON.stringify(user)},'comparison-0']))`,
        ),
        null,
      );
      await checkpoint(`${prefix}-deleted`);
      empty = true;
      await press(".marvin-history .page-header button");
      await waitFor(
        () =>
          evaluate(cdp, "!!document.querySelector('.marvin-history-empty')"),
        "Empty state missing",
      );
      await checkpoint(`${prefix}-empty`);
      failure = "list";
      await press(".marvin-history .page-header button");
      await waitFor(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('[data-marvin-history] [role=alert]')",
          ),
        "List error missing",
      );
      await checkpoint(`${prefix}-list-error`);
      failure = "";
      empty = false;
      await press(".marvin-history .page-header button");
      await waitFor(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('[data-history-view=personal-1]')",
          ),
        "Refresh failed",
      );
      failure = "detail";
      await press("[data-history-view=personal-1]");
      await waitFor(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('[data-marvin-history] [role=alert]')",
          ),
        "Detail error missing",
      );
      await checkpoint(`${prefix}-detail-error`);
    }
  // Identity refresh while a private detail read is still in flight.
  locale = "en-CH";
  failure = "";
  empty = false;
  deleted = false;
  await install();
  await navigate();
  await waitFor(
    () =>
      evaluate(
        cdp,
        "!!document.querySelector('[data-history-view=personal-0]')",
      ),
    "Race list missing",
  );
  holdDetail = true;
  await press("[data-history-view=personal-0]");
  await waitFor(async () => held.length === 1, "Detail was not held");
  user = "qa-new-owner";
  await evaluate(
    cdp,
    "window.qaOffset=70000; window.dispatchEvent(new Event('focus'))",
  );
  await waitFor(
    () =>
      evaluate(
        cdp,
        "document.querySelector('.marvin-history-list')?.innerText.includes('qa-new-owner')",
      ),
    "Private history did not change owner",
  );
  holdDetail = false;
  for (const item of held.splice(0))
    await respond(item.requestId, item.body).catch((error) => {
      if (
        !/Invalid InterceptionId|Invalid requestId|No resource|not found/i.test(
          error.message,
        )
      )
        throw error;
    });
  assert.ok(
    await evaluate(
      cdp,
      "!document.querySelector('[data-marvin-history]').innerText.includes('qa-owner') && !document.body.innerText.includes('private answer')",
    ),
  );
  await checkpoint("identity-pending-detail-discarded");
  assert.deepEqual(exceptions, []);
  assert.ok(
    requests.every((r) => r.method === "GET" || r.method === "DELETE"),
    "History must never bootstrap or run AI",
  );
  assert.ok(
    requests.every(
      (r) =>
        [
          "/api/auth/session",
          "/api/health",
          "/api/assistant/conversations",
        ].includes(r.path) ||
        /\/assistant\/conversations\/personal-\d+$/.test(r.path),
    ),
    "Unexpected inference or shared-state request",
  );
  audit.finish(91);
  await writeFile(
    join(root, "test-results/marvin-history-requests.json"),
    JSON.stringify(requests, null, 2),
  );
} catch (error) {
  console.error({
    locale,
    failure,
    requests: requests.slice(-8),
    exceptions,
    text: cdp
      ? await evaluate(cdp, "document.body.innerText.slice(-1700)").catch(
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
  assert.ok(basename(profile).startsWith("helvetic-marvin-history-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
