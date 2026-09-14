// Disposable localhost UI fixture. All identities, settings and grants are synthetic.
import {createServer} from "node:http";
import {spawn} from "node:child_process";
import {once} from "node:events";
import {Readable} from "node:stream";
import {resolve} from "node:path";
import {readFile,writeFile,mkdir} from "node:fs/promises";

const root=resolve(import.meta.dirname,"..");
const reserve=createServer();reserve.listen(0,"127.0.0.1");await once(reserve,"listening");
const nextPort=reserve.address().port;await new Promise(done=>reserve.close(done));
const child=spawn(process.execPath,[resolve(root,"node_modules/next/dist/bin/next"),"start","-H","127.0.0.1","-p",String(nextPort)],
  {cwd:resolve(root,"apps/web"),env:process.env,windowsHide:true,stdio:["ignore","pipe","pipe"]});
child.stdout.on("data",data=>process.stdout.write(data));child.stderr.on("data",data=>process.stderr.write(data));
let state={locale:"en-CH",denied:false,manager:true,geography:"verified"};
let monitor=null,history=[],statusActions=[];
const id="00000000-0000-4000-8000-000000000011",requests=[],audits=[];
const eventId="00000000-0000-4000-8000-000000000022";
let eventRows=[],reviewAudit=[],mutedHazards=[];
let emailConfig={timezone:"Europe/Zurich",delivery:{email:"off",digest_at:null,quiet_hours:null}},emailRevision=0;
function eventFixture(){return {id:eventId,monitor_id:id,version:1,revision:1,historical:false,state:"active",
  material_sequence:1,reviewed:false,dismissed:false,needs_review:true,muted:false,
  decision:{hazards:["storm"],importance:"warning",certainty:"Observed",match:{basis:"explicit_geometry"}},
  source:{attribution:"Synthetic warning authority",last_seen_at:"2026-09-13T10:00:00+00:00",message:{identity:{sent:"2026-09-13T09:00:00+00:00"},
    infos:[{language:"en-CH",event:"Synthetic storm",headline:"Warning for the saved place",description:"Original description from the synthetic source.",
      instruction:"Stay indoors.\nClose windows. <script>window.__hazardInjected = true</script>",web:"https://example.invalid/official-warning",
      effective:"2026-09-13T09:00:00+00:00",expires:"2026-09-14T09:00:00+00:00"},
    {language:"de-CH",event:"Synthetischer Sturm",headline:"Warnung für den gespeicherten Ort",instruction:"Bleiben Sie im Haus.",web:"https://example.invalid/official-warning"}]}}};}
function eventView(row,historical=false){
  if(state.nativeUnavailable&&!historical)return {id:row.id,monitor_id:id,version:eventRows[0].version,revision:row.revision,historical,state:"unavailable",reason:state.nativeUnavailable};
  if(state.evidenceUnavailable)return {id:row.id,monitor_id:id,version:eventRows[0].version,revision:row.revision,historical,state:"unavailable",reason:"hazard_evidence_unavailable"};
  return {...structuredClone(row),version:eventRows[0].version,historical,muted:mutedHazards.includes("storm")};
}
const server=createServer(async(req,res)=>{
  const url=new URL(req.url,"http://127.0.0.1"),path=url.pathname;
  const json=(body,status=200)=>{res.writeHead(status,{"Content-Type":"application/json","Cache-Control":"no-store"});res.end(JSON.stringify(body));};
  try{
    if(path==="/__qa/axe.js"){res.writeHead(200,{"Content-Type":"text/javascript"});return res.end(await readFile(resolve(root,"node_modules/axe-core/axe.min.js")));}
    if(path.startsWith("/api/")||path.startsWith("/__qa/")){
      let text="";for await(const chunk of req){text+=chunk;if(text.length>1024*1024)throw Error("Fixture input limit");}
      const body=text?JSON.parse(text):{};
      if(path==="/__qa/state"&&req.method==="POST"){state={...state,...body};return json(state);}
      if(path==="/__qa/seed-events"&&req.method==="POST"){
        monitor={id,status:"active",version:2,revision:1,configuration:{template_id:"hazard-watch",template_version:1,name:"Home warning fixture",
          location:{kind:"point",country:"CH",canton:"BS",latitude:47.56,longitude:7.59,radius_km:0},hazards:["storm"],minimum_importance:"warning"}};
        history=[{revision:1,configuration:monitor.configuration}];eventRows=[eventFixture()];reviewAudit=[];mutedHazards=[];
        if(body.native){
          const source=eventRows[0].source;
          source.history_complete=false;source.message.profile="meteoalarm-v2";
          source.message.infos[0].web="http://example.invalid/official-warning";
          source.message.infos[0].parameters=[["impacts","Falling branches. <script>window.__hazardInjected=true</script>"]];
          source.redistribution={url:"https://meteoalarm.org/en/live/",terms_url:"https://meteoalarm.org/en/live/page/terms-and-conditions",disclaimer:"Synthetic redistribution delay disclaimer."};
        }
        state={...state,denied:false,manager:true,evidenceUnavailable:false,nativeUnavailable:null,nativeSource:!!body.native};return json({id,eventId});
      }
      if(path==="/__qa/seed-lifecycle"&&req.method==="POST"){
        emailConfig={timezone:"Europe/Zurich",delivery:{email:"off",digest_at:null,quiet_hours:null}};emailRevision=0;
        monitor={id,status:"draft",health:"not_started",version:1,revision:1,last_poll_at:null,next_poll_at:null,
          configuration:{template_id:"hazard-watch",template_version:1,name:"Private lifecycle fixture",
            location:{kind:"point",country:"CH",canton:"BS",latitude:47.56,longitude:7.59,radius_km:0},hazards:["storm"],minimum_importance:"warning"}};
        history=[{revision:1,configuration:monitor.configuration}];eventRows=[];reviewAudit=[];mutedHazards=[];statusActions=[];
        state={...state,denied:false,manager:true,evidenceUnavailable:false,lifecycleReady:false};return json({id});
      }
      if(path==="/__qa/event"&&req.method==="POST"){
        const old=eventRows[0],row=structuredClone(old);row.version++;row.revision++;
        if(body.mode!=="translate"){row.material_sequence++;row.reviewed=false;row.dismissed=false;row.needs_review=true;}
        if(body.mode==="escalate"){row.decision.importance="alarm";row.source.message.infos[0].instruction="Evacuate through the north exit.";}
        if(body.mode==="translate")row.source.message.infos.push({language:"fr-CH",event:"Tempête synthétique",instruction:"Restez à l’intérieur."});
        if(body.mode==="cancel"){row.state="cancelled";row.source.message.infos=[];}
        if(body.mode==="resolve"){row.state="resolved";row.source.message.infos[0].instruction="All-clear issued by the synthetic authority.";}
        eventRows.unshift(row);return json({revision:row.revision});
      }
      if(path==="/__qa/requests")return json(requests);
      if(path==="/__qa/audit"&&req.method==="POST"){audits.push(body);await mkdir(resolve(root,"test-results/accessibility"),{recursive:true});await writeFile(resolve(root,"test-results/accessibility",state.suite==="email"?"hazard-email-audit.json":state.suite==="events"?"hazard-events-audit.json":"hazard-manual.json"),JSON.stringify(audits,null,2));return json({saved:true});}
      if(path==="/__qa/finish"&&req.method==="POST"){
        await mkdir(resolve(root,".tmp"),{recursive:true});await writeFile(resolve(root,".tmp",state.suite==="events"?"hazard-events-browser-requests.json":"hazard-browser-requests.json"),JSON.stringify(requests,null,2));
        json({finished:true});server.close();child.kill();return;
      }
      requests.push({path,method:req.method,query:url.search,body});
      if(path==="/api/auth/session")return json({authenticated:true,user:{id:"hazard-qa",name:"Hazard QA",email:"qa@example.invalid",locale:state.locale},organization:{id:"hazard-qa-org",name:"Synthetic QA"},role:state.manager?"organization_admin":"viewer",platform_admin:false,onboarding_required:false});
      if(path==="/api/health")return json({status:"ok",database:"synthetic",apertus:{configured:false},firecrawl:{configured:false}});
      if(path.startsWith("/api/hazard-watch")){
        if(state.denied)return json({code:"membership_required"},403);
        if(req.method!=="GET"&&!state.manager)return json({code:"subject_role_denied"},403);
        const route=path.slice("/api/hazard-watch".length);
        if(route==="/today"||route==="/inbox"){
          if(state.feedFailure)return json({code:"hazard_source_unavailable"},503);
          const current=eventRows[0]&&eventView(eventRows[0]);
          const item=current&&current.state!=="unavailable"&&current.needs_review&&!current.muted&&
            (route==="/today"||["active","planned"].includes(current.state))?
            {id:eventId,monitor_id:id,name:monitor.configuration.name,event_id:eventId,revision:current.revision,state:current.state,
             importance:current.decision.importance,certainty:current.decision.certainty,attribution:current.source.attribution,
             detected_at:"2026-09-13T10:00:00+00:00",last_seen_at:current.source.last_seen_at,
             href:`/hazard-watch?monitor=${id}&event=${eventId}&revision=${current.revision}`} : null;
          const continuation=state.feedContinuation&&!url.searchParams.has("cursor");
          const payload={items:item&&!continuation?[item]:[],next_cursor:continuation?"00000000-0000-4000-8000-000000000033":null,
            coverage_verified:false,has_active_places:!!monitor,unavailable_count:state.evidenceUnavailable?1:0};
          if(state.delayFeedMs)await new Promise(done=>setTimeout(done,state.delayFeedMs));return json(payload);
        }
        if(route==="/capabilities")return json({drafts_available:true,start_available:false,live_results_checked:false,
          ...(state.nativeSource?{source:state.nativeUnavailable?{state:"unavailable",supported_hazards:[]}:
            {state:"current",supported_hazards:["storm"],attribution:"Synthetic warning authority",last_poll_at:"2026-09-14T09:00:00Z"}}:{})});
        if(route==="/preview")return json({configuration:body.configuration,draft_available:true,start_available:false,live_results_checked:false,
          geography:state.geography==="verified"?{state:"verified",reason:"point_in_municipality",version:"2026-01",municipality_name:"Basel fixture",municipality_code:"2701",attribution:"Synthetic geography fixture",radius_coverage_verified:false}
          :{state:["outside_switzerland","municipality_canton_mismatch"].includes(state.geography)?"no_match":"unavailable",reason:state.geography}});
        if(route==="/monitors"){
          if(req.method==="POST"){
            monitor={id,status:"draft",configuration:body.configuration,version:1,revision:1};
            history=[{revision:1,configuration:body.configuration}];return json(monitor,201);
          }
          return json({items:monitor?[monitor]:[],next_cursor:null});
        }
        if(!monitor)return json({code:"hazard_monitor_not_found"},404);
        if(route===`/monitors/${id}/email`){
          if(state.emailDelay)await new Promise(done=>setTimeout(done,1000));
          if(req.method==="PUT"){
            if(body.expected_version!==monitor.version||state.emailConflict)return json({code:"hazard_version_conflict"},409);
            if(body.configuration.delivery.email!=="off"&&(!body.consent||state.emailVerified===false))return json({code:"hazard_email_unavailable"},409);
            emailConfig=structuredClone(body.configuration);emailRevision++;monitor.version++;
          }
          return json({revision:emailRevision,monitor_version:monitor.version,configuration:emailConfig,
            consent_active:emailConfig.delivery.email!=="off",email_verified:state.emailVerified!==false,
            recipient_email:"synthetic@example.invalid",uncertain_deliveries:state.emailUncertain?1:0,
            delivery_service_available:state.emailService!==false});
        }
        if(route===`/monitors/${id}/email-preview`)return json({status:state.evidenceUnavailable?"unavailable":"ready",
          quiet_hours:!!emailConfig.delivery.quiet_hours,more_available:false,
          items:state.evidenceUnavailable||emailConfig.delivery.email==="off"?[]:[{event_id:eventId,revision:1,
            detected_at:"2026-09-13T10:00:00+00:00",href:`/hazard-watch?monitor=${id}&event=${eventId}&revision=1`}]});
        if(route===`/monitors/${id}/readiness`){
          const ready=!!state.lifecycleReady&&!state.evidenceUnavailable;
          return json({version:monitor.version,start_available:ready&&["draft","paused"].includes(monitor.status),
            source_scope_verified:ready,blocking_reasons:ready?[]:[state.readinessCode||"hazard_source_not_configured"],live_results_checked:false});
        }
        if(route===`/monitors/${id}/actions`)return json({items:statusActions,next_cursor:null});
        if(route===`/monitors/${id}/commands`&&req.method==="POST"){
          if(body.expected_version!==monitor.version)return json({code:"hazard_version_conflict"},409);
          const allowed={start:["draft"],resume:["paused"],pause:["active"],archive:["draft","active","paused"]};
          if(!allowed[body.action]?.includes(monitor.status))return json({code:"hazard_action_invalid"},409);
          if(["start","resume"].includes(body.action)&&(!state.lifecycleReady||state.evidenceUnavailable))return json({code:"hazard_source_poll_not_current"},409);
          const previous=monitor.status;monitor.status={start:"active",resume:"active",pause:"paused",archive:"archived"}[body.action];monitor.version++;
          monitor.health=monitor.status==="active"?"waiting":monitor.status;
          statusActions.unshift({id:crypto.randomUUID(),action:body.action,previous_status:previous,status:monitor.status,
            version:monitor.version,configuration_revision:monitor.revision,created_at:"2026-09-13T10:00:00+00:00"});
          return json(monitor);
        }
        const eventRoot=`/monitors/${id}/events`,reader=`${eventRoot}/${eventId}`;
        if(route===eventRoot){return json({items:eventRows.length?[eventView(eventRows[0])].map(({source,...row})=>row):[],next_cursor:null,coverage_verified:false});}
        if(route===reader){if(state.delayEventMs)await new Promise(done=>setTimeout(done,state.delayEventMs));const revision=url.searchParams.get("revision"),row=revision?eventRows.find(r=>r.revision===Number(revision)):eventRows[0];
          return row?json(eventView(row,revision!==null)):json({code:"hazard_event_missing"},404);}
        if(route===reader+"/history")return json({items:eventRows.map(row=>eventView(row,true)).map(({source,...row})=>row),next_cursor:null});
        if(route===reader+"/reviews")return json({items:reviewAudit,next_cursor:null});
        if(route===reader+"/review"){
          const row=eventRows[0];if(!row||body.expected_version!==row.version||body.expected_revision!==row.revision)return json({code:"hazard_event_review_conflict"},409);
          if(state.evidenceUnavailable)return json({code:"hazard_event_review_conflict"},409);
          row.version++;row[body.action==="reviewed"?"reviewed":"dismissed"]=true;row.needs_review=false;
          reviewAudit.unshift({id:crypto.randomUUID(),revision:row.revision,material_sequence:row.material_sequence,action:body.action,created_at:"2026-09-13T10:01:00+00:00"});
          return json(eventView(row));
        }
        if(route===`/monitors/${id}/mutes`)return json({monitor_id:id,version:monitor.version,muted_hazards:mutedHazards});
        if(route.startsWith(`/monitors/${id}/mutes/`)&&req.method==="PATCH"){
          if(body.expected_version!==monitor.version)return json({code:"hazard_mute_conflict"},409);
          const kind=route.split("/").at(-1);mutedHazards=body.muted?[...new Set([...mutedHazards,kind])]:mutedHazards.filter(v=>v!==kind);monitor.version++;
          return json({monitor_id:id,version:monitor.version,muted_hazards:mutedHazards});
        }
        if(route===`/monitors/${id}/revisions`)return json({items:history,next_cursor:null});
        if(req.method!=="GET"&&body.expected_version!==monitor.version)return json({code:"hazard_version_conflict"},409);
        if(route===`/monitors/${id}/archive`){monitor={...monitor,status:"archived",version:monitor.version+1};return json(monitor);}
        if(route===`/monitors/${id}`){
          if(req.method==="DELETE"){monitor=null;history=[];return json({deleted:true});}
          if(req.method==="PATCH"){
            monitor={...monitor,configuration:body.configuration,version:monitor.version+1,revision:monitor.revision+1};
            history.unshift({revision:monitor.revision,configuration:monitor.configuration});
          }
          return json(monitor);
        }
        return json({code:"fixture_unknown_route"},404);
      }
      return json({code:"unavailable"},503);
    }
    const response=await fetch(`http://127.0.0.1:${nextPort}${req.url}`,{redirect:"manual",signal:AbortSignal.timeout(15000)});
    const headers=Object.fromEntries(response.headers);delete headers["content-encoding"];delete headers["content-length"];
    res.writeHead(response.status,headers);if(response.body)Readable.fromWeb(response.body).pipe(res);else res.end();
  }catch(error){json({code:"fixture_error",detail:String(error)},500);}
});
server.listen(0,"127.0.0.1");await once(server,"listening");
console.log(JSON.stringify({fixture:`http://127.0.0.1:${server.address().port}`,nextPort,id}));
child.once("exit",code=>{server.close();process.exitCode=code||0;});
