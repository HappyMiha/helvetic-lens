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
  audit = new AccessibilityAudit("monitoring-guidance");
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-monitoring-guidance-"));
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
const guideCatalogue = JSON.parse(await readFile(join(root, "services/api/helvetic_lens/monitoring_assistant_help.json"), "utf8"));
let activeRoute = "/monitoring";
let failHelp = false;
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
        context: { entity: null },
        persona: { quip_allowed: false },
      };
    else if (url.pathname === "/api/assistant/runtime")
      body = {
        display_name: "Synthetic runtime",
        ready: false,
        state: "stopped",
        selected_model: { display_name: "Synthetic" },
        policy: { cloud_fallback: false, single_runtime: true },
      };
    else if (url.pathname === "/api/assistant/conversations") {
      activeRoute = payload.route;
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
      if (failHelp) code = 503;
      body = {
        ...conversation,
        messages: [
          {
            id: "late",
            role: "assistant",
            content: guideCatalogue.locales[locale].routes[activeRoute] + " " + guideCatalogue.locales[locale].boundary,
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
  let checkpoints = 0;
  for (const language of ["en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"]) {
    locale = language;
    user = `qa-${language}`;
    organization = "qa-monitoring-guidance";
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: language === "en-CH" ? 1440 : 390, height: 1000,
      deviceScaleFactor: 1, mobile: language !== "en-CH",
    });
    for (const route of Object.keys(guideCatalogue.locales[language].routes)) {
      activeRoute = "";
      await initialize(true, true, route);
      await waitFor(async () => activeRoute === route, "Current section did not finish hydration");
      await click(".marvin-trigger");
      await panel();
      await ready();
      if (route === '/trademark-watch') {
        await click('[data-marvin-close]');
        await evaluate(cdp, "document.querySelector('.marvin-trigger').focus()");
        await cdp.send('Input.dispatchKeyEvent', {type:'keyDown', key:' ', code:'Space', windowsVirtualKeyCode:32, text:' '});
        await cdp.send('Input.dispatchKeyEvent', {type:'keyUp', key:' ', code:'Space', windowsVirtualKeyCode:32});
        await panel();
      }
      const copy = guideCatalogue.locales[language];
      assert.equal(activeRoute, route, "The server conversation was attached to the wrong section");
      assert.equal(await evaluate(cdp, "document.querySelector('.marvin-context-chip')?.textContent.trim()"),
        await evaluate(cdp, `document.querySelector('.sidebar a[href="${route}"]')?.textContent.trim()`));
      assert.equal(await evaluate(cdp, "document.querySelector('.marvin-primary-action')?.getAttribute('href')"), "/monitoring");
      assert.equal(await evaluate(cdp, "document.querySelector('.marvin-message p')?.innerText"), copy.routes[route]);
      assert.equal(await evaluate(cdp, "document.querySelector('[data-monitoring-assistant-help]')?.innerText"), copy.button);
      assert.equal(await evaluate(cdp, "!!document.querySelector('.marvin-quip')"), false);
      const before = requests.length;
      await evaluate(cdp, "document.querySelector('.marvin-chat textarea').focus()");
      await cdp.send("Input.insertText", {text:"PRIVATE UNSENT DRAFT"});
      if (route === '/hazard-watch' && language === 'en-CH') {
        failHelp = true;
        await click("[data-monitoring-assistant-help]", true);
        await waitFor(() => evaluate(cdp, "!!document.querySelector('.marvin-chat-error')"), "Failed help did not explain recovery");
        assert.equal(await evaluate(cdp, "document.querySelector('.marvin-chat textarea').value"), "PRIVATE UNSENT DRAFT");
        failHelp = false;
      }
      await click("[data-monitoring-assistant-help]", true);
      await waitFor(() => evaluate(cdp, `document.querySelector('.marvin-chat-log')?.innerText.includes(${JSON.stringify(copy.boundary)})`), "Offline section help did not arrive");
      assert.equal(await evaluate(cdp, "document.querySelector('.marvin-chat textarea').value"), "PRIVATE UNSENT DRAFT");
      const posted = requests.slice(before).filter(r=>r.path.endsWith('/messages'));
      assert.equal(posted.length, route === '/hazard-watch' && language === 'en-CH' ? 2 : 1);
      assert.equal(posted[0].body.message, copy.question);
      assert.ok(!JSON.stringify(requests.slice(before)).includes("PRIVATE UNSENT DRAFT"));
      assert.ok(!requests.slice(before).some(r=>r.path.includes('/remark') || r.path.includes('/handoffs')));
      const context = requests.filter(r=>r.path === '/api/assistant/context').at(-1).body;
      assert.equal(context.route, route);
      assert.equal(context.entity, undefined);
      await check(`${language}-${route.slice(1)}`, ".marvin-drawer");
      checkpoints++;
      if (route === '/hazard-watch' && language === 'en-CH') await writeFile(join(root, 'test-results/monitoring-guidance-desktop.png'), Buffer.from((await cdp.send('Page.captureScreenshot', {format:'png'})).data, 'base64'));
      if (route === '/pollen-watch' && language === 'de-CH') await writeFile(join(root, 'test-results/monitoring-guidance-mobile.png'), Buffer.from((await cdp.send('Page.captureScreenshot', {format:'png'})).data, 'base64'));
    }
    await click('.marvin-primary-action', true);
    await waitFor(async () => activeRoute === '/monitoring', 'The primary action did not open the management centre');
    await click('.marvin-trigger');
    await panel();
    await ready();
    assert.equal(await evaluate(cdp, "document.querySelector('.marvin-message p')?.innerText"), guideCatalogue.locales[language].routes['/monitoring']);
    await check(`${language}-client-navigation`, '.marvin-drawer');
    checkpoints++;
  }
  assert.deepEqual(exceptions, []);
  audit.finish(checkpoints);
  console.log(`Monitoring guidance: ${checkpoints} built-browser checks across nine directions and the centre in five locales. Offline help retains unsent drafts; context remains screen-only. APIs and sources synthetic.`);
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
  assert.ok(basename(profile).startsWith("helvetic-monitoring-guidance-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
