// Real production UI with intercepted synthetic API responses. No live backend.
import assert from "node:assert/strict";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
const accessibility = new AccessibilityAudit("digest-interests");
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-digests-browser-"));
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
async function waitFor(check, message) {
  for (let i = 0; i < 150; i++) {
    if (await check().catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}

let locale = "en-CH",
  revision = 1,
  invalid = false;
let preference;
let offlineMode = null;
const defaultPreference = () => ({
  enabled: false,
  frequency: "weekly",
  severities: ["unknown"],
  sources: [],
  next_delivery_at: null,
  last_sent_at: null,
});
function response(cursor = "") {
  const index = cursor ? Number(cursor.split(":")[1]) : 0;
  const stamp = `2026-09-05T${String(8 + revision).padStart(2, "0")}:00:00Z`;
  return {
    preference,
    source_options: ["fedlex"],
    delivery_mode: "disabled",
    deliveries: [{id:"synthetic-quiet-delivery",status:"queued",deferred_reason:"quiet_hours",item_count:0,created_at:"2026-09-05T08:00:00Z",summary:{events:[]}}],
    preview: {
      events:
        index < 2
          ? []
          : [
              {
                brief: offlineMode ? { status: "runtime_unverified", locale: locale.slice(0,2) } : {
                  status:"available", locale:locale.slice(0,2), assessment_id:"synthetic-saved-brief", saved_at:stamp,
                  what_happened:{text:"Synthetic saved AI brief <script>not executable</script>",evidence_ids:["e1"]},
                  importance:{text:"Synthetic organization relevance, not a legal conclusion.",level:"low",evidence_ids:["e1"]},
                  next_step:{text:"No action now; retain this source for review.",kind:"no_action_now",evidence_ids:["e1"]},
                  why_in_radar:[{interest_id:"match-one",name:"Saved naturalisation interest",text:"A saved explanation of the topic match.",evidence_ids:["e1"]}],
                  more_reasons:true,uncertainty:"Synthetic fixture only.",input_limitations:[],
                  evidence_links:{e1:"/corpus-evidence/synthetic-version?passage=article-1"},
                },
                event_id: "synthetic-match",
                title: "Synthetic matching event",
                source: "fedlex",
                severity: "unknown",
                detected_at: "2026-09-05T08:00:00Z",
                source_url: null,
                impacts: [],
                event_url: "/?event=synthetic-match",
                topics: [{topic_id:"topic-one",match_id:"match-one",name:"Saved naturalisation interest",confidence:"high",matched_at:"2026-09-05T08:00:00Z",terms:["citizenship","naturalisation"]}],
                topics_truncated: true,
                monitored_documents: [{law_id:"law-one",name:"Directly watched synthetic law"}],
                monitored_documents_truncated: true,
              },
            ],
      truncated: false,
      ai_runtime_unverified: offlineMode !== null,
      severity_filter_deferred: offlineMode === "filtered",
      counts_scope: "page",
      scanned_event_count: index < 2 ? 50 : 21,
      period_start: "2026-08-29T08:00:00Z",
      period_end: stamp,
      has_more: index < 2,
      current_cursor: `${revision}:${index}`,
      next_cursor: index < 2 ? `${revision}:${index + 1}` : null,
    },
  };
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
    requests.push({
      method: request.method,
      path: url.pathname + url.search,
      body: request.postData,
    });
    let body = {},
      code = 200;
    if (url.pathname === "/api/auth/session")
      body = {
        authenticated: true,
        user: { id: "qa", email: "qa@example.invalid", name: "QA", locale },
        organization: { id: "qa-org", name: "Isolated QA" },
        role: "viewer",
      };
    else if (url.pathname === "/api/health")
      body = {
        status: "ok",
        database: "sqlite",
        apertus: { configured: false, model: "qa" },
        firecrawl: { configured: false },
        private_sources_enabled: false,
      };
    else if (url.pathname === "/api/jobs") body = [];
    else if (
      url.pathname === "/api/digests" ||
      url.pathname === "/api/digests/preferences"
    ) {
      const cursor = url.searchParams.get("cursor") || "";
      if (url.searchParams.get("preview_page") !== "true") {
        code = 500;
        body = { detail: "Unbounded preview used" };
      } else if (request.method === "PUT") {
        preference = { ...preference, ...JSON.parse(request.postData) };
        revision++;
        body = response();
      } else if (
        cursor &&
        (invalid || Number(cursor.split(":")[0]) !== revision)
      ) {
        code = 422;
        body = { code: "invalid_digest_cursor", detail: "Restart preview" };
      } else body = response(cursor);
      await sleep(100); // Exercise a real pending page/save, including disabled controls.
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
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }],
  });
  async function click(selector) {
    await evaluate(
      cdp,
      `document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center',inline:'nearest'})`,
    );
    await evaluate(
      cdp,
      `new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`,
    );
    const point = await evaluate(
      cdp,
      `(() => { const el=document.querySelector(${JSON.stringify(selector)}); const r=el.getBoundingClientRect(); const x=r.left+r.width/2,y=r.top+r.height/2; return {x,y,hit:el.contains(document.elementFromPoint(x,y)),disabled:el.disabled}; })()`,
    );
    assert.ok(point.hit && !point.disabled, `Unreachable control: ${selector}`);
    await cdp.send("Input.dispatchMouseEvent", {
      type: "mousePressed",
      x: point.x,
      y: point.y,
      button: "left",
      clickCount: 1,
    });
    await cdp.send("Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x: point.x,
      y: point.y,
      button: "left",
      clickCount: 1,
    });
  }
  const ready = () =>
    evaluate(
      cdp,
      `!!document.querySelector('[data-digest-navigation]') && !document.querySelector('[data-digest-preview]').matches('[aria-busy="true"]')`,
    );
  const form = () =>
    evaluate(
      cdp,
      `(() => { const f=document.querySelector('main fieldset'); return {enabled:f.querySelector('input[type=checkbox]').checked, frequency:f.querySelector('select').value}; })()`,
    );
  for (locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    for (const width of [390, 1440]) {
      revision = 1;
      invalid = false;
      offlineMode = null;
      preference = defaultPreference();
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: width < 500,
      });
      const start = requests.length;
      await cdp.send("Page.navigate", {
        url: `${base}/digests?locale=${locale}`,
      });
      await waitFor(ready, "Digest preview failed to render");
      assert.equal(
        await evaluate(cdp, `document.documentElement.lang`),
        locale,
      );
      const firstText = await evaluate(
        cdp,
        `document.querySelector('[data-digest-navigation]').innerText`,
      );
      assert.ok(
        firstText.includes("0") &&
          firstText.includes("50") &&
          !firstText.includes("digestPage."),
      );
      await sleep(350);
      assert.equal(
        requests.slice(start).filter((r) => r.path.startsWith("/api/digests"))
          .length,
        1,
        "A sparse page must not automatically exhaust the period",
      );
      await evaluate(cdp, `(() => {
        const set = (selector,value) => {const input=document.querySelector(selector); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,value); input.dispatchEvent(new Event('input',{bubbles:true})); input.dispatchEvent(new Event('change',{bubbles:true}));};
        set('[data-quiet-start]','22:00'); set('[data-quiet-end]','07:00'); set('[data-digest-time]','08:15'); set('[data-digest-zone]','Europe/Zurich');
      })()`);
      assert.ok(await evaluate(cdp, `!document.querySelector('[data-digest-schedule]').innerText.includes('digestSchedule.')`), "Untranslated schedule copy");
      assert.ok(await evaluate(cdp, `document.querySelector('[data-digest-quiet-wait]').innerText.length > 20 && !document.querySelector('[data-digest-quiet-wait]').innerText.includes('digestQuiet.')`));
      assert.ok(await evaluate(cdp, `!document.querySelector('[data-digest-quiet]').innerText.includes('digestQuiet.')`));
      await click("main fieldset input[type=checkbox]");
      assert.equal((await form()).enabled, true);
      await click("[data-digest-next]");
      await waitFor(
        async () =>
          (await ready()) &&
          requests.slice(start).some((r) => r.path.includes("cursor=1%3A1")),
        "First continuation missing",
      );
      assert.equal(
        (await form()).enabled,
        true,
        "Paging overwrote unsaved preference",
      );
      assert.equal(
        await evaluate(
          cdp,
          `document.activeElement === document.querySelector('[data-digest-preview] h2')`,
        ),
        true,
        "Paging lost keyboard focus",
      );
      await click("[data-digest-next]");
      await waitFor(
        async () =>
          (await ready()) &&
          (await evaluate(
            cdp,
            `document.body.innerText.includes('Synthetic matching event')`,
          )),
        "Sparse continuation never reached its match",
      );
      assert.ok(await evaluate(cdp, `document.querySelector('[data-digest-interests]').innerText.includes('citizenship')`), 'Saved matching reasons missing');
      assert.equal(await evaluate(cdp, `document.querySelector('[data-digest-interests] a[href^="/topic-review"]').getAttribute('href')`), '/topic-review?match=match-one');
      assert.ok(await evaluate(cdp, `Array.from(document.querySelectorAll('[data-digest-interests] a')).some(a=>a.getAttribute('href')==='/?event=synthetic-match')`));
      assert.ok(await evaluate(cdp, `Array.from(document.querySelectorAll('[data-digest-interests] a')).every(a=>a.getBoundingClientRect().height>=44)`));
      await accessibility.check(cdp, `digest-interests-${locale}-${width}`, '[data-digest-interests]');
      assert.equal(await evaluate(cdp, `document.querySelector('[data-digest-brief] [lang]').lang`), locale.slice(0,2));
      assert.ok(await evaluate(cdp, `document.querySelector('[data-digest-brief]').innerText.includes('Synthetic saved AI brief <script>not executable</script>')`));
      assert.equal(await evaluate(cdp, `document.querySelectorAll('[data-digest-brief] script').length`), 0);
      assert.equal(await evaluate(cdp, `document.querySelector('[data-digest-brief] a').getAttribute('href')`), '/corpus-evidence/synthetic-version?passage=article-1');
      await click('[data-digest-brief] details summary');
      assert.ok(await evaluate(cdp, `document.querySelector('[data-digest-brief] details').innerText.includes('Saved naturalisation interest')`));
      assert.ok(await evaluate(cdp, `document.documentElement.scrollWidth<=innerWidth+1`));
      await accessibility.check(cdp, `digest-brief-${locale}-${width}`, '[data-digest-brief]');
      // Existing shell context/conversation bootstrap is not a generation call.
      const shellSetup = new Set(['/api/assistant/context','/api/assistant/conversations']);
      assert.equal(requests.slice(start).filter(r=>(r.method==='POST'&&!shellSetup.has(r.path))||r.path.includes('/brief')).length,0,'Digest reading must not generate, enqueue, or make per-event AI requests');
      if (locale === "en-CH") {
        await mkdir(join(root, "test-results/digest-preview"), {recursive:true});
        await evaluate(cdp, `document.querySelector('[data-digest-brief]').scrollIntoView({block:'center'})`);
        await sleep(150);
        const shot = await cdp.send("Page.captureScreenshot", {format:"png"});
        await writeFile(join(root, `test-results/digest-preview/interests-${width}.png`), Buffer.from(shot.data,"base64"));
      }
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('[data-digest-next]').disabled`,
        ),
        true,
      );
      await click("[data-digest-back]");
      await waitFor(ready, "Back to middle page failed");
      await click("[data-digest-back]");
      await waitFor(ready, "Back to pinned first page failed");
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('[data-digest-navigation]').innerText`,
        ),
        firstText,
      );
      await click("[data-digest-save]");
      await waitFor(
        async () =>
          (await ready()) &&
          requests.slice(start).some((r) => r.method === "PUT") &&
          (await evaluate(
            cdp,
            `!document.querySelector('main fieldset').disabled`,
          )),
        "Saved preferences did not produce a new bounded preview",
      );
      assert.equal((await form()).enabled, true);
      assert.equal(await evaluate(cdp, `document.querySelector('[data-digest-time]').value`), '08:15', 'Paging/save replaced local time');
      const saved = requests.slice(start).find((r) => r.method === "PUT");
      assert.deepEqual(JSON.parse(saved.body), {
        enabled: true,
        frequency: "weekly",
        schedule: {timezone:"Europe/Zurich",time:"08:15",quiet_start:"22:00",quiet_end:"07:00"},
        severities: ["unknown"],
        sources: [],
      });
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelector('[data-digest-back]').disabled`,
        ),
        true,
      );
      invalid = true;
      await click("[data-digest-next]");
      await waitFor(
        () =>
          evaluate(
            cdp,
            `!document.querySelector('[data-digest-navigation]') && !!document.querySelector('[data-digest-recovery]') && !document.body.innerText.includes('error.invalid_digest_cursor')`,
          ),
        "Stale cursor error did not offer recovery",
      );
      invalid = false;
      await click("[data-digest-recovery]");
      await waitFor(ready, "Restart failed");
      assert.equal(
        (await form()).enabled,
        true,
        "Recovery overwrote current choices",
      );
      assert.ok(
        await evaluate(
          cdp,
          `document.documentElement.scrollWidth <= innerWidth + 1`,
        ),
        `${locale} overflow at ${width}px`,
      );
      assert.equal(
        await evaluate(
          cdp,
          `Array.from(document.querySelectorAll('[data-digest-navigation] button')).filter(el=>el.getBoundingClientRect().height<44).length`,
        ),
        0,
        "Small touch controls",
      );
      const calls = requests
        .slice(start)
        .filter((r) => r.path.startsWith("/api/digests"));
      assert.ok(calls.every((r) => r.path.includes("preview_page=true")));
      assert.equal(
        calls.filter((r) => r.method !== "GET" && r.method !== "PUT").length,
        0,
      );
      if (locale === "en-CH") {
        await evaluate(
          cdp,
          `document.querySelector('[data-digest-navigation]').scrollIntoView({block:'center'})`,
        );
        await mkdir(join(root, "test-results/digest-preview"), {
          recursive: true,
        });
        const shot = await cdp.send("Page.captureScreenshot", {
          format: "png",
        });
        await writeFile(
          join(root, `test-results/digest-preview/preview-${width}.png`),
          Buffer.from(shot.data, "base64"),
        );
      }
      for (offlineMode of ["sources", "filtered"]) {
        preference.severities = offlineMode === "filtered" ? ["high"] : ["unknown"];
        await cdp.send("Page.navigate", { url: `${base}/digests?locale=${locale}` });
        await waitFor(ready, "Offline preview failed to render");
        assert.equal(await evaluate(cdp, `document.querySelectorAll('[data-digest-runtime] p').length`), offlineMode === "filtered" ? 2 : 1);
        assert.ok(await evaluate(cdp, `document.querySelector('[data-digest-runtime]').innerText.length > 50`));
        assert.ok(await evaluate(cdp, `document.documentElement.scrollWidth<=innerWidth+1`));
        assert.equal(await evaluate(cdp, `document.querySelector('[data-digest-coverage] a').getAttribute('href')`), '/');
        await accessibility.check(cdp, `digest-offline-${offlineMode}-${locale}-${width}`, '[data-digest-runtime]');
        if (locale === "en-CH") {
          await evaluate(cdp, `document.querySelector('[data-digest-runtime]').scrollIntoView({block:'center'})`);
          const shot = await cdp.send("Page.captureScreenshot", {format:"png"});
          await writeFile(join(root, `test-results/digest-preview/offline-${offlineMode}-${width}.png`), Buffer.from(shot.data,"base64"));
        }
      }
    }
  }
  assert.equal(
    requests.some((r) => r.path.startsWith("/api/digests/send")),
    false,
  );
  assert.deepEqual(exceptions, []);
  await accessibility.finish(40);
  console.log(
    "Digest production UI: 10 journeys (DE/FR/IT/RM/EN x 390/1440px), plus 20 offline source/filter states; bounded sparse next/back, captured period, focus, unsaved choices and local delivery clock, explicit schedule save, stale-cursor recovery and touch targets pass. All API calls intercepted; no mail, inference or production data touched.",
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
  assert.ok(basename(profile).startsWith("helvetic-digests-browser-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
