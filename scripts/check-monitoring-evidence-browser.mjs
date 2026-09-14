// Shared evidence UI on three real business readers. Native nine-domain API
// source ingestion/rights tests are separate; browser responses here are synthetic.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { monitoringEvidenceCopy } from "../apps/web/lib/monitoring-evidence-copy.ts";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";

const root = resolve(import.meta.dirname, "..");
const fixtures = JSON.parse(
  await readFile(
    join(root, ".tmp/business-item-browser-fixtures.json"),
    "utf8",
  ),
);
const chrome = [
  process.env.CHROME_BIN,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
]
  .filter(Boolean)
  .find(existsSync);
assert.ok(chrome);
const socket = createServer();
await new Promise((r) => socket.listen(0, "127.0.0.1", r));
const port = socket.address().port;
await new Promise((r) => socket.close(r));
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-evidence-ask-"));
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
const routes = {
  tenders: "tender-watch",
  ip: "trademark-watch",
  auctions: "auction-watch",
};
const panel = "[data-monitoring-evidence-ask]";
const audit = new AccessibilityAudit("monitoring-evidence-ask");
let cdp,
  domain = "tenders",
  locale = "en-CH",
  state,
  nav = 0,
  mode = "ready",
  role = "organization_admin",
  held;
const requests = [],
  errors = [];
async function wait(check, message) {
  for (let i = 0; i < 250; i++) {
    if (
      await Promise.resolve()
        .then(check)
        .catch(() => false)
    )
      return;
    await sleep(100);
  }
  throw Error(message);
}
const text = () =>
  evaluate(
    cdp,
    `document.querySelector(${JSON.stringify(panel)})?.innerText||''`,
  );
async function click(selector) {
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
        `(()=>{const el=[...document.querySelectorAll(${JSON.stringify(panel + " button")})].find(e=>e.textContent.trim()===${JSON.stringify(label)}&&!e.disabled);if(!el)return false;el.click();return true;})()`,
      ),
    "Missing button: " + label,
  );
}
async function response(id, body, code = 200) {
  await cdp
    .send("Fetch.fulfillRequest", {
      requestId: id,
      responseCode: code,
      responseHeaders: [
        { name: "Content-Type", value: "application/json" },
        { name: "Cache-Control", value: "no-store" },
      ],
      body: Buffer.from(JSON.stringify(body)).toString("base64"),
    })
    .catch(() => {});
}
async function navigate() {
  await evaluate(cdp, "window.__evidencePrevious=true");
  const suffix =
    domain === "tenders"
      ? `&dossier=${state.detail.id}`
      : domain === "ip"
        ? `&candidate=${state.detail.id}`
        : "";
  await cdp.send("Page.navigate", {
    url: `${base}/${routes[domain]}?monitor=${state.monitor.id}${suffix}&qa=${++nav}`,
  });
  await wait(
    () =>
      evaluate(
        cdp,
        `!window.__evidencePrevious&&document.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector(${JSON.stringify(panel)})`,
      ),
    "Reader did not open",
  );
}
async function open() {
  await click(panel + " > summary");
  await ready();
}
async function ready() {
  await wait(
    async () =>
      !(await text()).includes(monitoringEvidenceCopy[locale].loading) &&
      (await text()).includes(monitoringEvidenceCopy[locale].refresh),
    "Evidence did not settle",
  );
}
async function question(value) {
  await evaluate(
    cdp,
    `(()=>{const el=document.querySelector(${JSON.stringify(panel + " textarea")});Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(el,${JSON.stringify(value)});el.dispatchEvent(new Event('input',{bubbles:true}));})()`,
  );
}
async function check(name, required = panel) {
  await evaluate(
    cdp,
    "Promise.all(document.getAnimations().filter(a=>a.effect?.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})))",
  );
  assert.ok(
    await evaluate(cdp, "document.documentElement.scrollWidth<=innerWidth+1"),
  );
  await audit.check(cdp, name, required);
}
function packet(body) {
  return {
    binding: "a".repeat(64),
    reference_url:
      "/api/monitoring-centre/evidence/reference?" +
      new URLSearchParams({
        domain,
        monitor_id: state.monitor.id,
        item_id: state.detail.id,
        locale,
        expected_binding: "a".repeat(64),
      }),
    locale,
    record: {
      domain,
      monitor_id: state.monitor.id,
      item_id: mode === "wrong" ? "other" : state.detail.id,
      sequence: null,
    },
    extracts:
      body.question === "unmatched"
        ? []
        : [
            {
              pointer: "/facts/title",
              quote: `Original ${domain} text <script>window.evidenceInjected=true</script>`,
              context: { language: "en" },
            },
            {
              pointer: "/facts/instructions",
              quote: "Exact official instruction.\nPreserved second line.",
            },
            {
              pointer: "/facts/value",
              quote: "250",
              context: { currency: "CHF" },
            },
          ],
    has_matches: body.question !== "unmatched",
    more_matches: false,
    newer_available: mode === "historical",
    current_configuration: mode !== "historical",
    checked_at: "2026-09-14T15:00:00Z",
  };
}
try {
  await wait(async () => (await fetch(base)).ok, "Next did not start");
  let debug;
  await wait(async () => {
    debug = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split(
      "\n",
    )[0];
    return !!debug;
  }, "Chrome did not start");
  const target = await fetch(`http://127.0.0.1:${debug}/json/new?about:blank`, {
    method: "PUT",
  }).then((r) => r.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    errors.push(
      exceptionDetails.exception?.description || exceptionDetails.text,
    ),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    try {
      const url = new URL(request.url),
        path = url.pathname,
        body = request.postData ? JSON.parse(request.postData) : null;
      requests.push({ path, method: request.method, domain, mode });
      let data = {},
        code = 200;
      if (path === "/api/auth/session")
        data = {
          authenticated: true,
          user: {
            id: "owner",
            name: "Owner",
            email: "fixture@example.invalid",
            locale,
          },
          organization: { id: "org-a", name: "Synthetic workspace" },
          role,
          platform_admin: false,
          onboarding_required: false,
        };
      else if (path === "/api/health")
        data = {
          status: "ok",
          database: "synthetic",
          apertus: { configured: false },
          firecrawl: { configured: false },
        };
      else if (path === "/api/assistant/context")
        data = { context: { entity: null }, persona: { quip_allowed: false } };
      else if (path === "/api/jobs") data = [];
      else if (path === "/api/monitoring-centre/evidence/ask") {
        assert.equal(body.domain, domain);
        assert.equal(body.monitor_id, state.monitor.id);
        assert.equal(body.item_id, state.detail.id);
        assert.equal(body.locale, locale);
        assert.equal(request.method, "POST");
        if (body.question) assert.equal(body.expected_binding, "a".repeat(64));
        if (mode === "denied" || mode === "conflict") {
          code = mode === "denied" ? 404 : 409;
          data = {
            code:
              mode === "denied"
                ? "monitoring_evidence_not_found"
                : "monitoring_evidence_changed",
          };
        } else data = packet(body);
        if (mode === "delayed") {
          held = { requestId, data };
          return;
        }
      } else if (path.startsWith(`/api/${routes[domain]}`)) {
        if (path.endsWith("/capabilities"))
          data = {
            drafts_available: true,
            public_source_available: true,
            lookback_days: 90,
            cycle_hours: 6,
          };
        else if (path.endsWith("/source-status"))
          data = {
            state: "permission_required",
            traversal: null,
            source: null,
          };
        else if (path.endsWith(`/monitors/${state.monitor.id}`))
          data = state.monitor;
        else if (path.endsWith("/monitors"))
          data = { items: [state.monitor], next_cursor: null };
        else if (path.endsWith(`/${state.detail.id}`)) data = state.detail;
        else if (
          ["/dossiers", "/candidates", "/items"].some((end) =>
            path.endsWith(end),
          )
        )
          data = {
            ...state.page,
            items: state.page.items.map((item) => ({
              ...item,
              ...state.detail,
            })),
          };
        else
          data = {
            items: [],
            next_cursor: null,
            health: "waiting",
            coverage_verified: false,
          };
      }
      await response(requestId, data, code);
    } catch (error) {
      errors.push(String(error));
      await response(requestId, { code: "fixture_failed" }, 500);
    }
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: "*/api/*", requestStage: "Request" }],
  });
  await cdp.send("Network.setCookie", {
    name: "helvetic_lens_csrf",
    value: "synthetic",
    url: base,
  });
  for (const kind of Object.keys(routes))
    for (const language of Object.keys(monitoringEvidenceCopy))
      for (const width of [390, 1440]) {
        domain = kind;
        locale = language;
        state = structuredClone(fixtures[kind]);
        mode = "ready";
        role = "organization_admin";
        await cdp.send("Emulation.setDeviceMetricsOverride", {
          width,
          height: 1000,
          deviceScaleFactor: 1,
          mobile: width === 390,
        });
        await navigate();
        await open();
        assert.ok((await text()).includes(`Original ${domain} text <script>`));
        assert.ok((await text()).includes("CHF"));
        await click(panel + " li details > summary");
        const cited = new URL(
          await evaluate(
            cdp,
            `document.querySelector(${JSON.stringify(panel + " li details a")}).href`,
          ),
        );
        assert.equal(cited.origin, base);
        assert.equal(
          cited.pathname,
          "/api/monitoring-centre/evidence/reference",
        );
        assert.equal(cited.searchParams.get("domain"), domain);
        assert.equal(cited.searchParams.get("monitor_id"), state.monitor.id);
        assert.equal(cited.searchParams.get("item_id"), state.detail.id);
        assert.equal(
          cited.searchParams.get("expected_binding"),
          "a".repeat(64),
        );
        assert.equal(await evaluate(cdp, "!!window.evidenceInjected"), false);
        await check(`${domain}-${locale}-${width}-extracts`);
        await question("unmatched");
        await button(monitoringEvidenceCopy[locale].search);
        await ready();
        assert.ok(
          (await text()).includes(monitoringEvidenceCopy[locale].empty),
        );
        await check(`${domain}-${locale}-${width}-no-match`);
        if (domain === "tenders" && locale === "en-CH") {
          await button(monitoringEvidenceCopy[locale].refresh);
          await ready();
          assert.equal(
            await evaluate(
              cdp,
              `document.querySelector(${JSON.stringify(panel + " textarea")}).value`,
            ),
            "",
          );
          await evaluate(
            cdp,
            `document.querySelector(${JSON.stringify(panel)}).scrollIntoView({block:'start'})`,
          );
          await writeFile(
            join(root, `test-results/monitoring-evidence-${width}.png`),
            Buffer.from(
              (await cdp.send("Page.captureScreenshot", { format: "png" }))
                .data,
              "base64",
            ),
          );
        }
      }
  locale = "en-CH";
  for (const kind of Object.keys(routes)) {
    domain = kind;
    state = structuredClone(fixtures[kind]);
    mode = "ready";
    await navigate();
    await open();
    for (const scenario of ["conflict", "denied", "wrong"]) {
      mode = scenario;
      await question("source");
      await button(monitoringEvidenceCopy[locale].search);
      await ready();
      assert.ok((await text()).includes(monitoringEvidenceCopy[locale].failed));
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelectorAll(${JSON.stringify(panel + " blockquote")}).length`,
        ),
        0,
      );
      await check(`${domain}-${scenario}`);
      mode = "ready";
      await button(monitoringEvidenceCopy[locale].refresh);
      await ready();
    }
    mode = "historical";
    await button(monitoringEvidenceCopy[locale].refresh);
    await ready();
    assert.ok(
      (await text()).includes(monitoringEvidenceCopy[locale].historical),
    );
    await check(`${domain}-historical`);
    mode = "delayed";
    held = null;
    await button(monitoringEvidenceCopy[locale].refresh);
    await wait(() => held, "No pending evidence request");
    await evaluate(
      cdp,
      "window.dispatchEvent(new PageTransitionEvent('pagehide'))",
    );
    await response(held.requestId, held.data);
    await sleep(100);
    assert.equal(
      await evaluate(
        cdp,
        `document.querySelectorAll(${JSON.stringify(panel + " blockquote")}).length`,
      ),
      0,
    );
    await check(`${domain}-late-pagehide`, "main");
    mode = "ready";
    role = "viewer";
    await navigate();
    await open();
    await check(`${domain}-viewer`);
    await button(monitoringEvidenceCopy[locale].original);
    await wait(
      () =>
        evaluate(
          cdp,
          `!document.querySelector(${JSON.stringify(panel)}).open&&!document.querySelector(${JSON.stringify(panel + " textarea")})`,
        ),
      "Close retained evidence",
    );
    await check(`${domain}-closed`);
    role = "organization_admin";
  }
  assert.deepEqual(errors, []);
  assert.equal(
    requests.filter(
      (r) =>
        r.method !== "GET" &&
        !r.path.startsWith("/api/assistant/") &&
        r.path !== "/api/monitoring-centre/evidence/ask",
    ).length,
    0,
  );
  audit.finish(81);
  await writeFile(
    join(root, "test-results/monitoring-evidence-requests.json"),
    JSON.stringify(requests, null, 2),
  );
  console.log(
    "Evidence panel: 81 built-browser accessibility checkpoints; five locales, two widths, three native business readers, no matches, stale/wrong contexts, withdrawn access, viewer, close and late pagehide. Synthetic browser evidence; real nine-domain readers are covered separately.",
  );
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const ended = new Promise((r) => child.once("exit", r));
    child.kill();
    await Promise.race([ended, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-evidence-ask-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 8,
    retryDelay: 250,
  });
}
