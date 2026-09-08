// Real production feed UI with intercepted synthetic API; no model or user data.
import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import {existsSync} from "node:fs";
import {mkdtemp, readFile, rm, writeFile} from "node:fs/promises";
import {tmpdir} from "node:os";
import {basename, dirname, join, resolve} from "node:path";
import {createServer} from "node:net";
import {Cdp, evaluate, sleep} from "./browser-cdp.mjs";
import {AccessibilityAudit} from "./browser-accessibility.mjs";
const feedbackMode=process.argv.includes("--feedback");
const root=resolve(import.meta.dirname,".."),audit=new AccessibilityAudit(feedbackMode?"brief-feedback":"interest-brief");
const chrome=[process.env.CHROME_BIN,"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe","/usr/bin/google-chrome","/usr/bin/chromium"].filter(Boolean).find(existsSync);assert.ok(chrome);
const reserve=createServer();await new Promise(r=>reserve.listen(0,"127.0.0.1",r));const port=reserve.address().port;await new Promise(r=>reserve.close(r));
const base=`http://127.0.0.1:${port}`,profile=await mkdtemp(join(tmpdir(),"helvetic-brief-browser-"));
const server=spawn(process.execPath,[join(root,"node_modules/next/dist/bin/next"),"start","-H","127.0.0.1","-p",String(port)],{cwd:join(root,"apps/web"),stdio:"ignore",windowsHide:true});
const browser=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{stdio:"ignore",windowsHide:true});
let cdp,locale="en-CH",status="available",failure=false,feedback=[],receipts=new Map(),feedbackFailure="";const requests=[],exceptions=[];
async function waitFor(check,message){for(let i=0;i<180;i++){if(await check().catch(()=>false))return;await sleep(100);}throw new Error(message);}
const event={event_id:"synthetic-event",title:"Synthetic saved regulatory development",type:"updated",document_kind:"law",lifecycle_status:null,source:"Synthetic publisher",detected_at:"2026-09-08T08:00:00Z",official_dates:[],read_state:"unread",topic_matches:[],monitored_documents:[],law_impacts:[]};
const claim={text:"Synthetic saved explanation for review, not a legal conclusion.",evidence_ids:["ev1"]};
function brief(){return {event_id:event.event_id,locale:locale.slice(0,2),status,assessment_id:"synthetic-assessment",saved_at:"2026-09-08T09:00:00Z",ai_calls:0,evidence_links:{ev1:"/corpus-evidence/synthetic-version?passage=p1"},interest_names:{topic1:"Synthetic monitoring topic"},result:status==="available"?{what_happened:claim,why_in_radar:[{...claim,interest_id:"topic1"}],importance:{...claim,level:"low"},next_step:{...claim,kind:"no_action_now"},uncertainty:"Synthetic uncertainty.",input_limitations:["Synthetic input boundary."]}:null};}
try{
 await waitFor(async()=>(await fetch(base)).ok,"Isolated UI not ready");
 let debugPort;await waitFor(async()=>{debugPort=(await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0];return debugPort;},"Chrome not ready");
 const tab=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());cdp=new Cdp(tab.webSocketDebuggerUrl);
 await cdp.send("Page.enable");await cdp.send("Runtime.enable");cdp.on("Runtime.exceptionThrown",({exceptionDetails})=>exceptions.push(exceptionDetails.exception?.description||exceptionDetails.text));
 cdp.on("Fetch.requestPaused",async({requestId,request})=>{
  const path=new URL(request.url).pathname;requests.push({path,search:new URL(request.url).search,method:request.method});let body={},code=200;
  if(path==="/api/auth/session")body={authenticated:true,user:{id:`qa-${locale}`,locale,name:"QA",email:"qa@example.invalid"},organization:{id:"qa-org",name:"QA"},role:"viewer",platform_admin:false};
  else if(path==="/api/health")body={status:"ok",database:"postgresql",apertus:{configured:false},firecrawl:{configured:false}};
  else if(path==="/api/settings/interest-briefs")body={enabled:false};
  else if(path==="/api/interest-feed")body={items:[event],scanned_event_count:1,has_more:false,next_cursor:null};
  else if(path.endsWith("/feedback")){
   if(request.method==="POST"){
    const data=JSON.parse(request.postData);
    if(feedbackFailure==="conflict"){code=409;body={code:"feedback_conflict"};feedbackFailure="";}
    else {let row=receipts.get(data.request_id);if(!row){assert.equal(data.expected_previous_id,feedback[0]?.id||null);row={id:`feedback-${feedback.length+1}`,assessment_id:"synthetic-assessment",decision:data.decision,note:data.note,created_at:"2026-09-09T10:00:00Z"};feedback.unshift(row);receipts.set(data.request_id,row);}body={feedback:row,reused:true};if(feedbackFailure==="lost"){feedbackFailure="";code=503;body={code:"request_failed"};}}
   } else {const cursor=new URL(request.url).searchParams.get("cursor"),offset=cursor?feedback.findIndex(row=>row.id===cursor)+1:0,items=feedback.slice(offset,offset+2),more=offset+2<feedback.length;body={assessment_id:"synthetic-assessment",latest:feedback[0]||null,items,has_more:more,next_cursor:more?items.at(-1).id:null};}
  }
  else if(path.endsWith("/brief")){await sleep(120);if(failure){code=503;body={detail:"Synthetic read failure"};}else body=brief();}
  else if(["/api/laws","/api/scans","/api/jobs"].includes(path))body=[];
  else {code=503;body={detail:"Synthetic unrelated endpoint unavailable"};}
  await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"content-type",value:"application/json"}],body:Buffer.from(JSON.stringify(body)).toString("base64")});
 });await cdp.send("Fetch.enable",{patterns:[{urlPattern:"*/api/*"}]});
 async function click(selector){let point;await waitFor(async()=>{point=await evaluate(cdp,`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||e.disabled)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,ok:e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))};})()`);return point?.ok;},`Unreachable ${selector}`);for(const type of ["mousePressed","mouseReleased"])await cdp.send("Input.dispatchMouseEvent",{type,x:point.x,y:point.y,button:"left",clickCount:1});}
 for(const width of [390,1440])for(locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){
  failure=false;status="available";feedback=[];receipts=new Map();feedbackFailure="";const start=requests.length;
  await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:960,deviceScaleFactor:1,mobile:width===390});
  await cdp.send("Page.navigate",{url:`${base}/?locale=${locale}&qa=${width}`});
  await waitFor(()=>evaluate(cdp,`document.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector('[data-feed-brief]')`),"Feed missing");
  assert.equal(requests.slice(start).filter(r=>r.path.endsWith("/brief")).length,0,"Collapsed card fetched a brief");
  await evaluate(cdp,"window.__briefMarker='retained'");await click("[data-feed-brief]>summary");
  await waitFor(()=>evaluate(cdp,"!!document.querySelector('[data-brief-result]')"),"Saved result missing");
  assert.equal(await evaluate(cdp,"window.__briefMarker"),"retained");
  assert.equal(await evaluate(cdp,"document.querySelector('[data-brief-result]').lang"),locale.slice(0,2));
  assert.ok(requests.slice(start).filter(r=>r.path.endsWith("/brief")).every(r=>new URLSearchParams(r.search).get("locale")===locale.slice(0,2)),"Brief request did not use viewer language");
  assert.ok(await evaluate(cdp,"Array.from(document.querySelectorAll('[data-brief-result] a')).every(a=>a.getAttribute('href')==='/corpus-evidence/synthetic-version?passage=p1')"));
  assert.ok(await evaluate(cdp,"document.documentElement.scrollWidth<=innerWidth+1"));
  if(feedbackMode){
   assert.equal(requests.slice(start).filter(row=>row.path.endsWith("/feedback")).length,0);
   await click("[data-brief-feedback]>summary");
   await waitFor(()=>evaluate(cdp,"!!document.querySelector('[data-feedback-useful]:not(:disabled)')"),"Feedback did not load");
   await click("[data-feedback-note]");await cdp.send("Input.insertText",{text:'Synthetic note <img src=x onerror="window.__feedbackXss=true">'});
   await click("[data-feedback-useful]");
   await waitFor(()=>evaluate(cdp,"!!document.querySelector('[data-feedback-saved]')&&!document.querySelector('[data-feedback-useful]').disabled"),"Feedback not saved");
   assert.equal(feedback.length,1);assert.equal(feedback[0].decision,"useful");
   await audit.check(cdp,`feedback-saved-${width}-${locale}`,"body");
   await click("[data-feedback-note]");await cdp.send("Input.insertText",{text:"Keep this draft after conflict"});feedbackFailure="conflict";
   await click("[data-feedback-not-useful]");
   await waitFor(()=>evaluate(cdp,"!!document.querySelector('[data-brief-feedback] [role=alert]')"),"Conflict not announced");
   assert.equal(await evaluate(cdp,"document.querySelector('[data-feedback-note]').value"),"Keep this draft after conflict");
   assert.equal(feedback.length,1);
   await audit.check(cdp,`feedback-conflict-${width}-${locale}`,"body");
   await click("[data-feedback-reload]");
   await waitFor(()=>evaluate(cdp,"!document.querySelector('[data-feedback-useful]').disabled"),"Feedback reload failed");
   feedbackFailure="lost";await click("[data-feedback-not-useful]");
   await waitFor(()=>evaluate(cdp,"!!document.querySelector('[data-brief-feedback] [role=alert]')"),"Lost reply not shown");
   assert.equal(feedback.length,2);
   await click("[data-feedback-not-useful]");
   await waitFor(()=>evaluate(cdp,"!document.querySelector('[data-brief-feedback] [role=alert]')&&!document.querySelector('[data-feedback-useful]').disabled"),"Replay failed");
   assert.equal(feedback.length,2,"Lost reply retry duplicated feedback");
   await click("[data-feedback-withdraw]");
   await waitFor(()=>evaluate(cdp,"!document.querySelector('[data-feedback-withdraw]')&&!document.querySelector('[data-feedback-useful]').disabled"),"Withdrawal missing");
   assert.equal(feedback.length,3);assert.equal(feedback[0].decision,"withdrawn");
   await click("[data-feedback-history]>summary");await click("[data-feedback-history] button");
   await waitFor(()=>evaluate(cdp,"document.querySelector('[data-feedback-history]').innerText.includes('Synthetic note <img')"),"History continuation missing");
   assert.equal(await evaluate(cdp,"!!window.__feedbackXss"),false);
   assert.equal(await evaluate(cdp,"window.__briefMarker"),"retained","Saving reloaded the page");
   assert.ok(await evaluate(cdp,"document.documentElement.scrollWidth<=innerWidth+1"));
   await audit.check(cdp,`feedback-history-${width}-${locale}`,"body");
   if(locale==="en-CH"){const shot=await cdp.send("Page.captureScreenshot",{format:"png"});await writeFile(join(root,`test-results/brief-feedback-${width}.png`),Buffer.from(shot.data,"base64"));}
   assert.ok(requests.slice(start).filter(row=>row.method!=="GET").every(row=>row.path.endsWith("/feedback")||["/api/assistant/context","/api/assistant/conversations"].includes(row.path)));
   continue;
  }
  await audit.check(cdp,`available-${width}-${locale}`,"[data-feed-brief]");
  if(locale==="en-CH"){const shot=await cdp.send("Page.captureScreenshot",{format:"png"});await writeFile(join(root,`test-results/interest-brief-${width}.png`),Buffer.from(shot.data,"base64"));}
  failure=true;await click("[data-refresh-brief]");await waitFor(()=>evaluate(cdp,"document.querySelector('[data-feed-brief]').innerText.includes('Synthetic read failure')"),"Read error missing");
  assert.equal(await evaluate(cdp,"!!document.querySelector('[data-brief-result]')"),false,"Error exposed old result");
  failure=false;status="stale";await click("[data-refresh-brief]");
  await waitFor(()=>evaluate(cdp,"!!document.querySelector('[data-brief-status=stale]')"),"Stale state missing");
  assert.equal(await evaluate(cdp,"!!document.querySelector('[data-brief-result]')"),false);
  await audit.check(cdp,`stale-${width}-${locale}`,"[data-feed-brief]");
  for(status of ["not_scheduled","pending","failed","runtime_unverified","not_current","unavailable"]){await click("[data-refresh-brief]");await waitFor(()=>evaluate(cdp,`!!document.querySelector('[data-brief-status=${status}]')`),`Missing ${status}`);assert.equal(await evaluate(cdp,"!!document.querySelector('[data-brief-result]')"),false);}
  // The existing shell initializes Marvin's private context/conversation. Those
  // unrelated requests receive synthetic 503s here; no assistant is contacted.
  const shellInitialization=new Set(["/api/assistant/context","/api/assistant/conversations"]);
  assert.deepEqual(requests.slice(start).filter(r=>r.method!=="GET"&&!shellInitialization.has(r.path)),[],"Reader performed a mutation");
 }
 assert.deepEqual(exceptions,[]);audit.finish(feedbackMode?30:20);console.log(feedbackMode?"Ten five-locale desktop/mobile feedback journeys passed: save, conflict, retained draft, uncertain-reply replay, withdrawal, paged history, escaping and no page reload; no model calls.":"Ten five-locale desktop/mobile saved-brief journeys passed; no automatic generation or writes.");
}catch(error){console.error({locale,status,exceptions,text:cdp?await evaluate(cdp,"document.body.innerText.slice(-2000)").catch(()=>"unavailable"):"none"});throw error;}
finally{cdp?.close();for(const child of [browser,server]){const ended=new Promise(r=>child.once("exit",r));child.kill();await Promise.race([ended,sleep(2000)]);}assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith("helvetic-brief-browser-"));await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});}
