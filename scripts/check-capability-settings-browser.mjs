// Real production UI with intercepted synthetic API responses. No live backend.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { createServer } from "node:net";
import { Cdp, evaluate, pollJson, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
const accessibility = new AccessibilityAudit("capability-settings");

const root = resolve(import.meta.dirname, "..");
const chrome = [
  process.env.CHROME_BIN,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
]
  .filter(Boolean)
  .find(existsSync);
assert.ok(chrome, "A real Chrome executable is required.");
const reserve = createServer();
await new Promise((resolve) => reserve.listen(0, "127.0.0.1", resolve));
const port = reserve.address().port;
await new Promise((resolve) => reserve.close(resolve));
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
  {
    cwd: join(root, "apps/web"),
    stdio: "ignore",
    windowsHide: true,
  },
);
const profile = await mkdtemp(
  join(tmpdir(), "helvetic-capability-settings-browser-"),
);
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
let cdp;
const requests = [],
  exceptions = [];
async function waitFor(check, message) {
  for (let i = 0; i < 150; i++) {
    if (await check().catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}

let locale = "en-CH",
  role = "organization_admin",
  scenario = "profiles",
  settings;
const profiles = [
  {
    id: "synthetic-reviewed",
    revision: 1,
    status: "approved",
    model_id: "synthetic-model",
    scopes: [{ task: "ask", locale: "en-CH" }],
  },
  {
    id: "synthetic-candidate",
    revision: 1,
    status: "candidate",
    model_id: "synthetic-model",
    scopes: [],
  },
  {
    id: "synthetic-withdrawn",
    revision: 2,
    status: "revoked",
    model_id: "synthetic-model",
    scopes: [{ task: "impact_report", locale: "de-CH" }],
  },
];
function initial() {
  return {
    provider: "docker",
    product_id: "",
    base_url: "http://synthetic-manager/openai/v1",
    model: "local-apertus",
    explanation_profile: scenario === "missing" ? "removed-profile" : "",
    explanation_registry_valid: scenario !== "invalid",
    explanation_profiles: scenario === "profiles" ? profiles : [],
    timeout_seconds: 90,
    request_retries: 2,
    batch_concurrency: 1,
    context_chars: 24000,
    max_tokens: 1600,
    temperature: 0.1,
    top_p: 1,
    presence_penalty: 0,
    reasoning_effort: "default",
    json_mode: true,
    configured: true,
    api_key_configured: false,
    key_source: "none",
    source: "workspace",
    updated_at: null,
  };
}
try {
  await waitFor(
    async () => (await fetch(base)).ok,
    "Isolated settings UI failed to start",
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
      payload = request.postData ? JSON.parse(request.postData) : null;
    requests.push({
      path: url.pathname,
      method: request.method,
      body: payload,
    });
    let body = {},
      code = 200;
    if (url.pathname === "/api/auth/session")
      body = {
        authenticated: true,
        user: {
          id: `${locale}-${role}`,
          email: "qa@example.invalid",
          name: "QA",
          locale,
        },
        organization: { id: "qa-org", name: "QA" },
        role,
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
    else if (url.pathname === "/api/settings/apertus") {
      if (request.method === "PATCH")
        settings = {
          ...settings,
          ...payload,
          updated_at: new Date().toISOString(),
        };
      body = settings;
    } else if (
      [
        "/api/jobs",
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
  const writes = () =>
    requests.filter(
      (r) => r.method !== "GET" && !r.path.startsWith("/api/assistant/"),
    );
  async function open() {
    await cdp.send("Page.navigate", {
      url: `${base}/settings?locale=${locale}`,
    });
    await waitFor(
      () =>
        evaluate(
          cdp,
          `!!document.querySelector('#explanation-profile') && document.documentElement.lang===${JSON.stringify(locale)}`,
        ),
      "Profile selector missing",
    );
    await evaluate(
      cdp,
      `document.querySelector('#explanation-profile').scrollIntoView({block:'center'})`,
    );
    assert.ok(
      await evaluate(cdp, `document.documentElement.scrollWidth<=innerWidth+1`),
      "Settings overflow viewport",
    );
  }
  async function key(value) {
    const windowsVirtualKeyCode = {
      Home: 36,
      ArrowDown: 40,
      Tab: 9,
      Enter: 13,
    }[value];
    for (const type of ["keyDown", "keyUp"])
      await cdp.send("Input.dispatchKeyEvent", {
        type,
        key: value,
        code: value,
        windowsVirtualKeyCode,
      });
  }
  for (const language of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"])
    for (const width of [390, 1440]) {
      locale = language;
      role = "organization_admin";
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: width < 500,
      });
      for (const variant of ["profiles", "empty", "invalid", "missing"]) {
        scenario = variant;
        settings = initial();
        const before = writes().length;
        await open();
        const shown = await evaluate(
          cdp,
          `(()=>{const e=document.querySelector('#explanation-profile');return {value:e.value,options:e.options.length,text:document.querySelector('[data-capability-profile]').textContent,help:document.getElementById(e.getAttribute('aria-describedby'))?.textContent};})()`,
        );
        assert.equal(
          shown.value,
          variant === "missing" ? "removed-profile" : "",
        );
        assert.equal(
          shown.options,
          variant === "profiles" ? 4 : variant === "missing" ? 2 : 1,
        );
        assert.ok(shown.help?.length > 70);
        assert.ok(!shown.text.includes("undefined"));
        await accessibility.check(
          cdp,
          `${language}-${width}-${variant}`,
          "[data-capability-profile]",
        );
        assert.equal(
          writes().length,
          before,
          "Reading profiles caused a mutation",
        );
        if (variant === "profiles") {
          await evaluate(
            cdp,
            `document.querySelector('#explanation-profile').focus()`,
          );
          await key("Home");
          await key("ArrowDown");
          await key("Tab");
          await waitFor(
            () =>
              evaluate(
                cdp,
                `document.querySelector('#explanation-profile').value==='synthetic-reviewed' && !!document.querySelector('[data-capability-scopes]')`,
              ),
            "Keyboard selection did not update form",
          );
          assert.equal(
            writes().length,
            before,
            "Selecting profile called API before save",
          );
          const form = await evaluate(
            cdp,
            `(()=>{const e=document.querySelector('[data-capability-profile]').closest('form').querySelector('button[type=submit]');return {disabled:e.disabled,valid:e.form.checkValidity()};})()`,
          );
          assert.ok(!form.disabled && form.valid);
          await evaluate(
            cdp,
            `document.querySelector('[data-capability-profile]').closest('form').querySelector('button[type=submit]').focus()`,
          );
          const point = await evaluate(
            cdp,
            `(()=>{const e=document.querySelector('[data-capability-profile]').closest('form').querySelector('button[type=submit]');e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return {x,y,reachable:e.contains(document.elementFromPoint(x,y))};})()`,
          );
          assert.ok(point.reachable);
          for (const type of ["mousePressed", "mouseReleased"])
            await cdp.send("Input.dispatchMouseEvent", {
              type,
              x: point.x,
              y: point.y,
              button: "left",
              clickCount: 1,
            });
          await waitFor(
            async () => writes().length === before + 1,
            "Profile save missing",
          );
          assert.equal(writes().at(-1).path, "/api/settings/apertus");
          assert.equal(
            writes().at(-1).body.explanation_profile,
            "synthetic-reviewed",
          );
          assert.equal(writes().at(-1).body.model, "local-apertus");
          await open();
          assert.equal(
            await evaluate(
              cdp,
              `document.querySelector('#explanation-profile').value`,
            ),
            "synthetic-reviewed",
          );
          if (locale === "en-CH" && width === 390) {
            await mkdir(join(root, ".tmp"), { recursive: true });
            const shot = await cdp.send("Page.captureScreenshot", {
              format: "png",
            });
            await writeFile(
              join(root, ".tmp/capability-settings-mobile.png"),
              Buffer.from(shot.data, "base64"),
            );
          }
        }
      }
      role = "viewer";
      scenario = "profiles";
      settings = initial();
      const before = writes().length;
      await open();
      assert.ok(
        await evaluate(
          cdp,
          `document.querySelector('#explanation-profile').matches(':disabled')`,
        ),
      );
      assert.equal(writes().length, before);
    }
  assert.deepEqual(exceptions, []);
  accessibility.finish(40);
  console.log(
    "Capability settings: 40 full-page accessibility checkpoints, five locales at 390/1440px, keyboard selection, pointer save and reload, empty/invalid/missing profiles, read-only viewer; synthetic API only.",
  );
} catch (error) {
  console.error({
    locale,
    role,
    scenario,
    requests: requests.slice(-10),
    exceptions,
    focus: cdp
      ? await evaluate(
          cdp,
          "document.activeElement?.outerHTML.slice(0,600)",
        ).catch(() => "unavailable")
      : "none",
    text: cdp
      ? await evaluate(cdp, "document.body.innerText.slice(-1800)").catch(
          () => "unavailable",
        )
      : "none",
  });
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const ended = new Promise((resolve) => child.once("exit", resolve));
    child.kill();
    await Promise.race([ended, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(
    basename(profile).startsWith("helvetic-capability-settings-browser-"),
  );
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
