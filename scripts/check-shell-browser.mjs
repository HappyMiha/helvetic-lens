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
const profile = await mkdtemp(join(tmpdir(), "helvetic-shell-browser-"));
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
let locale = "en-CH",
  role = "viewer",
  platform = false;
async function waitFor(check, message) {
  for (let i = 0; i < 150; i++) {
    if (await check().catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}
const law = {
  organization_candidate_id: "candidate-old",
  candidate_id: "shared",
  watch_id: "watch",
  law_id: "law",
  law_title: "Synthetic monitored law",
  status: "awaiting_analysis",
  severity: "unknown",
  why: ["Saved official reference"],
  potential_effect: "Awaiting evidence review",
  suggested_next_step: "Inspect the saved evidence",
  coverage: {},
  analysis_history_count: 0,
  review_history_count: 0,
  links: { timeline: "/laws/law", analysis_history: "/api/test" },
};
const event = (title) => ({
  event_id: title,
  title,
  source: "fedlex",
  authority: "Fedlex",
  type: "amended",
  document_kind: "law",
  detected_at: "2026-09-05T08:00:00Z",
  read_state: "unread",
  severity: "unknown",
  coverage: { analysed: 0, total: 1 },
  items: [law],
});
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
        role,
        platform_admin: platform,
        organizations: [
          { id: "qa-org", name: "Isolated QA", role, current: true },
          {
            id: "other",
            name: "Second synthetic organization",
            role: "viewer",
            current: false,
          },
        ],
      };
    else if (url.pathname === "/api/health")
      body = {
        status: "ok",
        database: "sqlite",
        apertus: { configured: false, model: "qa" },
        firecrawl: { configured: false },
        private_sources_enabled: false,
      };
    else if (["/api/sources", "/api/laws"].includes(url.pathname)) body = [];
    else if (url.pathname === "/api/jobs") body = [];
    else if (url.pathname === "/api/impact-inbox/law-options")
      body = {
        items: [
          { id: "law", watch_id: "watch", title: "Synthetic monitored law" },
          {
            id: "other",
            watch_id: "other-watch",
            title: "Law from another page",
          },
        ],
        selected: null,
        has_more: true,
      };
    else if (url.pathname === "/api/impact-inbox/page") {
      if (url.searchParams.get("cursor") === "bad") {
        code = 422;
        body = {
          code: "invalid_inbox_cursor",
          detail: "Invalid cursor. Open the first page.",
        };
      } else {
        const later = url.searchParams.has("cursor"),
          linked = url.searchParams.has("candidate"),
          sparse = !later && url.searchParams.get("severity") === "high";
        body = {
          items: sparse
            ? []
            : [
                event(
                  linked
                    ? "Linked historical event"
                    : later
                      ? "Older saved event"
                      : "Newest saved event",
                ),
              ],
          total_events: sparse ? 0 : 1,
          total_impacts: sparse ? 0 : 1,
          unread: sparse ? 0 : 1,
          counts_scope: "page",
          scanned_event_count: linked ? 1 : 50,
          has_more: !later && !linked,
          next_cursor: !later && !linked ? "next" : null,
        };
      }
    } else {
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
  const press = async (key) => {
    const code = { Tab: 9, Escape: 27, Enter: 13 }[key.replace("Shift+", "")];
    const actual = key.replace("Shift+", "");
    const modifiers = key.startsWith("Shift+") ? 8 : 0;
    for (const type of ["keyDown", "keyUp"])
      await cdp.send("Input.dispatchKeyEvent", {
        type,
        key: actual,
        code: actual,
        windowsVirtualKeyCode: code,
        text: actual === "Enter" && type === "keyDown" ? "\r" : undefined,
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
    await sleep(150);
  };
  const isOpen = () =>
    evaluate(
      cdp,
      `!!document.querySelector('.mobile-nav-menu[data-state="open"]')`,
    );
  const closed = async () => {
    await waitFor(async () => !(await isOpen()), "Mobile menu failed to close");
    await waitFor(
      () => evaluate(cdp, `!document.querySelector('.mobile-nav-menu')`),
      "Closed menu retained its focus trap",
    );
  };
  const openMenu = async () => {
    await evaluate(cdp, `document.querySelector('.mobile-nav-more').focus()`);
    await press("Enter");
    try {
      await waitFor(isOpen, "Mobile menu did not open from keyboard");
    } catch (error) {
      console.error(
        await evaluate(
          cdp,
          `JSON.stringify({active:document.activeElement.outerHTML, trigger:document.querySelector('.mobile-nav-more')?.outerHTML, menu:document.querySelector('.mobile-nav-menu')?.outerHTML, width:innerWidth, media:matchMedia('(max-width: 900px)').matches})`,
        ),
      );
      throw error;
    }
    await waitFor(
      () =>
        evaluate(
          cdp,
          `!!document.querySelector('.mobile-nav-menu')?.contains(document.activeElement)`,
        ),
      "Focus did not enter mobile menu",
    );
    await evaluate(
      cdp,
      `Promise.all(document.querySelector('.mobile-nav-menu').getAnimations().map(a => a.finished.catch(() => {})))`,
    );
    await sleep(50);
  };
  const screenshots = join(root, "test-results/shell-navigation");
  await mkdir(screenshots, { recursive: true });
  for (const selectedLocale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    locale = selectedLocale;
    for (const width of [390, 768]) {
      for (const selectedRole of [
        "viewer",
        "organization_admin",
        "platform_admin",
      ]) {
        platform = selectedRole === "platform_admin";
        role = platform ? "organization_admin" : selectedRole;
        await resize(width);
        await cdp.send("Page.navigate", {
          url: `${base}/impact?qa=${selectedLocale}-${width}-${selectedRole}`,
        });
        await waitFor(
          () =>
            evaluate(
              cdp,
              `!!document.querySelector('[data-inbox-navigation]') && document.documentElement.lang === ${JSON.stringify(locale)}`,
            ),
          "Required populated route/locale missing",
        );
        await press("Tab");
        assert.ok(
          await evaluate(
            cdp,
            `document.activeElement.matches('.skip-link') && document.activeElement.getBoundingClientRect().top >= 0`,
          ),
          "First keyboard stop must be a visible skip link",
        );
        await press("Enter");
        await waitFor(
          () => evaluate(cdp, `document.activeElement.id === 'main-content'`),
          "Skip did not focus the actual content",
        );
        const beforeOverflow = await evaluate(
          cdp,
          `getComputedStyle(document.body).overflow`,
        );
        await openMenu();
        assert.ok(
          await evaluate(
            cdp,
            `(() => { const before = document.activeElement; document.querySelector('.skip-link').focus(); return before === document.activeElement && document.querySelector('.mobile-nav-menu').contains(document.activeElement); })()`,
          ),
          "Background focus escaped the dialog",
        );
        assert.equal(
          await evaluate(cdp, `getComputedStyle(document.body).overflow`),
          "hidden",
        );
        assert.ok(
          await evaluate(
            cdp,
            `!document.elementFromPoint(innerWidth / 2, innerHeight - 20)?.closest('.mobile-nav')`,
          ),
          "Background navigation must not sit above the modal backdrop",
        );
        assert.equal(
          await evaluate(
            cdp,
            `!!document.querySelector('.mobile-nav-menu a[href="/settings"]')`,
          ),
          role === "organization_admin",
        );
        assert.equal(
          await evaluate(
            cdp,
            `!!document.querySelector('.mobile-nav-menu a[href="/admin"]')`,
          ),
          platform,
        );
        assert.ok(
          await evaluate(
            cdp,
            `(() => { const d = document.querySelector('.mobile-nav-menu'); const title = document.getElementById(d.getAttribute('aria-labelledby')); return d.getAttribute('role') === 'dialog' && title?.textContent.trim().length > 0; })()`,
          ),
        );
        const moved = new Set();
        for (let i = 0; i < 36; i++) {
          await press(i < 18 ? "Tab" : "Shift+Tab");
          assert.ok(
            await evaluate(
              cdp,
              `document.querySelector('.mobile-nav-menu').contains(document.activeElement)`,
            ),
            "Keyboard focus escaped the menu",
          );
          moved.add(await evaluate(cdp, `document.activeElement.outerHTML`));
        }
        assert.ok(
          moved.size > 2,
          "Keyboard test never traversed the navigation",
        );
        await evaluate(
          cdp,
          `document.querySelector('.mobile-nav-menu .workspace-switcher button[aria-expanded]').focus()`,
        );
        await press("Enter");
        assert.ok(
          await evaluate(
            cdp,
            `!!document.querySelector('.mobile-nav-menu .workspace-menu')`,
          ),
        );
        await press("Escape");
        await waitFor(
          () =>
            evaluate(
              cdp,
              `!document.querySelector('.mobile-nav-menu .workspace-menu')`,
            ),
          "Escape did not close the nested workspace selector",
        );
        assert.ok(await isOpen(), "Escape closed both nested layers");
        await press("Escape");
        await closed();
        assert.ok(
          await evaluate(
            cdp,
            `document.activeElement.matches('.mobile-nav-more')`,
          ),
          "Menu opener focus was not restored",
        );
        assert.equal(
          await evaluate(cdp, `getComputedStyle(document.body).overflow`),
          beforeOverflow,
        );
        await openMenu();
        if (locale === "en-CH" && platform) {
          const shot = await cdp.send("Page.captureScreenshot", {
            format: "png",
          });
          await writeFile(
            join(screenshots, `menu-${width}.png`),
            Buffer.from(shot.data, "base64"),
          );
        }
        assert.ok(
          await evaluate(
            cdp,
            `(() => { const d = document.querySelector('.mobile-nav-menu'), r = d.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth + 1 && r.top >= 0 && r.bottom <= innerHeight; })()`,
          ),
          "Menu does not fit viewport",
        );
        await resize(1440);
        await closed();
        await waitFor(
          () => evaluate(cdp, `document.activeElement.id === 'main-content'`),
          "Resize returned focus to a hidden mobile control",
        );
        assert.ok(
          await evaluate(
            cdp,
            `!document.body.hasAttribute('data-scroll-locked')`,
          ),
        );
        await resize(width);
        await openMenu();
        await cdp.send("Input.dispatchMouseEvent", {
          type: "mousePressed",
          x: 5,
          y: 5,
          button: "left",
          clickCount: 1,
        });
        await cdp.send("Input.dispatchMouseEvent", {
          type: "mouseReleased",
          x: 5,
          y: 5,
          button: "left",
          clickCount: 1,
        });
        await closed();
        assert.ok(
          await evaluate(
            cdp,
            `document.activeElement.matches('.mobile-nav-more')`,
          ),
        );
      }
    }
  }
  // Explicit close button and actual route navigation, beyond source contracts.
  await openMenu();
  await evaluate(
    cdp,
    `document.querySelector('.mobile-nav-menu [data-slot="dialog-close"]').focus()`,
  );
  await press("Enter");
  await closed();
  assert.ok(
    await evaluate(cdp, `document.activeElement.matches('.mobile-nav-more')`),
  );
  await openMenu();
  await evaluate(
    cdp,
    `document.querySelector('.mobile-nav-menu a[href="/sources"]').focus()`,
  );
  await press("Enter");
  await waitFor(
    () =>
      evaluate(
        cdp,
        `location.pathname === '/sources' && !!document.getElementById('main-content')`,
      ),
    "Menu route navigation failed",
  );
  await closed();
  assert.ok(
    await evaluate(cdp, `!document.body.hasAttribute('data-scroll-locked')`),
  );
  assert.deepEqual(exceptions, []);
  assert.equal(
    requests.some((path) => path.startsWith("/api/auth/session/organization")),
    false,
    "The navigation test must not change organizations",
  );
  console.log(
    "Shell production UI: 30 populated language/role/mobile-width journeys passed; first-stop skip link, focus containment, nested Escape, role-filtered links, backdrop/close restoration and desktop resize cleanup. Synthetic intercepted APIs only; no organization switch or actual message/model call.",
  );
} catch (error) {
  if (cdp) {
    console.error(
      await evaluate(
        cdp,
        `(() => { const d=document.querySelector('.mobile-nav-menu'); return JSON.stringify({rect:d?.getBoundingClientRect(), styles:d ? ['top','bottom','left','right','width','transform','translate','maxHeight','padding','animationName'].map(k=>[k,getComputedStyle(d)[k]]) : [],width:innerWidth,height:innerHeight}); })()`,
      ),
    );
    const shot = await cdp.send("Page.captureScreenshot", { format: "png" });
    await mkdir(join(root, "test-results/shell-navigation"), {
      recursive: true,
    });
    await writeFile(
      join(root, "test-results/shell-navigation/failure.png"),
      Buffer.from(shot.data, "base64"),
    );
  }
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
  assert.ok(basename(profile).startsWith("helvetic-shell-browser-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
