// Built frontend, intercepted synthetic accounts and publications only.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { stripTypeScriptTypes } from "node:module";
import { pathToFileURL } from "node:url";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
const root = resolve(import.meta.dirname, "..");
const copy = (
  await readFile(join(root, "apps/web/lib/tender-copy.ts"), "utf8")
).replace(
  '"./river-copy"',
  JSON.stringify(pathToFileURL(join(root, "apps/web/lib/river-copy.ts")).href),
);
const { tenderCopy } = await import(
  "data:text/javascript;base64," +
    Buffer.from(stripTypeScriptTypes(copy)).toString("base64")
);
const { tenderEmailCopy } = await import(
  pathToFileURL(join(root, "apps/web/lib/tender-email-copy.ts")).href
);
const { tenderHistoryCopy } = await import(
  pathToFileURL(join(root, "apps/web/lib/tender-history-copy.ts")).href
);
const { tenderDocumentCopy } = await import(
  pathToFileURL(join(root, "apps/web/lib/tender-document-copy.ts")).href
);
const { tenderReviewCopy } = await import(
  pathToFileURL(join(root, "apps/web/lib/tender-review-copy.ts")).href
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-tender-qa-"));
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
const audit = new AccessibilityAudit("tender-watch");
const monitorId = "00000000-0000-4000-8000-000000000001",
  dossierId = "00000000-0000-4000-8000-000000000002";
let cdp,
  locale = "en-CH",
  manager = true,
  sourceEnabled = true,
  monitor = null,
  detail = null,
  sourceFailed = false;
let emailRevision = 0;
const docBefore = "00000000-0000-4000-8000-000000000021",
  docAfter = "00000000-0000-4000-8000-000000000022";
const docOldSet = "00000000-0000-4000-8000-000000000030",
  docSet = "00000000-0000-4000-8000-000000000031";
let docDenied = false,
  docParse = "partial",
  originalDownloads = 0;
let reviewConflict = false;
let profileRevisions = [],
  historyFailed = false;
let emailConfiguration = {
  timezone: "Europe/Zurich",
  delivery: { email: "off", digest_at: null, quiet_hours: null },
};
const exceptions = [],
  mutations = [];
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
    "document.querySelector('[data-tender-watch]')?.innerText || ''",
  );
async function button(name, selector = "[data-tender-watch]") {
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
async function field(label, value, tag = "input") {
  const klass = tag === "textarea" ? "HTMLTextAreaElement" : "HTMLInputElement";
  await evaluate(
    cdp,
    `(()=>{const label=Array.from(document.querySelectorAll('form label')).find(l=>l.firstChild.textContent.trim()===${JSON.stringify(label)}&&l.querySelector(${JSON.stringify(tag)})); const input=label.querySelector(${JSON.stringify(tag)}); Object.getOwnPropertyDescriptor(${klass}.prototype,'value').set.call(input,${JSON.stringify(value)});input.dispatchEvent(new Event('input',{bubbles:true}));})()`,
  );
}
async function navigate() {
  await cdp.send("Page.navigate", {
    url: `${base}/tender-watch${monitor ? `?monitor=${monitorId}&` : "?"}qa=${Date.now()}`,
  });
  await wait(
    async () => (await text()).includes(tenderCopy[locale].title),
    "Tender page did not load",
  );
}
async function openEmail() {
  await wait(
    () =>
      evaluate(
        cdp,
        `!!Array.from(document.querySelectorAll('summary')).find(node=>node.textContent.trim()===${JSON.stringify(pollenDeliveryCopy[locale].title)})`,
      ),
    "Email panel missing",
  );
  await evaluate(
    cdp,
    `Array.from(document.querySelectorAll('summary')).find(node=>node.textContent.trim()===${JSON.stringify(pollenDeliveryCopy[locale].title)}).click()`,
  );
  await wait(
    () =>
      evaluate(cdp, "!!document.querySelector('[data-tender-email] select')"),
    "Email configuration did not load",
  );
}
async function emailMode(mode) {
  await evaluate(
    cdp,
    `(()=>{const input=document.querySelector('[data-tender-email] select'); Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(input,${JSON.stringify(mode)}); input.dispatchEvent(new Event('change',{bubbles:true}));})()`,
  );
}
const material = (value, locator) => ({
  value,
  locator,
  coverage: value === null ? "unknown" : "known",
});
const summary = () => ({
  title: detail.material.title.value,
  phase: "open",
  deadline: detail.material.deadline.value,
  verdict: "needs_review",
  match_scope: "project_context",
  title_truncated: false,
});
function sourceDetail() {
  return {
    id: dossierId,
    monitor_id: monitorId,
    project_id: "project",
    lot_id: "lot",
    version: 1,
    sequence: 1,
    following: false,
    review_state: "new",
    decision: null,
    reviewed_sequence: null,
    evidence_version_id: "00000000-0000-4000-8000-000000000011",
    publication_id: "publication-1",
    source_hash: "a".repeat(64),
    profile_revision: 1,
    current_profile_revision: 1,
    kind: "new_opportunity",
    changes: [],
    material: {
      title: material({ en: "Software development lot" }, "/lots/0/title"),
      phase: material("open", "/type"),
      deadline: material(
        { utc: "2026-10-16T13:00:00Z", status: "known" },
        "/dates/offerDeadline",
      ),
      terms: material(
        {
          en: "3 references required <script>window.sourceInjected=true</script>",
        },
        "/terms",
      ),
      lot_criteria: material(null, "/lots/0"),
    },
    match: {
      verdict: "needs_review",
      matches: [],
      exclusions: [],
      unknowns: [{ code: "qualification_evidence_incomplete" }],
      qualification_gaps: [],
      project_context: [
        {
          code: "project_cpv_context",
          value: "72000000",
          selected_code: "72000000",
          locator: "/procurement",
        },
      ],
    },
  };
}
try {
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
  ).then((response) => response.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Browser.setDownloadBehavior", { behavior: "deny" });
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1365,
    height: 980,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp.send("Runtime.enable");
  await cdp.send("Network.setCookie", {
    name: "helvetic_lens_csrf",
    value: "synthetic-tender",
    url: base,
  });
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    exceptions.push(exceptionDetails.text),
  );
  cdp.on("Page.javascriptDialogOpening", () =>
    cdp.send("Page.handleJavaScriptDialog", { accept: true }),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url),
      payload = request.postData ? JSON.parse(request.postData) : null;
    let code = 200,
      body = {};
    let rawBody = null;
    if (url.pathname === "/api/auth/session")
      body = {
        authenticated: true,
        user: {
          id: "qa",
          name: "Tender QA",
          email: "tender@example.invalid",
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
    else if (url.pathname === "/api/jobs") body = [];
    else if (url.pathname.startsWith("/api/tender-watch")) {
      if (request.method !== "GET")
        mutations.push({ path: url.pathname, method: request.method, payload });
      if (url.pathname.endsWith("/capabilities"))
        body = {
          public_source_available: sourceEnabled,
          lookback_days: 90,
          cycle_hours: 6,
        };
      else if (url.pathname.endsWith("/profile-check"))
        body = {
          queries: [
            { query: payload.configuration.capabilities[0]?.phrases[0] },
          ],
          start_available: sourceEnabled,
          live_results_checked: false,
        };
      else if (url.pathname.includes("/document-observations/")) {
        const older = url.pathname.includes(docOldSet);
        if (url.pathname.endsWith("/comparison")) {
          body = {
            status: docDenied ? "unavailable" : "changed",
            truncated: !docDenied,
            total_changes: docDenied ? 0 : 1,
            before_snapshot_id: docBefore,
            after_snapshot_id: docAfter,
            changes: docDenied
              ? []
              : [
                  {
                    kind: "replaced",
                    before: [
                      {
                        snapshot_id: docBefore,
                        page: 2,
                        locator: "page:2/block:1",
                        text: "3 references required",
                        truncated: false,
                      },
                    ],
                    after: [
                      {
                        snapshot_id: docAfter,
                        page: 4,
                        locator: "page:4/block:1",
                        text: "5 references required",
                        truncated: false,
                      },
                    ],
                  },
                ],
          };
        } else {
          body = {
            id: older ? docOldSet : docSet,
            observed_at: "2026-09-12T10:00:00Z",
            coverage: "partial",
            items: [
              {
                item_id: url.searchParams.has("after_item")
                  ? "terms-appendix"
                  : "requirements",
                title: older
                  ? "Prior requirements"
                  : url.searchParams.has("after_item")
                    ? "Additional conditions"
                    : "Requirements",
                kind: "document",
                access: "available",
                lifecycle: "present",
                snapshot_id: older ? docBefore : docAfter,
                changes: older ? [] : ["replaced"],
                comparison_available: !older,
              },
            ],
            next_cursor:
              url.searchParams.has("after_item") || older
                ? null
                : "requirements",
          };
        }
      } else if (url.pathname.endsWith("/documents")) {
        body = {
          items: [
            {
              id: url.searchParams.has("after_id") ? docAfter : docBefore,
              item_id: "requirements",
              created_at: "2026-09-12T10:00:00Z",
            },
          ],
          next_cursor: url.searchParams.has("after_id") ? null : docBefore,
          coverage: "retained_only",
        };
      } else if (
        url.pathname.includes("/documents/") &&
        url.pathname.endsWith("/text")
      ) {
        if (docDenied) {
          code = 404;
          body = { code: "tender_document_unavailable" };
        } else
          body = {
            snapshot_id: docAfter,
            parse_status: docParse,
            extractor_version: "tender-xlsx-cells-v1",
            passages:
              docParse === "failed"
                ? []
                : Array.from({ length: 51 }, (_, i) => ({
                    page: null,
                    locator: `part:xl/worksheets/sheet1.xml/sheet:Conditions/cell:A${i + 1}/text`,
                    text:
                      i === 0
                        ? '5 references required <img src=x onerror="window.documentInjected=true">'
                        : `Saved document paragraph ${i + 1}`,
                  })),
          };
      } else if (
        url.pathname.includes("/documents/") &&
        url.pathname.endsWith("/original")
      ) {
        originalDownloads++;
        if (docDenied) {
          code = 404;
          body = { code: "tender_document_unavailable" };
        } else rawBody = "synthetic original document bytes";
      } else if (url.pathname.endsWith("/revisions")) {
        if (historyFailed) {
          code = 503;
          body = { code: "unavailable" };
        } else {
          const before = Number(
            url.searchParams.get("before_revision") || Infinity,
          );
          const limit = Number(url.searchParams.get("limit"));
          assert.equal(limit, 10);
          const rows = profileRevisions
            .filter((item) => item.revision < before)
            .sort((a, b) => b.revision - a.revision);
          body = {
            items: rows.slice(0, limit),
            next_cursor: rows.length > limit ? rows[limit - 1].revision : null,
          };
        }
      } else if (url.pathname.endsWith("/email")) {
        if (request.method === "PATCH") {
          assert.equal(payload.expected_version, monitor.version);
          assert.equal(
            payload.consent,
            payload.configuration.delivery.email !== "off",
          );
          emailConfiguration = structuredClone(payload.configuration);
          emailRevision++;
          monitor.version++;
        }
        body = {
          revision: emailRevision,
          monitor_version: monitor.version,
          configuration: emailConfiguration,
          consent_active: emailConfiguration.delivery.email !== "off",
          email_verified: true,
          recipient_email: "synthetic@example.test",
        };
      } else if (url.pathname.endsWith("/email-preview"))
        body = {
          status: "ready",
          quiet_hours: false,
          more_available: false,
          items: [],
        };
      else if (url.pathname.endsWith("/command")) {
        assert.equal(payload.expected_version, monitor.version);
        monitor.version++;
        monitor.status = {
          start: "active",
          resume: "active",
          pause: "paused",
          archive: "archived",
        }[payload.action];
        if (!detail && monitor.status === "active") detail = sourceDetail();
        body = monitor;
      } else if (url.pathname.endsWith("/decision")) {
        assert.equal(payload.expected_version, detail.version);
        assert.equal(payload.sequence, detail.sequence);
        assert.match(payload.request_key, /^[0-9a-f-]{36}$/);
        detail.version++;
        detail.decision = payload.decision;
        detail.reviewed_sequence = detail.sequence;
        detail.review_state = "reviewed";
        detail.following = true;
        body = detail;
      } else if (url.pathname.endsWith("/follow")) {
        assert.equal(payload.expected_version, detail.version);
        detail.version++;
        detail.following = payload.following;
        body = detail;
      } else if (url.pathname.endsWith("/review-changes")) {
        if (reviewConflict) {
          code = 409;
          body = { code: "tender_version_conflict" };
        } else {
          assert.equal(
            Number(url.searchParams.get("through_sequence")),
            detail.sequence,
          );
          assert.equal(
            Number(url.searchParams.get("reviewed_sequence")),
            detail.reviewed_sequence || 0,
          );
          const after = Number(
            url.searchParams.get("after_sequence") ||
              detail.reviewed_sequence ||
              0,
          );
          const entries = Array.from(
            { length: detail.sequence - after },
            (_, i) => {
              const sequence = after + i + 1;
              if (sequence === 4)
                return {
                  id: `unavailable-${sequence}`,
                  sequence,
                  available: false,
                };
              return {
                id: `review-${sequence}`,
                sequence,
                available: true,
                kind:
                  sequence === 3 || sequence === 23
                    ? "material_update"
                    : "source_update",
                changes:
                  sequence === 3
                    ? [{ field: "deadline", kind: "field_changed" }]
                    : sequence === 23
                      ? [{ field: "documents", kind: "field_changed" }]
                      : [],
                document_observation_id: sequence === 23 ? docSet : null,
              };
            },
          );
          body = {
            items: entries.slice(0, 20),
            next_cursor: entries.length > 20 ? entries[19].sequence : null,
          };
        }
      } else if (url.pathname.endsWith("/versions"))
        body = {
          items: detail
            ? [
                {
                  id: detail.evidence_version_id,
                  sequence: detail.sequence,
                  publication_id: detail.publication_id,
                  kind: detail.kind,
                  summary: summary(),
                  changes: detail.changes,
                  profile_revision: detail.profile_revision,
                  document_observation_id: detail.document_observation_id,
                },
                {
                  id: "00000000-0000-4000-8000-000000000010",
                  sequence: 1,
                  publication_id: "previous-publication",
                  kind: "source_update",
                  summary: summary(),
                  changes: [],
                  profile_revision: 1,
                  document_observation_id: docOldSet,
                },
              ]
            : [],
          next_cursor: null,
        };
      else if (url.pathname.endsWith("/dossiers"))
        body = {
          items:
            detail && (!url.searchParams.get("following") || detail.following)
              ? [{ ...detail, summary: summary() }]
              : [],
          next_cursor: null,
        };
      else if (url.pathname === `/api/tender-watch/dossiers/${dossierId}`) {
        if (sourceFailed) {
          code = 503;
          body = { code: "tender_evidence_invalid" };
        } else body = detail;
      } else if (
        url.pathname.endsWith("/monitors") &&
        request.method === "POST"
      ) {
        monitor = {
          id: monitorId,
          visibility: "private",
          owner_user_id: "qa",
          responsible_user_id: null,
          configuration: payload.configuration,
          version: 1,
          revision: 1,
          status: "draft",
          health: "waiting",
          last_poll_at: null,
          next_poll_at: new Date().toISOString(),
        };
        profileRevisions.push({
          revision: 1,
          configuration: structuredClone(payload.configuration),
        });
        body = monitor;
      } else if (url.pathname.endsWith("/monitors"))
        body = { items: monitor ? [monitor] : [], next_cursor: null };
      else if (request.method === "PATCH") {
        assert.equal(payload.expected_version, monitor.version);
        monitor.configuration = payload.configuration;
        monitor.version++;
        monitor.revision++;
        profileRevisions.push({
          revision: monitor.revision,
          configuration: structuredClone(payload.configuration),
        });
        body = monitor;
      } else if (request.method === "DELETE") {
        monitor = null;
        code = 204;
      } else body = monitor;
    } else {
      code = 503;
      body = { code: "unavailable" };
    }
    await cdp
      .send("Fetch.fulfillRequest", {
        requestId,
        responseCode: code,
        responseHeaders: [
          {
            name: "Content-Type",
            value:
              rawBody === null
                ? "application/json"
                : "application/octet-stream",
          },
          { name: "Cache-Control", value: "no-store" },
          ...(rawBody === null
            ? []
            : [
                {
                  name: "Content-Disposition",
                  value: `attachment; filename="synthetic.${originalDownloads > 1 ? "xlsx" : "docx"}"`,
                },
              ]),
        ],
        body:
          code === 204
            ? ""
            : Buffer.from(
                rawBody === null ? JSON.stringify(body) : rawBody,
              ).toString("base64"),
      })
      .catch(() => {});
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }],
  });
  await navigate();
  const c = tenderCopy[locale];
  await button(c.create);
  await field(c.name, "Basel tender profile");
  await field(c.company, "Synthetic Company");
  await button(c.addCapability);
  await field(c.capabilityName, "Software");
  await field(c.phrases, "software development\nICT services", "textarea");
  await button(c.check);
  await wait(
    async () => (await text()).includes(c.plan),
    "Discovery plan missing",
  );
  await audit.check(cdp, "configuration-plan", "form");
  await button(c.save);
  await wait(() => monitor?.status === "draft", "Draft not saved");
  assert.deepEqual(monitor.configuration.capabilities[0].phrases, [
    "software development",
    "ICT services",
  ]);
  await button(c.start);
  await wait(
    async () => (await text()).includes("Software development lot"),
    "Discovery missing",
  );
  assert.ok((await text()).includes(c.projectContext));
  await button(c.details);
  await wait(
    async () => (await text()).includes(c.internalDecision),
    "Dossier missing",
  );
  await button(c.follow);
  await wait(() => detail.following, "Following not saved");
  await button(c.bid);
  await wait(
    async () => (await text()).includes(`${c.internalDecision}: ${c.bid}`),
    "Decision did not remain in the dossier",
  );
  detail = {
    ...detail,
    sequence: 2,
    version: detail.version + 1,
    review_state: "needs_review",
    kind: "material_update",
    evidence_version_id: "00000000-0000-4000-8000-000000000012",
    document_observation_id: docSet,
    changes: [{ field: "deadline", kind: "field_changed" }],
    material: {
      ...detail.material,
      deadline: material(
        { utc: "2026-10-23T13:00:00Z", status: "known" },
        "/dates/offerDeadline",
      ),
    },
  };
  await button(c.refresh, "[data-tender-dossier]");
  await wait(
    async () => (await text()).includes(c.retained),
    "Material revision did not reopen review",
  );
  await audit.check(cdp, "material-review", "[data-tender-dossier]");
  await writeFile(
    join(root, "test-results/tender-watch-desktop.png"),
    Buffer.from(
      (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
      "base64",
    ),
  );
  await evaluate(
    cdp,
    `Array.from(document.querySelectorAll('[data-tender-dossier] summary')).find(node=>node.textContent.startsWith(${JSON.stringify(c.terms)})).click()`,
  );
  await wait(
    async () => (await text()).includes("3 references required"),
    "Source extract missing",
  );
  assert.equal(
    await evaluate(cdp, "window.sourceInjected === undefined"),
    true,
  );
  sourceFailed = true;
  await button(c.refresh, "[data-tender-dossier]");
  await wait(
    async () => (await text()).includes(c.failed),
    "Evidence failure not surfaced",
  );
  assert.equal(
    await evaluate(
      cdp,
      "!!document.querySelector('[data-tender-dossier] fieldset')",
    ),
    false,
  );
  sourceFailed = false;
  await button(c.refresh, "[data-tender-dossier]");
  await button(c.no_bid);
  await wait(
    () => detail.decision === "no_bid" && detail.reviewed_sequence === 2,
    "Latest decision not stored",
  );
  await button(c.back);
  await button(c.pause);
  await button(c.edit);
  await field(c.name, "Basel updated");
  await button(c.saveEdit);
  await button(c.resume);
  // Synthetic long-lived monitor exercises the real API's ten-revision page boundary.
  const originalProfile = structuredClone(profileRevisions[0].configuration);
  profileRevisions = Array.from({ length: 12 }, (_, i) => ({
    revision: i + 1,
    configuration: structuredClone(
      i === 11 ? monitor.configuration : originalProfile,
    ),
  }));
  monitor.revision = 12;
  detail = {
    ...detail,
    sequence: 23,
    review_state: "needs_review",
    changes: [{ field: "documents", kind: "field_changed" }],
  };
  for (const lang of Object.keys(tenderCopy)) {
    locale = lang;
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 390,
      height: 844,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await navigate();
    await button(tenderCopy[locale].details);
    await wait(
      async () => (await text()).includes(tenderCopy[locale].internalDecision),
      "Localized detail missing",
    );
    assert.equal(
      await evaluate(
        cdp,
        "document.documentElement.scrollWidth <= innerWidth + 1",
      ),
      true,
      `Overflow ${locale}`,
    );
    await audit.check(cdp, `reader-${locale}`, "[data-tender-dossier]");
    const rc = tenderReviewCopy[locale];
    await evaluate(
      cdp,
      "document.querySelector('[data-review-changes] > summary').click()",
    );
    await wait(
      () =>
        evaluate(cdp, "!!document.querySelector('[data-review-change=\"3\"]')"),
      "Earlier review change missing",
    );
    assert.ok((await text()).includes(rc.unavailable));
    assert.ok(
      await evaluate(
        cdp,
        `document.querySelector('[data-review-change="3"]').innerText.includes(${JSON.stringify(tenderCopy[locale].deadline)})`,
      ),
    );
    await button(tenderCopy[locale].more, "[data-review-changes]");
    await wait(
      () =>
        evaluate(
          cdp,
          "!!document.querySelector('[data-review-change=\"23\"]')",
        ),
      "Later document revision missing",
    );
    assert.equal(
      await evaluate(
        cdp,
        "!!document.querySelector('[data-review-change=\"3\"]')",
      ),
      false,
    );
    await audit.check(cdp, `review-window-${locale}`, "[data-review-changes]");
    if (locale === "en-CH") {
      reviewConflict = true;
      await evaluate(
        cdp,
        "document.querySelector('[data-review-changes] > summary').click()",
      );
      await wait(
        () => evaluate(cdp, "!document.querySelector('[data-review-change]')"),
        "Closing review history did not hide evidence",
      );
      await evaluate(
        cdp,
        "document.querySelector('[data-review-changes] > summary').click()",
      );
      await wait(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('[data-review-changes] [role=alert]')",
          ),
        "Stale review window not rejected",
      );
      assert.ok((await text()).includes(tenderCopy[locale].conflict));
      assert.equal(
        await evaluate(cdp, "!!document.querySelector('[data-review-change]')"),
        false,
      );
      await audit.check(cdp, "review-window-conflict", "[data-review-changes]");
      reviewConflict = false;
    }
    await evaluate(
      cdp,
      "document.querySelector('[data-review-changes] > summary').click()",
    );
    const dc = tenderDocumentCopy[locale];
    await evaluate(
      cdp,
      "document.querySelector('[data-tender-documents] > summary').click()",
    );
    await wait(
      () =>
        evaluate(
          cdp,
          "!!document.querySelector('[data-document-item=requirements]')",
        ),
      "Saved document set missing",
    );
    await button(dc.open, "[data-document-item=requirements]");
    await wait(
      () =>
        evaluate(
          cdp,
          "document.querySelector('[data-document-evidence=text]')?.innerText.includes('5 references required')",
        ),
      "Saved document text missing",
    );
    assert.ok((await text()).includes(dc.partial));
    assert.ok((await text()).includes(dc.spreadsheet));
    assert.ok((await text()).includes("/sheet:Conditions/cell:A1/text"));
    assert.equal(
      await evaluate(
        cdp,
        "document.documentElement.scrollWidth <= innerWidth + 1",
      ),
      true,
      "Spreadsheet text overflow",
    );
    if (locale === "en-CH") {
      await writeFile(
        join(root, "test-results/tender-xlsx-mobile.png"),
        Buffer.from(
          (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
          "base64",
        ),
      );
    }

    assert.equal(
      await evaluate(
        cdp,
        "!!window.documentInjected || !!document.querySelector('[data-document-evidence] img')",
      ),
      false,
    );
    await audit.check(
      cdp,
      `document-text-${locale}`,
      "[data-document-evidence]",
    );
    await button(tenderCopy[locale].more, "[data-document-evidence]");
    await wait(
      () =>
        evaluate(
          cdp,
          "document.querySelector('[data-document-evidence]')?.innerText.includes('Saved document paragraph 51')",
        ),
      "Bounded text pagination failed",
    );
    await button(dc.compare, "[data-document-item=requirements]");
    await wait(
      () =>
        evaluate(
          cdp,
          "document.querySelector('[data-document-evidence=comparison]')?.innerText.includes('3 references required')",
        ),
      "Exact original comparison missing",
    );
    assert.ok((await text()).includes(dc.truncated));
    assert.equal(
      await evaluate(
        cdp,
        "document.documentElement.scrollWidth <= innerWidth + 1",
      ),
      true,
      `Document overflow ${locale}`,
    );
    await audit.check(
      cdp,
      `document-comparison-${locale}`,
      "[data-document-evidence]",
    );
    if (locale === "en-CH") {
      await writeFile(
        join(root, "test-results/tender-documents-mobile.png"),
        Buffer.from(
          (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
          "base64",
        ),
      );
      const downloads = originalDownloads;
      await evaluate(
        cdp,
        `window.tenderDownloadNames = []; const previousAnchorClick = HTMLAnchorElement.prototype.click;
        HTMLAnchorElement.prototype.click = function(...args) { if (this.download) window.tenderDownloadNames.push(this.download); return previousAnchorClick.apply(this, args); };`,
      );
      await button(`${dc.after} · ${dc.download}`, "[data-document-evidence]");
      await wait(
        () => originalDownloads === downloads + 1,
        "Original download did not reach the private endpoint",
      );
      await wait(
        () =>
          evaluate(
            cdp,
            `window.tenderDownloadNames.includes(${JSON.stringify(`tender-${docAfter}.docx`)})`,
          ),
        "DOCX original download lost its validated extension",
      );
      await button(`${dc.after} · ${dc.download}`, "[data-document-evidence]");
      await wait(
        () =>
          evaluate(
            cdp,
            `window.tenderDownloadNames.includes(${JSON.stringify(`tender-${docAfter}.xlsx`)})`,
          ),
        "XLSX original download lost its validated extension",
      );
      docDenied = true;
      await button(tenderCopy[locale].refresh, "[data-document-evidence]");
      await wait(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('[data-document-evidence] [role=alert]')",
          ),
        "Unavailable comparison not shown",
      );
      assert.equal(
        await evaluate(
          cdp,
          "document.querySelector('[data-document-evidence]').innerText.includes('3 references required')",
        ),
        false,
      );
      await audit.check(cdp, "document-denial", "[data-document-evidence]");
      docDenied = false;
      await button(
        dc.title,
        '[data-tender-version="00000000-0000-4000-8000-000000000010"]',
      );
      await wait(
        () =>
          evaluate(
            cdp,
            "document.querySelector('[data-tender-documents]')?.innerText.includes('Prior requirements')",
          ),
        "Historical document set missing",
      );
      await audit.check(cdp, "document-history", "[data-tender-documents]");
      await evaluate(
        cdp,
        "document.querySelector('[data-tender-documents] > summary').click()",
      );
      await button(
        dc.title,
        '[data-tender-version="00000000-0000-4000-8000-000000000010"]',
      );
      await wait(
        () =>
          evaluate(
            cdp,
            "document.querySelector('[data-tender-documents]')?.open",
          ),
        "Repeated history click did not reopen documents",
      );
      await button(
        `${tenderCopy[locale].current} · ${dc.title}`,
        "[data-tender-dossier]",
      );
    }
    if (
      await evaluate(
        cdp,
        "document.querySelector('[data-tender-documents]')?.open",
      )
    )
      await evaluate(
        cdp,
        "document.querySelector('[data-tender-documents] > summary').click()",
      );
    const historySelector = "[data-tender-profile-history]";
    const historyBefore = mutations.length;
    await evaluate(
      cdp,
      `document.querySelector('${historySelector} > summary').click()`,
    );
    await wait(
      () =>
        evaluate(
          cdp,
          "!!document.querySelector('[data-profile-revision=\"12\"]')",
        ),
      "Profile history missing",
    );
    await button(tenderCopy[locale].more, historySelector);
    await wait(
      () =>
        evaluate(
          cdp,
          "!!document.querySelector('[data-profile-revision=\"1\"]')",
        ),
      "Older profile page missing",
    );
    await evaluate(
      cdp,
      "document.querySelector('[data-profile-revision=\"1\"] summary').click()",
    );
    await wait(
      async () => (await text()).includes(tenderHistoryCopy[locale].changed),
      "Profile difference not explained",
    );
    assert.ok((await text()).includes(originalProfile.name));
    assert.equal(
      await evaluate(
        cdp,
        "document.documentElement.scrollWidth <= innerWidth + 1",
      ),
      true,
      `History overflow ${locale}`,
    );
    await audit.check(cdp, `profile-history-${locale}`, historySelector);
    await button(tenderCopy[locale].current, historySelector);
    await wait(
      () =>
        evaluate(
          cdp,
          "!!document.querySelector('[data-profile-revision=\"12\"]')",
        ),
      "Latest profile page missing",
    );
    if (locale === "en-CH") {
      historyFailed = true;
      await button(tenderCopy[locale].refresh, historySelector);
      await wait(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('[data-tender-profile-history] [role=alert]')",
          ),
        "History error not visible",
      );
      assert.equal(
        await evaluate(
          cdp,
          "!!document.querySelector('[data-profile-revision]')",
        ),
        false,
      );
      historyFailed = false;
      await button(tenderCopy[locale].refresh, historySelector);
      await wait(
        () =>
          evaluate(
            cdp,
            "!!document.querySelector('[data-profile-revision=\"12\"]')",
          ),
        "History retry failed",
      );
    }
    assert.equal(
      mutations.length,
      historyBefore,
      "Viewing profile history must not mutate settings",
    );
    await evaluate(
      cdp,
      `document.querySelector('${historySelector} > summary').click()`,
    );
    await openEmail();
    await emailMode("daily_digest");
    await field(pollenDeliveryCopy[locale].digest, "08:45");
    assert.equal(
      await evaluate(
        cdp,
        "document.querySelector('[data-tender-email] button[type=submit]').matches(':disabled')",
      ),
      true,
    );
    await evaluate(
      cdp,
      `Array.from(document.querySelectorAll('[data-tender-email] label')).find(node=>node.textContent.includes(${JSON.stringify(tenderEmailCopy[locale].consent)})).querySelector('input').click()`,
    );
    await button(tenderCopy[locale].saveEdit, "[data-tender-email]");
    await wait(
      () => emailConfiguration.delivery.email === "daily_digest",
      "Email consent not saved",
    );
    await wait(
      () => evaluate(cdp, "!document.querySelector('[data-tender-email]')"),
      "Email settings did not finish refreshing",
    );
    await openEmail();
    await wait(
      async () => (await text()).includes(tenderEmailCopy[locale].active),
      "Active consent not visible",
    );
    await button(tenderEmailCopy[locale].preview, "[data-tender-email]");
    await wait(
      async () => (await text()).includes(tenderEmailCopy[locale].none),
      "Email preview missing",
    );
    await audit.check(cdp, `email-${locale}`, "[data-tender-email]");
    if (locale === "en-CH") {
      await evaluate(
        cdp,
        "document.querySelector('[data-tender-email]').scrollIntoView({block:'start'})",
      );
      await writeFile(
        join(root, "test-results/tender-email-mobile.png"),
        Buffer.from(
          (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
          "base64",
        ),
      );
    }
    await emailMode("off");
    await button(tenderCopy[locale].saveEdit, "[data-tender-email]");
    await wait(
      () => emailConfiguration.delivery.email === "off",
      "Email disable did not save",
    );
    await wait(
      () => evaluate(cdp, "!document.querySelector('[data-tender-email]')"),
      "Email disable did not finish refreshing",
    );
  }
  await writeFile(
    join(root, "test-results/tender-watch-mobile.png"),
    Buffer.from(
      (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
      "base64",
    ),
  );
  await cdp.send("Page.navigate", {
    url: `${base}/tender-watch?monitor=${monitorId}&dossier=${dossierId}&version=00000000-0000-4000-8000-000000000011`,
  });
  await wait(
    async () => (await text()).includes(tenderEmailCopy[locale].older),
    "Email link did not identify the older evidence revision",
  );
  assert.equal(
    await evaluate(
      cdp,
      "document.querySelector('[data-tender-dossier]')?.dataset.tenderDossier",
    ),
    dossierId,
  );
  await audit.check(cdp, "email-evidence-link", "[data-tender-dossier]");
  detail.monitor_id = "00000000-0000-4000-8000-000000000099";
  await cdp.send("Page.reload");
  await wait(
    async () => (await text()).includes(tenderCopy[locale].failed),
    "Mismatched monitor/dossier link did not fail closed",
  );
  assert.equal(
    await evaluate(
      cdp,
      "!!document.querySelector('[data-tender-dossier] fieldset')",
    ),
    false,
  );
  detail.monitor_id = monitorId;
  manager = false;
  await navigate();
  await wait(
    async () => (await text()).includes(tenderCopy[locale].readonly),
    "Viewer guidance missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      `Array.from(document.querySelectorAll('[data-tender-watch] button')).some(button=>button.textContent.trim()===${JSON.stringify(tenderCopy[locale].create)})`,
    ),
    false,
  );
  manager = true;
  sourceEnabled = false;
  monitor.status = "paused";
  await navigate();
  await wait(
    async () => (await text()).includes(tenderCopy[locale].sourceOff),
    "Source gate missing",
  );
  assert.equal(
    await evaluate(
      cdp,
      `Array.from(document.querySelectorAll('[data-tender-watch] button')).find(button=>button.textContent.trim()===${JSON.stringify(tenderCopy[locale].resume)})?.disabled`,
    ),
    true,
  );
  assert.deepEqual(exceptions, []);
  audit.finish(36);
  console.log(
    "Tender browser passed: profile plan/save/start, public context, follow/decisions/material review, evidence failure recovery, pause/edit/resume, five locales, mobile and viewer/source gates.",
  );
} catch (error) {
  console.error(
    JSON.stringify({
      text: cdp ? await text().catch(() => "") : "",
      mutations,
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
  assert.ok(basename(profile).startsWith("helvetic-tender-qa-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
