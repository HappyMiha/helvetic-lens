// Built application, synthetic identities/configurations, no source access or email.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { businessMonitorCopy } from "../apps/web/lib/business-monitor-copy.ts";
import { businessHandoverCopy } from "../apps/web/lib/business-handover-copy.ts";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";

const root = resolve(import.meta.dirname, "..");
const visual = process.argv.includes("--visual-check");
const chrome = [
  process.env.CHROME_BIN,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
]
  .filter(Boolean)
  .find(existsSync);
assert.ok(chrome);
const reserve = createServer();
await new Promise((done) => reserve.listen(0, "127.0.0.1", done));
const port = reserve.address().port;
await new Promise((done) => reserve.close(done));
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-business-scope-"));
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
const id = "00000000-0000-4000-8000-000000000001";
const owner = "00000000-0000-4000-8000-000000000011",
  peer = "00000000-0000-4000-8000-000000000012";
const routes = {
  tenders: "tender-watch",
  ip: "trademark-watch",
  auctions: "auction-watch",
};
const configs = {
  tenders: {
    template_id: "tender-watch",
    template_version: 1,
    name: "Shared Tender QA",
    company_name: "Example GmbH",
    capabilities: [{ name: "Software", phrases: ["software development"] }],
    cpv_codes: [],
    cpv_include_descendants: true,
    contract_cantons: [],
    offer_languages: [],
    authority_levels: [],
    excluded_phrases: [],
    excluded_cpv_codes: [],
    excluded_contract_types: [],
    minimum_contract_chf: null,
    maximum_contract_chf: null,
    available_reference_count: null,
    certificates: null,
    minimum_semantic_score: null,
  },
  ip: {
    template_id: "trademark-watch",
    template_version: 1,
    jurisdiction: "CH",
    name: "Shared IP QA",
    brands: [
      {
        key: "almora",
        name: "ALMORA",
        language: "en",
        exact_name: true,
        similar_names: true,
        word_variants: [],
        owners_of_interest: [],
        relevant_classes: [9, 42],
        goods_services: [
          {
            name: "Software",
            phrases: [{ language: "en", text: "computer software" }],
          },
        ],
      },
    ],
  },
  auctions: {
    schema_version: 1,
    name: "Shared Auction QA",
    categories: ["vehicles"],
    cantons: ["TI"],
    locations: [],
    keywords: [],
    brands: [],
    maximum_price_chf_cents: 1200000,
    budget_price_kind: "current_bid",
    notify: {
      new_match: true,
      price_above_limit: true,
      every_bid_change: false,
      deadline_change: true,
      documents_change: true,
      conditions_change: true,
      cancellation: true,
      ending_soon_hours: null,
    },
  },
};
let cdp,
  domain = "tenders",
  locale = "en-CH",
  user = owner,
  role = "organization_admin",
  organization = "workspace-a",
  row,
  history,
  nav = 0,
  conflict = false,
  denied = false,
  delayed = false,
  held;
const requests = [],
  mutations = [],
  errors = [],
  audit = new AccessibilityAudit(
    visual ? "business-monitor-visual" : "business-monitor-access",
  );
function reset(kind) {
  domain = kind;
  user = owner;
  role = "organization_admin";
  organization = "workspace-a";
  conflict = false;
  denied = false;
  delayed = false;
  history = [];
  row = {
    id,
    configuration: structuredClone(configs[kind]),
    visibility: "private",
    owner_user_id: owner,
    responsible_user_id: null,
    status: "active",
    version: 1,
    revision: 1,
    health: "waiting",
    last_poll_at: null,
    next_poll_at: null,
  };
}
const person = (identifier) =>
  identifier
    ? {
        id: identifier,
        name:
          identifier === owner ? "Monitor creator" : "Responsible colleague",
        available: true,
      }
    : null;
function scope(before) {
  const items = history.filter(
    (event) => !before || event.version < Number(before),
  );
  return {
    monitor_version: row.version,
    visibility: row.visibility,
    creator: person(row.owner_user_id),
    responsible: person(row.responsible_user_id),
    can_change_scope: user === row.owner_user_id,
    history: items.slice(0, 1),
    next_before_version: items.length > 1 ? items[0].version : null,
  };
}
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
async function click(selector) {
  await wait(
    () =>
      evaluate(
        cdp,
        `!!document.querySelector(${JSON.stringify(selector)})&&!document.querySelector(${JSON.stringify(selector)}).disabled`,
      ),
    `Missing ${selector}`,
  );
  await evaluate(
    cdp,
    `document.querySelector(${JSON.stringify(selector)}).click()`,
  );
}
async function value(selector, next) {
  await evaluate(
    cdp,
    `(()=>{const el=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(el,${JSON.stringify(next)});el.dispatchEvent(new Event('change',{bubbles:true}));})()`,
  );
}
async function response(requestId, body, code = 200) {
  await cdp
    .send("Fetch.fulfillRequest", {
      requestId,
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
  await evaluate(cdp, "window.__businessPreviousPage = true");
  await cdp.send("Page.navigate", {
    url: base + `/${routes[domain]}?monitor=${id}&locale=${locale}&qa=${++nav}`,
  });
  await wait(
    () =>
      evaluate(
        cdp,
        `!window.__businessPreviousPage&&document.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector('[data-business-access]')`,
      ),
    "Native monitor did not load",
  );
}
async function open() {
  await click("[data-business-access] summary");
  await wait(
    () =>
      evaluate(
        cdp,
        `document.querySelector('[data-business-access]')?.innerText.includes('Monitor creator')`,
      ),
    "Access settings missing",
  );
}
async function check(name) {
  await evaluate(
    cdp,
    "Promise.all(document.getAnimations().filter(a=>a.effect?.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})))",
  );
  assert.ok(
    await evaluate(cdp, "document.documentElement.scrollWidth<=innerWidth+1"),
  );
  await audit.check(cdp, name, "[data-business-access]");
}
const select = "[data-business-access] select";
async function share() {
  await value(select, "workspace");
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelector('[data-business-access] button[type=submit]').disabled",
    ),
    true,
  );
  await evaluate(
    cdp,
    `(()=>{const el=document.querySelectorAll('[data-business-access] select')[1];Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(el,${JSON.stringify(peer)});el.dispatchEvent(new Event('change',{bubbles:true}));})()`,
  );
  await click("[data-business-access] input[type=checkbox]");
  await click("[data-business-access] button[type=submit]");
  await wait(() => row.version === 2, "Sharing did not save");
  assert.equal(row.status, "paused");
  assert.equal(row.responsible_user_id, peer);
}
try {
  reset(domain);
  await wait(async () => (await fetch(base)).ok, "Next did not start");
  let debugPort;
  await wait(async () => {
    debugPort = (
      await readFile(join(profile, "DevToolsActivePort"), "utf8")
    ).split("\n")[0];
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
    errors.push(
      exceptionDetails.exception?.description || exceptionDetails.text,
    ),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url),
      path = url.pathname,
      body = request.postData ? JSON.parse(request.postData) : null;
    requests.push({ path, method: request.method, user });
    let data = {},
      code = 200;
    if (path === "/api/auth/session")
      data = {
        authenticated: true,
        user: {
          id: user,
          name: "Scope QA",
          email: "fixture@example.invalid",
          locale,
        },
        organization: { id: organization, name: "Scope QA workspace" },
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
    else if (path.startsWith("/api/monitoring-centre/business")) {
      if (
        denied ||
        organization !== "workspace-a" ||
        (user !== owner && row.visibility !== "workspace")
      ) {
        code = 404;
        data = { code: "business_monitor_not_found" };
      } else if (path.endsWith("/members"))
        data = {
          items: [
            { id: owner, name: "Monitor creator" },
            { id: peer, name: "Responsible colleague" },
          ],
          next_cursor: null,
        };
      else if (path.endsWith("/handover") && request.method === "POST") {
        mutations.push({ domain, body, user });
        assert.deepEqual(body, {
          expected_version: row.version,
          successor_user_id: peer,
          confirmed: true,
        });
        assert.equal(user, row.owner_user_id);
        assert.equal(role, "organization_admin");
        assert.equal(row.visibility, "workspace");
        const previous = row.owner_user_id;
        row = {
          ...row,
          owner_user_id: peer,
          responsible_user_id: peer,
          status: "paused",
          version: row.version + 1,
        };
        history.unshift({
          version: row.version,
          action: "handover",
          actor: person(user),
          previous_owner: person(previous),
          owner: person(peer),
          scope: "workspace",
          responsible: person(peer),
          created_at: "2026-09-14T12:01:00Z",
        });
        data = scope();
      } else if (request.method === "PUT") {
        mutations.push({ domain, body, user });
        if (conflict) {
          code = 409;
          data = { code: "business_scope_changed" };
        } else {
          assert.equal(body.expected_version, row.version);
          assert.equal(role, "organization_admin");
          assert.equal(
            body.confirmed,
            row.visibility === "private" && body.visibility === "workspace"
              ? true
              : body.confirmed,
          );
          row = {
            ...row,
            version: row.version + 1,
            visibility: body.visibility,
            responsible_user_id: body.responsible_user_id,
            status: row.status === "active" ? "paused" : row.status,
          };
          history.unshift({
            version: row.version,
            actor: person(user),
            scope: row.visibility,
            responsible: person(row.responsible_user_id),
            created_at: "2026-09-14T12:00:00Z",
          });
          data = scope();
        }
      } else {
        data = scope(url.searchParams.get("before_version"));
        if (delayed) {
          held = { requestId, data };
          return;
        }
      }
    } else if (path.startsWith(`/api/${routes[domain]}`)) {
      if (
        denied ||
        organization !== "workspace-a" ||
        (user !== owner && row.visibility !== "workspace")
      ) {
        code = 404;
        data = { code: `${domain}_monitor_not_found` };
      } else if (path.endsWith("/capabilities"))
        data = {
          drafts_available: true,
          public_source_available: true,
          lookback_days: 90,
          cycle_hours: 6,
        };
      else if (path.endsWith("/source-status"))
        data = { state: "permission_required", traversal: null, source: null };
      else if (path.endsWith(`/monitors/${id}`)) data = row;
      else if (path.endsWith("/monitors"))
        data = { items: [row], next_cursor: null };
      else if (path.endsWith("/revisions"))
        data = {
          items: [{ revision: 1, configuration: row.configuration }],
          next_cursor: null,
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
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: "*/api/*", requestStage: "Request" }],
  });
  await cdp.send("Network.setCookie", {
    name: "helvetic_lens_csrf",
    value: "synthetic",
    url: base,
  });
  for (const kind of visual ? ["tenders"] : Object.keys(routes))
    for (const language of visual
      ? ["en-CH"]
      : Object.keys(businessMonitorCopy))
      for (const width of [390, 1440]) {
        reset(kind);
        locale = language;
        await cdp.send("Emulation.setDeviceMetricsOverride", {
          width,
          height: 1000,
          deviceScaleFactor: 1,
          mobile: width === 390,
        });
        await navigate();
        await open();
        await check(`${kind}-${language}-${width}-private`);
        await share();
        await navigate();
        await open();
        assert.ok(
          await evaluate(
            cdp,
            `document.querySelector('[data-business-access]').innerText.includes(${JSON.stringify(businessMonitorCopy[locale].workspace)})`,
          ),
        );
        await check(`${kind}-${language}-${width}-shared`);
        if (visual) {
          await evaluate(
            cdp,
            "document.querySelector('[data-business-access]').scrollIntoView({block:'start'})",
          );
          await writeFile(
            join(root, `test-results/business-monitor-access-${width}.png`),
            Buffer.from(
              (await cdp.send("Page.captureScreenshot", { format: "png" }))
                .data,
              "base64",
            ),
          );
        }
        if (!visual) {
          assert.equal(
            await evaluate(
              cdp,
              "document.querySelector('[data-business-handover] select').value",
            ),
            "",
          );
          assert.ok(
            await evaluate(
              cdp,
              "document.querySelector('[data-business-handover] button[type=submit]').disabled",
            ),
          );
          await value("[data-business-handover] select", peer);
          assert.ok(
            await evaluate(
              cdp,
              "document.querySelector('[data-business-handover] button[type=submit]').disabled",
            ),
          );
          await click("[data-business-handover] input[type=checkbox]");
          await check(`${kind}-${language}-${width}-handover`);
          await click("[data-business-handover] button[type=submit]");
          await wait(() => row.owner_user_id === peer, "Handover did not save");
          await navigate();
          await open();
          assert.equal(
            await evaluate(
              cdp,
              "!!document.querySelector('[data-business-handover]')",
            ),
            false,
          );
          assert.ok(
            await evaluate(
              cdp,
              `document.querySelector('[data-business-access]').innerText.includes(${JSON.stringify(businessHandoverCopy[locale].previous)})`,
            ),
          );
        }
      }
  locale = "en-CH";
  for (const kind of visual ? [] : Object.keys(routes)) {
    reset(kind);
    await navigate();
    await open();
    await share();
    user = peer;
    await navigate();
    await open();
    assert.equal(
      await evaluate(
        cdp,
        "document.querySelector('[data-business-access] select').disabled",
      ),
      true,
    );
    assert.equal(
      await evaluate(
        cdp,
        "!!document.querySelector('[data-tender-email],[data-trademark-email],[data-auction-email]')",
      ),
      false,
    );
    await value("[data-business-access] label:last-of-type select", owner);
    await click("[data-business-access] button[type=submit]");
    await wait(() => row.version === 3, "Assignment did not save");
    await navigate();
    await open();
    await click("[data-business-access] div > button:last-child");
    await wait(
      () =>
        evaluate(
          cdp,
          "document.querySelectorAll('[data-business-access] li').length===2",
        ),
      "History continuation missing",
    );
    await check(`${kind}-peer-history`);
    role = "viewer";
    await navigate();
    await open();
    assert.equal(
      await evaluate(
        cdp,
        "!!document.querySelector('[data-business-access] form')",
      ),
      false,
    );
    await check(`${kind}-viewer`);
    user = owner;
    role = "organization_admin";
    await navigate();
    await open();
    conflict = true;
    await value(select, "private");
    await click("[data-business-access] button[type=submit]");
    await wait(
      () =>
        evaluate(
          cdp,
          "!!document.querySelector('[data-business-access] [role=alert]')",
        ),
      "Conflict not reported",
    );
    assert.equal(
      await evaluate(
        cdp,
        "!!document.querySelector('[data-business-access] form')",
      ),
      false,
    );
    await check(`${kind}-conflict`);
    conflict = false;
    await click("[data-business-access] button");
    await wait(
      () =>
        evaluate(
          cdp,
          "!!document.querySelector('[data-business-access] form')",
        ),
      "Reload failed",
    );
    await value(select, "private");
    await click("[data-business-access] button[type=submit]");
    await wait(() => row.visibility === "private", "Withdrawal did not save");
    user = peer;
    await cdp.send("Page.navigate", {
      url: base + `/${routes[domain]}?monitor=${id}&qa=${++nav}`,
    });
    await wait(
      () =>
        evaluate(
          cdp,
          "!document.querySelector('[data-business-access]')&&!!document.querySelector('main [role=alert]')",
        ),
      "Old private link remained readable",
    );
    reset(kind);
    await navigate();
    delayed = true;
    await click("[data-business-access] summary");
    await wait(() => !!held, "No pending scope read");
    await evaluate(cdp, "window.dispatchEvent(new Event('pagehide'))");
    delayed = false;
    await response(held.requestId, held.data);
    held = null;
    await sleep(200);
    assert.equal(
      await evaluate(
        cdp,
        "!!document.querySelector('[data-business-access] form')",
      ),
      false,
    );
  }
  assert.deepEqual(errors, []);
  assert.ok(mutations.every((item) => item.body && item.body.expected_version));
  audit.finish(visual ? 4 : 99);
  console.log(
    visual
      ? "Desktop and mobile scope-panel screenshots saved; four accessibility checkpoints passed."
      : "All three directions: five locales/two widths, explicit consent, sharing/pause, assignment, owner-only email, viewer, history pagination, conflict, withdrawal and pagehide late-response checks passed.",
  );
  await writeFile(
    join(
      root,
      visual
        ? "test-results/business-monitor-visual-requests.json"
        : "test-results/business-monitor-access-requests.json",
    ),
    JSON.stringify({ mutations, requests }, null, 2),
  );
} finally {
  cdp?.close();
  browser.kill();
  server.kill();
  await sleep(250);
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 8,
    retryDelay: 250,
  }).catch(() => {});
}
