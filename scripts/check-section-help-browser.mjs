// Real production frontend, isolated browser profile, synthetic API only.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { createServer } from "node:net";
import { Cdp, evaluate, pollJson, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { GUIDE_ROUTES } from "../apps/web/lib/section-guides.ts";
const root = resolve(import.meta.dirname, "..");
const accessibility = new AccessibilityAudit("section-help");
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
  { cwd: join(root, "apps/web"), stdio: "ignore", windowsHide: true },
);
const profile = await mkdtemp(join(tmpdir(), "helvetic-help-browser-"));
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
  role = "organization_admin",
  platform = true,
  authenticated = true;
const requests = [],
  exceptions = [];
async function waitFor(check, message) {
  for (let n = 0; n < 150; n++) {
    if (await check().catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}
const writes = () =>
  requests.filter((r) => !["GET", "HEAD"].includes(r.method)).length;
const localized = (value) =>
  Object.fromEntries(
    ["en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"].map((key) => [key, value]),
  );
try {
  await waitFor(async () => (await fetch(base)).ok, "UI did not start");
  let debugPort;
  await waitFor(async () => {
    debugPort = (
      await readFile(join(profile, "DevToolsActivePort"), "utf8")
    ).split("\n")[0];
    return !!debugPort;
  }, "Browser did not start");
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
    const path = new URL(request.url).pathname;
    requests.push({ path, method: request.method });
    let body = {},
      code = 200;
    if (path === "/api/auth/session")
      body = {
        authenticated,
        user: authenticated
          ? { id: "help-qa", email: "qa@example.invalid", name: "QA", locale }
          : undefined,
        organization: { id: "help-qa", name: "QA" },
        role,
        platform_admin: platform,
      };
    else if (path === "/api/health")
      body = {
        status: "ok",
        database: "postgresql",
        apertus: { configured: false },
        firecrawl: { configured: false },
      };
    else if (path === "/api/source-packs")
      body = {
        catalogue_revision: "synthetic",
        starter: {
          id: "federal",
          revision: "1",
          name: localized("Federal starter"),
          description: localized("Synthetic federal scope"),
          expected_first_data: localized("Bounded collection"),
          state: "inactive",
          active_subpack_count: 0,
          subpack_count: 1,
        },
        items: [
          {
            id: "basel-stadt-legislation",
            parent_id: "cantonal",
            revision: "1",
            name: localized("Basel-Stadt"),
            description: localized("Synthetic German legislation pilot only."),
            expected_first_data: localized("Bounded starter collection."),
            filters: { streams: [] },
            authorities: [],
            document_kinds: [],
            languages: ["de"],
            cadences: [],
            historical_windows: [],
            known_gaps: [],
            capabilities: [],
            last_success_at: null,
            partial: true,
            subscription: { enabled: false },
            pending_request: null,
          },
        ],
      };
    else if (
      [
        "/api/monitoring-topics",
        "/api/jobs",
        "/api/scans",
        "/api/sources",
        "/api/laws",
      ].includes(path)
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
  const click = async (selector) => {
    // Dialog overlay exit and scroll-lock removal finish after focus restoration.
    await waitFor(
      () =>
        evaluate(
          cdp,
          `(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)return false;el.scrollIntoView({block:'center',behavior:'instant'});const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));})()`,
        ),
      `Control stayed covered: ${selector}`,
    );
    await evaluate(
      cdp,
      `new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`,
    );
    const point = await evaluate(
      cdp,
      `(()=>{const el=document.querySelector(${JSON.stringify(selector)}); if(!el) throw new Error('Missing '+${JSON.stringify(selector)});el.scrollIntoView({block:'center',behavior:'instant'});const r=el.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return {x,y,visible:el.contains(document.elementFromPoint(x,y))};})()`,
    );
    if (!point.visible) {
      const shot = await cdp.send("Page.captureScreenshot", { format: "png" });
      await writeFile(
        join(root, ".tmp", "help-failure.png"),
        Buffer.from(shot.data, "base64"),
      );
      console.error(
        await evaluate(
          cdp,
          `(()=>{const el=document.querySelector(${JSON.stringify(selector)});const d=document.querySelector('[data-section-guide]');return {point:${JSON.stringify(point)},element:document.elementFromPoint(${point.x},${point.y})?.outerHTML,rect:d?.getBoundingClientRect().toJSON(),transform:d&&getComputedStyle(d).transform,translate:d&&getComputedStyle(d).translate};})()`,
        ),
      );
    }
    assert.ok(point.visible, `Not pointer-reachable: ${selector}`);
    for (const type of ["mousePressed", "mouseReleased"])
      await cdp.send("Input.dispatchMouseEvent", {
        type,
        x: point.x,
        y: point.y,
        button: "left",
        clickCount: 1,
      });
  };
  const key = async (key, code = key) => {
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key,
      code,
      windowsVirtualKeyCode:
        key === "Escape"
          ? 27
          : key === "Tab"
            ? 9
            : key === "F1"
              ? 112
              : undefined,
    });
    await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key, code });
  };
  async function navigate(path) {
    await cdp.send("Page.navigate", { url: `${base}${path}` });
    await waitFor(
      () =>
        evaluate(cdp, `!!document.querySelector('[data-page-guide-trigger]')`),
      `Guide missing: ${path}`,
    );
    await sleep(250);
  }
  async function openGuide() {
    await click("[data-page-guide-trigger]");
    await waitFor(
      () => evaluate(cdp, `!!document.querySelector('[data-section-guide]')`),
      "Guide did not open",
    );
    await sleep(250);
    assert.equal(
      await evaluate(
        cdp,
        `document.querySelector('[data-section-guide]').lang`,
      ),
      "en",
    );
    assert.equal(await evaluate(cdp, `document.activeElement.tagName`), "H2");
  }
  const routes = [
    ...Object.keys(GUIDE_ROUTES),
    "/laws/fixture-id",
    "/compare/fixture-id",
    "/native-comparison/fixture-id",
    "/evidence/fixture-id",
    "/corpus-evidence/fixture-id",
  ];
  for (const path of process.argv.includes("--focused") ? [] : routes) {
    authenticated = path !== "/login";
    await navigate(path);
    const before = writes();
    await openGuide();
    for (const tab of ["controls", "data", "setup", "start"]) {
      await click(`[data-section-guide] [role="tab"][id$="trigger-${tab}"]`);
      assert.ok(
        await evaluate(
          cdp,
          `document.querySelector('[role="tabpanel"][data-state="active"]').innerText.length>40`,
        ),
      );
    }
    await key("Escape");
    await waitFor(
      () => evaluate(cdp, `!document.querySelector('[data-section-guide]')`),
      "Escape failed",
    );
    await waitFor(
      () =>
        evaluate(
          cdp,
          `document.activeElement.matches('[data-page-guide-trigger]')`,
        ),
      "Focus did not return to guide trigger",
    );
    assert.equal(writes(), before, `Help wrote data on ${path}`);
  }
  authenticated = true;
  for (const width of [390, 1440])
    for (const permission of ["viewer", "organization_admin"]) {
      role = permission;
      platform = false;
      locale = width === 390 ? "de-CH" : "en-CH";
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: width < 500,
      });
      await navigate("/onboarding/basel-stadt");
      await click(".marvin-trigger");
      await waitFor(
        () => evaluate(cdp, `!!document.querySelector('dialog[open]')`),
        "Marvin did not open",
      );
      await key("F1");
      assert.equal(
        await evaluate(cdp, `!!document.querySelector('[data-section-guide]')`),
        false,
        "F1 stacked a guide behind a native dialog",
      );
      await key("Escape");
      await waitFor(
        () => evaluate(cdp, `!document.querySelector('dialog[open]')`),
        "Marvin did not close",
      );
      const before = writes();
      await key("F1");
      await waitFor(
        () => evaluate(cdp, `!!document.querySelector('[data-section-guide]')`),
        "F1 failed",
      );
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('[data-section-guide]').lang`,
        ),
        "en",
      );
      await accessibility.check(
        cdp,
        `start-${width}-${permission}`,
        "[data-section-guide]",
      );
      if (permission === "organization_admin") {
        await mkdir(join(root, ".tmp"), { recursive: true });
        const shot = await cdp.send("Page.captureScreenshot", {
          format: "png",
        });
        await writeFile(
          join(root, ".tmp", `help-start-${width}.png`),
          Buffer.from(shot.data, "base64"),
        );
      }
      for (let n = 0; n < 12; n++) {
        await key("Tab");
        assert.ok(
          await evaluate(
            cdp,
            `document.querySelector('[data-section-guide]').contains(document.activeElement)`,
          ),
          "Focus escaped modal",
        );
      }
      await click('[role="tab"][id$="trigger-controls"]');
      assert.equal(
        await evaluate(
          cdp,
          `!!document.querySelector('[data-guide-control="page:enable"]')`,
        ),
        permission === "organization_admin",
      );
      if (permission === "organization_admin") {
        assert.ok(
          await evaluate(
            cdp,
            `document.querySelector('[data-guide-control="page:preview"]').innerText.includes('Currently disabled')`,
          ),
        );
        await click('[data-guide-control="page:enable"] button');
        await waitFor(
          () =>
            evaluate(
              cdp,
              `document.activeElement.matches('[data-basel-enable]')`,
            ),
          "Show me failed to focus original control",
        );
        assert.ok(
          await evaluate(
            cdp,
            `document.activeElement.hasAttribute('data-guide-highlight')`,
          ),
        );
        assert.equal(writes(), before, "Show me activated a shared source");
        await openGuide();
        await click('[role="tab"][id$="trigger-data"]');
        await click('[role="tab"][id$="trigger-controls"]');
        // A formerly visible control can disappear while the guide is open.
        await evaluate(
          cdp,
          `document.querySelector('[data-basel-enable]').style.display='none'`,
        );
        await click('[data-guide-control="page:enable"] button');
        assert.ok(
          await evaluate(
            cdp,
            `document.querySelector('[data-section-guide]').innerText.includes('This control is not currently shown')`,
          ),
        );
      }
      await accessibility.check(
        cdp,
        `controls-${width}-${permission}`,
        "[data-section-guide]",
      );
      const geometry = await evaluate(
        cdp,
        `(()=>{const dialog=document.querySelector('[data-section-guide]'),close=dialog.querySelector('[aria-label="Close page guide"]'),chapter=dialog.querySelector('[role="tabpanel"][data-state="active"]'),r=close.getBoundingClientRect();return {closeVisible:close.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)),closeRect:r.toJSON(),closeStyle:getComputedStyle(close).display,chapterWidth:chapter.clientWidth,chapterContent:chapter.scrollWidth,dialogHeight:dialog.clientHeight,dialogContent:dialog.scrollHeight};})()`,
      );
      assert.ok(
        geometry.closeVisible,
        `Close control must stay reachable: ${JSON.stringify(geometry)}`,
      );
      assert.ok(
        geometry.chapterContent <= geometry.chapterWidth + 1,
        `Help chapter overflows: ${JSON.stringify(geometry)}`,
      );
      await mkdir(join(root, ".tmp"), { recursive: true });
      const shot = await cdp.send("Page.captureScreenshot", { format: "png" });
      await writeFile(
        join(root, ".tmp", `help-${width}-${permission}.png`),
        Buffer.from(shot.data, "base64"),
      );
      assert.ok(
        await evaluate(
          cdp,
          `document.documentElement.scrollWidth<=innerWidth+1`,
        ),
        "Horizontal page overflow",
      );
      assert.ok(
        await evaluate(
          cdp,
          `(()=>{const r=document.querySelector('[data-section-guide]').getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1})()`,
        ),
        "Dialog exceeds viewport",
      );
      await click('[data-section-guide] input[type="search"]');
      await cdp.send("Input.insertText", { text: "zzzz-no-such-control" });
      assert.ok(
        await evaluate(
          cdp,
          `document.querySelector('[data-section-guide]').innerText.includes('No matching explanation')`,
        ),
      );
      assert.equal(writes(), before, "Guide interaction wrote data");
      await key("Escape");
      await navigate("/settings");
      await openGuide();
      if (permission === "viewer")
        assert.ok(
          await evaluate(
            cdp,
            `document.querySelector('[data-section-guide]').innerText.includes('requires an organization administrator')`,
          ),
        );
    }
  // Public form state survives help, and help cannot submit credentials.
  authenticated = false;
  locale = "en-CH";
  await navigate("/login");
  await click('input[type="email"]');
  await cdp.send("Input.insertText", { text: "draft@example.invalid" });
  const before = writes();
  await openGuide();
  await key("Escape");
  assert.equal(
    await evaluate(cdp, `document.querySelector('input[type="email"]').value`),
    "draft@example.invalid",
  );
  assert.equal(writes(), before);
  assert.deepEqual(exceptions, []);
  accessibility.finish(8);
  console.log(
    `Contextual help: ${process.argv.includes("--focused") ? "focused viewport checks" : `${routes.length} page routes`}, four chapters, desktop/mobile roles, English in localized UI, keyboard/focus, safe highlighting, disabled/missing targets, search, draft preservation and no help writes passed.`,
  );
} catch (error) {
  console.error({
    locale,
    role,
    exceptions,
    requests: requests.slice(-6),
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
  assert.ok(basename(profile).startsWith("helvetic-help-browser-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
