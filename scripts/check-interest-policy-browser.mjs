// Real production prompt UI with intercepted synthetic API; no model or user data.
import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import {existsSync} from "node:fs";
import {mkdtemp, readFile, rm, writeFile} from "node:fs/promises";
import {tmpdir} from "node:os";
import {basename, dirname, join, resolve} from "node:path";
import {createServer} from "node:net";
import {Cdp, evaluate, sleep} from "./browser-cdp.mjs";
import {AccessibilityAudit} from "./browser-accessibility.mjs";
const root=resolve(import.meta.dirname,".."),audit=new AccessibilityAudit("interest-policy");
const chrome=[process.env.CHROME_BIN,"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe","/usr/bin/google-chrome","/usr/bin/chromium"].filter(Boolean).find(existsSync);assert.ok(chrome);
const reserve=createServer();await new Promise(r=>reserve.listen(0,"127.0.0.1",r));const port=reserve.address().port;await new Promise(r=>reserve.close(r));
const base=`http://127.0.0.1:${port}`,profile=await mkdtemp(join(tmpdir(),"helvetic-policy-browser-"));
const server=spawn(process.execPath,[join(root,"node_modules/next/dist/bin/next"),"start","-H","127.0.0.1","-p",String(port)],{cwd:join(root,"apps/web"),stdio:"ignore",windowsHide:true});
const browser=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{stdio:"ignore",windowsHide:true});


let cdp,locale="en-CH",role="organization_admin",failure=false,conflict=false,saved;
const requests=[],exceptions=[];
function defaults(){return {enabled:false,locale:"en",max_pending:4,max_daily:20,revision:0,source:"environment",updated_at:null,usage:{pending:0,last_24_hours:0},hard_limits:{max_pending:4,max_daily:20},ai_calls:0};}
const model={provider:"docker",product_id:"",base_url:"http://synthetic-manager/openai/v1",model:"local-apertus",explanation_profile:"",explanation_registry_valid:true,explanation_profiles:[],timeout_seconds:90,request_retries:2,batch_concurrency:1,context_chars:24000,max_tokens:1600,temperature:0.1,top_p:1,presence_penalty:0,reasoning_effort:"default",json_mode:true,configured:true,api_key_configured:false,key_source:"none",source:"workspace",updated_at:null};
async function waitFor(check,message){for(let i=0;i<180;i++){if(await check().catch(()=>false))return;await sleep(100);}throw new Error(message);}
try{
 await waitFor(async()=>(await fetch(`${base}/settings`,{signal:AbortSignal.timeout(2000)})).ok,"Isolated UI not ready");
 let debugPort;await waitFor(async()=>{debugPort=(await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0];return debugPort;},"Chrome not ready");
 const tab=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());cdp=new Cdp(tab.webSocketDebuggerUrl);
 await cdp.send("Page.enable");await cdp.send("Runtime.enable");cdp.on("Runtime.exceptionThrown",({exceptionDetails})=>exceptions.push(exceptionDetails.exception?.description||exceptionDetails.text));
 cdp.on("Fetch.requestPaused",async({requestId,request})=>{
  const path=new URL(request.url).pathname;requests.push({path,method:request.method,body:request.postData});let body={},code=200;
  if(path==="/api/auth/session")body={authenticated:true,user:{id:`qa-${locale}-${role}`,locale,name:"QA",email:"qa@example.invalid"},organization:{id:"qa-org",name:"QA"},role,platform_admin:false};
  else if(path==="/api/health")body={status:"ok",database:"postgresql",apertus:{configured:false},firecrawl:{configured:false}};
  else if(path==="/api/settings/apertus")body=model;
  else if(path==="/api/profile")body={name:"QA organization",business_areas:[],description:""};
  else if(path==="/api/settings/interest-briefs"){
    if(request.method==="PATCH"){
      if(failure){code=503;body={detail:"Synthetic save failure"};}
      else if(conflict){code=409;saved={...saved,max_daily:6,revision:saved.revision+1};body={detail:"Synthetic revision conflict"};}
      else {const data=JSON.parse(request.postData);assert.equal(data.revision,saved.revision);saved={...saved,...data,revision:saved.revision+1,source:"organization"};body=saved;}
    }else body=saved;
  }else {code=503;body={detail:"Synthetic unrelated endpoint unavailable"};}
  await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"content-type",value:"application/json"}],body:Buffer.from(JSON.stringify(body)).toString("base64")});
 });await cdp.send("Fetch.enable",{patterns:[{urlPattern:"*/api/*"}]});
 async function click(selector){let point;await waitFor(async()=>{point=await evaluate(cdp,`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||e.disabled)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,ok:e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))};})()`);return point?.ok;},`Unreachable ${selector}`);for(const type of ["mousePressed","mouseReleased"])await cdp.send("Input.dispatchMouseEvent",{type,x:point.x,y:point.y,button:"left",clickCount:1});}


 async function type(selector,text){await click(selector);await cdp.send("Input.dispatchKeyEvent",{type:"keyDown",key:"a",code:"KeyA",modifiers:2,windowsVirtualKeyCode:65});await cdp.send("Input.dispatchKeyEvent",{type:"keyUp",key:"a",code:"KeyA",modifiers:2,windowsVirtualKeyCode:65});await cdp.send("Input.insertText",{text});}
 async function key(name,code){for(const type of ["keyDown","keyUp"])await cdp.send("Input.dispatchKeyEvent",{type,key:name,windowsVirtualKeyCode:code});}
 for(const width of [390,1440])for(locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"])for(role of ["organization_admin","viewer"]){
  saved=defaults();failure=false;conflict=false;const before=requests.length;
  await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:960,deviceScaleFactor:1,mobile:width===390});
  await cdp.send("Page.navigate",{url:`${base}/settings?locale=${locale}&qa=${width}-${role}`});
  await waitFor(()=>evaluate(cdp,`document.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector('#brief-policy-enabled')`),"Policy form missing");
  await evaluate(cdp,"window.__policyMarker='retained'");
  assert.ok(await evaluate(cdp,"document.documentElement.scrollWidth<=innerWidth+1"));
  assert.equal(requests.slice(before).filter(r=>r.method==="PATCH").length,0);
  if(role==="viewer"){
    assert.ok(await evaluate(cdp,"document.querySelector('[data-brief-policy] fieldset').disabled"));
    await audit.check(cdp,`viewer-${width}-${locale}`,"[data-brief-policy]");continue;
  }
  await click("#brief-policy-enabled");
  assert.equal(await evaluate(cdp,"!!document.querySelector('#brief-policy-locale')"),false,"Admin must not override user language");
  await type("#brief-policy-pending","2");await type("#brief-policy-daily","3");
  assert.equal(requests.slice(before).filter(r=>r.method==="PATCH").length,0);
  await audit.check(cdp,`admin-${width}-${locale}`,"[data-brief-policy]");
  if(locale==="en-CH"){await evaluate(cdp,"document.querySelector('[data-brief-policy]').scrollIntoView({block:'center'})");const shot=await cdp.send("Page.captureScreenshot",{format:"png"});await writeFile(join(root,`test-results/interest-policy-${width}.png`),Buffer.from(shot.data,"base64"));}
  failure=true;await click("[data-brief-policy] button[type=submit]");await waitFor(()=>evaluate(cdp,"document.querySelector('[data-brief-policy]').innerText.includes('Synthetic save failure')"),"Save error missing");
  assert.ok(await evaluate(cdp,"document.querySelector('#brief-policy-enabled').checked"));
  failure=false;await click("[data-brief-policy] button[type=submit]");
  await waitFor(()=>evaluate(cdp,"!document.querySelector('[data-brief-policy] fieldset').disabled && document.querySelector('[data-brief-policy] button[type=submit]').disabled"),"Saved UI did not settle");
  assert.equal(saved.enabled,true);assert.equal(saved.locale,"en");assert.equal(saved.max_pending,2);assert.equal(saved.max_daily,3);
  await type("#brief-policy-daily","4");conflict=true;await click("[data-brief-policy] button[type=submit]");
  await waitFor(()=>evaluate(cdp,"document.querySelector('[data-brief-policy]').innerText.includes('Synthetic revision conflict')"),"Revision conflict missing");
  assert.equal(await evaluate(cdp,"document.querySelector('#brief-policy-daily').value"),"4");
  conflict=false;await click("[data-brief-policy] button[type=button]");
  await waitFor(()=>evaluate(cdp,"document.querySelector('#brief-policy-daily').value==='6'"),"Reload did not show saved policy");
  assert.equal(await evaluate(cdp,"window.__policyMarker"),"retained");
  const allowed=new Set(["/api/settings/interest-briefs","/api/assistant/context","/api/assistant/conversations"]);
  assert.deepEqual(requests.slice(before).filter(r=>r.method!=="GET"&&!allowed.has(r.path)),[],"Policy editing started unrelated work");
 }
 assert.deepEqual(exceptions,[]);audit.finish(20);console.log("Twenty five-locale mobile/desktop admin/viewer policy journeys passed; edits require save, failures preserve drafts, conflicts reload explicitly, and no model calls occur.");
}catch(error){console.error({locale,role,exceptions,text:cdp?await evaluate(cdp,"document.body.innerText.slice(0,3500)").catch(()=>"unavailable"):"none"});throw error;}
finally{cdp?.close();for(const child of [browser,server]){const ended=new Promise(r=>child.once("exit",r));child.kill();await Promise.race([ended,sleep(2000)]);}assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith("helvetic-policy-browser-"));await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});}
