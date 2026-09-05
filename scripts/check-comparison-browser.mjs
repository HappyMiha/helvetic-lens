// Real production UI with intercepted synthetic API responses. No live backend.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { createServer } from "node:net";
import { Cdp, evaluate, pollJson, sleep } from "./browser-cdp.mjs";

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
const profile = await mkdtemp(join(tmpdir(), "helvetic-comparison-browser-"));
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
let locale = "en-CH";
const fixture = JSON.parse(
  await readFile(
    join(root, "scripts/fixtures/comparison-synthetic.json"),
    "utf8",
  ),
);
async function waitFor(check, message) {
  for (let i = 0; i < 150; i++) {
    if (await check().catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}
try {
  await waitFor(
    async () => (await fetch(base)).ok,
    "Isolated production UI failed to start",
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
  ).then((response) => response.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    exceptions.push(exceptionDetails.text),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url);
    requests.push(url.pathname + url.search);
    let body = {},
      code = 200;
    if (url.pathname === "/api/auth/session")
      body = {
        authenticated: true,
        user: { id: "qa", email: "qa@example.invalid", name: "QA", locale },
        organization: { id: "qa-org", name: "Isolated QA" },
        role: "organization_admin",
      };
    else if (url.pathname === "/api/health")
      body = {
        status: "ok",
        database: "sqlite",
        apertus: { configured: true, model: "qa" },
        firecrawl: { configured: false },
        private_sources_enabled: false,
      };
    else if (url.pathname === `/api/comparisons/${fixture.id}`) body = fixture;
    else if (url.pathname.endsWith("/ai-history"))
      body = { items: [], total: 0 };
    else if (url.pathname.endsWith("/ask-jobs") || url.pathname === "/api/jobs")
      body = [];
    else {
      code = 503;
      body = { detail: "Unconfigured synthetic QA endpoint" };
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
  // Intercept every application API request before it can reach Next's proxy.
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }],
  });
  const screenshots = join(root, "test-results/comparison-overlays");
  await mkdir(screenshots, { recursive: true });
  const capture = async (name) => {
    const result = await cdp.send("Page.captureScreenshot", { format: "png" });
    await writeFile(
      join(screenshots, name + ".png"),
      Buffer.from(result.data, "base64"),
    );
  };
  const press = async (key, modifiers = 0) => {
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key,
      code: key,
      windowsVirtualKeyCode: key === "Tab" ? 9 : 27,
      modifiers,
    });
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key,
      code: key,
      windowsVirtualKeyCode: key === "Tab" ? 9 : 27,
      modifiers,
    });
  };
  const resize = async (width) => {
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width,
      height: 844,
      deviceScaleFactor: 1,
      mobile: width < 500,
    });
    await sleep(100);
  };
  const modal = () =>
    evaluate(cdp, `!!document.querySelector('dialog.analysis-column:modal')`);
  const clickTab = async (tab) => {
    await evaluate(
      cdp,
      `(() => { const trigger = document.querySelector('.comparison-task-tabs [aria-controls="companion-${tab}"]'); trigger.focus(); trigger.click(); })()`,
    );
    await waitFor(
      modal,
      `Comparison task did not become modal: ${await evaluate(cdp, "JSON.stringify({width:innerWidth,dialog:document.querySelector('dialog.analysis-column')?.outerHTML.slice(0,600),tabs:document.querySelector('.comparison-task-tabs')?.outerHTML})")}`,
    );
  };
  for (const selectedLocale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    locale = selectedLocale;
    for (const width of [390, 768, 1024]) {
      await resize(width);
      await cdp.send("Page.navigate", { url: `${base}/compare/${fixture.id}` });
      await waitFor(
        () =>
          evaluate(
            cdp,
            `!!document.querySelector('.comparison-layout') && document.documentElement.lang === ${JSON.stringify(locale)}`,
          ),
        "Required populated comparison/locale missing",
      );
      assert.equal(await modal(), false);
      await clickTab("ask");
      assert.ok(
        await evaluate(
          cdp,
          `document.querySelector('.analysis-column').contains(document.activeElement)`,
        ),
      );
      assert.ok(
        await evaluate(
          cdp,
          `document.querySelector('.analysis-column').getAttribute('aria-label').trim().length > 0`,
        ),
      );
      assert.ok(
        await evaluate(
          cdp,
          `(() => { const before = document.activeElement; document.querySelector('.back-link').focus(); return document.activeElement === before && document.querySelector('.analysis-column').contains(document.activeElement); })()`,
        ),
        "Background remained focusable",
      );
      assert.equal(
        await evaluate(cdp, `document.documentElement.style.overflow`),
        "hidden",
      );
      const focused = new Set();
      for (let i = 0; i < 16; i++) {
        await press("Tab", i < 8 ? 0 : 8);
        focused.add(await evaluate(cdp, `document.activeElement.outerHTML`));
        assert.ok(
          await evaluate(
            cdp,
            `document.querySelector('.analysis-column').contains(document.activeElement)`,
          ),
          "Tab escaped the modal",
        );
      }
      assert.ok(focused.size > 1, "Keyboard injection never moved focus");
      await evaluate(
        cdp,
        `document.querySelector('#apertus-question').focus()`,
      );
      await cdp.send("Input.insertText", { text: "Synthetic unsent draft" });
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('#apertus-question').value`,
        ),
        "Synthetic unsent draft",
        "Draft was never entered",
      );
      if (locale === "en-CH") await capture(`ask-${width}`);
      await press("Escape");
      await waitFor(
        async () => !(await modal()),
        "Escape failed to close comparison",
      );
      assert.ok(
        await evaluate(
          cdp,
          `document.activeElement.matches('.comparison-task-tabs [aria-controls="companion-ask"]')`,
        ),
        "Opener focus was not restored",
      );
      assert.equal(
        await evaluate(cdp, `document.documentElement.style.overflow`),
        "",
      );
      assert.equal(
        await evaluate(cdp, `location.search.includes('task=')`),
        false,
        "Close retained a stale task URL",
      );
      await clickTab("ask");
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('#apertus-question').value`,
        ),
        "Synthetic unsent draft",
      );
      await resize(1440);
      await waitFor(
        async () => !(await modal()),
        "Desktop panel remained modal",
      );
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('.analysis-column').getAttribute('role')`,
        ),
        "dialog",
      );
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('.analysis-column').getAttribute('aria-modal')`,
        ),
        null,
      );
      await evaluate(cdp, `document.querySelector('.back-link').focus()`);
      assert.ok(
        await evaluate(cdp, `document.activeElement.matches('.back-link')`),
      );
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('#apertus-question').value`,
        ),
        "Synthetic unsent draft",
        "Resize lost the Ask draft",
      );
      if (locale === "en-CH" && width === 390) await capture("ask-desktop");
      await resize(width);
      await waitFor(modal, "Return to overlay viewport lost open state");
      await evaluate(cdp, `document.querySelector('.companion-close').click()`);
      await waitFor(async () => !(await modal()), "Close button failed");
      if (width === 1024) {
        await clickTab("summary");
        await cdp.send("Input.dispatchMouseEvent", {
          type: "mousePressed",
          x: 10,
          y: 150,
          button: "left",
          clickCount: 1,
        });
        await cdp.send("Input.dispatchMouseEvent", {
          type: "mouseReleased",
          x: 10,
          y: 150,
          button: "left",
          clickCount: 1,
        });
        await waitFor(
          async () => !(await modal()),
          "Backdrop click failed to close tablet drawer",
        );
      }
      await clickTab("summary");
      const citationCount = await evaluate(
        cdp,
        `document.querySelectorAll('.analysis-column .comparison-citations button').length`,
      );
      assert.ok(
        citationCount > 0,
        "Required populated citation fixture missing",
      );
      await evaluate(
        cdp,
        `document.querySelector('.analysis-column .comparison-citations button').click()`,
      );
      await waitFor(
        async () => !(await modal()),
        "Citation did not return to evidence",
      );
      await waitFor(
        () =>
          evaluate(
            cdp,
            `document.activeElement.closest('.comparison-evidence-pane') !== null`,
          ),
        "Citation jump lost evidence focus",
      );
      assert.ok(
        await evaluate(
          cdp,
          `document.documentElement.scrollWidth <= innerWidth + 1`,
        ),
        `Overflow at ${width}/${locale}`,
      );
    }
  }
  assert.deepEqual(
    exceptions,
    [],
    "Runtime errors in required populated comparison",
  );
  assert.ok(
    requests.some((path) => path.startsWith(`/api/comparisons/${fixture.id}`)),
    "No comparison fixture was used",
  );
  console.log(
    "Comparison production UI: 15 populated locale/overlay-width journeys passed; modal focus isolation, forward/back Tab, Escape/close and return focus, draft persistence through close/desktop resize, nonmodal desktop and cited evidence focus. All API calls intercepted; no live model or data mutation. Physical keyboard/mobile, screen-reader and other-browser review remain separate.",
  );
} catch (error) {
  console.error({
    requests,
    exceptions,
    page: cdp
      ? await evaluate(
          cdp,
          "JSON.stringify({url:location.href,ready:document.readyState,html:document.documentElement.outerHTML.slice(0,1800)})",
        ).catch(() => "unavailable")
      : "no browser",
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
  assert.ok(basename(profile).startsWith("helvetic-comparison-browser-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
