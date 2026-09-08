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
const root=resolve(import.meta.dirname,".."),audit=new AccessibilityAudit("interest-request");
const chrome=[process.env.CHROME_BIN,"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe","/usr/bin/google-chrome","/usr/bin/chromium"].filter(Boolean).find(existsSync);assert.ok(chrome);
const reserve=createServer();await new Promise(r=>reserve.listen(0,"127.0.0.1",r));const port=reserve.address().port;await new Promise(r=>reserve.close(r));
const base=`http://127.0.0.1:${port}`,profile=await mkdtemp(join(tmpdir(),"helvetic-request-browser-"));
const server=spawn(process.execPath,[join(root,"node_modules/next/dist/bin/next"),"start","-H","127.0.0.1","-p",String(port)],{cwd:join(root,"apps/web"),stdio:"ignore",windowsHide:true});
const browser=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{stdio:"ignore",windowsHide:true});
let cdp,locale="en-CH",status="not_scheduled",failure=false,admissionReads=0,generationReads=0,sendFailure=true;const requests=[],exceptions=[];
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
  const path=new URL(request.url).pathname;requests.push({path,search:new URL(request.url).search,method:request.method,body:request.postData});let body={},code=200;
  if(path==="/api/auth/session")body={authenticated:true,user:{id:`qa-${locale}`,locale,name:"QA",email:"qa@example.invalid"},organization:{id:"qa-org",name:"QA"},role:"viewer",platform_admin:false};
  else if(path==="/api/health")body={status:"ok",database:"postgresql",apertus:{configured:false},firecrawl:{configured:false}};
  else if(path==="/api/settings/interest-briefs")body={enabled:true};
  else if(path==="/api/interest-feed")body={items:[event],scanned_event_count:1,has_more:false,next_cursor:null};
  else if(path.endsWith("/brief/requests")){if(sendFailure){code=503;body={detail:"Synthetic request failure"};}else {body={job:{id:"synthetic-admission"},ai_calls:0};}}
  else if(path==="/api/jobs/synthetic-admission"){admissionReads++;body={id:"synthetic-admission",type:"interest_brief_admission",created_at:"2026-09-08T09:00:00Z",attempts:1,max_attempts:3,error:null,state:admissionReads<2?"running":"succeeded",result:{data:{outcomes:[{job_id:"synthetic-generation"}]}}};}
  else if(path==="/api/jobs/synthetic-generation"){generationReads++;status=generationReads<4?"pending":"available";body={id:"synthetic-generation",type:"interest_event_brief",created_at:"2026-09-08T09:00:00Z",attempts:1,max_attempts:3,error:null,state:generationReads<4?"running":"succeeded"};}
  else if(path.endsWith("/brief")){await sleep(120);if(failure){code=503;body={detail:"Synthetic read failure"};}else body=brief();}
  else if(["/api/laws","/api/scans","/api/jobs"].includes(path))body=[];
  else {code=503;body={detail:"Synthetic unrelated endpoint unavailable"};}
  await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"content-type",value:"application/json"}],body:Buffer.from(JSON.stringify(body)).toString("base64")});
 });await cdp.send("Fetch.enable",{patterns:[{urlPattern:"*/api/*"}]});
 async function click(selector){let point;await waitFor(async()=>{point=await evaluate(cdp,`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||e.disabled)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,ok:e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))};})()`);return point?.ok;},`Unreachable ${selector}`);for(const type of ["mousePressed","mouseReleased"])await cdp.send("Input.dispatchMouseEvent",{type,x:point.x,y:point.y,button:"left",clickCount:1});}
 for(const width of [390,1440])for(locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){
  failure=false;status="not_scheduled";sendFailure=true;admissionReads=0;generationReads=0;const start=requests.length;
  await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:960,deviceScaleFactor:1,mobile:width===390});
  await cdp.send("Page.navigate",{url:`${base}/?locale=${locale}&qa=${width}`});
  await waitFor(()=>evaluate(cdp,`document.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector('[data-feed-brief]')`),"Feed missing");
  await click("[data-feed-brief]>summary");
  await waitFor(()=>evaluate(cdp,"!!document.querySelector('[data-request-brief]')"),"Missing language request action");
  assert.equal(requests.slice(start).filter(r=>r.path.endsWith("/brief/requests")).length,0,"Read created AI work");
  await evaluate(cdp,"window.__briefMarker='retained'");
  await audit.check(cdp,`ready-${width}-${locale}`,"[data-feed-brief]");
  await click("[data-request-brief]");
  await waitFor(()=>evaluate(cdp,"document.querySelector('[data-brief-request]').innerText.includes('Synthetic request failure')"),"Request failure not shown");
  sendFailure=false;await click("[data-request-brief]");
  await waitFor(()=>evaluate(cdp,"document.querySelector('[data-request-brief]')?.disabled"),"Request did not yield to background work");
  assert.equal(await evaluate(cdp,"window.__briefMarker"),"retained");
  const writes=requests.slice(start).filter(r=>r.path.endsWith("/brief/requests"));
  assert.equal(writes.length,2);assert.equal(JSON.parse(writes[0].body).request_id,JSON.parse(writes[1].body).request_id);
  assert.ok(writes.every(r=>JSON.parse(r.body).locale===locale.slice(0,2)));
  await click("[data-brief-request] summary");
  await waitFor(()=>evaluate(cdp,"!!document.querySelector('[data-brief-request] details p')"),"Exact task detail did not load");
  if(locale==="en-CH"){const shot=await cdp.send("Page.captureScreenshot",{format:"png"});await writeFile(join(root,`test-results/interest-request-active-${width}.png`),Buffer.from(shot.data,"base64"));}
  await waitFor(()=>evaluate(cdp,"!!document.querySelector('[data-brief-result]')"),"Background completion did not refresh saved brief");
  assert.equal(await evaluate(cdp,"window.__briefMarker"),"retained");
  assert.equal(await evaluate(cdp,"document.querySelector('[data-brief-result]').lang"),locale.slice(0,2));
  assert.ok(await evaluate(cdp,"document.documentElement.scrollWidth<=innerWidth+1"));
  await audit.check(cdp,`complete-${width}-${locale}`,"[data-feed-brief]");
  if(locale==="en-CH"){const shot=await cdp.send("Page.captureScreenshot",{format:"png"});await writeFile(join(root,`test-results/interest-request-${width}.png`),Buffer.from(shot.data,"base64"));}
  const permitted=new Set(["/api/assistant/context","/api/assistant/conversations",`/api/interest-feed/events/${event.event_id}/brief/requests`]);
  assert.deepEqual(requests.slice(start).filter(r=>r.method!=="GET"&&!permitted.has(r.path)),[]);

 }
 assert.deepEqual(exceptions,[]);audit.finish(20);console.log("Ten five-locale desktop/mobile explicit language-request journeys passed; no writes before click, stable retry ID, two-stage background completion, no page reload.");
}catch(error){console.error({locale,status,exceptions,text:cdp?await evaluate(cdp,"document.body.innerText.slice(-2000)").catch(()=>"unavailable"):"none"});throw error;}
finally{cdp?.close();for(const child of [browser,server]){const ended=new Promise(r=>child.once("exit",r));child.kill();await Promise.race([ended,sleep(2000)]);}assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith("helvetic-request-browser-"));await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});}
