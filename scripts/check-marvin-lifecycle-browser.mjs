// Production UI, synthetic intercepted APIs and speech spy; no working service.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { createServer } from "node:net";
import { Cdp, evaluate, pollJson, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";

const root = resolve(import.meta.dirname, ".."),
  audit = new AccessibilityAudit("marvin-lifecycle");
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-marvin-lifecycle-"));
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
const fixture = JSON.parse(
  await readFile(
    join(root, "scripts/fixtures/comparison-synthetic.json"),
    "utf8",
  ),
);
const requests = [],
  exceptions = [],
  held = [];
let includeJobs = false,
  holdJobsUser = "";
let cdp,
  initScript,
  locale = "en-CH",
  user = "qa-a",
  organization = "qa-org-a",
  hold = "",
  generation = 0;
let conversation = {
  id: "",
  draft: "",
  handoffs: [],
  messages: [],
  visibility: "personal",
};
const calls = () =>
  requests.filter(
    (r) =>
      r.path.startsWith("/api/assistant/") ||
      (r.path === "/api/jobs" && r.query === "?workload=ai&limit=50"),
  );
async function waitFor(check, message) {
  for (let i = 0; i < 150; i++) {
    if (await check().catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}
async function respond(requestId, body, code = 200) {
  await cdp.send("Fetch.fulfillRequest", {
    requestId,
    responseCode: code,
    responseHeaders: [{ name: "Content-Type", value: "application/json" }],
    body: Buffer.from(JSON.stringify(body)).toString("base64"),
  });
}
async function releaseHeld() {
  assert.ok(held.length, "The pending request was not exercised");
  for (const item of held.splice(0))
    await respond(item.requestId, item.body).catch((error) => {
      // An AbortController may have removed the paused request from Chromium.
      if (
        !/Invalid InterceptionId|Invalid requestId|No resource|not found/i.test(
          error.message,
        )
      )
        throw error;
    });
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
    ).split("\n")[0];
    return !!debugPort;
  }, "Chrome did not start");
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
      payload = request.postData ? JSON.parse(request.postData) : null;
    requests.push({
      path: url.pathname,
      query: url.search,
      method: request.method,
      body: payload,
      user,
      organization,
    });
    let body = {},
      code = 200;
    if (url.pathname === "/api/auth/session")
      body = {
        authenticated: true,
        user: {
          id: user,
          email: `${user}@example.invalid`,
          name: user,
          locale,
        },
        organization: { id: organization, name: organization },
        role: "organization_admin",
      };
    else if (url.pathname === "/api/health")
      body = {
        status: "ok",
        database: "sqlite",
        apertus: { configured: false },
        firecrawl: { configured: false },
      };
    else if (url.pathname === "/api/assistant/context")
      body = {
        context: {
          entity: {
            kind: "law",
            id: "synthetic",
            label: `${user}/${organization}/${payload.route}`,
          },
        },
        persona: { quip_allowed: false },
      };
    else if (url.pathname === "/api/assistant/runtime")
      body = {
        display_name: "Synthetic runtime",
        ready: true,
        state: "ready",
        selected_model: { display_name: "Synthetic" },
        policy: { cloud_fallback: false, single_runtime: true },
      };
    else if (url.pathname === "/api/assistant/conversations") {
      conversation = {
        id: `conversation-${++generation}`,
        draft: "",
        handoffs: [],
        messages: [
          {
            id: `saved-${generation}`,
            role: "assistant",
            content: `Saved ${user}/${organization}/${payload.route}`,
            created_at: "2026-09-06T08:00:00Z",
          },
        ],
        visibility: "personal",
      };
      body = structuredClone(conversation);
    } else if (
      url.pathname.startsWith("/api/assistant/conversations/") &&
      url.pathname.endsWith("/messages")
    ) {
      body = {
        ...conversation,
        messages: [
          {
            id: "late",
            role: "assistant",
            content: "LATE PRIVATE ANSWER MUST NOT APPEAR",
            created_at: "2026-09-06T08:00:00Z",
          },
        ],
      };
    } else if (
      url.pathname.startsWith("/api/assistant/conversations/") &&
      request.method === "PATCH"
    )
      body = { ...conversation, draft: payload.draft };
    else if (url.pathname === `/api/comparisons/${fixture.id}`) body = fixture;
    else if (url.pathname.endsWith("/ai-history"))
      body = { items: [], total: 0, next_cursor: null };
    else if (
      url.pathname === "/api/jobs" &&
      url.searchParams.get("workload") === "ai" &&
      includeJobs
    )
      body = [
        {
          id: `job-${user}-${organization}`,
          type: "ask",
          state: "running",
          target_type: "comparison",
          target_id: fixture.id,
          progress: { current: 1, total: 2 },
          steps: [
            { name: `Private job ${user}/${organization}`, state: "running" },
          ],
          result: null,
        },
      ];
    else if (
      [
        "/api/jobs",
        "/api/monitoring-topics",
        "/api/sources",
        "/api/laws",
        "/api/scans",
      ].includes(url.pathname)
    )
      body = [];
    else if (url.pathname === "/api/source-packs")
      body = {
        items: [],
        starter: {
          id: "synthetic",
          state: "inactive",
          name: { "en-CH": "Synthetic starter" },
          description: { "en-CH": "No live sources connected." },
          expected_first_data: {
            "en-CH": "Synthetic only; no automatic data.",
          },
        },
      };
    else {
      body = { detail: "Unconfigured synthetic endpoint" };
      code = 503;
    }
    if (
      (hold === "bootstrap" &&
        url.pathname === "/api/assistant/conversations") ||
      (hold === "chat" && url.pathname.endsWith("/messages")) ||
      (holdJobsUser === user &&
        url.pathname === "/api/jobs" &&
        url.searchParams.get("workload") === "ai")
    ) {
      hold = "";
      holdJobsUser = "";
      held.push({ requestId, body });
      return;
    }
    await respond(requestId, body, code).catch(() => {});
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }],
  });
  const click = async (selector, keyboard = false) => {
    const point = await evaluate(
      cdp,
      `(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`,
    );
    if (keyboard) {
      await evaluate(
        cdp,
        `document.querySelector(${JSON.stringify(selector)}).focus()`,
      );
      for (const type of ["keyDown", "keyUp"])
        await cdp.send("Input.dispatchKeyEvent", {
          type,
          key: "Enter",
          code: "Enter",
          windowsVirtualKeyCode: 13,
          ...(type === "keyDown" ? { text: "\r" } : {}),
        });
    } else
      for (const type of ["mousePressed", "mouseReleased"])
        await cdp.send("Input.dispatchMouseEvent", {
          type,
          x: point.x,
          y: point.y,
          button: "left",
          clickCount: 1,
        });
  };
  const panel = () =>
    waitFor(
      () => evaluate(cdp, "!!document.querySelector('.marvin-drawer[open]')"),
      "Panel not open",
    );
  const ready = () =>
    waitFor(
      () =>
        evaluate(
          cdp,
          `document.querySelector('.marvin-chat-log')?.innerText.includes(${JSON.stringify(`Saved ${user}/${organization}`)})`,
        ),
      "Current personal conversation missing",
    );
  const check = async (name, selector) => {
    assert.ok(
      await evaluate(
        cdp,
        "document.documentElement.scrollWidth <= innerWidth+1",
      ),
      "Page overflow",
    );
    await audit.check(cdp, name, selector);
  };
  const quiet = async (start, message) => {
    await sleep(800);
    assert.deepEqual(calls().slice(start), [], message);
  };
  const settings = async () => {
    await click(".marvin-settings-toggle");
    await waitFor(
      () => evaluate(cdp, "!!document.querySelector('[data-marvin-pause]')"),
      "Pause control missing",
    );
  };
  const changeRoute = async (path) => {
    if (await evaluate(cdp, "!!document.querySelector('.marvin-drawer[open]')"))
      await click("[data-marvin-close]");
    // Use the application's actual Next Link, retaining the mounted shell.
    await evaluate(
      cdp,
      `document.querySelector('.sidebar a[href=${JSON.stringify(path)}]').click()`,
    );
    await waitFor(
      () => evaluate(cdp, `location.pathname===${JSON.stringify(path)}`),
      "Client navigation failed",
    );
  };
  async function initialize(enabled, attached = true, route = "/topics") {
    if (initScript)
      await cdp.send("Page.removeScriptToEvaluateOnNewDocument", {
        identifier: initScript,
      });
    initScript = (
      await cdp.send("Page.addScriptToEvaluateOnNewDocument", {
        source: `
      localStorage.setItem('helvetic_lens_companion_v1',JSON.stringify({enabled:${enabled},contextAttached:${attached},sound:false,voice:true,spontaneous:false,tone:'dry'}));
      window.__spoken=[]; Object.defineProperty(window,'speechSynthesis',{value:{getVoices:()=>[],speak:u=>window.__spoken.push(u.text),cancel(){},resume(){},addEventListener(){},removeEventListener(){}}});
      window.__realNow=Date.now; window.__clockOffset=0; Date.now=()=>window.__realNow()+window.__clockOffset;
    `,
      })
    ).identifier;
    await cdp.send("Page.navigate", {
      url: `${base}${route}?locale=${locale}`,
    });
    await waitFor(
      () =>
        evaluate(
          cdp,
          `document.documentElement.lang===${JSON.stringify(locale)} && !!document.querySelector('.marvin-trigger')`,
        ),
      "Entry not ready",
    );
    // Remove seeding after initial load so reload checks real persisted choices.
    await cdp.send("Page.removeScriptToEvaluateOnNewDocument", {
      identifier: initScript,
    });
    initScript = null;
  }
  for (const language of ["en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"])
    for (const width of [390, 1440]) {
      locale = language;
      user = `qa-${language}-${width}`;
      organization = "qa-org-a";
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: width < 500,
      });
      const start = calls().length,
        name = `${language}-${width}`;
      await initialize(false);
      await quiet(start, "Disabled entry issued assistant requests");
      await check(`${name}-paused`, ".marvin-resume");
      if (language === "en-CH" && width === 390)
        await writeFile(
          join(root, "test-results/marvin-paused-mobile.png"),
          Buffer.from(
            (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
            "base64",
          ),
        );
      await click(".marvin-resume", true);
      await panel();
      await ready();
      assert.equal(
        calls()
          .slice(start)
          .filter((r) => r.path === "/api/assistant/conversations").length,
        1,
        "Resume duplicated bootstrap",
      );
      assert.equal(
        calls()
          .slice(start)
          .some((r) => r.method === "PATCH"),
        false,
        "Reading a saved conversation wrote a draft",
      );
      await check(`${name}-enabled`, ".marvin-chat");
      await click(".marvin-context-chip");
      await waitFor(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('.marvin-context-chip.is-detached') && !document.querySelector('.marvin-chat')",
          ),
        "Detach retained private chat",
      );
      const detached = calls().length;
      await changeRoute("/sources");
      await click(".marvin-trigger");
      await panel();
      await quiet(detached, "Detached navigation reattached context");
      await check(`${name}-detached-route`, ".marvin-context-chip.is-detached");
      await settings();
      await click("[data-marvin-pause]");
      await waitFor(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('[data-marvin-paused]') && !document.querySelector('.shell.assistant-open')",
          ),
        "Pause retained panel layout",
      );
      await click(".marvin-resume");
      await panel();
      await quiet(detached, "Resume silently reattached context");
      await check(
        `${name}-resumed-detached`,
        ".marvin-context-chip.is-detached",
      );
      await cdp.send("Page.reload");
      await waitFor(
        () => evaluate(cdp, "!!document.querySelector('.marvin-trigger')"),
        "Reload failed",
      );
      await click(".marvin-trigger");
      await panel();
      await quiet(detached, "Reload forgot context-detached preference");
      await click(".marvin-context-chip");
      await ready();
      await check(`${name}-reattached`, ".marvin-chat");
      await settings();
      await click("[data-marvin-pause]");
      const paused = calls().length;
      await cdp.send("Page.reload");
      await waitFor(
        () => evaluate(cdp, "!!document.querySelector('[data-marvin-paused]')"),
        "Reload forgot paused preference",
      );
      await quiet(paused, "Paused reload initiated requests");
      await check(`${name}-paused-reload`, ".marvin-resume");
    }
  locale = "en-CH";
  user = "owner-a";
  organization = "org-a";
  includeJobs = true;
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
  });
  hold = "bootstrap";
  await initialize(true);
  await click(".marvin-trigger");
  await panel();
  await waitFor(
    () => Promise.resolve(held.length === 1),
    "Bootstrap was not held",
  );
  await click(".marvin-context-chip");
  await releaseHeld();
  await sleep(200);
  assert.ok(
    await evaluate(
      cdp,
      "!document.querySelector('.marvin-chat') && !document.querySelector('.marvin-context-chip').innerText.includes('owner-a')",
    ),
    "Late bootstrap restored detached data",
  );
  await check("late-bootstrap-detached", ".marvin-context-chip.is-detached");
  await click(".marvin-context-chip");
  await ready();
  hold = "chat";
  await click(".marvin-chat textarea");
  await cdp.send("Input.insertText", { text: "Private unsent work" });
  await click(".marvin-chat button[type=submit]");
  await waitFor(() => Promise.resolve(held.length === 1), "Chat was not held");
  await changeRoute("/sources");
  await click(".marvin-trigger");
  await panel();
  await ready();
  await releaseHeld();
  await sleep(300);
  assert.ok(
    await evaluate(
      cdp,
      "!document.querySelector('.marvin-chat-log').innerText.includes('LATE PRIVATE') && !window.__spoken.some(t=>t.includes('LATE PRIVATE'))",
    ),
    "Old chat response reached the new page or voice",
  );
  await check("late-chat-new-route", ".marvin-chat");
  // An actual auth-resource refresh changes identity without a page reload.
  user = "owner-b";
  holdJobsUser = user;
  await evaluate(
    cdp,
    "window.__clockOffset+=70000;window.dispatchEvent(new Event('focus'))",
  );
  await ready();
  await waitFor(
    () => Promise.resolve(held.length === 1),
    "Replacement identity job read was not held",
  );
  assert.ok(
    await evaluate(
      cdp,
      "!document.querySelector('.marvin-jobs')?.innerText.includes('owner-a')",
    ),
    "Fresh identity reused the previous job cache while its read was pending",
  );
  await releaseHeld();
  await waitFor(
    () =>
      evaluate(
        cdp,
        "document.querySelector('.marvin-jobs')?.innerText.includes('owner-b/org-a')",
      ),
    "Current identity jobs did not load",
  );
  assert.ok(
    await evaluate(
      cdp,
      "!document.querySelector('.marvin-chat-log').innerText.includes('owner-a')",
    ),
    "User switch kept the previous user's messages",
  );
  await check("identity-switched", ".marvin-chat");
  organization = "org-b";
  await evaluate(
    cdp,
    "window.__clockOffset+=70000;window.dispatchEvent(new Event('focus'))",
  );
  await ready();
  assert.ok(
    await evaluate(
      cdp,
      "!document.querySelector('.marvin-chat-log').innerText.includes('org-a')",
    ),
    "Organization switch kept private history",
  );
  await check("organization-switched", ".marvin-chat");
  // Legacy unscoped drafts cannot be attributed to an account; only the current
  // user's organization-scoped tab draft is eligible for restoration.
  const ownedKey =
    "helvetic_lens_companion_draft_v1:" +
    JSON.stringify([organization, user, fixture.id]);
  await evaluate(
    cdp,
    `sessionStorage.setItem(${JSON.stringify(ownedKey)},'OWNED TAB DRAFT');sessionStorage.setItem(${JSON.stringify("helvetic_lens_companion_draft_v1:" + fixture.id)},'UNOWNED LEGACY DRAFT')`,
  );
  await cdp.send("Page.addScriptToEvaluateOnNewDocument", {
    source:
      "window.__realNow=Date.now;window.__clockOffset=0;Date.now=()=>window.__realNow()+window.__clockOffset;",
  });
  await cdp.send("Page.navigate", { url: `${base}/compare/${fixture.id}` });
  await waitFor(
    () => evaluate(cdp, "!!document.querySelector('.marvin-trigger')"),
    "Comparison failed",
  );
  await click(".marvin-trigger");
  await panel();
  await waitFor(
    () =>
      evaluate(
        cdp,
        "document.querySelector('#marvin-question')?.value==='OWNED TAB DRAFT'",
      ),
    "Owned draft was lost",
  );
  await check("owned-comparison-draft", "#marvin-question");
  await click("#marvin-question");
  await evaluate(cdp, "document.querySelector('#marvin-question').select()");
  await cdp.send("Input.insertText", { text: "Edited draft" });
  await waitFor(
    () =>
      Promise.resolve(
        calls().some(
          (r) => r.method === "PATCH" && r.body?.draft === "Edited draft",
        ),
      ),
    "Edited draft was not saved",
  );
  const beforeClear = calls().length;
  await evaluate(
    cdp,
    "document.querySelector('#marvin-question').focus();document.querySelector('#marvin-question').select()",
  );
  for (const type of ["keyDown", "keyUp"])
    await cdp.send("Input.dispatchKeyEvent", {
      type,
      key: "Backspace",
      code: "Backspace",
      windowsVirtualKeyCode: 8,
    });
  await waitFor(
    () =>
      Promise.resolve(
        calls()
          .slice(beforeClear)
          .some((r) => r.method === "PATCH" && r.body?.draft === ""),
      ),
    "Clearing back to the initial empty draft was not saved",
  );
  user = "owner-c";
  // The replacement page has a fresh clock; install a bounded stale-time shift.
  await evaluate(
    cdp,
    "window.__clockOffset+=70000;window.dispatchEvent(new Event('focus'))",
  );
  await ready();
  assert.equal(
    await evaluate(cdp, "document.querySelector('#marvin-question').value"),
    "",
    "Another account inherited a private tab draft",
  );
  assert.equal(
    requests
      .filter((r) => r.user === "owner-c")
      .some((r) => JSON.stringify(r.body).includes("OWNED TAB DRAFT")),
    false,
    "Private draft sent under replacement account",
  );
  await check("foreign-draft-excluded", "#marvin-question");
  await click(".marvin-context-chip");
  await waitFor(
    () => evaluate(cdp, "!document.querySelector('#marvin-question')"),
    "Detach failed before draft race",
  );
  hold = "bootstrap";
  await click(".marvin-context-chip");
  await waitFor(
    () => Promise.resolve(held.length === 1),
    "Draft restore was not held",
  );
  await click("#marvin-question");
  await cdp.send("Input.insertText", { text: "Typed while restoring history" });
  await releaseHeld();
  await ready();
  assert.equal(
    await evaluate(cdp, "document.querySelector('#marvin-question').value"),
    "Typed while restoring history",
    "Late history overwrote the current user edit",
  );
  await check("typed-draft-survives-restore", "#marvin-question");
  assert.deepEqual(exceptions, []);
  audit.finish(67);
  console.log(
    "Marvin lifecycle: 10 locale/viewport journeys preserve pause and detach across navigation/reload/resume; seven pending-response/account/draft boundaries, saved clearing and typing during restore pass. Speech and all APIs synthetic; no live data or inference.",
  );
  await writeFile(
    join(root, "test-results/marvin-lifecycle-requests.json"),
    JSON.stringify(requests, null, 2),
  );
} catch (error) {
  console.error({
    locale,
    user,
    organization,
    requests: requests.slice(-12),
    exceptions,
    text: cdp
      ? await evaluate(cdp, "document.body.innerText.slice(-1600)").catch(
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
  assert.ok(basename(profile).startsWith("helvetic-marvin-lifecycle-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
