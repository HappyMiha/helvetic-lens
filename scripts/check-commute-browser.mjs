// Built product UI, isolated browser, synthetic accounts/feeds only.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile, mkdir } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";

const root = resolve(import.meta.dirname, "..");
const { commuteCopy } = await import(
  pathToFileURL(join(root, "apps/web/lib/commute-copy.ts")).href
);
const { newCommute, zurichDate } = await import(
  pathToFileURL(join(root, "apps/web/lib/commute-watch.ts")).href
);
const { commuteEmailCopy } = await import(
  pathToFileURL(join(root, "apps/web/lib/commute-email-copy.ts")).href
);
const { commuteInterchangeCopy } = await import(
  pathToFileURL(join(root, "apps/web/lib/commute-interchange-copy.ts")).href
);
const { pollenDeliveryCopy } = await import(
  pathToFileURL(join(root, "apps/web/lib/pollen-delivery-copy.ts")).href
);
const chrome = [
  process.env.CHROME_BIN,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "/usr/bin/google-chrome",
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-commute-qa-"));
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
const audit = new AccessibilityAudit("commute-watch");
const id = "00000000-0000-4000-8000-000000000001",
  legId = "00000000-0000-4000-8000-000000000002",
  eventId = "00000000-0000-4000-8000-000000000003";
const leg = {
  id: legId,
  label: "Tram 8: Basel SBB → Claraplatz",
  enabled: true,
  departure_wall_time: "07:45:00",
  service_day: "2026-09-14",
};
const time = "2026-09-14T05:40:00+00:00";
let cdp,
  locale = "en-CH",
  manager = true,
  enabled = true,
  sourceEnabled = false,
  monitor = null,
  denied = false,
  conflict = false;
let eventConflict = false;
let emailVerified = true,
  emailConflict = false,
  emailDenied = false;
let emailConfig = {
  timezone: "Europe/Zurich",
  delivery: { email: "off", digest_at: null, quiet_hours: null },
};
let emailRevision = 0;
let sparseToday = false,
  omitEventPage = false;
let historySequence = 1,
  previewCount = 0,
  unknownRequests = [],
  captured = [],
  exceptions = [],
  delayMonitor = false,
  heldRequest = null;
const event = {
  id: eventId,
  available: true,
  monitor_id: id,
  source: "swiss_gtfs_trip_updates",
  version: 2,
  sequence: 1,
  reviewed_sequence: 0,
  configuration_revision: 1,
  service_day: "2026-09-14",
  muted: false,
  current: {
    states: {
      [legId]: {
        condition: "cancelled",
        availability: "present",
        reason: "material",
        observed_at: time,
        delay_seconds: null,
      },
    },
    editions: {
      [legId]: {
        header: [["de", "Offizielle Testmeldung"]],
        description: [["de", "<script>window.sourceExecuted=true</script>"]],
        active_periods: [],
      },
    },
  },
};
const evidence = () => ({
  current: event.current,
  source: event.source,
  feed_sha256: "a".repeat(64),
  entity_sha256: "b".repeat(64),
  feed_observed_at: time,
  recorded_at: time,
  service_day: event.service_day,
  configuration_revision: event.configuration_revision,
  legs: {
    [legId]: {
      route_name: "Tram 8",
      boarding_name: "Basel SBB",
      alighting_name: "Claraplatz",
    },
  },
});
const savedEvidence = structuredClone(evidence());
const todayText = () =>
  evaluate(
    cdp,
    "document.querySelector('[data-commute-today]')?.innerText || ''",
  );
async function openToday() {
  await cdp.send("Page.navigate", { url: `${base}/?qa=${Date.now()}` });
  await wait(
    () => evaluate(cdp, "!!document.querySelector('h1')"),
    "Today shell missing",
  );
}
async function wait(check, message) {
  for (let i = 0; i < 200; i++) {
    if (
      await Promise.resolve()
        .then(check)
        .catch(() => false)
    )
      return;
    await sleep(100);
  }
  throw new Error(message);
}
const text = () =>
  evaluate(
    cdp,
    "document.querySelector('[data-commute-watch]')?.innerText || ''",
  );
async function button(name, selector = "[data-commute-watch]") {
  const expression = `Array.from(document.querySelectorAll(${JSON.stringify(selector + " button")})).find(b=>b.textContent.trim()===${JSON.stringify(name)}&&!b.matches(':disabled'))`;
  await wait(
    () =>
      evaluate(
        cdp,
        `(()=>{const button=${expression};if(!button)return false;button.click();return true;})()`,
      ),
    `Missing enabled button: ${name}`,
  );
}
async function field(label, value) {
  await evaluate(
    cdp,
    `(()=>{const label=Array.from(document.querySelectorAll('form label')).find(l=>l.firstChild.textContent.trim()===${JSON.stringify(label)}&&l.querySelector('input'));const input=label.querySelector('input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(value)});input.dispatchEvent(new Event('input',{bubbles:true}));})()`,
  );
}
async function navigate(query = monitor ? `?monitor=${id}` : "") {
  await cdp.send("Page.navigate", {
    url: `${base}/commute-watch${query}${query ? "&" : "?"}qa=${Date.now()}`,
  });
  await wait(
    async () => (await text()).includes(commuteCopy[locale].title),
    "Commute page did not load",
  );
}
async function fulfill(requestId, body, code = 200) {
  await cdp
    .send("Fetch.fulfillRequest", {
      requestId,
      responseCode: code,
      responseHeaders: [
        { name: "Content-Type", value: "application/json" },
        { name: "Cache-Control", value: "no-store" },
      ],
      body:
        code === 204
          ? ""
          : Buffer.from(JSON.stringify(body)).toString("base64"),
    })
    .catch(() => {});
}
try {
  await wait(
    async () => (await fetch(base, { signal: AbortSignal.timeout(1000) })).ok,
    "Next did not start",
  );
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
  ).then((response) => response.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1365,
    height: 980,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp.send("Network.setCookie", {
    name: "helvetic_lens_csrf",
    value: "synthetic-commute",
    url: base,
  });
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    exceptions.push(
      exceptionDetails.exception?.description || exceptionDetails.text,
    ),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url),
      payload = request.postData ? JSON.parse(request.postData) : null;
    let body = {},
      code = 200;
    if (url.pathname === "/api/auth/session")
      body = {
        authenticated: true,
        user: {
          id: "qa",
          name: "Commute QA",
          email: "commute@example.invalid",
          locale,
        },
        organization: { id: "private-qa", name: "Private QA" },
        role: manager ? "organization_admin" : "viewer",
        platform_admin: false,
        onboarding_required: false,
      };
    else if (url.pathname === "/api/health")
      body = {
        status: "ok",
        database: "synthetic",
        apertus: { configured: false },
        firecrawl: { configured: false },
      };
    else if (url.pathname.startsWith("/api/commute-watch")) {
      const path = url.pathname.slice("/api/commute-watch".length);
      if (request.method !== "GET") {
        captured.push({ path, method: request.method, payload });
        assert.equal(
          request.headers["X-CSRF-Token"] || request.headers["x-csrf-token"],
          "synthetic-commute",
        );
      }
      if (!enabled) {
        body = { code: "commute_disabled" };
        code = 404;
      } else if (path === "/today") {
        const item = {
          id: eventId,
          monitor_id: id,
          event_id: eventId,
          name: monitor?.configuration.name,
          sequence: event.sequence,
          event_version: event.version,
          signal_sequence: event.sequence,
          configuration_revision: event.configuration_revision,
          service_day: event.service_day,
          source: event.source,
          detected_at: time,
          states: event.current.states,
          reference_labels: [leg],
          priority:
            event.current.states[legId].availability === "present" &&
            event.current.states[legId].condition === "cancelled"
              ? "urgent"
              : "normal",
          reasons: ["unread_journey_change", "outside_window_saved"],
          href: `/commute-watch?monitor=${id}&event=${eventId}&sequence=${event.sequence}`,
        };
        body = {
          items:
            monitor?.status === "active" &&
            !denied &&
            !event.muted &&
            event.reviewed_sequence < event.sequence &&
            (!sparseToday || url.searchParams.has("cursor"))
              ? [item]
              : [],
          next_cursor:
            sparseToday && !url.searchParams.has("cursor") ? eventId : null,
        };
      } else if (path === `/events/${eventId}`) {
        if (denied || url.searchParams.get("monitor_id") !== id) {
          code = 404;
          body = { code: "commute_event_unavailable" };
        } else {
          const sequence = Number(
            url.searchParams.get("sequence") || event.sequence,
          );
          body = {
            event: { ...event, reference_labels: [leg] },
            snapshot: {
              id: `history-${sequence}`,
              sequence,
              evidence: sequence < event.sequence ? savedEvidence : evidence(),
              evidence_hash: "c".repeat(64),
              created_at: time,
            },
            newer_available: sequence < event.sequence,
            current_configuration:
              event.configuration_revision === monitor.revision,
          };
        }
      } else if (path === "/capabilities")
        body = {
          drafts_available: true,
          start_available: sourceEnabled,
          blocking_reasons: sourceEnabled ? [] : ["commute_feed_unavailable"],
        };
      else if (path === "/catalog")
        body = {
          items: url.searchParams.has("after_id")
            ? [
                {
                  ...leg,
                  id: "00000000-0000-4000-8000-000000000004",
                  label: "Tram 8: Claraplatz → Kleinhüningen",
                },
              ]
            : [leg],
          next_cursor: url.searchParams.has("after_id") ? null : legId,
          complete_network: false,
          coverage: "imported_verified_legs_only",
        };
      else if (path === "/preview") {
        previewCount++;
        assert.equal(payload.static_version, undefined);
        body = {
          service_day: payload.service_day,
          start_available: sourceEnabled,
          blocking_reasons: sourceEnabled ? [] : ["commute_feed_unavailable"],
          live_results_checked: false,
          legs: [
            {
              reference_id: legId,
              boarding_name: "Basel SBB",
              alighting_name: "Claraplatz",
              route_name: "Tram 8",
              departure: "2026-09-14T05:45:00+00:00",
              arrival: "2026-09-14T06:00:00+00:00",
            },
          ],
        };
        if (payload.configuration.leg_reference_ids.length === 2) {
          const nextId = payload.configuration.leg_reference_ids[1];
          body.legs.push({
            reference_id: nextId,
            boarding_name: "Claraplatz platform 2",
            alighting_name: "Kleinhüningen",
            route_name: "Tram 8",
            departure: "2026-09-14T06:04:00+00:00",
            arrival: "2026-09-14T06:30:00+00:00",
          });
          body.interchanges = [
            {
              from_reference_id: legId,
              to_reference_id: nextId,
              state: "minimum_met",
              scheduled_seconds: 240,
              min_transfer_time: 240,
            },
          ];
        }
      } else if (path === "/monitors" && request.method === "POST") {
        assert.match(payload.request_key, /^[0-9a-f-]{36}$/);
        monitor = {
          id,
          configuration: payload.configuration,
          reference_labels: [leg],
          version: 1,
          revision: 1,
          status: "draft",
          health: "not_started",
          paused_on: null,
          last_check_at: null,
          next_check_at: null,
        };
        body = monitor;
      } else if (path === "/monitors")
        body = { items: monitor ? [monitor] : [], next_cursor: null };
      else if (path === `/monitors/${id}` && request.method === "GET") {
        if (delayMonitor) {
          heldRequest = { requestId, body: structuredClone(monitor) };
          return;
        }
        body = monitor;
      } else if (path === `/monitors/${id}` && request.method === "PATCH") {
        assert.equal(payload.expected_version, monitor.version);
        monitor = {
          ...monitor,
          configuration: payload.configuration,
          version: monitor.version + 1,
          revision: monitor.revision + 1,
          status: "draft",
        };
        body = monitor;
      } else if (path === `/monitors/${id}` && request.method === "DELETE") {
        assert.equal(payload.expected_version, monitor.version);
        monitor = null;
        code = 204;
      } else if (path === `/monitors/${id}/email`) {
        if (emailDenied) {
          code = 404;
          body = { code: "commute_not_found" };
        } else if (request.method === "PUT" && emailConflict) {
          code = 409;
          body = { code: "commute_version_conflict" };
        } else {
          if (request.method === "PUT") {
            assert.ok(manager);
            assert.equal(payload.expected_version, monitor.version);
            assert.equal(
              payload.consent,
              payload.configuration.delivery.email !== "off",
            );
            assert.ok(!payload.consent || emailVerified);
            emailConfig = payload.configuration;
            emailRevision++;
            monitor.version++;
          }
          body = {
            revision: emailRevision,
            monitor_version: monitor.version,
            configuration: emailConfig,
            email_verified: emailVerified,
            consent_active:
              emailVerified && emailConfig.delivery.email !== "off",
            recipient_email: "commute@example.invalid",
            uncertain_deliveries: 1,
            delivery_service_available: false,
          };
        }
      } else if (path === `/monitors/${id}/email-preview`) {
        if (emailDenied) {
          code = 404;
          body = { code: "commute_not_found" };
        } else
          body = {
            status: "daily_already_attempted",
            quiet_hours: true,
            more_available: true,
            items: [
              {
                event_id: eventId,
                sequence: event.sequence,
                service_day: event.service_day,
                href: `/commute-watch?monitor=${id}&event=${eventId}&sequence=${event.sequence}`,
              },
            ],
          };
      } else if (path === `/monitors/${id}/commands`) {
        assert.equal(payload.expected_version, monitor.version);
        if (conflict) {
          body = { code: "commute_version_conflict" };
          code = 409;
        } else if (
          !sourceEnabled &&
          ["start", "resume"].includes(payload.action)
        ) {
          body = { code: "commute_source_not_ready" };
          code = 409;
        } else {
          monitor.version++;
          if (["pause_today", "unpause_today"].includes(payload.action))
            monitor.paused_on =
              payload.action === "pause_today" ? zurichDate() : null;
          else
            monitor.status = {
              start: "active",
              resume: "active",
              pause: "paused",
              archive: "archived",
            }[payload.action];
          monitor.health = "waiting_for_predictions";
          body = monitor;
        }
      } else if (path === `/monitors/${id}/revisions`)
        body = {
          items: [
            {
              revision: monitor.revision,
              configuration: monitor.configuration,
              reference_labels: [leg],
            },
          ],
          next_cursor: null,
        };
      else if (path === `/monitors/${id}/events`)
        body = {
          items:
            monitor.status === "draft" || omitEventPage
              ? []
              : [denied ? { id: eventId, available: false } : event],
          next_cursor: null,
        };
      else if (path === `/events/${eventId}/review`) {
        assert.equal(payload.expected_version, event.version);
        assert.equal(payload.sequence, event.sequence);
        if (eventConflict) {
          code = 409;
          body = { code: "commute_version_conflict" };
        } else if (denied) {
          code = 404;
          body = { code: "commute_event_unavailable" };
        } else {
          event.version++;
          if (payload.muted === undefined)
            event.reviewed_sequence = event.sequence;
          else event.muted = payload.muted;
          body = event;
        }
      } else if (path === `/events/${eventId}/history`) {
        if (denied) {
          code = 404;
          body = { code: "commute_event_unavailable" };
        } else {
          historySequence =
            Number(url.searchParams.get("after_sequence") || 0) + 1;
          body = {
            items: [
              {
                id: `history-${historySequence}`,
                sequence: historySequence,
                evidence: evidence(),
                evidence_hash: "c".repeat(64),
                created_at: time,
              },
            ],
            next_cursor: historySequence === 1 ? 1 : null,
          };
        }
      } else {
        unknownRequests.push(path);
        code = 404;
        body = { code: "unknown_fixture_route" };
      }
    } else if (url.pathname === "/api/interest-feed") {
      body = {
        items: [],
        scanned_event_count: 0,
        has_more: false,
        next_cursor: null,
      };
    } else {
      code = 503;
      body = { code: "unavailable" };
    }
    await fulfill(requestId, body, code);
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }],
  });
  await navigate();
  const c = commuteCopy[locale];
  await button(c.create);
  await field(c.name, "Basel daily commute");
  await field(c.day, "2026-09-14");
  await button(c.search);
  await wait(
    async () => (await text()).includes(leg.label),
    "Catalog did not load",
  );
  await button(c.more, "[data-commute-editor]");
  await wait(
    async () => (await text()).includes("Kleinhüningen"),
    "Catalog next page missing",
  );
  assert.equal(
    captured.length,
    0,
    "Catalog navigation must not submit a draft",
  );
  await button(c.previous, "[data-commute-editor]");
  await button(c.select, "[data-commute-editor]");
  await button(c.check);
  await wait(() => previewCount === 1, "Preview missing");
  await wait(
    async () => (await text()).includes(c.previewHelp),
    "Preview content missing",
  );
  assert.equal(monitor, null);
  await audit.check(cdp, "preview", "[data-commute-editor]");
  await button(c.more, "[data-commute-editor]");
  await button(c.select, "[data-commute-editor]");
  await button(c.check);
  await wait(
    async () =>
      (await text()).includes(commuteInterchangeCopy[locale].minimum_met),
    "Interchange explanation missing",
  );
  assert.ok((await text()).includes(commuteInterchangeCopy[locale].note));
  await audit.check(cdp, "interchange-preview", "[data-commute-interchanges]");
  await evaluate(
    cdp,
    `Array.from(document.querySelectorAll('[data-commute-editor] button')).filter(x=>x.textContent.trim()===${JSON.stringify(c.remove)}).at(-1).click()`,
  );
  await button(c.save);
  await wait(() => monitor?.status === "draft", "Draft not saved");
  await wait(
    async () => (await text()).includes(c.start),
    "Draft detail not loaded",
  );
  sourceEnabled = true;
  await navigate();
  await button(c.start);
  await wait(
    async () => (await text()).includes(c.cancelled),
    "Cancellation missing",
  );
  assert.equal(await evaluate(cdp, "!!window.sourceExecuted"), false);
  await openToday();
  await wait(
    async () => (await todayText()).includes(c.urgent),
    "Today cancellation missing",
  );
  assert.ok((await todayText()).includes(c.outside_window_saved));
  await audit.check(cdp, "today-cancellation", "[data-commute-today]");
  omitEventPage = true;
  await evaluate(
    cdp,
    "document.querySelector('[data-commute-today] a').click()",
  );
  await wait(
    async () => (await text()).includes(c.savedUpdate),
    "Today exact link failed outside the first event page",
  );
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelectorAll('[data-commute-event]').length",
    ),
    1,
  );
  omitEventPage = false;
  await button(c.review);
  await wait(
    () => event.reviewed_sequence === event.sequence,
    "Exact review failed",
  );
  await openToday();
  await sleep(300);
  assert.equal(await todayText(), "", "Reviewed update remained in Today");
  await navigate();
  await button(c.mute);
  await wait(() => event.muted, "Mute failed");
  event.sequence++;
  event.version++;
  await navigate();
  await wait(
    async () => (await text()).includes(c.unread),
    "New version incorrectly reviewed",
  );
  eventConflict = true;
  await button(c.review);
  await wait(
    async () => (await text()).includes(c.conflict),
    "Event conflict feedback disappeared",
  );
  assert.equal((await text()).includes("Offizielle Testmeldung"), false);
  eventConflict = false;
  await button(c.refresh, "[data-commute-detail]");
  await button(c.history);
  await wait(
    async () => (await text()).includes(c.evidence),
    "History missing",
  );
  await button(c.more, "[data-commute-event]");
  await wait(() => historySequence === 2, "History pagination failed");
  denied = true;
  await button(c.previous, "[data-commute-event]");
  await wait(
    async () => (await text()).includes(c.unavailable),
    "Revoked evidence remained visible",
  );
  assert.equal((await text()).includes("Offizielle Testmeldung"), false);
  denied = false;
  await navigate();
  await button(c.pause_today);
  await wait(() => monitor.paused_on !== null, "Pause today failed");
  await button(c.unpause_today);
  await wait(() => monitor.paused_on === null, "Resume today failed");
  conflict = true;
  await button(c.pause);
  await wait(
    async () => (await text()).includes(c.conflict),
    "Conflict notice was lost during reload",
  );
  conflict = false;
  await button(c.pause);
  await wait(() => monitor.status === "paused", "Pause failed");
  await button(c.edit);
  await field(c.name, "Basel revised commute");
  await button(c.save);
  await wait(() => monitor.revision === 2, "Settings revision not saved");
  await button(c.start);
  await wait(() => monitor.status === "active", "Restart failed");
  for (const lang of Object.keys(commuteCopy)) {
    locale = lang;
    await navigate();
    await wait(
      async () => (await text()).includes(commuteCopy[locale].cancelled),
      `Locale detail missing: ${locale}`,
    );
    await audit.check(cdp, `desktop-${locale}`, "[data-commute-watch]");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 390,
      height: 844,
      deviceScaleFactor: 1,
      mobile: true,
    });
    assert.equal(
      await evaluate(
        cdp,
        "document.documentElement.scrollWidth<=window.innerWidth+1",
      ),
      true,
      `Horizontal overflow: ${locale}`,
    );
    await audit.check(cdp, `mobile-${locale}`, "[data-commute-watch]");
    if (locale === "en-CH") {
      await evaluate(
        cdp,
        "document.querySelector('[data-commute-event]').scrollIntoView({block:'center'})",
      );
      await mkdir(join(root, "test-results"), { recursive: true });
      await writeFile(
        join(root, "test-results/commute-watch-active-mobile.png"),
        Buffer.from(
          (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
          "base64",
        ),
      );
    }
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 1365,
      height: 980,
      deviceScaleFactor: 1,
      mobile: false,
    });
  }
  locale = "en-CH";
  manager = false;
  await navigate();
  await wait(
    async () => (await text()).includes(c.readonly),
    "Viewer notice missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      `Array.from(document.querySelectorAll('[data-commute-watch] button')).some(b=>[${JSON.stringify(c.create)},${JSON.stringify(c.review)},${JSON.stringify(c.pause)}].includes(b.textContent.trim()))`,
    ),
    false,
  );
  manager = true;
  enabled = false;
  await navigate();
  await wait(
    async () => (await text()).includes(c.featureOff),
    "Feature gate missing",
  );
  assert.equal((await text()).includes(monitor.configuration.name), false);
  enabled = true;
  delayMonitor = true;
  await navigate();
  await wait(() => heldRequest !== null, "Delayed private response missing");
  await button(c.create);
  await wait(
    () => evaluate(cdp, "!!document.querySelector('[data-commute-editor]')"),
    "New editor missing",
  );
  await fulfill(heldRequest.requestId, heldRequest.body);
  heldRequest = null;
  delayMonitor = false;
  await sleep(150);
  assert.equal(
    await evaluate(cdp, "!!document.querySelector('[data-commute-editor]')"),
    true,
    "Late response replaced the new selection",
  );
  event.muted = false;
  event.reviewed_sequence = 0;
  event.current.states[legId] = {
    ...event.current.states[legId],
    availability: "stale",
  };
  for (const lang of Object.keys(commuteCopy)) {
    locale = lang;
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 390,
      height: 844,
      deviceScaleFactor: 1,
      mobile: true,
    });
    await openToday();
    await wait(
      async () => (await todayText()).includes(commuteCopy[locale].lastKnown),
      "Stale Today information missing",
    );
    assert.equal(
      (await todayText()).includes(commuteCopy[locale].urgent),
      false,
    );
    assert.equal(
      await evaluate(
        cdp,
        "document.documentElement.scrollWidth<=window.innerWidth+1",
      ),
      true,
    );
    await audit.check(cdp, `today-mobile-${locale}`, "[data-commute-today]");
  }
  locale = "en-CH";
  await navigate(`?monitor=${id}&event=${eventId}&sequence=1`);
  await wait(
    async () => (await text()).includes(c.newerUpdate),
    "Old exact version was replaced by the newest",
  );
  assert.ok(
    (await text()).includes(c.savedUpdate) &&
      (await text()).includes(c.latestState),
  );
  await audit.check(cdp, "linked-old-version", "[data-commute-linked]");
  denied = true;
  await button(c.review, "[data-commute-linked]");
  await wait(
    () => evaluate(cdp, "!document.querySelector('[data-commute-linked]')"),
    "Revoked current review left the saved snapshot visible",
  );
  denied = false;
  sparseToday = true;
  await openToday();
  await button(c.more, "[data-commute-today]");
  await wait(
    async () => (await todayText()).includes(c.lastKnown),
    "Sparse page did not advance",
  );
  enabled = false;
  await evaluate(cdp, "window.dispatchEvent(new Event('focus'))");
  await wait(
    async () => !(await todayText()),
    "Disabled feature left the second Today page visible",
  );
  enabled = true;
  sparseToday = false;
  // Explicit consent, versioned save and exact private preview; no SMTP in this harness.
  const emailText = () =>
    evaluate(
      cdp,
      "document.querySelector('[data-commute-email]')?.innerText || ''",
    );
  const openEmail = async () => {
    await wait(
      () =>
        evaluate(
          cdp,
          `(()=>{const summary=Array.from(document.querySelectorAll('summary')).find(x=>x.textContent===${JSON.stringify(pollenDeliveryCopy[locale].title)}); if(!summary)return false; if(!summary.parentElement.open)summary.click(); return true;})()`,
        ),
      "Email settings missing",
    );
    await wait(
      async () => (await emailText()).includes("commute@example.invalid"),
      "Email preferences did not load",
    );
  };
  const mode = async (value) =>
    evaluate(
      cdp,
      `(()=>{const select=document.querySelector('[data-commute-email] select'); Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(select,${JSON.stringify(value)}); select.dispatchEvent(new Event('change',{bubbles:true}));})()`,
    );
  await navigate();
  await openEmail();
  const consentRevision = monitor.revision,
    reviewedBeforeMail = event.reviewed_sequence;
  assert.ok((await emailText()).includes(commuteEmailCopy[locale].serviceOff));
  assert.ok((await emailText()).includes(commuteEmailCopy[locale].uncertain));
  await mode("daily_digest");
  await evaluate(
    cdp,
    "document.querySelector('[data-commute-email] input[type=checkbox]:not([required])').click()",
  );
  await field(pollenDeliveryCopy[locale].end, "22:00");
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelector('[data-commute-email] button[type=submit]').matches(':disabled')",
    ),
    true,
  );
  await evaluate(
    cdp,
    "document.querySelector('[data-commute-email] input[required][type=checkbox]').click()",
  );
  await button(commuteEmailCopy[locale].save, "[data-commute-email]");
  await wait(
    async () =>
      (await emailText()).includes(pollenDeliveryCopy[locale].invalidQuiet),
    "Equal quiet endpoints were not rejected",
  );
  assert.equal(emailRevision, 0);
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelector('[data-commute-email] fieldset').disabled",
    ),
    false,
  );
  await field(pollenDeliveryCopy[locale].end, "07:00");
  await evaluate(
    cdp,
    "document.querySelector('[data-commute-email] input[required][type=checkbox]').click()",
  );
  await button(commuteEmailCopy[locale].save, "[data-commute-email]");
  await wait(() => emailRevision === 1, "Email consent not saved");
  await openEmail();
  assert.equal(
    monitor.revision,
    consentRevision,
    "Email changed journey configuration",
  );
  assert.equal(
    event.reviewed_sequence,
    reviewedBeforeMail,
    "Email marked Today reviewed",
  );
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelector('[data-commute-email] input[required][type=checkbox]').checked",
    ),
    false,
  );
  await button(commuteEmailCopy[locale].preview, "[data-commute-email]");
  await wait(
    async () => (await emailText()).includes(commuteEmailCopy[locale].daily),
    "Daily schedule status missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelector('[data-commute-email] a').getAttribute('href')",
    ),
    `/commute-watch?monitor=${id}&event=${eventId}&sequence=${event.sequence}`,
  );
  await audit.check(cdp, "email-desktop", "[data-commute-email]");
  emailDenied = true;
  await button(commuteEmailCopy[locale].preview, "[data-commute-email]");
  await wait(
    () =>
      evaluate(
        cdp,
        "!document.querySelector('[data-commute-email] a') && !document.querySelector('[data-commute-email] form')",
      ),
    "Denied email preview retained private content",
  );
  emailDenied = false;
  await button(c.refresh, "[data-commute-email]");
  await openEmail();
  await mode("off");
  emailConflict = true;
  await button(commuteEmailCopy[locale].save, "[data-commute-email]");
  await wait(
    async () => (await emailText()).includes(c.conflict),
    "Email conflict not shown",
  );
  assert.equal(
    await evaluate(
      cdp,
      "!!document.querySelector('[data-commute-email] form')",
    ),
    false,
  );
  emailConflict = false;
  await button(c.refresh, "[data-commute-email]");
  await openEmail();
  await mode("off");
  await button(commuteEmailCopy[locale].save, "[data-commute-email]");
  await wait(
    () => emailConfig.delivery.email === "off",
    "Email opt-out failed",
  );
  emailVerified = false;
  for (const lang of Object.keys(commuteCopy)) {
    locale = lang;
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 390,
      height: 844,
      deviceScaleFactor: 1,
      mobile: true,
    });
    await navigate();
    await openEmail();
    assert.ok((await emailText()).includes(commuteEmailCopy[locale].verify));
    assert.equal(
      await evaluate(
        cdp,
        "Array.from(document.querySelectorAll('[data-commute-email] select option')).filter(x=>x.value!=='off').every(x=>x.disabled)",
      ),
      true,
    );
    assert.equal(
      await evaluate(
        cdp,
        "document.documentElement.scrollWidth<=window.innerWidth+1",
      ),
      true,
    );
    await audit.check(cdp, `email-mobile-${locale}`, "[data-commute-email]");
  }
  locale = "en-CH";
  manager = false;
  await navigate();
  await openEmail();
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelector('[data-commute-email] fieldset').disabled",
    ),
    true,
  );
  assert.equal(
    await evaluate(
      cdp,
      "!!document.querySelector('[data-commute-email] button[type=submit]')",
    ),
    false,
  );
  manager = true;
  emailVerified = true;
  await navigate();
  await button(c.archive);
  await wait(() => monitor.status === "archived", "Archive failed");
  await button(c.delete);
  await button(c.cancel);
  assert.ok(monitor);
  await button(c.delete);
  await button(c.confirmDelete);
  await wait(() => monitor === null, "Delete failed");
  await wait(
    async () => (await text()).includes(c.empty),
    "Deleted row remains visible",
  );
  await mkdir(join(root, "test-results"), { recursive: true });
  await writeFile(
    join(root, "test-results/commute-watch.png"),
    Buffer.from(
      (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
      "base64",
    ),
  );
  assert.deepEqual(unknownRequests, []);
  assert.deepEqual(exceptions, []);
  assert.equal(heldRequest, null);
  audit.finish(25);
  console.log(
    "Commute browser passed: catalog pagination, preview/save/start, exact review/mute, revoked history, conflict recovery, pause/edit/archive/delete, five locales, desktop/mobile and private role/source gates.",
  );
} catch (error) {
  console.error(
    JSON.stringify({
      text: cdp ? await text().catch(() => "") : "",
      captured,
      unknownRequests,
      exceptions,
    }),
  );
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const stopped = new Promise((done) => child.once("exit", done));
    child.kill();
    await Promise.race([stopped, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-commute-qa-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
