// Compiled native editors with synthetic saved configurations and model replies.
// API tests separately enforce real capability, input, budget and membership gates.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { monitoringConfigurationCopy as copy } from "../apps/web/lib/monitoring-configuration-copy.ts";
import { pollenEditCopy } from "../apps/web/lib/pollen-edit-copy.ts";
import { riverCopy } from "../apps/web/lib/river-copy.ts";
import { roadCopy } from "../apps/web/lib/road-copy.ts";
import { commuteCopy } from "../apps/web/lib/commute-copy.ts";
import { trademarkCopy } from "../apps/web/lib/trademark-copy.ts";
import { auctionCopy } from "../apps/web/lib/auction-copy.ts";

const root = resolve(import.meta.dirname, ".."),
  configs = JSON.parse(
    await readFile(
      join(root, "scripts/fixtures/monitoring-configurations.json"),
      "utf8",
    ),
  );
const routes = {
  pollen: "pollen-watch",
  river: "river-watch",
  air: "air-watch",
  warnings: "hazard-watch",
  commute: "commute-watch",
  traffic: "road-watch",
  tenders: "tender-watch",
  ip: "trademark-watch",
  auctions: "auction-watch",
};
const editCopy = {
  pollen: pollenEditCopy,
  river: riverCopy,
  air: riverCopy,
  warnings: roadCopy,
  commute: commuteCopy,
  traffic: roadCopy,
  tenders: riverCopy,
  ip: trademarkCopy,
  auctions: auctionCopy,
};
const chrome = [
  process.env.CHROME_BIN,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/google-chrome",
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-configuration-check-"));
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
const audit = new AccessibilityAudit("monitoring-configuration-drafts"),
  id = "00000000-0000-4000-8000-000000000011",
  panel = "[data-configuration-draft]";
let cdp,
  locale = "en-CH",
  domain = "river",
  mode = "ready",
  role = "organization_admin",
  held,
  checks = 0;
const requests = [],
  errors = [];
async function wait(fn, label) {
  for (let n = 0; n < 200; n++) {
    if (
      await Promise.resolve()
        .then(fn)
        .catch(() => false)
    )
      return;
    await sleep(100);
  }
  throw Error(label);
}
const text = () => evaluate(cdp, "document.body.innerText");
async function button(label, scope = "main") {
  await wait(
    () =>
      evaluate(
        cdp,
        `(()=>{const b=[...document.querySelectorAll(${JSON.stringify(scope + " button")})].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled);if(!b)return false;b.click();return true;})()`,
      ),
    "Missing button " + label,
  );
}
async function fill(selector, value) {
  await evaluate(
    cdp,
    `(()=>{const e=document.querySelector(${JSON.stringify(selector)});const p=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:e.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));})()`,
  );
}
async function response(requestId, data, code = 200) {
  await cdp
    .send("Fetch.fulfillRequest", {
      requestId,
      responseCode: code,
      responseHeaders: [{ name: "Content-Type", value: "application/json" }],
      body: Buffer.from(JSON.stringify(data)).toString("base64"),
    })
    .catch(() => {});
}
function monitor() {
  return {
    id,
    owner_user_id: "owner",
    scope: "private",
    version: 1,
    revision: 1,
    runtime_version: 0,
    configuration_hash: "a".repeat(64),
    status: "draft",
    health: "waiting",
    state: { coverage: {} },
    configuration: configs[domain],
    last_poll_at: null,
    last_check_at: null,
    next_check_at: null,
    paused_on: null,
    reference_labels: [],
  };
}
async function navigate() {
  await evaluate(cdp, "window.__oldConfigurationDocument=true");
  await cdp.send("Page.navigate", {
    url: `${base}/monitoring/settings?category=${domain}&monitor=${id}&qa=${Date.now()}${domain === "pollen" ? "#draft=" + id : ""}`,
  });
  await wait(
    () =>
      evaluate(
        cdp,
        `!window.__oldConfigurationDocument&&document.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector('[data-native-settings]')`,
      ),
    "Page unavailable",
  );
  await button(editCopy[domain][locale].edit, "[data-native-settings]");
  await wait(
    () => evaluate(cdp, `!!document.querySelector('${panel}')`),
    "Editor did not open",
  );
  await evaluate(cdp, `document.querySelector('${panel} > summary').click()`);
}
async function check(name) {
  assert.ok(
    await evaluate(cdp, "document.documentElement.scrollWidth<=innerWidth+1"),
    "Overflow",
  );
  await audit.check(cdp, name, panel);
  checks++;
}
async function ask() {
  await fill(
    panel + " textarea",
    "Rename this monitor to Proposed configuration",
  );
  await button(copy[locale].generate, panel);
}
try {
  await wait(async () => (await fetch(base)).ok, "Next unavailable");
  let debug;
  await wait(async () => {
    debug = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split(
      "\n",
    )[0];
    return !!debug;
  }, "Chrome unavailable");
  let target;
  await wait(async () => {
    target = await fetch(`http://127.0.0.1:${debug}/json/new?about:blank`, {
      method: "PUT",
    }).then((r) => r.json());
    return !!target.webSocketDebuggerUrl;
  }, "Debugger unavailable");
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    errors.push(
      exceptionDetails.exception?.description || exceptionDetails.text,
    ),
  );
  cdp.on("Page.javascriptDialogOpening", () =>
    cdp.send("Page.handleJavaScriptDialog", { accept: true }),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    try {
      const path = new URL(request.url).pathname,
        body = request.postData ? JSON.parse(request.postData) : null;
      requests.push({ path, method: request.method, body, domain });
      let data = {},
        code = 200;
      const native =
        domain === "pollen"
          ? "/api/monitoring-subjects"
          : `/api/${routes[domain]}`;
      if (path === "/api/auth/session")
        data = {
          authenticated: true,
          user: {
            id: "owner",
            name: "Draft QA",
            email: "draft@example.invalid",
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
      else if (path === "/api/monitoring-settings")
        data = { can_configure_connectors: false, items: [] };
      else if (path === "/api/jobs") data = [];
      else if (path === "/api/monitoring-centre/configuration/draft") {
        assert.equal(body.domain, domain);
        assert.equal(body.locale, locale);
        // Native editor starts from the saved fixture and may omit schema defaults.
        assert.equal(body.configuration.station_id, configs[domain].station_id);
        const configuration = {
          ...body.configuration,
          ...(domain === "pollen"
            ? { timezone: "Europe/Berlin" }
            : { name: "Proposed configuration" }),
        };
        data = {
          domain,
          locale,
          request_key: mode === "wrong" ? "other" : body.request_key,
          input_binding: "a".repeat(64),
          capability_binding: "b".repeat(64),
          prompt_version: "monitoring-configuration-draft-v1",
          configuration,
          changed_fields: [domain === "pollen" ? "timezone" : "name"],
        };
        if (mode === "offline") {
          code = 503;
          data = { code: "configuration_draft_unavailable" };
        }
        if (mode === "held") {
          held = { requestId, data };
          return;
        }
      } else if (path.startsWith(native)) {
        if (domain === "pollen" && path.endsWith("/state"))
          data = {
            ...monitor(),
            runtime: {
              version: 0,
              run_id: null,
              health: "not_started",
              email_consent: false,
              muted: false,
            },
            start_available: false,
            blocking_reasons: [],
            coverage: [],
            current: [],
          };
        else if (path.endsWith("/capabilities"))
          data = {
            drafts_available: true,
            public_source_available: false,
            start_available: false,
          };
        else if (path.endsWith("/source-status")) {
          code = 503;
          data = { code: "source_unavailable" };
        } else if (
          path ===
          (domain === "pollen" ? native + "/" + id : native + "/monitors/" + id)
        )
          data = monitor();
        else if (path === (domain === "pollen" ? native : native + "/monitors"))
          data = { items: [monitor()], next_cursor: null };
        else if (path.endsWith("/stations"))
          data = {
            stations: [
              {
                id: configs[domain].station_id,
                name: "Synthetic Basel",
                waterbody: "Rhine",
                area: "Basel",
                source_url: "https://example.invalid/source",
              },
            ],
          };
        else if (path.endsWith("/mutes"))
          data = { monitor_id: id, version: 1, muted_hazards: [] };
        else if (
          /\/(history|changes|revisions|dossiers|candidates|items|events|corridors|catalog|activity|measurements)$/.test(
            path,
          )
        )
          data = {
            items: [],
            next_cursor: null,
            next_before: null,
            next_before_revision: null,
            next: null,
            coverage: {},
            states: {},
            editions: {},
            health: "waiting",
          };
        else {
          code = 503;
          data = { code: "unavailable" };
        }
      } else {
        code = 503;
        data = { code: "unavailable" };
      }
      await response(requestId, data, code);
    } catch (error) {
      errors.push(String(error));
      await response(requestId, { code: "fixture_failed" }, 500);
    }
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }],
  });
  await cdp.send("Network.setCookie", {
    name: "helvetic_lens_csrf",
    value: "synthetic",
    url: base,
  });
  for (const category of process.env.CONFIGURATION_CHECK_DOMAIN
    ? [process.env.CONFIGURATION_CHECK_DOMAIN]
    : Object.keys(routes))
    for (const language of process.env.CONFIGURATION_CHECK_LOCALE
      ? [process.env.CONFIGURATION_CHECK_LOCALE]
      : Object.keys(copy))
      for (const width of [390, 1440]) {
        domain = category;
        locale = language;
        mode = "ready";
        await cdp.send("Emulation.setDeviceMetricsOverride", {
          width,
          height: 1000,
          deviceScaleFactor: 1,
          mobile: false,
        });
        await navigate();
        await ask();
        await wait(
          () => text().then((t) => t.includes(copy[locale].ready)),
          "Proposal missing",
        );
        assert.ok(
          !(await evaluate(
            cdp,
            "[...document.querySelectorAll('[data-native-settings] input')].some(i=>i.value==='Proposed configuration')",
          )),
        );
        await check(`draft-${domain}-${locale}-${width}`);
        await button(copy[locale].apply, panel);
        await wait(
          () =>
            evaluate(
              cdp,
              domain === "pollen"
                ? "document.querySelector('input[name=pollen-timezone]')?.value==='Europe/Berlin'"
                : "[...document.querySelectorAll('[data-native-settings] input')].some(i=>i.value==='Proposed configuration')",
            ),
          "Draft not loaded into native fields",
        );
        assert.equal(
          requests.filter(
            (r) =>
              r.method !== "GET" &&
              !r.path.startsWith("/api/assistant/") &&
              r.path !== "/api/monitoring-centre/configuration/draft",
          ).length,
          0,
          "Proposal persisted a monitor",
        );
        if (locale === "en-CH" && domain === "warnings")
          await writeFile(
            join(root, `test-results/configuration-draft-${width}.png`),
            Buffer.from(
              (await cdp.send("Page.captureScreenshot", { format: "png" }))
                .data,
              "base64",
            ),
          );
      }
  domain = "river";
  locale = "en-CH";
  for (const state of ["offline", "wrong"]) {
    mode = state;
    await navigate();
    await ask();
    await wait(
      () => text().then((t) => t.includes(copy[locale].unavailable)),
      "Manual fallback missing",
    );
    await check(state);
  }
  mode = "held";
  await navigate();
  await ask();
  await wait(() => !!held, "Request not held");
  await fill(
    '[data-native-settings] form input[maxlength="100"]',
    "Manual replacement",
  );
  await response(held.requestId, held.data);
  held = null;
  await sleep(200);
  assert.ok(!(await text().then((t) => t.includes(copy[locale].ready))));
  await check("late-response-discarded");
  domain = "warnings";
  mode = "ready";
  await navigate();
  await fill("[data-native-settings] form select:not([name])", "point");
  await fill("input[name=latitude]", "47.56");
  await fill("input[name=longitude]", "7.59");
  await fill("input[name=radius]", "5");
  await evaluate(cdp, `document.querySelector('${panel} > summary').click()`);
  await ask();
  await wait(
    () => text().then((t) => t.includes(copy[locale].ready)),
    "Point proposal missing",
  );
  await button(copy[locale].apply, panel);
  await wait(
    () =>
      evaluate(
        cdp,
        "document.querySelector('input[name=name]')?.value==='Proposed configuration'",
      ),
    "Point draft missing",
  );
  assert.ok(
    await evaluate(
      cdp,
      "document.activeElement===document.querySelector('input[name=name]')",
    ),
    "Focus did not move into the native editor",
  );
  await button(roadCopy[locale].preview, "[data-native-settings] form");
  await wait(
    () => requests.some((r) => r.path === "/api/hazard-watch/preview"),
    "Native preview missing",
  );
  const previewRequest = requests.findLast(
    (r) => r.path === "/api/hazard-watch/preview",
  );
  assert.deepEqual(previewRequest.body.configuration.location, {
    kind: "point",
    country: "CH",
    canton: "BS",
    latitude: 47.56,
    longitude: 7.59,
    radius_km: 5,
  });
  await check("point-location-native-preview-after-draft");
  assert.deepEqual(errors, []);
  audit.finish(checks);
  console.log(
    `Configuration drafts: ${checks} browser/axe checks; nine saved native editors, five locales, two widths; no save on apply.`,
  );
} catch (error) {
  if (cdp) {
    console.error(
      "Overflow details",
      await evaluate(
        cdp,
        "[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>({tag:e.tagName,class:e.className,width:e.getBoundingClientRect().width,text:e.textContent.slice(0,80)})).slice(-20)",
      ).catch(() => []),
    );
    await writeFile(
      join(root, "test-results/configuration-draft-failure.png"),
      Buffer.from(
        (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
        "base64",
      ),
    );
  }
  console.error({
    domain,
    locale,
    mode,
    errors,
    recent: requests.slice(-7),
    text: cdp ? await text().catch(() => "") : "",
  });
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const done = new Promise((r) => child.once("exit", r));
    child.kill();
    await Promise.race([done, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-configuration-check-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
