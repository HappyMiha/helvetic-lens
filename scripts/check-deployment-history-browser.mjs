// Production frontend, intercepted synthetic API only. Never deploys anything.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { createServer } from "node:net";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { monitoringProgressFixture } from "./monitoring-progress-fixtures.mjs";

const root = resolve(import.meta.dirname, "..");
const audit = new AccessibilityAudit("deployment-history");
const chrome = [process.env.CHROME_BIN, "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "/usr/bin/google-chrome", "/usr/bin/chromium"].filter(Boolean).find(existsSync);
assert.ok(chrome);
const reserve=createServer();
await new Promise(resolve=>reserve.listen(0,"127.0.0.1",resolve));
const port=reserve.address().port;
await new Promise(resolve=>reserve.close(resolve));
const base=`http://127.0.0.1:${port}`;
const server=spawn(process.execPath,[join(root,"node_modules/next/dist/bin/next"),"start","-H","127.0.0.1","-p",String(port)],{cwd:join(root,"apps/web"),stdio:"ignore",windowsHide:true});
const profile=await mkdtemp(join(tmpdir(),"helvetic-deployment-browser-"));
const browser=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{stdio:"ignore",windowsHide:true});
let cdp,locale="en-CH",administrator=true,failDetail=true;
let deploymentBranch="main";
let deploymentProgress, serviceState="idle";
const monitoringBranch="codex/HappyDucky02/monitoring-v2";
const unknownBranch={"de-CH":"Unbekannt","fr-CH":"Inconnu","it-CH":"Sconosciuto","rm-CH":"Nunenconuschent","en-CH":"Unknown"};
const requests=[],exceptions=[];
async function waitFor(check,message){for(let i=0;i<180;i++){if(await check().catch(()=>false))return;await sleep(100);}throw new Error(message);}
const run=(id,status="succeeded")=>({id,kind:"release",status,target_sha:"a".repeat(40),previous_sha:"b".repeat(40),activated_sha:status==="succeeded"?"a".repeat(40):null,host:"Synthetic-host",environment:"test",release:"test-release",started_at:"2026-09-08T08:00:00Z",finished_at:"2026-09-08T08:05:00Z",duration_seconds:300,changes:[{sha:"a".repeat(40),short_sha:"aaaaaaa",subject:"Synthetic pinned change",author:"QA",committed_at:"2026-09-08T07:00:00Z"}],steps:[{name:"api_tests",status,error:status==="failed"?"Synthetic gate diagnostics: a regression failed.":null}],rollback:{status:status==="failed"?"succeeded":"not_required",backup_restored:status==="failed"},error:status==="failed"?"Synthetic deployment failure":null,release_notes:{kind:"commit_summary",previous_sha:"b".repeat(40),target_sha:"a".repeat(40),text:"Synthetic pinned release notes\n- Improved source monitoring\n- Fixed a previous regression",captured_at:"2026-09-08T08:00:00Z",repository_notes_available:false,changes_may_be_truncated:false,text_truncated:false},compare_url:"https://github.com/HappyMiha/helvetic-lens/compare/"+"b".repeat(40)+"..."+"a".repeat(40)});
try {
  await waitFor(async()=> (await fetch(base)).ok,"Frontend did not start");
  let debugPort;
  await waitFor(async()=>{debugPort=(await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0];return debugPort;},"Chrome did not start");
  const tab=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());
  cdp=new Cdp(tab.webSocketDebuggerUrl);
  await cdp.send("Page.enable");await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown",({exceptionDetails})=>exceptions.push(exceptionDetails.exception?.description||exceptionDetails.text));
  cdp.on("Fetch.requestPaused",async({requestId,request})=>{
    const url=new URL(request.url),path=url.pathname;
    requests.push({path,method:request.method,query:url.search});
    let body={},code=200;
    if(path==="/api/auth/session") body={authenticated:true,platform_admin:administrator,user:{id:`qa-${administrator}-${locale}`,email:"qa@example.invalid",name:"QA",locale},organization:{id:"qa-org",name:"QA"},role:"organization_admin"};
    else if(path==="/api/health")body={status:"ok",database:"postgresql",apertus:{configured:false},firecrawl:{configured:false}};
    else if(path==="/api/admin/deployments")body={schema_version:1,service:{enabled:deploymentBranch!==null,state:deploymentBranch===null?"status_unavailable":serviceState,poll_interval_seconds:120,last_checked_at:"2026-09-08T08:00:00Z"},remote:{branch:deploymentBranch,sha:deploymentBranch===null?null:"a".repeat(40)},current:{sha:"b".repeat(40),release:"test-release"},monitoring_progress:deploymentProgress,last_run:run("latest"),history:[]};
    else if(path==="/api/admin/deployments/history")body={items:url.searchParams.get("cursor")==="older"?[run("old")]:url.searchParams.get("status")==="succeeded"?[run("success")]:[run("success"),run("failure","failed")],next_cursor:url.searchParams.get("cursor")||url.searchParams.get("status")?null:"older",mode:"journal",archive_started_at:"2026-09-08T08:00:00Z",legacy_retention_unknown:true};
    else if(path.startsWith("/api/admin/deployments/history/")){
      const id=path.split("/").pop();
      if(id==="failure"&&failDetail){failDetail=false;code=503;body={detail:"Synthetic detail unavailable"};}
      else body=run(id,id==="failure"?"failed":"succeeded");
    } else if(["/api/laws","/api/scans","/api/jobs"].includes(path)) body=[];
    else { code=503; body={detail:"Synthetic unrelated endpoint unavailable"}; }
    await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"content-type",value:"application/json"}],body:Buffer.from(JSON.stringify(body)).toString("base64")});
  });
  await cdp.send("Fetch.enable",{patterns:[{urlPattern:"*/api/*"}]});
  const click=async selector=>{
    let point;
    await waitFor(async()=>{
      point=await evaluate(cdp,`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el||el.disabled)return null;el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return {x,y,visible:el.contains(document.elementFromPoint(x,y))};})()`);
      return point?.visible;
    },`Pointer cannot reach ${selector}`);
    for(const type of ["mousePressed","mouseReleased"])await cdp.send("Input.dispatchMouseEvent",{type,x:point.x,y:point.y,button:"left",clickCount:1});
  };
  for(const width of [390,1440])for(locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){
    administrator=true;failDetail=true;
    deploymentBranch=width===390?monitoringBranch:"main";
    await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:960,deviceScaleFactor:1,mobile:width===390});
    await cdp.send("Page.navigate",{url:`${base}/deployments?locale=${locale}&qa=${width}`});
    await waitFor(()=>evaluate(cdp,`document.documentElement.lang===${JSON.stringify(locale)}&&document.querySelectorAll('[data-deployment-run]').length===2`),"History list missing");
    assert.equal(await evaluate(cdp,`document.querySelector('[data-deployment-branch]').textContent.trim().split(' · ').at(-1)`),deploymentBranch,"Git card must show the instance's branch");
    assert.ok(await evaluate(cdp,`document.querySelector('[data-deployment-branch-description]').textContent.includes(${JSON.stringify(deploymentBranch)})`),"Description must show the instance's branch");
    assert.equal(await evaluate(cdp,`document.querySelector('[data-deployment-latest]').open`),false,"Latest run should not push history behind an expanded report");
    await click('[data-deployment-run="success"]');
    await waitFor(()=>evaluate(cdp,`document.querySelector('[data-deployment-detail="success"]')?.innerText.includes('Synthetic pinned release notes')`),"Pinned notes missing");
    assert.ok(await evaluate(cdp,`document.querySelector('[data-deployment-detail="success"]').innerText.includes('10:00')`),"Start time missing");
    await click('[data-deployment-detail="success"] details summary');
    assert.ok(await evaluate(cdp,`document.querySelector('[data-deployment-detail="success"]').innerText.includes('Synthetic pinned change')`),"Commit list not reachable");
    assert.ok(await evaluate(cdp,`document.querySelector('[data-deployment-detail="success"] a')?.href.includes('bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb...aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')`));
    assert.ok(await evaluate(cdp,`document.documentElement.scrollWidth<=innerWidth+1`),"Horizontal page overflow");
    assert.ok(await evaluate(cdp,`Array.from(document.querySelectorAll('[data-deployment-history] button')).every(b=>b.getBoundingClientRect().height>=44)`),"Small action target");
    await audit.check(cdp,`success-${width}-${locale}`,'[data-deployment-detail="success"]');
    await click('[data-deployment-run="failure"]');
    await waitFor(()=>evaluate(cdp,`document.querySelector('[data-deployment-detail="failure"]')?.innerText.includes('Synthetic detail unavailable')`),"Detail error missing");
    await click('[data-deployment-detail="failure"] button');
    await waitFor(()=>evaluate(cdp,`document.querySelector('[data-deployment-detail="failure"]')?.innerText.includes('Synthetic gate diagnostics')`),"Retry did not recover exact attempt");
    await audit.check(cdp,`failure-${width}-${locale}`,'[data-deployment-detail="failure"]');
    await click('[data-deployment-next]');
    await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-deployment-run="old"]')`),"Older history unavailable");
    assert.ok(await evaluate(cdp,`document.querySelector('[data-deployment-next]').disabled`));
    await click('[data-deployment-back]');
    await waitFor(()=>evaluate(cdp,`document.querySelectorAll('[data-deployment-run]').length===2`),"Newer page missing");
    await evaluate(cdp,`{const select=document.querySelector('[data-deployment-filter]');select.value='succeeded';select.dispatchEvent(new Event('change',{bubbles:true}));}`);
    await waitFor(()=>evaluate(cdp,`document.querySelectorAll('[data-deployment-run]').length===1&&!!document.querySelector('[data-deployment-run="success"]')`),"Outcome filter failed");
    if(locale==="en-CH"){
      await click('[data-deployment-run="success"]');
      await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-deployment-detail="success"] pre')`),"Screenshot detail missing");
      await evaluate(cdp,`document.querySelector('[data-deployment-detail="success"]').scrollIntoView({block:'start'})`);
      await mkdir(join(root,"test-results/deployment-history"),{recursive:true});
      const shot=await cdp.send("Page.captureScreenshot",{format:"png"});
      await writeFile(join(root,"test-results/deployment-history",`${width}.png`),Buffer.from(shot.data,"base64"));
    }
  }
  deploymentBranch=null;
  await cdp.send("Emulation.setDeviceMetricsOverride",{width:390,height:960,deviceScaleFactor:1,mobile:true});
  for(locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){
    await cdp.send("Page.navigate",{url:`${base}/deployments?locale=${locale}&qa=unavailable`});
    await waitFor(()=>evaluate(cdp,`document.documentElement.lang===${JSON.stringify(locale)}&&document.querySelector('[data-deployment-branch]')?.textContent.trim().split(' · ').at(-1)===${JSON.stringify(unknownBranch[locale])}`),"Unavailable status must show a localized unknown branch");
    const description=await evaluate(cdp,`document.querySelector('[data-deployment-branch-description]').textContent`);
    assert.ok(description.trim().length>20&&!description.includes("main")&&!description.includes(monitoringBranch)&&!description.includes("{branch}"),"Unavailable description must not invent a release channel");
    assert.ok(await evaluate(cdp,`document.documentElement.scrollWidth<=innerWidth+1`),"Unavailable branch view overflows mobile width");
  }
  const progressText=selector=>evaluate(cdp,`document.querySelector(${JSON.stringify(selector)})?.textContent.trim()`);
  const openProgress=async kind=>{
    deploymentProgress=monitoringProgressFixture(kind);
    await cdp.send("Page.navigate",{url:`${base}/deployments?locale=${locale}&qa=progress-${kind}`});
    await waitFor(()=>evaluate(cdp,`document.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector('[data-monitoring-progress]')`),"Monitoring progress missing");
  };
  for(const width of [390,1440])for(locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){
    deploymentBranch=monitoringBranch;
    serviceState=width===390?"deploying":"idle";
    await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:960,deviceScaleFactor:1,mobile:width===390});
    await openProgress("divergent");
    assert.equal(await progressText('[data-monitoring-card="git"] [data-monitoring-percent]'),"≈33%");
    assert.match(await progressText('[data-monitoring-card="git"] [data-monitoring-ratio]'),/^3\/9 /);
    assert.equal(await progressText('[data-monitoring-card="deployed"] [data-monitoring-percent]'),"≈25%");
    assert.match(await progressText('[data-monitoring-card="deployed"] [data-monitoring-ratio]'),/^2\/8 /);
    assert.equal(await progressText('[data-monitoring-remaining-count]'),"6");
    assert.match(await progressText('[data-monitoring-in-progress]'),/^2 /);
    assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-monitoring-pollen]').length`),6);
    assert.match(await progressText('[data-monitoring-pollen-counts]'),/1\/6.*1\/6/);
    assert.ok(await evaluate(cdp,`document.querySelector('[data-monitoring-card="git"]').textContent.includes('aaaaaaaaaaaa')&&document.querySelector('[data-monitoring-card="deployed"]').textContent.includes('bbbbbbbbbbbb')`),"Each measure must retain its revision");
    if(locale==="en-CH")assert.equal(await progressText('[data-monitoring-card="deployed"] h3'),width===390?"Last verified release":"Already on this site");
    assert.ok(await evaluate(cdp,`!document.querySelector('[data-monitoring-unfinished]').open&&!document.querySelector('[data-monitoring-awaiting]').open&&!document.querySelector('[data-monitoring-pollen-steps]').open`),"Task lists must start collapsed");
    await click('[data-monitoring-pollen-steps] summary');
    assert.ok(await evaluate(cdp,`Array.from(document.querySelectorAll('[data-monitoring-pollen]')).every(row=>row.getBoundingClientRect().height>0)`),"All six Pollen steps must be reachable");
    if(locale==="en-CH")assert.equal(await progressText('[data-monitoring-pollen="true"][data-monitoring-task="MV2-070"] dt'),"In Git","Unfinished rows must not be labelled completed");
    assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-monitoring-progress] img').length`),0,"Backlog title markup must render as text");
    assert.notEqual(await progressText('[data-monitoring-pollen="true"][data-monitoring-task="MV2-071"] [data-monitoring-latest-status]'),await progressText('[data-monitoring-pollen="true"][data-monitoring-task="MV2-071"] [data-monitoring-deployed-status]'),"Reopened Pollen work must preserve deployed status");
    await click('[data-monitoring-unfinished] summary');
    assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-monitoring-unfinished] [data-monitoring-task]').length`),6);
    assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-monitoring-progress] [data-monitoring-task="MV2-026"]').length`),0,"Deferred work is excluded from remaining");
    await click('[data-monitoring-awaiting] summary');
    assert.deepEqual(await evaluate(cdp,`Array.from(document.querySelectorAll('[data-monitoring-awaiting] [data-monitoring-task]'),node=>node.dataset.monitoringTask)`),["MV2-001","MV2-074"],"Awaiting deployment must compare IDs, not aggregate totals");
    assert.ok((await progressText('[data-monitoring-awaiting] [data-monitoring-task="MV2-074"]')).includes('<img src=x onerror=alert(1)>'),"Backlog markup must remain literal text");
    assert.ok(await evaluate(cdp,`document.documentElement.scrollWidth<=innerWidth+1`),"Progress task lists overflow");
    await audit.check(cdp,`progress-${width}-${locale}`,'[data-monitoring-progress]');
    if(locale==="en-CH"){
      await evaluate(cdp,`document.querySelector('[data-monitoring-unfinished]').open=false;document.querySelector('[data-monitoring-awaiting]').open=false;document.querySelector('[data-monitoring-pollen-steps]').open=false;const panel=document.querySelector('[data-monitoring-progress]');panel.style.scrollMarginTop='90px';panel.scrollIntoView({block:'start'})`);
      const shot=await cdp.send("Page.captureScreenshot",{format:"png"});
      await writeFile(join(root,"test-results/deployment-history",`progress-${width}.png`),Buffer.from(shot.data,"base64"));
    }
    const unavailableSide=width===390?"latest":"deployed";
    await openProgress(`${unavailableSide}-unavailable`);
    const card=unavailableSide==="latest"?"git":"deployed";
    assert.equal(await evaluate(cdp,`document.querySelector('[data-monitoring-card="${card}"] [data-monitoring-ratio]')`),null,"Unavailable must not appear as zero completion");
    assert.ok(await progressText(`[data-monitoring-card="${card}"] [data-monitoring-percent]`));
    assert.ok(!(await progressText('[data-monitoring-awaiting] summary')).match(/ · \d+$/),"Awaiting count needs both snapshots");
    assert.ok(await evaluate(cdp,`document.querySelector('[data-monitoring-card="${card==="git"?"deployed":"git"}"] [data-monitoring-ratio]')!==null`),"Independent valid snapshot must remain visible");
    assert.ok(await evaluate(cdp,`document.documentElement.scrollWidth<=innerWidth+1`),"Unavailable progress overflows");
    await audit.check(cdp,`progress-unavailable-${width}-${locale}`,'[data-monitoring-progress]');
    deploymentBranch="main";
    deploymentProgress=monitoringProgressFixture();
    await cdp.send("Page.navigate",{url:`${base}/deployments?locale=${locale}&qa=main-progress-hidden`});
    await waitFor(()=>evaluate(cdp,`document.querySelector('[data-deployment-branch]')?.textContent.includes('main')`),"Main status missing");
    assert.equal(await evaluate(cdp,`document.querySelector('[data-monitoring-progress]')`),null,"Monitoring progress must stay off the main channel");
  }
  locale="en-CH";deploymentBranch=monitoringBranch;serviceState="idle";
  await cdp.send("Emulation.setDeviceMetricsOverride",{width:390,height:960,deviceScaleFactor:1,mobile:true});
  await openProgress("zero");
  assert.equal(await progressText('[data-monitoring-card="git"] [data-monitoring-percent]'),"≈0%","A valid no-DONE backlog has real zero progress");
  await openProgress("missing");
  assert.equal(await evaluate(cdp,`document.querySelectorAll('[data-monitoring-ratio]').length`),0,"Absent metadata must never invent counters");
  await openProgress("no-required");
  assert.equal(await progressText('[data-monitoring-card="git"] [data-monitoring-percent]'),"Not applicable");
  await openProgress("older-pollen");
  assert.equal(await progressText('[data-monitoring-pollen="true"][data-monitoring-task="MV2-071"] [data-monitoring-deployed-status]'),"Not present in this revision");
  administrator=false;
  const before=requests.length;
  await cdp.send("Page.navigate",{url:`${base}/deployments?qa=nonadmin`});
  await waitFor(()=>evaluate(cdp,`!document.querySelector('[data-deployment-history]')&&!!document.querySelector('.error-note')`),"Non-admin denial missing");
  assert.equal(requests.slice(before).filter(r=>r.path.startsWith('/api/admin/deployments')).length,0);
  assert.equal(await evaluate(cdp,`document.querySelector('[data-monitoring-progress]')`),null);
  // The existing companion initializes its private conversation/context via
  // POST on every route; those intercepted fixture calls do not deploy or infer.
  assert.deepEqual(requests.filter(r=>r.method!=="GET" && !["/api/assistant/context","/api/assistant/conversations"].includes(r.path)),[]);
  assert.deepEqual(exceptions,[]);
  audit.finish(40);
  console.log("Deployment history and Monitoring progress pass in five locales at desktop/mobile widths: distinct revisions/denominators, reopened tasks, Pollen, unavailable metadata, collapsed lists, main isolation and non-admin boundary.");
} catch(error){console.error({locale,requests:requests.slice(-10),exceptions,text:cdp?await evaluate(cdp,"document.body.innerText.slice(-2500)").catch(()=>"unavailable"):"none"});throw error;}
finally{
  cdp?.close();
  for(const child of [browser,server]){const ended=new Promise(resolve=>child.once("exit",resolve));child.kill();await Promise.race([ended,sleep(2000)]);}
  assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith("helvetic-deployment-browser-"));
  await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
