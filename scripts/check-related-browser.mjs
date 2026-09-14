// Disposable local browser, built product and synthetic responses. No live writes.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { relatedCopy } from "../apps/web/lib/related-copy.ts";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
const root=resolve(import.meta.dirname,"..");
const chrome=[process.env.CHROME_BIN,"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe","/usr/bin/google-chrome"].filter(Boolean).find(existsSync);assert.ok(chrome);
const reserve=createServer();await new Promise(done=>reserve.listen(0,"127.0.0.1",done));const port=reserve.address().port;await new Promise(done=>reserve.close(done));const base=`http://127.0.0.1:${port}`;
const server=spawn(process.execPath,[join(root,"node_modules/next/dist/bin/next"),"start","-H","127.0.0.1","-p",String(port)],{cwd:join(root,"apps/web"),stdio:"ignore",windowsHide:true});
const profile=await mkdtemp(join(tmpdir(),"helvetic-related-qa-"));
const browser=spawn(chrome,["--headless=new","--no-first-run","--no-default-browser-check","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{stdio:"ignore",windowsHide:true});
let cdp,locale="en-CH",role="organization_admin",denied=false,revoked=false,empty=false;
const exceptions=[],mutations=[];const audit=new AccessibilityAudit("related-developments");
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,"0")}`;
const references=["warnings","river","traffic"].map((domain,n)=>({domain,monitor_id:id(n+10),event_id:id(n+20),revision:1,evidence_hash:"a".repeat(64)}));
function member(ref){return {reference:ref,monitor_name:"Private fixture "+ref.domain,availability:revoked&&ref.domain==="traffic"?"unavailable":"available",href:revoked&&ref.domain==="traffic"?null:`/${{warnings:"hazard",river:"river",traffic:"road"}[ref.domain]}-watch?monitor=${ref.monitor_id}&event=${ref.event_id}&revision=${ref.revision}`,...(revoked&&ref.domain==="traffic"?{}:{source_state:"active",authority:{namespace:ref.domain,identifier:"source-authority-"+ref.domain},source_at:"2026-09-14T09:00:00Z",source_until:ref.domain==="river"?null:"2026-09-14T18:00:00Z",time_kind:ref.domain==="river"?"instant":"interval",geography:{id:id(70),place_id:"2701",boundary_version:"2026-01",valid_until:"2026-10-01T00:00:00Z"},reviewed:false})};}
let versions=[{members:references,title:"Private local story",action:"create"}],status="active";
function detail(number=versions.length){const value=versions[number-1];return {id:id(1),title:value.title,version:versions.length,revision:number,status,historical:number!==versions.length,association_state:revoked?"unverified":value.members.length===1?"separate":"possible",members:value.members.map(member),links:[]};}
async function wait(check,message){for(let i=0;i<200;i++){if(await Promise.resolve().then(check).catch(()=>false))return;await sleep(100);}throw Error(message);}
const text=()=>evaluate(cdp,"document.querySelector('[data-related-developments]')?.innerText||''");
async function ready(label=relatedCopy[locale].stories){await wait(async()=>(await text()).includes(label)&&!(await text()).includes(relatedCopy[locale].loading),"Related page not ready: "+label);}
async function navigate(path="/related-developments"){await cdp.send("Page.navigate",{url:base+path});await ready();}
async function button(label){const q=`[...document.querySelectorAll('[data-related-developments] button')].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled)`;await wait(()=>evaluate(cdp,`!!(${q})`),`Missing button ${label}`);await evaluate(cdp,`(${q}).click()`);}
async function input(selector,value){await evaluate(cdp,`(()=>{const e=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));})()`);}
try {
  await wait(async()=>(await fetch(base)).ok,"Next did not start");let debugPort;
  await wait(async()=>{debugPort=(await readFile(join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0];return !!debugPort;},"Chrome did not start");
  const target=await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());cdp=new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");await cdp.send("Runtime.enable");cdp.on("Runtime.exceptionThrown",({exceptionDetails})=>exceptions.push(exceptionDetails.text));
  cdp.on("Fetch.requestPaused",async({requestId,request})=>{
    const url=new URL(request.url),path=url.pathname;let code=200,result={};const body=request.postData?JSON.parse(request.postData):{};
    if(path.startsWith("/api/related-developments")&&request.method!=="GET")mutations.push({path,body});
    if(path==="/api/auth/session")result={authenticated:true,user:{id:"qa-related",name:"QA",email:"qa@example.invalid",locale},organization:{id:"qa-org",name:"QA"},role,platform_admin:role==="organization_admin",onboarding_required:false};
    else if(path==="/api/health")result={status:"ok",database:"synthetic",apertus:{configured:false},firecrawl:{configured:false}};
    else if(path==="/api/jobs")result=[];
    else if(path.startsWith("/api/related-developments")){
      const route=path.slice("/api/related-developments".length);
      if(denied){code=403;result={code:"membership_required"};}
      else if(route==="/capabilities")result={can_write:role==="organization_admin",can_review_bindings:role==="organization_admin"};
      else if(route==="/candidates")result={items:empty?[]:references.filter(r=>r.domain===url.searchParams.get("domain")).map(member),next:null};
      else if(route.startsWith("/events/")){const ref=references.find(r=>route.endsWith(r.event_id));result=member({...ref,revision:2});}
      else if(route==="/preview")result={can_save:body.members.length>0&&!revoked,members:body.members.map(member),links:[{state:revoked?"unknown":"possible",reason:revoked?"source_unavailable":"same_verified_area_and_overlapping_time"}]};
      else if(route==="/stories"&&request.method==="GET")result={items:empty||url.searchParams.get("archived")==="true"!==(status==="archived")?[]:[detail()],next:null};
      else if(route==="/stories"&&request.method==="POST"){versions=[{members:body.members,title:body.title,action:"create"}];status="active";result=detail();code=201;}
      else if(route.endsWith("/history"))result={items:versions.map((v,n)=>({revision:n+1,action:v.action,created_at:"2026-09-14T10:00:00Z"})).reverse(),next:null};
      else if(route.startsWith("/stories/")&&request.method==="GET")result=detail(Number(url.searchParams.get("revision"))||versions.length);
      else if(route.startsWith("/stories/")&&request.method==="POST"){
        assert.equal(body.expected_version,versions.length);
        if(body.action==="revise")versions.push({members:body.members,title:body.title,action:body.members.length<versions.at(-1).members.length?"split":"merge"});
        else {status=body.action==="archive"?"archived":"active";versions.push({...versions.at(-1),action:body.action});}result=detail();
      }
      else if(route==="/bindings/inspect")result={fact:{source_revision:"b".repeat(64),source_feature:{namespace:"fixture",identifier:"reviewed-geography"},availability:"available"},source_feature_hash:"a".repeat(64),bindings:[]};
      else if(route.startsWith("/bindings/municipalities"))result={state:"verified",version:"2026-01",sha256:"a".repeat(64),municipality_code:"2701",municipality_name:"Basel",expires_on:"2026-10-01"};
      else if(route==="/bindings"){assert.equal(body.reviewed,true);assert.equal(body.evidence_hash.length,64);result={id:body.id};code=201;}
      else {code=404;result={code:"not_found"};}
    }else{code=503;result={code:"unavailable"};}
    await cdp.send("Fetch.fulfillRequest",{requestId,responseCode:code,responseHeaders:[{name:"Content-Type",value:"application/json"},{name:"Cache-Control",value:"no-store"}],body:Buffer.from(JSON.stringify(result)).toString("base64")}).catch(()=>{});
  });
  await cdp.send("Fetch.enable",{patterns:[{urlPattern:`${base}/api/*`,requestStage:"Request"}]});
  for(const language of Object.keys(relatedCopy)){
    locale=language;await cdp.send("Emulation.setDeviceMetricsOverride",{width:language==="en-CH"?1280:390,height:900,deviceScaleFactor:1,mobile:false});
    await navigate(`/related-developments?story=${id(1)}`);await ready(relatedCopy[locale].possible);
    for(const label of [relatedCopy[locale].title,relatedCopy[locale].noTransfer,relatedCopy[locale].instant])assert.ok((await text()).includes(label));
    assert.equal(await evaluate(cdp,"document.documentElement.scrollWidth<=innerWidth+1"),true,`Overflow ${locale}`);
    await audit.check(cdp,`story-${locale}`,"[data-related-developments]");
  }
  locale="en-CH";const c=relatedCopy[locale];await navigate(`/related-developments?story=${id(1)}`);await button(c.edit);await ready(c.save);
  await button(c.remove+" · "+c.traffic);await button(c.check);await ready(c.same_verified_area_and_overlapping_time);await button(c.save);await ready(c.possible);assert.equal(versions.at(-1).members.length,2);
  await audit.check(cdp,"split","[data-related-developments]");
  await navigate(`/related-developments?story=${id(1)}&revision=1`);await button(c.useRevision);await button(c.refreshMembers);await button(c.check);await button(c.save);await ready(c.possible);assert.equal(versions.at(-1).members.length,3);assert.ok(versions.at(-1).members.every(r=>r.revision===2));
  await button(c.archive);await ready(c.archived);await button(c.restore);await ready(c.active);
  await audit.check(cdp,"restored","[data-related-developments]");
  revoked=true;await button(c.refresh);await ready(c.unverified);assert.ok(!(await text()).includes("source-authority-traffic"));await audit.check(cdp,"source-revoked","[data-related-developments]");
  denied=true;await button(c.refresh);await wait(async()=>(await text()).includes(c.failed),"No denial");assert.ok(!(await text()).includes("source-authority-river"));await audit.check(cdp,"denied","[data-related-developments]");
  denied=false;revoked=false;await button(c.refresh);await ready(c.possible);
  await evaluate(cdp,"window.dispatchEvent(new PageTransitionEvent('pagehide'))");assert.ok(!(await text()).includes("source-authority"));
  await evaluate(cdp,"window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))");await ready(c.possible);
  await cdp.send("Input.dispatchKeyEvent",{type:"keyDown",key:"Tab",code:"Tab",windowsVirtualKeyCode:9});await cdp.send("Input.dispatchKeyEvent",{type:"keyUp",key:"Tab",code:"Tab",windowsVirtualKeyCode:9});assert.ok(await evaluate(cdp,"document.activeElement!==document.body"));
  role="viewer";await navigate(`/related-developments?story=${id(1)}`);await ready(c.readonly);assert.equal(await evaluate(cdp,`[...document.querySelectorAll('[data-related-developments] button')].find(b=>b.textContent===${JSON.stringify(c.edit)}).disabled`),true);await audit.check(cdp,"viewer","[data-related-developments]");
  role="organization_admin";empty=true;await navigate();await ready(c.noStories);await button(c.newStory);await ready(c.empty);await audit.check(cdp,"empty","[data-related-developments]");
  empty=false;await button(c.refresh);await ready(c.warnings);await wait(()=>evaluate(cdp,"!!document.querySelector('[data-related-developments] article input[type=checkbox]')"),"No candidate");
  await input('[data-related-developments] input[maxlength="200"]',"New complete group");
  for(const domain of ["warnings","river","traffic"]){await input('[data-related-developments] select',domain);await wait(()=>evaluate(cdp,`document.querySelector('[data-related-developments] article:has(input[type=checkbox]) h3')?.textContent.includes(${JSON.stringify("Private fixture "+domain)})`),"Candidate domain missing");await evaluate(cdp,"document.querySelector('[data-related-developments] article input[type=checkbox]').click()");}
  await button(c.bindingReview);await button(c.inspect);await ready(c.sourceFeature);
  await input('[data-related-developments] input[inputmode="numeric"]',"2701");await button(c.checkArea);await ready("Basel");
  await input('[data-related-developments] input[maxlength="64"]',"a".repeat(64));await input('[data-related-developments] input[type="datetime-local"]',"2026-09-30T12:00");
  await evaluate(cdp,"document.querySelector('[data-related-developments] fieldset input[type=checkbox]').click()");
  await audit.check(cdp,"binding-review","[data-related-developments]");await button(c.publish);await ready(c.save);
  await button(c.check);await button(c.save);await ready("New complete group");assert.equal(versions[0].members.length,3);
  await audit.check(cdp,"created","[data-related-developments]");
  assert.ok(mutations.filter(m=>m.path.includes("/stories")).every(m=>m.body.request_key));assert.deepEqual(exceptions,[]);audit.finish(13);
  console.log("Related developments: five locales/mobile, create/split/rejoin/history/archive, current refs, source and access redaction, page-return privacy, keyboard and viewer boundaries passed.");
} finally {
  cdp?.close();for(const child of [browser,server]){const stopped=new Promise(done=>child.once("exit",done));child.kill();await Promise.race([stopped,sleep(2000)]);}
  assert.equal(dirname(resolve(profile)),resolve(tmpdir()));assert.ok(basename(profile).startsWith("helvetic-related-qa-"));await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
