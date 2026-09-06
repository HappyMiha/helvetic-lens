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
const profile = await mkdtemp(join(tmpdir(), "helvetic-registry-browser-"));
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

let locale = "en-CH";
let role = "viewer";
let returnJourney=false, hideReturnRow=false;
const row = {
  id: "qa-row",
  event_id: "qa-event",
  record_type: "event",
  event_type: "changed",
  detected_at: "2026-09-05T08:00:00Z",
  title:
    "Synthetic — Verordnung über die Informationssicherheit und den Datenschutz / Protection des données et surveillance des développements parlementaires",
  authority: "Fedlex",
  connector: "fedlex",
  connector_health: "healthy",
  kind: "act",
  languages: ["de", "fr"],
  lifecycle: "unknown",
  impact: "high",
  analysis_state: "pending",
  read: false,
  watched: true,
  why: "Synthetic saved evidence for layout only.",
  linked_laws: [],
  official_dates: {},
  timeline_url: "/laws/qa-law",
  evidence_url: "/corpus-evidence/qa-native",
};
try {
  await waitFor(
    async () => (await fetch(base)).ok,
    "Isolated UI did not start",
  );
  let debugPort;
  await waitFor(async () => {
    debugPort = (
      await readFile(join(profile, "DevToolsActivePort"), "utf8")
    ).split("\n")[0];
    return !!debugPort;
  }, "Browser did not start");
  await pollJson(`http://127.0.0.1:${debugPort}/json/version`);
  const target = await fetch(
    `http://127.0.0.1:${debugPort}/json/new?about:blank`,
    { method: "PUT" },
  ).then((r) => r.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    exceptions.push(exceptionDetails.text),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    const url = new URL(request.url);
    requests.push({ method: request.method, path: url.pathname + url.search });
    let body = {},
      code = 200;
    if (url.pathname === "/api/auth/session")
      body = {
        authenticated: true,
        user: { id: "qa", email: "qa@example.invalid", name: "QA", locale },
        organization: { id: "qa-org", name: "Isolated QA" },
        role,
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
    else if (url.pathname === "/api/registry") {
      const empty = url.searchParams.get("q") === "no-results";
      body = {
        view: url.searchParams.get("view"),
        groups: empty
          ? []
          : [
              {
                name: url.searchParams.has("start") ? "Custom range" : "Today",
                items: returnJourney ? Array.from({length:20},(_,i)=>({...row,id:`qa-return-${i}`,event_id:`qa-event-${i}`,title:`Record ${i}: ${row.title.repeat(i===19?12:1)}`,evidence_url:`/corpus-evidence/qa-native-${i}`})).filter(item=>!hideReturnRow || item.id!=="qa-return-19") : [row],
              },
            ],
        count: empty ? 0 : returnJourney ? 20 : 1,
        next_cursor: url.searchParams.has("cursor") ? null : "next",
      };
    } else if (/^\/api\/regulatory-versions\/qa-native-\d+\/page$/.test(url.pathname)) {
      body={id:url.pathname.split('/')[3],law_id:null,law_name:'Synthetic return evidence',native:true,origin:'official_connector',created_at:'2026-09-06T08:00:00Z',source_url:'https://example.invalid/source',content_type:'text/html',artifact_url:null,declared_date:null,synthetic:true,identity_json:{language:'de'},passages:[{id:'p1',text:'Synthetic saved evidence for registry return.',page:1}],passage_count:1,plain_text:null,pagination:{offset:0,end:1,total:1,size:50,mode:'passages',next_offset:null,previous_offset:null,target_found:null}};
    } else {
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
  async function click(selector) {
    await evaluate(
      cdp,
      `document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center',inline:'nearest'})`,
    );
    await evaluate(
      cdp,
      `new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`,
    );
    const pos = await evaluate(
      cdp,
      `(()=>{const el=document.querySelector(${JSON.stringify(selector)});const r=el.getBoundingClientRect();const x=r.left+r.width/2,y=r.top+r.height/2;return{x,y,hit:el.contains(document.elementFromPoint(x,y)),disabled:el.disabled}})()`,
    );
    assert.ok(pos.hit && !pos.disabled, `Unreachable ${selector}`);
    await cdp.send("Input.dispatchMouseEvent", {
      type: "mousePressed",
      x: pos.x,
      y: pos.y,
      button: "left",
      clickCount: 1,
    });
    await cdp.send("Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x: pos.x,
      y: pos.y,
      button: "left",
      clickCount: 1,
    });
  }
  const ready = () =>
    evaluate(
      cdp,
      `!!document.querySelector('[data-registry-filters]') && !!document.querySelector('main article')`,
    );
  const choose = async (name, value) => {
    await evaluate(
      cdp,
      `(()=>{const el=document.querySelector('select[name="${name}"]');el.value=${JSON.stringify(value)};el.dispatchEvent(new Event('change',{bubbles:true}));})()`,
    );
    await waitFor(
      () =>
        evaluate(
          cdp,
          `new URLSearchParams(location.search).get(${JSON.stringify(name)})===${JSON.stringify(value)}`,
        ),
      "Filter URL did not update",
    );
  };
  for (locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"])
    for (const width of [390, 1440])
      for (const path of ["/registry", "/discover"]) {
        await cdp.send("Emulation.setDeviceMetricsOverride", {
          width,
          height: 900,
          deviceScaleFactor: 1,
          mobile: width < 500,
        });
        await cdp.send("Page.navigate", {
          url: `${base}${path}?locale=${locale}`,
        });
        await waitFor(ready, "Missing required populated registry");
        assert.ok(await evaluate(cdp, `!!document.querySelector('a[href="/corpus-evidence/qa-native"]')`), "Native saved-source link missing from registry");
        await waitFor(
          () =>
            evaluate(
              cdp,
              `document.documentElement.lang===${JSON.stringify(locale)}`,
            ),
          "Locale not applied",
        );
        assert.equal(
          await evaluate(
            cdp,
            `document.querySelector('[data-registry-advanced]').open`,
          ),
          false,
        );
        assert.deepEqual(
          await evaluate(
            cdp,
            `Array.from(document.querySelectorAll('[data-registry-filters] select')).filter(el=>el.checkVisibility()).map(el=>el.name).sort()`,
          ),
          ["impact", "read", "watched"],
        );
        assert.equal(
          await evaluate(
            cdp,
            `document.querySelectorAll('main article button').length`,
          ),
          0,
          "Viewer gained a mutation control",
        );
        const initial = await evaluate(cdp, `location.href`);
        await click('[data-registry-period="today"]');
        await waitFor(
          () =>
            evaluate(cdp, `new URLSearchParams(location.search).has('start')`),
          "Today preset did not set dates",
        );
        const today = await evaluate(
          cdp,
          `new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Zurich',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())`,
        );
        assert.ok(
          await evaluate(
            cdp,
            `new URLSearchParams(location.search).get('start')===${JSON.stringify(today)} && new URLSearchParams(location.search).get('end')===${JSON.stringify(today)}`,
          ),
        );
        await choose("read", "unread");
        assert.ok(
          await evaluate(
            cdp,
            `!!document.querySelector('[data-remove-filter="read"]') && !!document.querySelector('[data-remove-filter="dates"]')`,
          ),
        );
        await click("[data-registry-advanced] summary");
        await waitFor(
          () =>
            evaluate(
              cdp,
              `document.querySelector('[data-registry-advanced]').open`,
            ),
          "Disclosure did not open",
        );
        await choose("authority", "parliament");
        assert.ok(
          await evaluate(
            cdp,
            `!document.body.innerText.includes('registryFilters.') && !!document.querySelector('[data-remove-filter="authority"]')`,
          ),
        );
        const authority = await evaluate(
          cdp,
          `document.querySelector('select[name="authority"] option[value="parliament"]').textContent`,
        );
        if (locale !== "en-CH") assert.notEqual(authority, "Parliament");
        await click('[data-remove-filter="authority"]');
        await waitFor(
          () =>
            evaluate(
              cdp,
              `!new URLSearchParams(location.search).has('authority')`,
            ),
          "Chip removal failed",
        );
        assert.ok(
          await evaluate(
            cdp,
            `new URLSearchParams(location.search).get('read')==='unread' && new URLSearchParams(location.search).has('start')`,
          ),
        );
        await evaluate(cdp, "history.back()");
        await waitFor(
          () =>
            evaluate(
              cdp,
              `new URLSearchParams(location.search).get('authority')==='parliament' && document.querySelector('select[name="authority"]').value==='parliament'`,
            ),
          "Browser back lost filter state",
        );
        await click("[data-registry-clear]");
        await waitFor(
          () => evaluate(cdp, `location.href===${JSON.stringify(initial)}`),
          "Clear removed locale or retained filters",
        );
        await click('[data-registry-filters] input[name="q"]');
        await cdp.send("Input.insertText", { text: "no-results" });
        await cdp.send("Input.dispatchKeyEvent", {
          type: "keyDown",
          key: "Enter",
          code: "Enter",
          windowsVirtualKeyCode: 13,
          text: "\r",
        });
        await cdp.send("Input.dispatchKeyEvent", {
          type: "keyUp",
          key: "Enter",
          code: "Enter",
          windowsVirtualKeyCode: 13,
        });
        await waitFor(
          () =>
            evaluate(
              cdp,
              `!!document.querySelector('[data-registry-empty-clear]')`,
            ),
          "Empty results did not offer recovery",
        );
        await click("[data-registry-empty-clear]");
        await waitFor(ready, "Empty recovery failed");
        await click("[data-registry-advanced] summary"); // Collapse if still open after explicit clear.
        await waitFor(
          () =>
            evaluate(
              cdp,
              `!document.querySelector('[data-registry-advanced]').open`,
            ),
          "Advanced filters did not collapse",
        );
        assert.ok(
          await evaluate(
            cdp,
            `document.documentElement.scrollWidth<=innerWidth+1`,
          ),
          `Overflow ${locale} ${width}`,
        );
        assert.equal(
          await evaluate(
            cdp,
            `Array.from(document.querySelectorAll('[data-registry-period]')).filter(el=>el.getBoundingClientRect().height<44).length`,
          ),
          0,
        );
        if (locale === "en-CH" && path === "/registry") {
          await evaluate(
            cdp,
            `document.querySelector('[data-registry-filters]').scrollIntoView({block:'start'})`,
          );
          await mkdir(join(root, "test-results/registry-filters"), {
            recursive: true,
          });
          const shot = await cdp.send("Page.captureScreenshot", {
            format: "png",
          });
          await writeFile(
            join(root, `test-results/registry-filters/filters-${width}.png`),
            Buffer.from(shot.data, "base64"),
          );
        }
      }
  role = "organization_admin";
  locale = "en-CH";
  await cdp.send("Page.navigate", {
    url: `${base}/registry?locale=en-CH&authority=missing&cursor=old`,
  });
  await waitFor(ready, "Deep-link fixture missing");
  await waitFor(
    () =>
      evaluate(
        cdp,
        `document.querySelector('[data-registry-advanced]').open && document.querySelector('select[name="authority"]').value==='missing'`,
      ),
    "Deep-link disclosure lost unknown filter",
  );
  assert.ok(
    await evaluate(
      cdp,
      `document.querySelector('[data-remove-filter="authority"]').textContent.includes('Unavailable filter value')`,
    ),
  );
  assert.equal(
    await evaluate(
      cdp,
      `document.querySelectorAll('main article button').length`,
    ),
    1,
    "Admin read-state control missing",
  );
  await choose("read", "unread");
  assert.ok(
    await evaluate(
      cdp,
      `!new URLSearchParams(location.search).has('cursor') && new URLSearchParams(location.search).get('authority')==='missing'`,
    ),
  );
  assert.equal(
    requests.filter(
      (r) => r.path.startsWith("/api/registry") && r.method !== "GET",
    ).length,
    0,
  );
  returnJourney=true;
  for (locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"])
    for(const width of [390,1440])
      for(const path of ['/registry','/discover']) {
        const route=`${path}?locale=${locale}&read=unread&cursor=return-page`;
        await cdp.send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<500});
        await cdp.send('Page.navigate',{url:base+route});
        await waitFor(()=>evaluate(cdp,`document.querySelectorAll('[data-registry-row]').length===20`),'Required long registry missing');
        assert.equal(await evaluate(cdp,`document.querySelectorAll('main [role="tab"],main [role="tabpanel"]').length`),0,'Page navigation must not claim tab keyboard behavior');
        assert.equal(await evaluate(cdp,`document.querySelector('main nav a[aria-current="page"]').pathname`),path);
        await evaluate(cdp,`document.querySelector('#registry-monitored-tab').focus()`);
        await cdp.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
        await cdp.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
        assert.equal(await evaluate(cdp,'document.activeElement.id'),'registry-events-tab','Navigation links lost their normal Tab order');
        const selector='[data-registry-row="qa-return-19"] a[href="/corpus-evidence/qa-native-19"]';
        const before=await evaluate(cdp,'performance.timeOrigin');
        await click(selector);
        await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-registry-return]') && document.body.innerText.includes('Synthetic return evidence')`),'Evidence return link missing');
        assert.equal(await evaluate(cdp,`document.querySelector('[data-registry-return]').getAttribute('href')`),route,'Filters/cursor were lost in explicit return link');
        await click('[data-registry-return]');
        await waitFor(()=>evaluate(cdp,`document.activeElement?.closest('[data-registry-row]')?.dataset.registryRow==='qa-return-19'`),'Explicit return did not focus the originating row');
        assert.equal(await evaluate(cdp,'location.pathname+location.search'),route);
        assert.equal(await evaluate(cdp,'performance.timeOrigin'),before,'Return unexpectedly reloaded the document');
        assert.ok(await evaluate(cdp,`(()=>{const r=document.activeElement.getBoundingClientRect();return r.top>90 && r.bottom<innerHeight-75})()`),'Restored link is hidden by sticky navigation');
        assert.equal(await evaluate(cdp,`sessionStorage.getItem('helvetic.registry-position.v1')`),null,'Return marker was not consumed');
        await click(selector);
        await waitFor(()=>evaluate(cdp,`location.pathname==='/corpus-evidence/qa-native-19'`),'Second evidence navigation failed');
        await evaluate(cdp,'history.back()');
        await waitFor(()=>evaluate(cdp,`location.pathname===${JSON.stringify(path)} && document.activeElement?.closest('[data-registry-row]')?.dataset.registryRow==='qa-return-19'`),'Native Back lost row focus');
      }
  // A removed row in a newly fetched page must not send the reader elsewhere.
  await click('[data-registry-row="qa-return-19"] a[href="/corpus-evidence/qa-native-19"]');
  await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-registry-return]')`),'Missing evidence departure marker');
  const returnRoute=await evaluate(cdp,`document.querySelector('[data-registry-return]').getAttribute('href')`);
  hideReturnRow=true;
  await cdp.send('Page.navigate',{url:base+returnRoute});
  await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-registry-return-missing]')`),'Removed record lacked honest return notice');
  assert.equal(await evaluate(cdp,'location.pathname+location.search'),returnRoute,'Missing record rewrote filters');
  assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-registry-row]').length`),19);
  assert.deepEqual(exceptions, []);
  console.log(
    "Registry production UI: 20 required localized journeys (five locales x mobile/desktop x Monitoring/Discover), progressive controls, date presets, chips, URL/back state, empty recovery, unknown deep-link values, cursor reset and viewer/admin controls pass. Twenty additional long-list evidence round trips retain filtered cursors, exact focus and native Back; missing-row recovery is explicit. All APIs intercepted; no production data, AI or messages touched.",
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
  assert.ok(basename(profile).startsWith("helvetic-registry-browser-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
