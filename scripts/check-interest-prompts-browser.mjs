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
const root=resolve(import.meta.dirname,".."),audit=new AccessibilityAudit("interest-prompts");
const chrome=[process.env.CHROME_BIN,"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe","/usr/bin/google-chrome","/usr/bin/chromium"].filter(Boolean).find(existsSync);assert.ok(chrome);
const reserve=createServer();await new Promise(r=>reserve.listen(0,"127.0.0.1",r));const port=reserve.address().port;await new Promise(r=>reserve.close(r));
const base=`http://127.0.0.1:${port}`,profile=await mkdtemp(join(tmpdir(),"helvetic-prompt-browser-"));
const server=spawn(process.execPath,[join(root,"node_modules/next/dist/bin/next"),"start","-H","127.0.0.1","-p",String(port)],{cwd:join(root,"apps/web"),stdio:"ignore",windowsHide:true});
const browser=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{stdio:"ignore",windowsHide:true});

let cdp,locale="en-CH",scope="organization",role="organization_admin",failure=false,revision=1;
const requests=[],exceptions=[];
const fields=["impact_instructions","impact_synthesis_instructions","ask_instructions","answer_synthesis_instructions","repair_instructions"];
let saved;
function defaults(){return {...Object.fromEntries(fields.map(k=>[k,"Synthetic review guidance with enough characters."])),interest_brief_instructions:"",ask_context_mode:"automatic",revision,fingerprint:`synthetic-${revision}`,source:"defaults",updated_at:null};}
async function waitFor(check,message){for(let i=0;i<180;i++){if(await check().catch(()=>false))return;await sleep(100);}throw new Error(message);}
try{
 await waitFor(async()=>(await fetch(`${base}/prompts`,{signal:AbortSignal.timeout(2000)})).ok,"Isolated UI not ready");
 let debugPort;await waitFor(async()=>{debugPort=(await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0];return debugPort;},"Chrome not ready");
 const tab=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());cdp=new Cdp(tab.webSocketDebuggerUrl);
 await cdp.send("Page.enable");await cdp.send("Runtime.enable");cdp.on("Runtime.exceptionThrown",({exceptionDetails})=>exceptions.push(exceptionDetails.exception?.description||exceptionDetails.text));
 cdp.on("Fetch.requestPaused",async({requestId,request})=>{
  const path=new URL(request.url).pathname;requests.push({path,method:request.method,body:request.postData});let body={},code=200;
  if(path==="/api/auth/session")body={authenticated:true,user:{id:`qa-${locale}-${role}`,locale,name:"QA",email:"qa@example.invalid"},organization:{id:"qa-org",name:"QA"},role,platform_admin:scope==="platform"&&role==="organization_admin"};
  else if(path==="/api/health")body={status:"ok",database:"postgresql",apertus:{configured:false},firecrawl:{configured:false}};
  else if(["/api/settings/prompts","/api/admin/prompts"].includes(path)){
   if(request.method==="PATCH"){
    if(failure){code=503;body={detail:"Synthetic save failure"};}
    else {revision++;saved={...saved,...JSON.parse(request.postData),revision,fingerprint:`synthetic-${revision}`,source:"saved"};body=saved;}
   }else body=saved;
  }
  else {code=503;body={detail:"Synthetic unrelated endpoint unavailable"};}
  await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"content-type",value:"application/json"}],body:Buffer.from(JSON.stringify(body)).toString("base64")});
 });await cdp.send("Fetch.enable",{patterns:[{urlPattern:"*/api/*"}]});
 async function click(selector){let point;await waitFor(async()=>{point=await evaluate(cdp,`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||e.disabled)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,ok:e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))};})()`);return point?.ok;},`Unreachable ${selector}`);for(const type of ["mousePressed","mouseReleased"])await cdp.send("Input.dispatchMouseEvent",{type,x:point.x,y:point.y,button:"left",clickCount:1});}

 async function type(text){await click("#interest_brief_instructions");await cdp.send("Input.dispatchKeyEvent",{type:"keyDown",key:"a",code:"KeyA",modifiers:2,windowsVirtualKeyCode:65});await cdp.send("Input.dispatchKeyEvent",{type:"keyUp",key:"a",code:"KeyA",modifiers:2,windowsVirtualKeyCode:65});await cdp.send("Input.insertText",{text});}
 for(const width of [390,1440])for(locale of ["de-CH","fr-CH","it-CH","rm-CH","en-CH"]){
  scope="organization";role="organization_admin";failure=false;saved=defaults();const start=requests.length;
  await cdp.send("Emulation.setDeviceMetricsOverride",{width,height:960,deviceScaleFactor:1,mobile:width===390});
  await cdp.send("Page.navigate",{url:`${base}/prompts?locale=${locale}&qa=${width}`});
  await waitFor(()=>evaluate(cdp,`document.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector('#interest_brief_instructions')`),"Prompt editor missing");
  assert.ok(await evaluate(cdp,"!document.querySelector('#interest_brief_instructions').required && document.querySelector('#interest_brief_instructions').maxLength===4000"));
  assert.ok(await evaluate(cdp,"document.documentElement.scrollWidth<=innerWidth+1"));
  assert.ok(await evaluate(cdp,"document.querySelector('#interest_brief_instructions').parentElement.querySelector('.field-help').innerText.replace(/[^0-9]/g,'').endsWith('4000')"),"Displayed limit differs from field limit");
  await evaluate(cdp,"window.__promptMarker='retained'");
  await type(`Synthetic focus ${locale}`);
  await audit.check(cdp,`editor-${width}-${locale}`,"#interest_brief_instructions");
  if(locale==="en-CH"){const shot=await cdp.send("Page.captureScreenshot",{format:"png"});await writeFile(join(root,`test-results/interest-prompts-${width}.png`),Buffer.from(shot.data,"base64"));}
  failure=true;await click("form button[type=submit]");await waitFor(()=>evaluate(cdp,"document.body.innerText.includes('Synthetic save failure')"),"Save error missing");
  assert.equal(await evaluate(cdp,"document.querySelector('#interest_brief_instructions').value"),`Synthetic focus ${locale}`);
  failure=false;await click("form button[type=submit]");await waitFor(()=>evaluate(cdp,"document.querySelector('form button[type=submit]').disabled && !document.querySelector('form button[type=submit] .animate-spin')"),"Save did not settle");
  await waitFor(()=>Promise.resolve(saved.interest_brief_instructions===`Synthetic focus ${locale}`),"Saved focus missing");
  await waitFor(()=>evaluate(cdp,"document.querySelector('form button[type=submit]').disabled && !document.querySelector('form button[type=submit] .animate-spin')"),"Saved UI did not settle");
  await type(""); // Select-all plus Backspace makes an intentional empty override.
  await cdp.send("Input.dispatchKeyEvent",{type:"keyDown",key:"Backspace",code:"Backspace",windowsVirtualKeyCode:8});await cdp.send("Input.dispatchKeyEvent",{type:"keyUp",key:"Backspace",code:"Backspace",windowsVirtualKeyCode:8});
  await click("form button[type=submit]");await waitFor(()=>Promise.resolve(saved.interest_brief_instructions===""),"Empty override was rejected");
  assert.equal(await evaluate(cdp,"window.__promptMarker"),"retained","Save reloaded the page");
  const allowed=new Set(["/api/settings/prompts","/api/assistant/context","/api/assistant/conversations"]);
  assert.deepEqual(requests.slice(start).filter(r=>r.method!=="GET"&&!allowed.has(r.path)),[],"Save triggered unrelated generation or mutation");
 }
 scope="platform";saved=defaults();await cdp.send("Page.navigate",{url:`${base}/prompts?scope=platform&qa=global`});
 await waitFor(()=>evaluate(cdp,"!!document.querySelector('#interest_brief_instructions')"),"Platform editor missing");
 await type("Synthetic global focus");await click("form button[type=submit]");await waitFor(()=>Promise.resolve(saved.interest_brief_instructions==="Synthetic global focus"),"Global save failed");
 assert.ok(requests.some(r=>r.path==="/api/admin/prompts"&&r.method==="PATCH"));
 role="viewer";const before=requests.length;await cdp.send("Page.navigate",{url:`${base}/prompts?scope=platform&qa=denied`});
 await waitFor(()=>evaluate(cdp,"!!document.querySelector('[role=alert]')"),"Denied state missing");
 assert.equal(await evaluate(cdp,"!!document.querySelector('#interest_brief_instructions')"),false);
 assert.equal(requests.slice(before).filter(r=>r.path==="/api/admin/prompts").length,0);
 assert.deepEqual(exceptions,[]);audit.finish(10);console.log("Ten five-locale desktop/mobile prompt edit/error/retry/empty-save journeys, platform save and viewer denial passed; no AI calls.");
}catch(error){console.error({locale,scope,exceptions,text:cdp?await evaluate(cdp,"document.body.innerText.slice(-2000)").catch(()=>"unavailable"):"none"});throw error;}
finally{cdp?.close();for(const child of [browser,server]){const ended=new Promise(r=>child.once("exit",r));child.kill();await Promise.race([ended,sleep(2000)]);}assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith("helvetic-prompt-browser-"));await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});}
