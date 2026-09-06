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
// A populated 200-group fixture is mandatory, not conditional on live data.
const originalCluster = fixture.diff.change_clusters[0];
const originalChange = fixture.diff.items.find(item => item.id === originalCluster.change_ids[0]);
fixture.diff.change_clusters = Array.from({length:200}, (_,index) => index === 0 ? originalCluster : {
  ...structuredClone(originalCluster), id:`qa-material-${index}`, change_ids:[`qa-change-${index}`],
  old_unit_ids:[`qa-old-unit-${index}`], new_unit_ids:[`qa-new-unit-${index}`], ambiguous:index === 199,
});
for (let index=1; index<200; index++) {
  const text = `Art. ${index}. Synthetic multilingual retention obligation: Aufbewahrungspflicht et conservation des pièces justificatives. ${index === 199 ? 'ONLY_LAST_199' : ''} ${'A very long saved legal passage. '.repeat(18)}`;
  fixture.diff.items.push({...structuredClone(originalChange), id:`qa-change-${index}`,
    old:{id:`qa-before-${index}`,page:null,text:`Before ${text}`},new:{id:`qa-after-${index}`,page:null,text:`After ${text}`},
    old_parts:[{kind:'removed',text:`Before ${text}`}],new_parts:[{kind:'added',text:`After ${text}`}],
  });
}
fixture.diff.items.push({...structuredClone(originalChange),id:'qa-extra-change',
  old:{id:'qa-extra-old',page:null,text:'SECOND_CHANGE_ONLY previous rule'},
  new:{id:'qa-extra-new',page:null,text:'SECOND_CHANGE_ONLY current rule'},
  old_parts:[{kind:'removed',text:'SECOND_CHANGE_ONLY previous rule'}],
  new_parts:[{kind:'added',text:'SECOND_CHANGE_ONLY current rule'}],
});
fixture.diff.change_clusters[199].change_ids.push('qa-extra-change');
fixture.diff.classification_counts.substantive = 201;
fixture.diff.material_count = 201;
fixture.diff.counts.modified = 201;
let comparisonFixture = fixture;
const savedAnswer = {id: "qa-saved-answer", type: "question", status: "succeeded", question: "Which record duties changed?", created_at: "2026-09-06T08:00:00Z", last_used_at: null, use_count: 1, model: "synthetic", prompt_revision: 1, coverage: {},
  comparison: {id: fixture.id, mode: fixture.mode, before: {id: fixture.old_version_id, artifact_url: `/api/versions/${fixture.old_version_id}/artifact`}, after: {id: fixture.new_version_id, artifact_url: `/api/versions/${fixture.new_version_id}/artifact`}},
  result: {supported: true, answer: "Synthetic supported answer.", citations: fixture.analysis.result.citations}};
const historyItems = [savedAnswer, {...savedAnswer, id: "qa-failed", status: "failed", error: "Synthetic failure", result: null}, {...savedAnswer, id: "qa-unsupported", result: {...savedAnswer.result, supported: false}}, {...savedAnswer, id: "qa-uncited", result: {...savedAnswer.result, citations: []}}];
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
    else if (url.pathname === `/api/comparisons/${fixture.id}`) body = comparisonFixture;
    else if (url.pathname.endsWith("/ai-history"))
      body = { items: historyItems, total: historyItems.length };
    else if (url.pathname === "/api/monitoring-context") body = {kind: "answer", id: savedAnswer.id, title: fixture.law.name, question: savedAnswer.question, answer_created_at: savedAnswer.created_at, reference_url: `/compare/${fixture.id}?task=ask`, requires_confirmation: true, ai_calls: 0, watches: []};
    else if (url.pathname === "/api/monitoring-topics") body = [];
    else if (url.pathname === "/api/source-packs") body = {items: []};
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
  for (const selectedLocale of ["en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"]) {
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
      const groups = () => evaluate(cdp, `Array.from(document.querySelectorAll('[data-material-group]')).map(node => node.dataset.materialGroup)`);
      const setInput = async (selector,value,tag='HTMLInputElement') => evaluate(cdp, `(() => {const node=document.querySelector(${JSON.stringify(selector)}); Object.getOwnPropertyDescriptor(${tag}.prototype,'value').set.call(node,${JSON.stringify(value)}); node.dispatchEvent(new Event('input',{bubbles:true})); node.dispatchEvent(new Event('change',{bubbles:true}));})()`);
      assert.equal((await groups()).length,5,'Material cards must be bounded before interaction');
      assert.equal(await evaluate(cdp, `document.querySelector('[data-material-page]').options.length`),40);
      assert.equal(await evaluate(cdp, `document.querySelectorAll('[data-material-group] details[open]').length`),0);
      const origin = await evaluate(cdp, 'performance.timeOrigin');
      if (locale === 'en-CH' && width === 390) {
        const seen = new Set();
        for(let page=0;page<40;page++) {
          await setInput('[data-material-page]',String(page),'HTMLSelectElement');
          await waitFor(async () => (await groups())[0] === (page === 0 ? originalCluster.id : `qa-material-${page*5}`),'Material page did not change');
          for(const id of await groups()) {assert.ok(!seen.has(id),'Repeated group'); seen.add(id);}
          assert.equal((await groups()).length,5);
        }
        assert.equal(seen.size,200,'Every saved group must remain reachable');
      } else {
        await setInput('[data-material-page]','39','HTMLSelectElement');
        await waitFor(async () => (await groups())[0] === 'qa-material-195','Last material page unavailable');
      }
      assert.ok(await evaluate(cdp, `document.activeElement === document.querySelector('[data-material-reader] h3')`),'Page movement must focus the reading heading');
      await sleep(200);
      assert.ok(await evaluate(cdp, `document.querySelector('[data-material-reader] h3').getBoundingClientRect().top >= document.querySelector('.comparison-task-tabs').getBoundingClientRect().bottom`),'Sticky navigation covered the focused heading');
      await evaluate(cdp, `document.querySelector('[data-material-evidence]').click()`);
      await waitFor(() => evaluate(cdp, `document.activeElement?.id === 'qa-change-195'`),'Later material group lost exact evidence focus');
      await evaluate(cdp, `document.querySelector('.diff-toolbar .segmented button').click()`);
      await waitFor(async () => (await groups())[0] === 'qa-material-195','Returning from exact evidence lost material page');
      await setInput('[data-material-search]','ONLY_LAST_199');
      await waitFor(async () => (await groups()).length === 1 && (await groups())[0] === 'qa-material-199','Search must include saved text outside the first page');
      assert.ok(await evaluate(cdp, `document.querySelector('[data-material-group] .needs-review-label') !== null`));
      await setInput('[data-material-search]','SECOND_CHANGE_ONLY');
      await waitFor(async () => (await groups()).length === 1 && (await groups())[0] === 'qa-material-199','Search ignored a non-leading exact change');
      await setInput('[data-material-group] select','qa-extra-change','HTMLSelectElement');
      await waitFor(() => evaluate(cdp, `document.activeElement?.id === 'qa-extra-change'`),'Secondary exact change was unreachable');
      await evaluate(cdp, `document.querySelector('.diff-toolbar .segmented button').click()`);
      await waitFor(() => evaluate(cdp, `document.querySelector('[data-material-search]')?.value === 'SECOND_CHANGE_ONLY'`),'Evidence return lost search');
      await setInput('[data-material-search]','no-such-test-phrase');
      await waitFor(() => evaluate(cdp, `!!document.querySelector('[data-material-empty]') && !document.querySelector('[data-material-group]')`),'Missing honest empty search state');
      await evaluate(cdp, `document.querySelector('[data-material-clear]').click()`);
      await waitFor(async () => (await groups()).length === 5,'Clear search did not restore overview');
      assert.ok(await evaluate(cdp, `!document.querySelector('[data-material-reader]').innerText.includes('materialPage.')`),'Untranslated reading controls');
      assert.ok(await evaluate(cdp, `Array.from(document.querySelectorAll('[data-material-reader] button,[data-material-reader] input,[data-material-reader] select')).every(node=>node.getBoundingClientRect().height >= 44)`),'Reading controls need touch targets');
      assert.ok(await evaluate(cdp, `parseFloat(getComputedStyle(document.querySelector('.material-delta p')).fontSize) >= 16`));
      assert.equal(await evaluate(cdp,'performance.timeOrigin'),origin,'Material navigation reloaded the document');
      if(locale === 'en-CH' && width === 390) {
        await evaluate(cdp, `document.querySelector('[data-material-reader]').scrollIntoView()`);
        await sleep(350);
        await capture('material-390');
        await resize(320);
        await evaluate(cdp, `document.documentElement.style.fontSize='32px'; document.querySelector('[data-material-reader]').scrollIntoView()`);
        await capture('material-320-text-zoom');
        assert.ok(await evaluate(cdp, `document.querySelector('[data-material-reader]').scrollWidth <= document.querySelector('[data-material-reader]').clientWidth + 1`),'Material text zoom/reflow overflow');
        await capture('material-320-text-zoom');
        await evaluate(cdp, `document.documentElement.style.fontSize='';`);
        await resize(width);
      }

      await clickTab("ask");
      await waitFor(() => evaluate(cdp, `document.querySelectorAll('#companion-ask [data-monitor-answer]').length === 1`), "Only the succeeded cited answer should offer monitoring");
      assert.ok(await evaluate(cdp, `document.querySelector('#companion-ask [data-monitor-answer] a').getAttribute('href').includes('record=qa-saved-answer')`));
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
      await clickTab("history");
      await evaluate(cdp, `document.querySelectorAll('#companion-history .ai-history-item').forEach(item => item.open = true)`);
      assert.equal(await evaluate(cdp, `document.querySelectorAll('#companion-history [data-monitor-answer]').length`), 1, "History must not offer failed/unsupported/uncited answers");
      if (width === 390) {
        await evaluate(cdp, `document.querySelector('.companion-close').click()`);
        await waitFor(async () => !(await modal()), "History close failed before Ask entry check");
        await clickTab("ask");
      }
      await evaluate(cdp, `document.querySelector('${width === 390 ? "#companion-ask" : "#companion-history"} [data-monitor-answer] a').click()`);
      await waitFor(() => evaluate(cdp, `!!document.querySelector('[data-monitor-saved-question]')`), "History action did not reach saved question context");
      assert.ok(await evaluate(cdp, `location.pathname === '/topics' && location.search.includes('from=answer') && location.search.includes('record=qa-saved-answer') && !location.search.includes('duties')`));
      assert.ok(await evaluate(cdp, `document.querySelector('[data-monitor-saved-question]').innerText.includes('Which record duties changed?')`));
      assert.equal(await evaluate(cdp, `document.querySelector('[name="topic-name"]').value`), "", "Navigation silently activated/copied a topic");
      assert.ok(await evaluate(cdp, `document.documentElement.scrollWidth <= innerWidth + 1`), "Saved question context overflowed on mobile");
      if (locale === "en-CH") await capture(`monitor-from-answer-${width}`);
    }
  }
  // Legacy saved comparisons may have material rows but no cluster metadata.
  comparisonFixture = structuredClone(fixture);
  comparisonFixture.diff.change_clusters = [];
  await resize(390);
  await cdp.send('Page.navigate',{url:`${base}/compare/${fixture.id}`});
  await waitFor(() => evaluate(cdp, `document.querySelectorAll('.diff-row').length === 40 && !!document.querySelector('.pagination')`),'Legacy material rows lost their pager');
  const legacyIds = new Set();
  for(let page=0;page<6;page++) {
    const ids=await evaluate(cdp, `Array.from(document.querySelectorAll('.diff-row')).map(node=>node.id)`);
    for(const id of ids){assert.ok(!legacyIds.has(id));legacyIds.add(id);}
    if(page<5){
      await evaluate(cdp, `document.querySelector('.pagination button:last-child').click()`);
      await waitFor(async()=> (await evaluate(cdp, `document.querySelector('.diff-row')?.id`)) !== ids[0],'Legacy next page did not change');
    }
  }
  assert.equal(legacyIds.size,201,'Legacy material rows must all remain reachable');
  assert.ok(await evaluate(cdp, `document.querySelector('.pagination button:last-child').disabled`));
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
    "Comparison production UI: 200-group navigation/search/evidence/return and 320px text-zoom check, plus 15 populated locale/overlay-width journeys passed; modal focus isolation, forward/back Tab, Escape/close and return focus, draft persistence through close/desktop resize, nonmodal desktop and cited evidence focus, saved-answer-only monitoring buttons in Ask/history and history-to-topic navigation retaining the saved question without implicit copy/activation. All API calls intercepted; no live model or data mutation. Physical keyboard/mobile, screen-reader and other-browser review remain separate.",
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
