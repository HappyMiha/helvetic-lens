// Real production UI with intercepted synthetic histories; no backend or AI calls.
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
  audit = new AccessibilityAudit("document-history");
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
const profile = await mkdtemp(
  join(tmpdir(), "helvetic-document-history-browser-"),
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
let cdp,
  locale = "en-CH",
  role = "organization_admin",
  fail = false,
  hold = false,
  releaseHeld;
const requests = [],
  exceptions = [];
const stamp = "2026-09-01T12:34:56Z";
const versions = Array.from({ length: 45 }, (_, i) => ({
  id: `version-${45 - i}`,
  law_id: "history-law",
  title: `Saved evidence ${45 - i}`,
  origin: "import",
  declared_date: "2026-08-01",
  content_type: "text/plain",
  characters: 4500,
  passage_count: 23,
  page_count: 3,
  created_at: stamp,
  synthetic: true,
  identity_json: {},
  source_url: "https://example.invalid/law",
  filename: "synthetic.txt",
}));
const records = {
  versions,
  comparisons: Array.from({ length: 55 }, (_, i) => ({
    id: `comparison-${55 - i}`,
    mode: "historical",
    old_version_id: "version-2",
    new_version_id: "version-1",
    created_at: stamp,
    counts: { added: 1, removed: 0, modified: 1, unchanged: 5 },
  })),
  observations: Array.from({ length: 65 }, (_, i) => ({
    id: `observation-${65 - i}`,
    version_id: "version-1",
    origin: "live",
    created_at: stamp,
    declared_date: null,
    filename: `saved-${65 - i}.txt`,
    source_url: null,
    synthetic: true,
  })),
};
function page(kind, index = 0) {
  return {
    items: records[kind].slice(index * 20, (index + 1) * 20),
    total: records[kind].length,
    limit: 20,
    as_of: stamp,
    first_cursor: `${kind}:0`,
    next_cursor:
      (index + 1) * 20 < records[kind].length ? `${kind}:${index + 1}` : null,
  };
}
const timelineRecords = {
  timeline: Array.from({ length: 55 }, (_, i) => ({
    id: `event:${55 - i}`,
    type: "event",
    event_type: "new_version",
    label: "New Version",
    detail: "official metadata",
    at: stamp,
    url: `https://example.invalid/event/${55 - i}`,
  })),
  identifiers: Array.from({ length: 55 }, (_, i) => ({
    scheme: "SR",
    value: `Identifier ${55 - i}`,
    source_url: `https://example.invalid/id/${55 - i}`,
  })),
  expressions: Array.from({ length: 55 }, (_, i) => ({
    id: `expression-${55 - i}`,
    language: "de",
    title: `Expression ${55 - i}`,
    url: `https://example.invalid/expression/${55 - i}`,
  })),
  relations: Array.from({ length: 55 }, (_, i) => ({
    id: `relation-${55 - i}`,
    direction: "incoming",
    type: "replaces",
    state: "confirmed",
    other_work_id: `work-${55 - i}`,
    other_title: `Related act ${55 - i}`,
    other_timeline_url: `/laws/related-${55 - i}`,
    provenance: "official_metadata",
  })),
  source_provenance: Array.from({ length: 55 }, (_, i) => ({
    origin: "live",
    observed_at: stamp,
    source_url: `https://example.invalid/source/${55 - i}`,
  })),
};
let emptyTimeline = false;
function timelinePage(kind, index = 0) {
  const records = emptyTimeline ? [] : timelineRecords[kind];
  return {
    items: records.slice(index * 20, (index + 1) * 20),
    total: records.length,
    limit: 20,
    as_of: stamp,
    first_cursor: `${kind}:0`,
    next_cursor:
      (index + 1) * 20 < records.length ? `${kind}:${index + 1}` : null,
  };
}
function detail() {
  return {
    id: "history-law",
    name: "Synthetic saved legislative history",
    active: true,
    current_version_id: "version-1",
    current_version: versions.at(-1),
    last_result: "baseline_created",
    last_checked: stamp,
    last_error: null,
    source_url: "https://example.invalid/law",
    source_id: "source",
    synthetic: true,
    ...Object.fromEntries(Object.keys(records).map((k) => [k, page(k).items])),
    history_pages: Object.fromEntries(
      Object.keys(records).map((k) => {
        const { items, ...info } = page(k);
        return [k, info];
      }),
    ),
    regulatory_timeline: {
      monitoring: { active: true },
      work: {
        id: "work",
        kind: "act",
        authority: "Synthetic",
        lifecycle: "in_force",
        stable_official_url: null,
      },
      normalized_versions: 45,
      ...Object.fromEntries(
        Object.keys(timelineRecords).map((k) => [k, timelinePage(k).items]),
      ),
      pages: Object.fromEntries(
        Object.keys(timelineRecords).map((k) => {
          const { items, ...info } = timelinePage(k);
          return [k, info];
        }),
      ),
    },
  };
}
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
async function click(selector, keyboard = false) {
  await waitFor(() => visible(selector), `Missing ${selector}`);
  await evaluate(
    cdp,
    `document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center'})`,
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
    return;
  }
  await sleep(80);
  const point = await evaluate(
    cdp,
    `(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`,
  );
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", ...point });
  for (const type of ["mousePressed", "mouseReleased"])
    await cdp.send("Input.dispatchMouseEvent", {
      type,
      button: "left",
      clickCount: 1,
      ...point,
    });
}
const controls = (kind) => `[data-history-controls=${kind}]`;
const next = (kind) => `${controls(kind)} button:nth-child(2)`;
const previous = (kind) => `${controls(kind)} button:first-child`;
async function historyPage(kind, index) {
  await waitFor(
    async () => {
      const nodes = await evaluate(
        cdp,
        `Array.from(document.querySelectorAll(${JSON.stringify(kind === "versions" ? ".version-list > .version-row" : kind === "comparisons" ? "#history-comparisons" : "[data-history-controls=observations]")})).length`,
      );
      if (kind === "versions")
        return (
          nodes === page(kind, index).items.length &&
          (await visible(
            `.version-list a[href='/evidence/${page(kind, index).items[0].id}']`,
          ))
        );
      if (kind === "comparisons")
        return (
          !!nodes &&
          (await visible(`a[href='/compare/${page(kind, index).items[0].id}']`))
        );
      return await evaluate(
        cdp,
        `document.querySelector('.observations tbody')?.innerText.includes(${JSON.stringify(page(kind, index).items[0].filename)})`,
      );
    },
    `${kind} page ${index + 1} not rendered`,
  );
}
async function regulatoryPage(kind, index) {
  const first = timelinePage(kind, index).items[0];
  const marker = first.source_url || first.url || first.other_timeline_url;
  await waitFor(
    () =>
      evaluate(
        cdp,
        `(()=>{const list=document.querySelector('[data-timeline-rows=${kind}]');
    return list?.getClientRects().length && list.children.length === ${timelinePage(kind, index).items.length}
      && list.querySelector('a')?.getAttribute('href') === ${JSON.stringify(marker)};})()`,
      ),
    `${kind} timeline page ${index + 1} not rendered`,
  );
}
async function check(name, heading = "history-versions") {
  await audit.check(cdp, name, `#${heading}`);
  assert.equal(
    await evaluate(cdp, "document.documentElement.scrollWidth > innerWidth+1"),
    false,
    "Horizontal page overflow",
  );
}
try {
  await waitFor(
    async () => (await fetch(base)).ok,
    "Production server unavailable",
  );
  let debugPort;
  await waitFor(async () => {
    debugPort = (
      await readFile(join(profile, "DevToolsActivePort"), "utf8")
    ).split("\n")[0];
    return !!debugPort;
  }, "Browser unavailable");
  await pollJson(`http://127.0.0.1:${debugPort}/json/version`);
  const target = await fetch(
    `http://127.0.0.1:${debugPort}/json/new?about:blank`,
    { method: "PUT" },
  ).then((r) => r.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  // Exercise ordinary history controls with the product's explicit companion-off preference.
  await cdp.send("Page.addScriptToEvaluateOnNewDocument", {
    source:
      "localStorage.setItem('helvetic_lens_companion_v1', JSON.stringify({enabled:false,spontaneous:false,sound:false,voice:false}))",
  });
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    exceptions.push(
      exceptionDetails.exception?.description || exceptionDetails.text,
    ),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url);
    requests.push({
      method: request.method,
      path: url.pathname,
      query: url.search,
      body: request.postData,
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
        organization: { id: "qa-history-org", name: "History QA" },
        role,
        platform_admin: false,
      };
    else if (url.pathname === "/api/health")
      body = {
        status: "ok",
        database: "postgresql",
        apertus: { configured: false },
        firecrawl: { configured: false },
      };
    else if (url.pathname === "/api/profile")
      body = { name: "Synthetic organization", business_areas: [] };
    else if (url.pathname === "/api/laws/history-law") {
      assert.equal(url.searchParams.get("paged_history"), "true");
      body = detail();
    } else if (
      url.pathname.startsWith("/api/laws/history-law/history/") ||
      url.pathname.startsWith("/api/laws/history-law/timeline/")
    ) {
      const kind = url.pathname.split("/").at(-1),
        cursor = url.searchParams.get("cursor");
      assert.ok(cursor?.startsWith(kind + ":"));
      assert.equal(url.searchParams.get("limit"), "20");
      if (hold) {
        hold = false;
        await new Promise((resolve) => (releaseHeld = resolve));
      }
      if (fail) {
        fail = false;
        code = 503;
        body = { detail: "Synthetic saved-history page unavailable" };
      } else
        body = url.pathname.includes("/timeline/")
          ? timelinePage(kind, Number(cursor.split(":")[1]))
          : page(kind, Number(cursor.split(":")[1]));
    } else if (url.pathname === "/api/laws/history-law/ai-history")
      body = { items: [], total: 0 };
    else if (
      [
        "/api/scans",
        "/api/jobs",
        "/api/laws",
        "/api/sources",
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
    for (const width of [390, 1440])
      for (const organizationRole of ["organization_admin", "viewer"]) {
        locale = language;
        role = organizationRole;
        const label = `${locale}-${width}-${role}`,
          start = requests.length;
        await cdp.send("Emulation.setDeviceMetricsOverride", {
          width,
          height: 900,
          deviceScaleFactor: 1,
          mobile: width === 390,
        });
        await cdp.send("Page.navigate", {
          url: `${base}/laws/history-law?locale=${locale}`,
        });
        await waitFor(
          () =>
            evaluate(
              cdp,
              `document.documentElement.lang===${JSON.stringify(locale)} && !!document.getElementById('history-versions')`,
            ),
          "Law did not render",
        );
        await historyPage("versions", 0);
        await evaluate(cdp, "window.__historyPageToken=crypto.randomUUID()");
        const token = await evaluate(cdp, "window.__historyPageToken");
        await check(`${label}-first`);
        assert.ok(
          await evaluate(
            cdp,
            // Chromium falls back to a 12-hour locale for Romansh; both forms
            // must still show the exact Swiss local hour, minute and second.
            "/\\b(?:14:34:56|2:34:56\\s*PM)\\b/.test(document.querySelector('[data-history-controls=versions]').innerText)",
          ),
          "History cutoff must include seconds in Europe/Zurich",
        );
        const initializationWrites = requests
          .slice(start)
          .filter((r) => r.method !== "GET");
        assert.deepEqual(
          initializationWrites,
          [],
          "Document entry must not initialize the disabled companion",
        );
        assert.equal(
          requests
            .slice(start)
            .some((r) => r.path.startsWith("/api/assistant/")),
          false,
          "Disabled companion sent an entry request",
        );
        assert.equal(
          await evaluate(
            cdp,
            "document.querySelectorAll('.saved-selectors select').length",
          ),
          role === "viewer" ? 0 : 2,
        );
        await click(next("versions"), true);
        await historyPage("versions", 1);
        await waitFor(
          () =>
            evaluate(cdp, "document.activeElement?.id==='history-versions'"),
          "History heading focus was not restored",
        );
        if (role !== "viewer")
          await click(
            ".version-list .version-row:first-child button:not([aria-label])",
          );
        await click(next("versions"));
        await historyPage("versions", 2);
        assert.equal(
          await evaluate(
            cdp,
            `document.querySelector(${JSON.stringify(next("versions"))}).disabled`,
          ),
          true,
        );
        if (role !== "viewer") {
          assert.equal(
            await evaluate(
              cdp,
              "document.querySelector('.saved-selectors select').value",
            ),
            "version-25",
          );
          assert.ok(
            await evaluate(
              cdp,
              "Array.from(document.querySelector('.saved-selectors select').options).some(o=>o.value==='version-1')",
            ),
            "Current version outside the first page is selectable",
          );
        }
        await check(`${label}-old-version`);
        await click(previous("versions"));
        await historyPage("versions", 1);
        await click(previous("versions"));
        await historyPage("versions", 0);
        if (role !== "viewer")
          assert.equal(
            await evaluate(
              cdp,
              "document.querySelector('.saved-selectors select').value",
            ),
            "version-25",
          );
        await click(next("comparisons"));
        await historyPage("comparisons", 1);
        await click(next("comparisons"));
        await historyPage("comparisons", 2);
        await check(`${label}-old-comparison`, "history-comparisons");
        await click("#history-observations");
        await click(next("observations"));
        await historyPage("observations", 1);
        await click(next("observations"));
        await historyPage("observations", 2);
        await click(next("observations"));
        await historyPage("observations", 3);
        await check(`${label}-old-observation`, "history-observations");
        if (role === "viewer") {
          for (const kind of Object.keys(timelineRecords)) {
            await click(`[data-timeline-kind=${kind}]`, true);
            await regulatoryPage(kind, 0);
            await click(next(`regulatory-${kind}`), true);
            await regulatoryPage(kind, 1);
            await waitFor(
              () =>
                evaluate(
                  cdp,
                  `document.activeElement?.id === 'history-regulatory-${kind}'`,
                ),
              "Timeline heading focus missing",
            );
            await click(next(`regulatory-${kind}`));
            await regulatoryPage(kind, 2);
            assert.equal(
              await evaluate(
                cdp,
                `document.querySelector(${JSON.stringify(next(`regulatory-${kind}`))}).disabled`,
              ),
              true,
            );
            await check(
              `${label}-timeline-${kind}`,
              `history-regulatory-${kind}`,
            );
            if (locale === "en-CH" && width === 390 && kind === "relations") {
              await evaluate(
                cdp,
                "document.querySelector('[data-regulatory-timeline]').scrollIntoView({block:'start'})",
              );
              await writeFile(
                join(root, "test-results/regulatory-timeline-mobile.png"),
                Buffer.from(
                  (await cdp.send("Page.captureScreenshot", { format: "png" }))
                    .data,
                  "base64",
                ),
              );
            }
            await click(previous(`regulatory-${kind}`));
            await regulatoryPage(kind, 1);
            await click(previous(`regulatory-${kind}`));
            await regulatoryPage(kind, 0);
          }
        }
        assert.equal(
          await evaluate(cdp, "window.__historyPageToken"),
          token,
          "History navigation reloaded the document",
        );
        assert.deepEqual(
          requests.slice(start).filter((r) => r.method !== "GET"),
          initializationWrites,
          "History navigation called a mutation after entry",
        );
        assert.equal(
          requests
            .slice(start)
            .filter(
              (r) =>
                r.path.includes("/history/versions") &&
                r.query.includes(encodeURIComponent("versions:0")),
            ).length > 0,
          true,
          "Back did not preserve the original first cursor",
        );
        if (
          locale === "en-CH" &&
          width === 390 &&
          role === "organization_admin"
        ) {
          await writeFile(
            join(root, "test-results/document-history-mobile.png"),
            Buffer.from(
              (await cdp.send("Page.captureScreenshot", { format: "png" }))
                .data,
              "base64",
            ),
          );
        }
      }
  // Uncached navigation failure, retry of the same page and visible loading on the actual UI.
  await cdp.send("Page.navigate", {
    url: `${base}/laws/history-law?locale=en-CH`,
  });
  await historyPage("versions", 0);
  fail = true;
  hold = true;
  await click(next("versions"));
  await waitFor(
    () => Promise.resolve(!!releaseHeld),
    "Held request not issued",
  );
  await check("en-CH-loading");
  releaseHeld();
  releaseHeld = null;
  await waitFor(
    () => visible(`${controls("versions")} [role=alert]`),
    "Missing page error",
  );
  await check("en-CH-error");
  await click(`${controls("versions")} button:nth-child(3)`);
  await historyPage("versions", 1);
  await check("en-CH-recovered");
  // Timeline retains the last readable page while a request is pending or fails.
  const kind = "timeline",
    nav = controls("regulatory-timeline");
  await click("[data-timeline-kind=timeline]");
  await regulatoryPage(kind, 0);
  hold = true;
  fail = true;
  await click(next("regulatory-timeline"));
  await waitFor(
    () => Promise.resolve(!!releaseHeld),
    "Timeline request was not held",
  );
  await regulatoryPage(kind, 0);
  await check("timeline-loading-retained", "history-regulatory-timeline");
  releaseHeld();
  releaseHeld = null;
  await waitFor(() => visible(`${nav} [role=alert]`), "Missing timeline error");
  await regulatoryPage(kind, 0);
  await check("timeline-error-retained", "history-regulatory-timeline");
  await click(`${nav} button:nth-child(3)`);
  await regulatoryPage(kind, 1);
  await check("timeline-recovered", "history-regulatory-timeline");
  await click("[data-timeline-kind=expressions]");
  await regulatoryPage("expressions", 0);
  await click("[data-timeline-kind=timeline]");
  await regulatoryPage(kind, 1);
  await click(`${nav} button:last-child`);
  await regulatoryPage(kind, 0);
  emptyTimeline = true;
  await cdp.send("Page.navigate", {
    url: `${base}/laws/history-law?locale=en-CH`,
  });
  await waitFor(
    () =>
      evaluate(
        cdp,
        "document.querySelector('[data-timeline-rows=timeline]')?.children.length===0",
      ),
    "Empty timeline missing",
  );
  for (const section of Object.keys(timelineRecords)) {
    await click(`[data-timeline-kind=${section}]`);
    await check(`timeline-empty-${section}`, `history-regulatory-${section}`);
    assert.equal(
      await evaluate(
        cdp,
        `document.querySelector(${JSON.stringify(next(`regulatory-${section}`))}).disabled`,
      ),
      true,
    );
  }
  assert.deepEqual(exceptions, []);
  audit.finish(141);
  console.log(
    "History journeys: five locales, mobile/desktop, admin/viewer, complete pages, pinned selection/current version, keyboard/focus, error/retry, loading and no history-triggered mutations; disabled companion sends no entry requests; synthetic APIs only.",
  );
} catch (error) {
  console.error({
    locale,
    role,
    requests: requests.slice(-12),
    exceptions,
    text: cdp
      ? await evaluate(cdp, "document.body.innerText.slice(-1800)").catch(
          () => null,
        )
      : null,
  });
  throw error;
} finally {
  releaseHeld?.();
  cdp?.close();
  for (const child of [browser, server]) {
    const ended = new Promise((r) => child.once("exit", r));
    child.kill();
    await Promise.race([ended, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-document-history-browser-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
