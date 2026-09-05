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
const profile = await mkdtemp(join(tmpdir(), "helvetic-topics-browser-"));
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
let viewer = false;
let qaUser = "qa",
  qaOrganization = "qa-org",
  saveFailure = false;
const plan = {
  name: "Synthetic long topic — Datenschutz und parlamentarische Entwicklungen / protection des données",
  goal: "Follow fictional privacy developments in the saved organization corpus.",
  concepts: ["privacy"],
  synonyms: ["data protection"],
  exclusions: ["sport"],
  jurisdictions: ["CH"],
  languages: ["de", "fr", "it", "rm", "en"],
  source_pack_ids: ["fedlex-legislation"],
  document_kinds: ["act"],
  event_kinds: ["amended"],
  importance_floor: "low",
};
const topic = (i) => ({
  id: `topic-${i}`,
  status: "active",
  current_revision: 3,
  created_at: "2026-09-05T08:00:00Z",
  updated_at: "2026-09-05T08:00:00Z",
  plan: { ...plan, name: `${plan.name} ${i}` },
  revisions: [],
});
const savedTopics = Array.from({ length: 30 }, (_, i) => topic(i));
const enabledPack = {
  id: "fedlex-legislation",
  name: {
    "en-CH": "Synthetic federal law sources",
    "de-CH": "Synthetische Bundesrechtsquellen",
    "fr-CH": "Sources fédérales synthétiques",
    "it-CH": "Fonti federali sintetiche",
    "rm-CH": "Funtaunas federalas sinteticas",
  },
  subscription: { enabled: true },
};
const otherPack = {
  id: "parliament-business",
  name: {
    "en-CH": "Synthetic parliamentary sources",
    "de-CH": "Synthetische Parlamentsquellen",
    "fr-CH": "Sources parlementaires synthétiques",
    "it-CH": "Fonti parlamentari sintetiche",
    "rm-CH": "Funtaunas parlamentaras sinteticas",
  },
  subscription: { enabled: false },
};
let previewFailure = false;
let dialogAccept = false;
const dialogs = [];
async function waitFor(check, message) {
  for (let i = 0; i < 150; i++) {
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
    exceptions.push(
      exceptionDetails.exception?.description || exceptionDetails.text,
    ),
  );
  cdp.on("Page.javascriptDialogOpening", async ({ type, message }) => {
    dialogs.push({ type, message });
    await cdp.send("Page.handleJavaScriptDialog", { accept: dialogAccept });
  });
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url);
    requests.push({
      path: url.pathname,
      method: request.method,
      body: request.postData ? JSON.parse(request.postData) : null,
    });
    let body = {},
      code = 200;
    if (url.pathname === "/api/auth/session")
      body = {
        authenticated: true,
        user: { id: qaUser, name: "QA", email: "qa@example.invalid", locale },
        organization: { id: qaOrganization, name: "Synthetic QA" },
        role: viewer ? "viewer" : "organization_admin",
        platform_admin: false,
      };
    else if (url.pathname === "/api/health")
      body = {
        status: "ok",
        database: "qa",
        apertus: { configured: false, model: "qa" },
        firecrawl: { configured: false },
        private_sources_enabled: false,
      };
    else if (url.pathname === "/api/source-packs")
      body = { items: [enabledPack, otherPack] };
    else if (url.pathname === "/api/monitoring-topics/preview") {
      await sleep(300);
      if (previewFailure) {
        code = 422;
        body = { detail: "Synthetic preview validation failure" };
      } else
        body = {
          candidate_count: 0,
          scanned_event_count: 0,
          scan_limit: 500,
          result_limit: 10,
          items: [],
          sample_complete: true,
          sample_captured_at: "2026-09-05T08:00:00Z",
          total_available_events: 0,
        };
    } else if (
      url.pathname === "/api/monitoring-topics" &&
      request.method === "POST"
    ) {
      code = saveFailure ? 503 : 201;
      body = saveFailure
        ? { detail: "Synthetic interrupted activation" }
        : topic("new");
    } else if (
      url.pathname.startsWith("/api/monitoring-topics/") &&
      request.method === "PUT"
    )
      body = topic(29);
    else if (url.pathname === "/api/monitoring-topics") body = savedTopics;
    else if (url.pathname === "/api/jobs") body = [];
    else {
      code = 503;
      body = { detail: "Synthetic QA endpoint unavailable" };
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
  const fill = async (name, value) => {
    await evaluate(
      cdp,
      `(() => {const input=document.querySelector('[name="${name}"]'); const proto=input.tagName==='TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto,'value').set.call(input,${JSON.stringify(value)}); input.dispatchEvent(new Event('input',{bubbles:true}));})()`,
    );
  };
  const click = async (selector) => {
    await evaluate(
      cdp,
      `new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))`,
    );
    const point = await evaluate(
      cdp,
      `(() => {const el=document.querySelector(${JSON.stringify(selector)}); el.scrollIntoView({block:'center'}); const r=el.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2; return {x,y,visible:r.width>0&&r.height>0&&el.contains(document.elementFromPoint(x,y))};})()`,
    );
    assert.ok(point.visible, `Control not reachable by pointer: ${selector}`);
    for (const type of ["mousePressed", "mouseReleased"])
      await cdp.send("Input.dispatchMouseEvent", {
        type,
        x: point.x,
        y: point.y,
        button: "left",
        clickCount: 1,
      });
  };
  const previewRequests = () =>
    requests.filter((r) => r.path === "/api/monitoring-topics/preview");
  for (const selectedLocale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    locale = selectedLocale;
    for (const width of [390, 1440]) {
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 844,
        deviceScaleFactor: 1,
        mobile: width < 500,
      });
      await cdp.send("Page.navigate", {
        url: `${base}/topics?qa=${locale}-${width}`,
      });
      await waitFor(
        () =>
          evaluate(
            cdp,
            `document.querySelectorAll('[data-topic-edit]').length === 30 && document.documentElement.lang === ${JSON.stringify(locale)}`,
          ),
        "Required saved-topic/locale fixture missing",
      );
      assert.ok(
        await evaluate(
          cdp,
          `!document.querySelector('[data-topic-scope-options]').open && !document.querySelector('[data-topic-matching-options]').open`,
        ),
      );
      assert.ok(
        await evaluate(
          cdp,
          `document.querySelector('[data-topic-scope]').textContent.includes(${JSON.stringify(enabledPack.name[locale])}) && !document.querySelector('[data-topic-scope]').textContent.includes(${JSON.stringify(otherPack.name[locale])})`,
        ),
        "Only already enabled packs should be selected by default",
      );
      await fill("topic-name", "Synthetic manual interest");
      await fill("topic-goal", "Follow privacy in the saved events.");
      await fill("topic-concepts", "privacy, naturalisation");
      await click("[data-topic-scope-options] summary");
      assert.ok(
        await evaluate(
          cdp,
          `Array.from(document.querySelectorAll('[data-topic-scope-options] input[type="checkbox"]')).every(c=>c.parentElement.textContent.trim().length > 2 && !c.parentElement.textContent.includes('_'))`,
        ),
        "Raw kind identifiers leaked into choices",
      );
      await click(
        '[data-topic-scope-options] input[value="fedlex-legislation"]',
      );
      await sleep(2300); // Includes the real resource poll; it must not reselect options.
      assert.ok(
        await evaluate(
          cdp,
          `!document.querySelector('[data-topic-scope-options] input[value="fedlex-legislation"]').checked`,
        ),
        "Catalogue polling undid a user's cleared selection",
      );
      await click("[data-topic-scope-options] summary");
      const count = previewRequests().length;
      await click('.monitoring-topic-builder button[type="submit"]');
      await waitFor(
        () =>
          evaluate(
            cdp,
            `document.querySelector('[data-topic-scope-options]').open && !!document.querySelector('.monitoring-topic-builder [role="alert"]')`,
          ),
        "Invalid hidden scope was not exposed with an error",
      );
      assert.equal(
        previewRequests().length,
        count,
        "Invalid scope should be corrected before a preview request",
      );
      await click(
        '[data-topic-scope-options] input[value="fedlex-legislation"]',
      );
      await click("[data-topic-scope-options] summary");
      await click('.monitoring-topic-builder button[type="submit"]');
      await waitFor(
        () =>
          evaluate(
            cdp,
            `document.querySelector('.monitoring-topic-builder fieldset').disabled`,
          ),
        "Pending preview did not protect the submitted draft",
      );
      await waitFor(
        () =>
          evaluate(
            cdp,
            `!!document.querySelector('[data-topic-preview]') && !!document.querySelector('[data-topic-save]')`,
          ),
        "Manual no-AI preview failed",
      );
      const sent = previewRequests().at(-1).body;
      assert.deepEqual(sent.concepts, ["privacy", "naturalisation"]);
      assert.deepEqual(sent.source_pack_ids, ["fedlex-legislation"]);
      assert.ok(
        sent.languages.length === 5 &&
          sent.document_kinds.includes("act") &&
          sent.event_kinds.includes("amended"),
      );
      assert.equal(sent.goal, "Follow privacy in the saved events.");
      const postsBefore = requests.filter(
        (r) => r.path === "/api/monitoring-topics" && r.method === "POST",
      ).length;
      await click("[data-topic-save]");
      await waitFor(
        () =>
          requests.filter(
            (r) => r.path === "/api/monitoring-topics" && r.method === "POST",
          ).length ===
          postsBefore + 1,
        "Explicit manual activation did not submit",
      );
      await waitFor(
        () =>
          evaluate(
            cdp,
            `!document.querySelector('[data-topic-save]') && !document.querySelector('.monitoring-topic-builder fieldset').disabled`,
          ),
        "Activation did not reset the editor",
      );
      const saved = requests
        .filter(
          (r) => r.path === "/api/monitoring-topics" && r.method === "POST",
        )
        .at(-1).body;
      assert.ok(saved.idempotency_key);
      assert.equal(saved.ai_draft_id, undefined);
      // Reproduce editing from the bottom of the scrollable main, not window.
      await evaluate(
        cdp,
        `document.querySelector('[data-topic-edit="topic-29"]').scrollIntoView({block:'center'})`,
      );
      assert.ok(
        await evaluate(
          cdp,
          `document.querySelector('.monitoring-topic-builder').getBoundingClientRect().bottom < 0`,
        ),
        "Edit fixture is not genuinely below the form",
      );
      await click('[data-topic-edit="topic-29"]');
      await waitFor(
        () =>
          evaluate(
            cdp,
            `document.activeElement.name === 'topic-name' && document.querySelector('.monitoring-topic-builder').getBoundingClientRect().top >= document.querySelector('.topbar').getBoundingClientRect().bottom && document.querySelector('.monitoring-topic-builder').getBoundingClientRect().top < 200`,
          ),
        "Edit did not focus/reveal the loaded form in the main scroller",
      );
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('[name="topic-name"]').value`,
        ),
        topic(29).plan.name,
      );
      // Four explicit discard decisions per locale/width; no backend write.
      const guardStart = dialogs.length;
      await fill("topic-goal", "Do not lose this edited topic draft.");
      assert.ok(
        await evaluate(cdp, `!!document.querySelector('[data-topic-unsaved]')`),
      );
      dialogAccept = false;
      await click('[data-topic-edit="topic-0"]');
      await waitFor(
        () => dialogs.length === guardStart + 1,
        "Switching topics did not ask about unsaved edits",
      );
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('[name="topic-goal"]').value`,
        ),
        "Do not lose this edited topic draft.",
      );
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('[name="topic-name"]').value`,
        ),
        topic(29).plan.name,
      );
      dialogAccept = true;
      await click('[data-topic-edit="topic-0"]');
      await waitFor(
        () =>
          evaluate(
            cdp,
            `document.querySelector('[name="topic-name"]').value === ${JSON.stringify(topic(0).plan.name)}`,
          ),
        "Accepted discard did not switch topics",
      );
      assert.equal(dialogs.length, guardStart + 2);
      await click('[data-topic-edit="topic-29"]');
      assert.equal(
        dialogs.length,
        guardStart + 2,
        "An unchanged saved plan prompted unnecessarily",
      );
      await fill("topic-goal", "Keep this text when cancelling a new topic.");
      dialogAccept = false;
      await click("[data-topic-new]");
      await waitFor(
        () => dialogs.length === guardStart + 3,
        "Starting a new topic did not protect the draft",
      );
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('[name="topic-goal"]').value`,
        ),
        "Keep this text when cancelling a new topic.",
      );
      dialogAccept = true;
      await click("[data-topic-new]");
      await waitFor(
        () =>
          evaluate(
            cdp,
            `document.querySelector('[name="topic-name"]').value === '' && !document.querySelector('[data-topic-unsaved]')`,
          ),
        "Accepted new topic did not reset the baseline",
      );
      assert.equal(dialogs.length, guardStart + 4);
      await click('[data-topic-edit="topic-29"]');
      await fill("topic-goal", "Temporary change");
      await fill("topic-goal", topic(29).plan.goal);
      await click('[data-topic-edit="topic-0"]');
      assert.equal(
        dialogs.length,
        guardStart + 4,
        "Reverting a change still caused a discard prompt",
      );
      await click('[data-topic-edit="topic-29"]');
      // A real accepted reload loses React memory, but requires explicit recovery.
      await fill("topic-goal", `Recover this ${locale} ${width} edit.`);
      await waitFor(
        () =>
          evaluate(
            cdp,
            `!!document.querySelector('[data-topic-tab-saved]') && Object.keys(sessionStorage).some(key=>key.startsWith('helvetic-topic-tab-v1:'))`,
          ),
        "Tab draft was not stored",
      );
      const writesBeforeRecovery = requests.filter(
        (r) =>
          r.method !== "GET" && r.path.startsWith("/api/monitoring-topics"),
      ).length;
      dialogAccept = true;
      await cdp.send("Page.reload");
      await waitFor(
        () =>
          evaluate(
            cdp,
            `!!document.querySelector('[data-topic-recovery]') && document.querySelector('.monitoring-topic-builder fieldset').disabled`,
          ),
        "Reload did not offer a saved draft",
      );
      assert.equal(
        requests.filter(
          (r) =>
            r.method !== "GET" && r.path.startsWith("/api/monitoring-topics"),
        ).length,
        writesBeforeRecovery,
        "Recovery must not submit or ask AI",
      );
      assert.ok(
        await evaluate(cdp, `!document.querySelector('[data-topic-save]')`),
      );
      if (locale === "en-CH") {
        await mkdir(join(root, "test-results/topic-editor"), {
          recursive: true,
        });
        const shot = await cdp.send("Page.captureScreenshot", {
          format: "png",
        });
        await writeFile(
          join(root, "test-results/topic-editor", `recovery-${width}.png`),
          Buffer.from(shot.data, "base64"),
        );
      }
      await click("[data-topic-restore]");
      await waitFor(
        () =>
          evaluate(
            cdp,
            `document.activeElement.name === 'topic-name' && !document.querySelector('[data-topic-recovery]')`,
          ),
        "Restored draft did not focus editor",
      );
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('[name="topic-goal"]').value`,
        ),
        `Recover this ${locale} ${width} edit.`,
      );
      assert.ok(
        await evaluate(
          cdp,
          `!!document.querySelector('[data-topic-unsaved]') && !document.querySelector('[data-topic-save]')`,
        ),
      );
      // Restoring preserves the loaded baseline; reverting clears storage.
      await fill("topic-goal", topic(29).plan.goal);
      await waitFor(
        () =>
          evaluate(
            cdp,
            `!document.querySelector('[data-topic-unsaved]') && !Object.keys(sessionStorage).some(key=>key.startsWith('helvetic-topic-tab-v1:'))`,
          ),
        "Reverted recovered draft was not cleared",
      );
      if (locale === "en-CH") {
        await mkdir(join(root, "test-results/topic-editor"), {
          recursive: true,
        });
        const shot = await cdp.send("Page.captureScreenshot", {
          format: "png",
        });
        await writeFile(
          join(root, `test-results/topic-editor/editor-${width}.png`),
          Buffer.from(shot.data, "base64"),
        );
      }
      assert.ok(
        await evaluate(
          cdp,
          `document.documentElement.scrollWidth <= innerWidth + 1 && document.querySelector('.main').scrollWidth <= document.querySelector('.main').clientWidth + 1`,
        ),
        "Topic editor overflows horizontally",
      );
    }
  }
  // A server validation failure must leave the user's edited plan intact.
  previewFailure = true;
  await fill("topic-goal", "Keep this revised goal after a failed preview.");
  await click('.monitoring-topic-builder button[type="submit"]');
  await waitFor(
    () =>
      evaluate(
        cdp,
        `!!document.querySelector('.monitoring-topic-builder [role="alert"]') && !document.querySelector('.monitoring-topic-builder fieldset').disabled`,
      ),
    "Failed preview did not recover",
  );
  assert.equal(
    await evaluate(cdp, `document.querySelector('[name="topic-goal"]').value`),
    "Keep this revised goal after a failed preview.",
  );
  dialogAccept = false;
  const beforeReload = dialogs.length;
  await cdp.send("Page.reload");
  await waitFor(
    () => dialogs.length === beforeReload + 1,
    "Dirty draft reload did not raise native beforeunload",
  );
  assert.equal(dialogs.at(-1).type, "beforeunload");
  assert.equal(
    await evaluate(cdp, `document.querySelector('[name="topic-goal"]').value`),
    "Keep this revised goal after a failed preview.",
  );
  previewFailure = false;
  await click('.monitoring-topic-builder button[type="submit"]');
  await waitFor(
    () =>
      evaluate(
        cdp,
        `!!document.querySelector('[data-topic-save]') && !document.querySelector('.monitoring-topic-builder fieldset').disabled`,
      ),
    "Failed draft could not be retried",
  );
  await click("[data-topic-save]");
  await waitFor(
    () => requests.some((r) => r.method === "PUT"),
    "Edited revision did not submit",
  );
  const revision = requests.find((r) => r.method === "PUT");
  assert.equal(revision.path, "/api/monitoring-topics/topic-29");
  assert.equal(revision.body.expected_revision, 3);
  assert.equal(
    revision.body.goal,
    "Keep this revised goal after a failed preview.",
  );
  assert.deepEqual(revision.body.exclusions, ["sport"]);
  assert.deepEqual(revision.body.synonyms, ["data protection"]);
  await waitFor(
    () =>
      evaluate(
        cdp,
        `!document.querySelector('[data-topic-unsaved]') && !document.querySelector('.monitoring-topic-builder fieldset').disabled`,
      ),
    "Saved revision did not release the draft guard",
  );
  // Preserve the activation key across a failed write and real reload.
  await fill("topic-name", "Retry recovered activation");
  await fill(
    "topic-goal",
    "Keep the same explicit activation after connection loss.",
  );
  await fill("topic-concepts", "privacy");
  await click('.monitoring-topic-builder button[type="submit"]');
  await waitFor(
    () =>
      evaluate(
        cdp,
        `!!document.querySelector('[data-topic-save]') && !document.querySelector('.monitoring-topic-builder fieldset').disabled`,
      ),
    "Activation retry preview missing",
  );
  saveFailure = true;
  await click("[data-topic-save]");
  await waitFor(
    () =>
      evaluate(
        cdp,
        `document.querySelector('.monitoring-topic-builder').textContent.includes('Synthetic interrupted activation') && !document.querySelector('.monitoring-topic-builder fieldset').disabled`,
      ),
    "Failed activation lost editable plan",
  );
  const activationKey = requests
    .filter((r) => r.method === "POST" && r.path === "/api/monitoring-topics")
    .at(-1).body.idempotency_key;
  dialogAccept = true;
  await cdp.send("Page.reload");
  await waitFor(
    () => evaluate(cdp, `!!document.querySelector('[data-topic-recovery]')`),
    "Failed activation not recoverable",
  );
  await click("[data-topic-restore]");
  await click('.monitoring-topic-builder button[type="submit"]');
  await waitFor(
    () =>
      evaluate(
        cdp,
        `!!document.querySelector('[data-topic-save]') && !document.querySelector('.monitoring-topic-builder fieldset').disabled`,
      ),
    "Recovered activation needs fresh preview",
  );
  saveFailure = false;
  await click("[data-topic-save]");
  await waitFor(
    () =>
      evaluate(
        cdp,
        `!document.querySelector('[data-topic-unsaved]') && !document.querySelector('.monitoring-topic-builder fieldset').disabled`,
      ),
    "Recovered activation did not save",
  );
  assert.equal(
    requests
      .filter((r) => r.method === "POST" && r.path === "/api/monitoring-topics")
      .at(-1).body.idempotency_key,
    activationKey,
  );
  assert.ok(
    await evaluate(
      cdp,
      `!Object.keys(sessionStorage).some(key=>key.startsWith('helvetic-topic-tab-v1:'))`,
    ),
  );

  // Storage denial is visible; successful recovery remains optional, never automatic.
  await evaluate(
    cdp,
    `window.qaStorageSet = Storage.prototype.setItem; Storage.prototype.setItem = function(){throw new DOMException('Synthetic quota','QuotaExceededError')}`,
  );
  await fill("topic-goal", "Keep this draft in the original account only.");
  await waitFor(
    () =>
      evaluate(cdp, `!!document.querySelector('[data-topic-storage-error]')`),
    "Storage failure was silent",
  );
  assert.ok(
    await evaluate(cdp, `!document.querySelector('[data-topic-tab-saved]')`),
  );
  await evaluate(cdp, `Storage.prototype.setItem = window.qaStorageSet`);
  await fill("topic-name", "Original account draft");
  await waitFor(
    () => evaluate(cdp, `!!document.querySelector('[data-topic-tab-saved]')`),
    "Storage did not recover",
  );
  // Use the actual Next navigation link and browser Back, without a reload.
  await click('a[href="/registry"]');
  await waitFor(
    () => evaluate(cdp, `location.pathname === '/registry'`),
    "Registry navigation did not complete",
  );
  const routeHistory = await cdp.send("Page.getNavigationHistory");
  await cdp.send("Page.navigateToHistoryEntry", {
    entryId: routeHistory.entries[routeHistory.currentIndex - 1].id,
  });
  await waitFor(
    () =>
      evaluate(
        cdp,
        `location.pathname === '/topics' && !!document.querySelector('[data-topic-recovery]')`,
      ),
    "Client route/Back lost the saved draft",
  );
  await click("[data-topic-restore]");
  assert.equal(
    await evaluate(cdp, `document.querySelector('[name="topic-goal"]').value`),
    "Keep this draft in the original account only.",
  );
  qaUser = "another-user";
  await cdp.send("Page.navigate", { url: `${base}/topics?qa=other-user` });
  await waitFor(
    () =>
      evaluate(
        cdp,
        `!!document.querySelector('[name="topic-goal"]') && !document.querySelector('[data-topic-recovery]') && document.querySelector('[name="topic-goal"]').value === ''`,
      ),
    "Another user saw the first account's draft",
  );
  qaUser = "qa";
  qaOrganization = "another-org";
  await cdp.send("Page.navigate", { url: `${base}/topics?qa=other-org` });
  await waitFor(
    () =>
      evaluate(
        cdp,
        `!!document.querySelector('[name="topic-goal"]') && !document.querySelector('[data-topic-recovery]') && document.querySelector('[name="topic-goal"]').value === ''`,
      ),
    "Another organization saw a foreign draft",
  );
  qaOrganization = "qa-org";
  await cdp.send("Page.navigate", { url: `${base}/topics?qa=original-scope` });
  await waitFor(
    () => evaluate(cdp, `!!document.querySelector('[data-topic-recovery]')`),
    "Original account lost its retained draft",
  );
  await click("[data-topic-discard-recovery]");
  await waitFor(
    () =>
      evaluate(
        cdp,
        `!document.querySelector('[data-topic-recovery]') && !Object.keys(sessionStorage).some(key=>key.startsWith('helvetic-topic-tab-v1:'))`,
      ),
    "Explicit discard did not clear the tab draft",
  );
  viewer = true;
  await cdp.send("Page.navigate", { url: `${base}/topics?qa=viewer` });
  await waitFor(
    () =>
      evaluate(
        cdp,
        `!!document.querySelector('[data-topic-history]') && !document.querySelector('.monitoring-topic-builder')`,
      ),
    "Viewer route did not load saved topics",
  );
  assert.ok(
    await evaluate(cdp, `!document.querySelector('[data-topic-edit]')`),
    "Viewer was offered an edit control",
  );
  assert.equal(
    requests.some(
      (r) =>
        r.path.includes("/draft") ||
        (r.path === "/api/source-packs" && r.method !== "GET"),
    ),
    false,
    "Manual topic editing must not call AI or activate source coverage",
  );
  assert.equal(dialogs.filter((d) => d.type === "confirm").length, 40);
  assert.equal(dialogs.filter((d) => d.type === "beforeunload").length, 13);
  assert.deepEqual(exceptions, []);
  console.log(
    "Topic production UI: 10 required five-locale/mobile-desktop journeys passed; progressive scope, localized choices, polling-safe selections, no-AI preview/explicit activation, idempotency, hidden-scope recovery, busy protection, deep-list edit focus, retained failed draft, 40 localized discard decisions, native reload cancellation and 10 accepted reload/explicit restore journeys with no automatic writes; activation retry key recovery, storage denial, actual client navigation/Back, account/organization isolation and explicit discard. All APIs synthetic; no real monitoring/model call.",
  );
} catch (error) {
  console.error({
    exceptions,
    dialogs,
    requests: requests.slice(-10),
    page: cdp
      ? await evaluate(
          cdp,
          `JSON.stringify({url:location.href,active:document.activeElement.tagName,form:document.querySelector('.monitoring-topic-builder')?.innerText})`,
        ).catch(() => "unavailable")
      : null,
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
  assert.ok(basename(profile).startsWith("helvetic-topics-browser-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
