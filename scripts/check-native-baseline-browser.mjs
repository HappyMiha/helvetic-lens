// Production UI, real Chrome, intercepted synthetic API. Never contacts a model.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { createServer } from "node:net";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
const audit = new AccessibilityAudit("native-baseline");
const root = resolve(import.meta.dirname, "..");
const chrome = [process.env.CHROME_BIN, "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "/usr/bin/google-chrome", "/usr/bin/chromium"].filter(Boolean).find(existsSync);
assert.ok(chrome);
const reserve = createServer();
await new Promise(resolve => reserve.listen(0, "127.0.0.1", resolve));
const port = reserve.address().port;
await new Promise(resolve => reserve.close(resolve));
const base = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, [join(root,"node_modules/next/dist/bin/next"), "start", "-H", "127.0.0.1", "-p", String(port)], {cwd:join(root,"apps/web"),stdio:"ignore",windowsHide:true});
const profile = await mkdtemp(join(tmpdir(), "helvetic-native-baseline-browser-"));
const browser = spawn(chrome, ["--headless=new","--no-first-run","--no-default-browser-check","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"], {stdio:"ignore",windowsHide:true});
let cdp, locale="en-CH", viewer=false, revision=0, chosen=null, conflict=false, stale=false, noChoices=false, readFailure=false;
const requests=[],exceptions=[];
async function waitFor(check,message) { for(let i=0;i<160;i++){if(await check().catch(()=>false))return;await sleep(100);}throw new Error(message); }
const snapshot=id=>({id,version_key:`Synthetic saved snapshot ${id}`,saved_at:"2026-09-04T08:00:00Z",evidence_url:`/corpus-evidence/${id}`});
const route="/api/registry/events/synthetic-event";
function comparison(url){
  const offset=Number(url.searchParams.get("offset")||0), material=url.searchParams.get("material_only")!=="false";
  const items=Array.from({length:22},(_,i)=>({id:`change-${i}`,kind:i<2?"modified":"unchanged",classification:i<2?"substantive":"unchanged",
    old:{id:`old-p${i}`,text:`Vorher: ${i<2?"Die Frist beträgt 10 Tage.":"Unveränderter Text."}`,page:1},
    new:{id:`new-p${i}`,text:`Nachher: ${i<2?"Die Frist beträgt 30 Tage.":"Unveränderter Text."}`,page:1}})).filter((_,i)=>!material||i<2);
  return {event_id:"synthetic-event",title:"Synthetische Gesetzesänderung",language:"de",after:snapshot("current"),before:chosen&&!stale?snapshot(chosen):null,
    revision,status:stale?"stale":chosen?"ready":"unselected",comparison_id:chosen&&!stale?`comparison-${chosen}`:null,
    counts:chosen?{modified:2,added:0,removed:0,unchanged:20}:null,material_count:chosen?2:null,
    items:chosen&&!stale?items.slice(offset,offset+20):[],pagination:chosen&&!stale?{offset,total:items.length,next_offset:offset+20<items.length?offset+20:null,previous_offset:offset?0:null}:null};
}
try {
  await waitFor(async()=>(await fetch(base)).ok,"Isolated UI did not start");
  let debugPort;await waitFor(async()=>{debugPort=(await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0];return debugPort;},"Chrome did not start");
  const tab=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());
  cdp=new Cdp(tab.webSocketDebuggerUrl);await cdp.send("Page.enable");await cdp.send("Runtime.enable");
  cdp.on("Runtime.exceptionThrown",({exceptionDetails})=>exceptions.push(exceptionDetails.exception?.description||exceptionDetails.text));
  cdp.on("Fetch.requestPaused",async({requestId,request})=>{
    const url=new URL(request.url),path=url.pathname;requests.push({path,method:request.method,body:request.postData});
    let body={},code=200;
    if(path==="/api/auth/session")body={authenticated:true,user:{id:`qa-${locale}-${viewer}`,locale,name:"QA",email:"qa@example.invalid"},organization:{id:"qa-org",name:"QA"},role:viewer?"viewer":"organization_admin",platform_admin:false};
    else if(path===`${route}/baselines`)body={after_version_id:"current",items:noChoices?[]:url.searchParams.get("after")?[snapshot("older")]:[snapshot("baseline")],next_after:noChoices||url.searchParams.get("after")?null:"cursor"};
    else if(path===`${route}/comparison`){
      if(request.method==="PUT"){
        const input=JSON.parse(request.postData);await sleep(150);
        if(conflict||input.expected_revision!==revision){code=409;body={code:"native_selection_conflict",detail:"Synthetic concurrent edit"};conflict=false;}
        else {chosen=input.before_version_id;revision++;stale=false;body={revision,comparison_id:chosen?`comparison-${chosen}`:null};}
      } else if(readFailure){code=503;body={detail:"Synthetic comparison read unavailable"};}
      else body=comparison(url);
    } else if(path==="/api/health")body={status:"ok",database:"postgresql",apertus:{configured:false},firecrawl:{configured:false}};
    else if(["/api/laws","/api/scans","/api/jobs"].includes(path))body=[];
    else {code=503;body={detail:"Synthetic unrelated endpoint unavailable"};}
    await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"content-type",value:"application/json"}],body:Buffer.from(JSON.stringify(body)).toString("base64")});
  });
  await cdp.send("Fetch.enable",{patterns:[{urlPattern:"*/api/*"}]});
  async function click(selector){
    let point;await waitFor(async()=>{point=await evaluate(cdp,`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el||el.disabled)return null;el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,visible:el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))};})()`);return point?.visible;},`Unreachable ${selector}`);
    for(const type of ["mousePressed","mouseReleased"])await cdp.send("Input.dispatchMouseEvent",{type,x:point.x,y:point.y,button:"left",clickCount:1});
  }
  const select=async value=>evaluate(cdp,`{const el=document.querySelector('#native-baseline');el.value=${JSON.stringify(value)};el.dispatchEvent(new Event('change',{bubbles:true}));}`);
  for(const width of [390,1440])for(locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){
    revision=0;chosen=null;stale=false;viewer=false;conflict=false;
    await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:960,deviceScaleFactor:1,mobile:width===390});
    await cdp.send("Page.navigate",{url:`${base}/native-comparison/synthetic-event?locale=${locale}&qa=${width}`});
    await waitFor(()=>evaluate(cdp,`document.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector('#native-baseline option[value="baseline"]')`),"Baseline editor did not load");
    assert.equal(await evaluate(cdp,"document.querySelector('#native-baseline').value"),"");
    assert.ok(await evaluate(cdp,"document.querySelector('[data-native-save]').disabled"));
    await evaluate(cdp,"window.__nativeNavigationMarker='unchanged'");
    await select("baseline");await click("[data-native-save]");
    await waitFor(()=>evaluate(cdp,"document.querySelectorAll('[data-native-change]').length===2"),"Saved material comparison missing");
    assert.equal(await evaluate(cdp,"window.__nativeNavigationMarker"),"unchanged","Saving reloaded the page");
    assert.ok(await evaluate(cdp,"document.querySelector('[data-native-change] p').lang==='de'"));
    assert.ok(await evaluate(cdp,"Array.from(document.querySelectorAll('[data-native-change] a')).every(a=>a.getAttribute('href').includes('?passage='))"));
    assert.ok(await evaluate(cdp,"document.documentElement.scrollWidth<=innerWidth+1"),"Horizontal page overflow");
    assert.ok(await evaluate(cdp,"Array.from(document.querySelectorAll('[data-native-baseline] button')).every(b=>b.getBoundingClientRect().height>=44)"));
    await audit.check(cdp,`ready-${width}-${locale}`,"[data-native-baseline]");
    if(locale==="en-CH"){
      await mkdir(join(root,"test-results"),{recursive:true});
      const shot=await cdp.send("Page.captureScreenshot",{format:"png"});
      await writeFile(join(root,"test-results",`native-baseline-${width}.png`),Buffer.from(shot.data,"base64"));
    }
    await click("[data-native-all]");await waitFor(()=>evaluate(cdp,"document.querySelectorAll('[data-native-change]').length===20"),"All passages missing");
    await click("[data-native-next]");await waitFor(()=>evaluate(cdp,"!!document.querySelector('[data-native-change=\"change-20\"]')"),"Second diff page missing");
    await click("[data-native-previous]");await waitFor(()=>evaluate(cdp,"!!document.querySelector('[data-native-change=\"change-0\"]')"),"Previous diff page missing");
    await click("[data-native-more]");await waitFor(()=>evaluate(cdp,"!!document.querySelector('#native-baseline option[value=\"older\"]')"),"More versions missing");
    assert.equal(await evaluate(cdp,"document.querySelector('#native-baseline').value"),"baseline","Candidate paging lost current choice");
    await select("older");conflict=true;await click("[data-native-save]");
    await waitFor(()=>evaluate(cdp,"!!document.querySelector('.error-note')"),"Save conflict not visible");
    await audit.check(cdp,`conflict-${width}-${locale}`,"[data-native-baseline]");
    await click("[data-native-refresh]");await waitFor(()=>evaluate(cdp,"!document.querySelector('.error-note')&&!document.querySelector('[data-native-clear]').disabled"),"Refresh did not recover");
    await click("[data-native-clear]");await waitFor(()=>evaluate(cdp,"!document.querySelector('[data-native-diff]')&&document.querySelector('[data-native-clear]').disabled"),"Clear did not remove comparison");
    assert.equal(chosen,null);
  }
  assert.equal(requests.filter(r=>r.method==="PUT").length,30,"One save/conflict/clear each; no duplicate writes");
  stale=true;chosen="baseline";revision=1;
  await cdp.send("Page.navigate",{url:`${base}/native-comparison/synthetic-event?qa=stale`});
  await waitFor(()=>evaluate(cdp,"document.querySelector('.panel[role=status]')?.innerText.includes('needs review')"),"Stale state missing");
  assert.equal(await evaluate(cdp,"!!document.querySelector('[data-native-diff]')"),false);
  stale=false;chosen=null;noChoices=true;readFailure=true;
  await cdp.send("Page.navigate",{url:`${base}/native-comparison/synthetic-event?qa=empty-retry`});
  await waitFor(()=>evaluate(cdp,"!!document.querySelector('.error-note')"),"Read error missing");
  readFailure=false;
  await click("[data-native-refresh]");
  await waitFor(()=>evaluate(cdp,"!!document.querySelector('#native-baseline')&&!document.querySelector('.error-note')"),"Read retry failed");
  assert.ok(await evaluate(cdp,"document.querySelector('[data-native-save]').disabled&&document.querySelector('[data-native-baseline]').innerText.includes('No other accessible')"));
  noChoices=false;
  viewer=true;chosen="baseline";revision=1;
  const before=requests.length;await cdp.send("Page.navigate",{url:`${base}/native-comparison/synthetic-event?viewer=true`});
  await waitFor(()=>evaluate(cdp,"!!document.querySelector('[data-native-diff]')&&document.querySelector('#native-baseline').disabled"),"Viewer cannot read saved comparison");
  assert.equal(await evaluate(cdp,"!!document.querySelector('[data-native-save]')||!!document.querySelector('[data-native-clear]')"),false);
  assert.equal(requests.slice(before).filter(r=>r.method==="PUT").length,0);
  assert.deepEqual(exceptions,[]);audit.finish(20);
  console.log("10 desktop/mobile baseline journeys across five locales passed: no guessed baseline, save without reload, source links, paging, conflict/reload/clear and read-only viewer.");
}catch(error){console.error({locale,requests:requests.slice(-12),exceptions,text:cdp?await evaluate(cdp,"document.body.innerText.slice(-3000)").catch(()=>"unavailable"):"none"});throw error;}
finally{
  cdp?.close();for(const child of [browser,server]){const ended=new Promise(resolve=>child.once("exit",resolve));child.kill();await Promise.race([ended,sleep(2000)]);}
  assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith("helvetic-native-baseline-browser-"));
  await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
