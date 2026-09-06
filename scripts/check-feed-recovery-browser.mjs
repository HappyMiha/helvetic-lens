// Real production UI with intercepted synthetic API responses. No live backend.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { createServer } from "node:net";
import { Cdp, evaluate, pollJson, sleep } from "./browser-cdp.mjs";

const root = resolve(import.meta.dirname, "..");
const chrome = [process.env.CHROME_BIN, "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "/usr/bin/google-chrome", "/usr/bin/chromium"].filter(Boolean).find(existsSync);
assert.ok(chrome, "A real Chrome executable is required.");
const reserve = createServer();
await new Promise(resolve => reserve.listen(0, "127.0.0.1", resolve));
const port = reserve.address().port;
await new Promise(resolve => reserve.close(resolve));
const base = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, [join(root, "node_modules/next/dist/bin/next"), "start", "-H", "127.0.0.1", "-p", String(port)], {
  cwd: join(root, "apps/web"), stdio: "ignore", windowsHide: true,
});
const profile = await mkdtemp(join(tmpdir(), "helvetic-feed-recovery-browser-"));
const browser = spawn(chrome, ["--headless=new", "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore", windowsHide: true });
let cdp;
const requests = [], exceptions = [];
async function waitFor(check, message) {
  for (let i = 0; i < 150; i++) {
    if (await check().catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}
let locale="en-CH", role="viewer", user="qa", scenario="interests";
const topic = () => ({id:"topic-one",name:"Synthetic topic",url:"/topics#topic-one",monitoring_from:"2026-09-01T12:00:00Z",history_status:scenario === "pending" ? "queued" : scenario === "interrupted" ? "failed" : "complete",captured_at:"2026-09-06T00:00:00Z",processed_through:"2026-09-05T12:00:00Z",processed:500,remaining:scenario === "pending" ? 4 : 0});
const readiness = () => ({captured_at:"2026-09-06T01:00:00Z",active_document_watch:false,topics:scenario === "interests" ? [] : [topic()],more_topics:false,more_packs:false,enabled_pack_count_shown:scenario === "sources" ? 0 : 1,sources_pending:scenario === "sync",sources_need_attention:scenario === "attention",source_freshness_verified:false,quiet_period_verified:false});
try {
  await waitFor(async () => (await fetch(base)).ok, "Isolated production UI failed to start");
  let debugPort;
  await waitFor(async () => { debugPort = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]; return !!debugPort; }, "Browser failed to start");
  await pollJson(`http://127.0.0.1:${debugPort}/json/version`);
  const target = await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: "PUT" }).then(response => response.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) => exceptions.push(exceptionDetails.exception?.description || exceptionDetails.text));

  cdp.on("Fetch.requestPaused", async ({requestId, request}) => {
    const path=new URL(request.url).pathname;
    requests.push({path,method:request.method});
    let body={},code=200;
    if (path === "/api/auth/session") body={authenticated:true,user:{id:user,email:"qa@example.invalid",name:"QA",locale},organization:{id:"qa-org",name:"QA"},role};
    else if (path === "/api/health") body={status:"ok",database:"postgresql",apertus:{configured:false},firecrawl:{configured:false}};
    else if (path === "/api/interest-feed") body={items:[],scanned_event_count:0,has_more:scenario === "page",next_cursor:scenario === "page" ? "next-synthetic-page" : null};
    else if (path === "/api/interest-feed/readiness") body=readiness();
    else if (["/api/jobs","/api/scans","/api/laws"].includes(path)) body=[];
    else {code=503;body={detail:"Synthetic endpoint unavailable"};}
    await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"Content-Type",value:"application/json"}],body:Buffer.from(JSON.stringify(body)).toString("base64")}).catch(()=>{});
  });
  await cdp.send("Fetch.enable",{patterns:[{urlPattern:`${base}/api/*`,requestStage:"Request"}]});
  const click = async selector => {
    await evaluate(cdp, `new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))`);
    const point = await evaluate(cdp, `(()=>{const el=document.querySelector(${JSON.stringify(selector)});el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect(), x=r.x+r.width/2,y=r.y+r.height/2;return {x,y,visible:el.contains(document.elementFromPoint(x,y))};})()`);
    assert.ok(point.visible, `Control not reachable by pointer: ${selector}`);
    for (const type of ["mousePressed", "mouseReleased"]) await cdp.send("Input.dispatchMouseEvent", {type, x:point.x, y:point.y, button: "left", clickCount: 1});
  };
  for (const language of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]) for (const width of [390,1440]) {
    locale=language;user=`${language}-${width}`;
    await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:900,deviceScaleFactor:1,mobile:width<500});
    for (const [kind,destination] of [["interests","/onboarding"],["sources","/sources#source-packs"],["pending","/topics"],["interrupted","/topics"],["attention","/sources#source-packs"],["sync","/sources#source-packs"],["filters","/"],["link","/"],["page","/?locale="+locale+"&cursor=next-synthetic-page"]]) {
      scenario=kind;
      const extra=kind === "filters" ? "&state=unread&period=today" : kind === "link" ? "&event=missing-event" : "";
      await cdp.send("Page.navigate",{url:`${base}/?locale=${locale}${extra}`});
      await waitFor(()=>evaluate(cdp, `document.documentElement.lang === ${JSON.stringify(locale)} && document.querySelector('[data-feed-empty-reason]')?.getAttribute('data-feed-empty-reason') === ${JSON.stringify('feedRecovery.'+kind)}`),"Expected recovery state missing");
      assert.equal(await evaluate(cdp,`document.querySelector('[data-feed-recovery-action]').getAttribute('href')`),destination);
      assert.ok(await evaluate(cdp,`document.documentElement.scrollWidth <= innerWidth + 1`),"Recovery overflows viewport");
      assert.ok(await evaluate(cdp,`!document.querySelector('[data-feed-empty]').innerText.includes('feedRecovery.')`),"Untranslated recovery key");
      if (kind === "pending") {
        await click('[data-feed-readiness] summary');
        assert.ok(await evaluate(cdp,`document.querySelector('[data-feed-history]').innerText.includes('500') && document.querySelector('[data-feed-history]').innerText.includes('4')`));
        if(locale === "en-CH") {
          await mkdir(join(root,".tmp"),{recursive:true});
          const shot=await cdp.send("Page.captureScreenshot",{format:"png"});
          await writeFile(join(root,".tmp",`feed-recovery-${width}.png`),Buffer.from(shot.data,"base64"));
        }
      }
    }
  }
  assert.deepEqual(requests.filter(r=>r.method !== "GET" && !r.path.startsWith('/api/assistant/')),[]);
  assert.deepEqual(exceptions,[]);
  console.log("Empty feed production UI: 90 five-language mobile/desktop states pass nine distinct recovery reasons, exact next actions, accessible saved-history details, bounded-layout checks and no mutations. All API responses intercepted.");
} catch (error) {
  console.error({locale,role,user,requests:requests.slice(-12),exceptions,text:cdp ? await evaluate(cdp,'document.body.innerText.slice(-2400)').catch(()=> 'unavailable') : 'none'});
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const ended = new Promise(resolve => child.once("exit", resolve));
    child.kill();
    await Promise.race([ended, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-feed-recovery-browser-"));
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
