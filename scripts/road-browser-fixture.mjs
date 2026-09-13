// Local disposable HTTP fixture for manual browser QA. No real accounts/sources.
import {createServer} from "node:http";
import {spawn} from "node:child_process";
import {once} from "node:events";
import {Readable} from "node:stream";
import {resolve} from "node:path";
import {readFile, mkdir, writeFile} from "node:fs/promises";

const root = resolve(import.meta.dirname, "..");
const reserve = createServer(); reserve.listen(0, "127.0.0.1"); await once(reserve, "listening");
const nextPort = reserve.address().port; await new Promise(done => reserve.close(done));
const child = spawn(process.execPath, [resolve(root, "node_modules/next/dist/bin/next"), "start", "-H", "127.0.0.1", "-p", String(nextPort)],
  {cwd:resolve(root,"apps/web"), env:process.env, windowsHide:true, stdio:["ignore","pipe","pipe"]});
child.stdout.on("data", chunk => process.stdout.write(chunk)); child.stderr.on("data", chunk => process.stderr.write(chunk));
const id="00000000-0000-4000-8000-000000000001", eventId="00000000-0000-4000-8000-000000000002", refId="00000000-0000-4000-8000-000000000003";
const time="2026-09-13T10:00:00+00:00";
const corridor={id:refId,name:"Synthetic corridor northbound",flow:"north",attribution:"Synthetic topology"};
const payload = (kind="road_closure",state="active") => ({state,corridors:{[refId]:{state,coverage:"verified",facts:[{
  kind,phase:state,probability:"certain",valid_from:"2026-09-13T09:00:00+00:00",valid_until:"2026-09-13T16:00:00+00:00",
  lanes_restricted:kind==="lane_restriction"?1:null,lanes_operational:kind==="lane_restriction"?1:null}]}}});
let state={locale:"en-CH",denied:false,available:true,stale:false,manager:true,sparse:false,emptyEvents:true};
let monitor={id,version:2,revision:1,status:"active",health:"ready",last_check_at:time,configuration:{
  template_id:"road-watch",template_version:1,name:"Private synthetic road",corridor_reference_ids:[refId],
  materiality:{event_kinds:["road_closure","lane_restriction"],minimum_delay_seconds:900,include_planned:true}}};
let event={id:eventId,monitor_id:id,version:3,sequence:2,reviewed_sequence:0,muted:false,updated_at:time};
let email={revision:0,configuration:{timezone:"Europe/Zurich",delivery:{email:"off",digest_at:null,quiet_hours:null}},
  consent_active:false,email_verified:true,uncertain_deliveries:0,recipient_email:"qa@example.invalid"};
const eventView=()=>({...event,payload:state.available?payload(state.kind||"lane_restriction"):null,availability:!state.available?"unavailable":state.stale?"stale":"available",attribution:state.available?"Synthetic official traffic source":null});
const version=n=>({sequence:n,payload:state.available?payload(n===1?"road_closure":state.kind||"lane_restriction"):null,
  availability:state.available?"available":"unavailable",attribution:state.available?"Synthetic official traffic source":null,created_at:time});
const requests=[];
const auditPath=resolve(root,"test-results/accessibility/road-manual.json");
const audits=await readFile(auditPath,"utf8").then(text=>JSON.parse(text)).catch(error=>{
  if(error.code==="ENOENT")return [];
  throw error;
});
const server = createServer(async(req,res)=>{
  const url=new URL(req.url,"http://127.0.0.1"), path=url.pathname;
  const json=(body,code=200)=>{res.writeHead(code,{"Content-Type":"application/json","Cache-Control":"no-store"});res.end(JSON.stringify(body));};
  try {
    if(path==="/__qa/axe.js") {res.writeHead(200,{"Content-Type":"text/javascript","Cache-Control":"no-store"});return res.end(await readFile(resolve(root,"node_modules/axe-core/axe.min.js")));}
    if(path.startsWith("/api/") || path.startsWith("/__qa/")) {
      let text="";for await(const chunk of req) {text+=chunk;if(text.length>2*1024*1024) throw Error("Fixture body too large");}
      const body=text?JSON.parse(text):{};
      if(path==="/__qa/audit" && req.method==="POST") {audits.push(body);await mkdir(resolve(root,"test-results/accessibility"),{recursive:true});await writeFile(resolve(root,"test-results/accessibility/road-manual.json"),JSON.stringify(audits,null,2));return json({saved:true});}
      if(path==="/__qa/state" && req.method==="POST"){state={...state,...body};return json(state);}
      if(path==="/__qa/requests") return json(requests);
      if(path==="/__qa/finish" && req.method==="POST") {json({finished:true});server.close();child.kill();return;}
      requests.push({path,method:req.method,query:url.search,body});
      if(path==="/api/auth/session") return json({authenticated:true,user:{id:"road-qa",name:"Road QA",email:"qa@example.invalid",locale:state.locale},
        organization:{id:"road-qa-org",name:"Synthetic QA"},role:state.manager?"organization_admin":"viewer",platform_admin:false,onboarding_required:false});
      if(path==="/api/health") return json({status:"ok",database:"synthetic",apertus:{configured:false},firecrawl:{configured:false}});
      if(path.startsWith("/api/road-watch")) {
        if(state.denied) return json({code:"membership_required"},403);
        const route=path.slice("/api/road-watch".length);
        if(route==="/capabilities")return json({drafts_available:true,start_available:state.available});
        if(route==="/catalog")return json({items:[corridor],next_cursor:null});
        if(route==="/preview")return json({configuration:body.configuration,corridors:[corridor],start_available:state.available});
        if(route==="/monitors") {
          if(req.method==="POST")monitor={...monitor,status:"draft",configuration:body.configuration};
          return json(req.method==="POST"?monitor:{items:monitor?[monitor]:[],next_cursor:null},req.method==="POST"?201:200);
        }
        if(route===`/monitors/${id}`) {
          if(req.method==="DELETE"){monitor=null;res.writeHead(204);return res.end();}
          if(req.method==="PATCH") monitor={...monitor,configuration:body.configuration,version:monitor.version+1,revision:monitor.revision+1,status:"draft"};
          return json(monitor);
        }
        if(route===`/monitors/${id}/corridors`)return json({items:state.available?[corridor]:[{id:refId,state:"unavailable"}],next_cursor:null});
        if(route===`/monitors/${id}/commands`) {monitor={...monitor,version:monitor.version+1,status:{start:"active",pause:"paused",resume:"active",archive:"archived"}[body.action]};return json(monitor);}
        if(route===`/monitors/${id}/revisions`)return json({items:[{revision:monitor.revision,configuration:monitor.configuration}],next_cursor:null});
        if(route===`/monitors/${id}/email`) {
          if(req.method==="PUT") {
            if(body.expected_version!==monitor.version)return json({code:"road_version_conflict"},409);
            monitor={...monitor,version:monitor.version+1};
            email={...email,configuration:body.configuration,revision:email.revision+1,consent_active:body.consent};
          }
          return json({...email,monitor_version:monitor.version,delivery_service_available:state.available});
        }
        if(route===`/monitors/${id}/email-preview`)return json({status:state.available&&email.consent_active?"ready":"unavailable",
          quiet_hours:!!email.configuration.delivery.quiet_hours,more_available:false,items:state.available&&email.consent_active?
          [{event_id:eventId,sequence:2,detected_at:time,href:`/road-watch?monitor=${id}&event=${eventId}&sequence=2`}]:[]});
        if(route===`/monitors/${id}/events`)return json({items:state.emptyEvents?[]:[eventView()],next_cursor:null});
        if(route===`/events/${eventId}`) {
          const sequence=Number(url.searchParams.get("sequence")||2);
          return json({event:eventView(),snapshot:version(sequence),previous:sequence>1?version(sequence-1):null,
            corridors:state.available?[corridor]:[],current_configuration:true,newer_available:sequence<2});
        }
        if(route===`/events/${eventId}/history`)return json({items:[version(1),version(2)],next_cursor:null});
        if(route===`/events/${eventId}/review`) {
          if(body.expected_version!==event.version)return json({code:"road_event_version_conflict"},409);
          event={...event,version:event.version+1,...(typeof body.muted==="boolean"?{muted:body.muted}:{reviewed_sequence:event.sequence})};
          return json({version:event.version,reviewed_sequence:event.reviewed_sequence});
        }
        if(route==="/today" || route==="/inbox") {
          const isInbox=route==="/inbox", metadata=isInbox?{has_active_routes:monitor?.status==="active",
            source_available:state.available&&!state.stale,unverified_routes:!state.available,unverified_count:state.stale?1:0}:{};
          if(state.sparse && !url.searchParams.has("cursor"))return json({items:[],next_cursor:eventId,...metadata});
          return json({...metadata,items:state.available && monitor?.status==="active" && !event.muted && event.reviewed_sequence<event.sequence &&
            (!isInbox||state.kind==="road_closure"&&!state.stale) ? [{id:eventId,monitor_id:id,name:monitor.configuration.name,
            event_id:eventId,sequence:2,detected_at:time,event:eventView(),corridors:[corridor],priority:state.kind==="road_closure"&&!state.stale?"urgent":"normal",reason:"unread_road_change",
            href:`/road-watch?monitor=${id}&event=${eventId}&sequence=2`}]:[],next_cursor:null});
        }
        return json({code:"fixture_unknown_road_route"},404);
      }
      if(path==="/api/interest-feed")return json({items:[],scanned_event_count:0,has_more:false,next_cursor:null});
      return json({code:"unavailable"},503);
    }
    const response=await fetch(`http://127.0.0.1:${nextPort}${req.url}`,{redirect:"manual",signal:AbortSignal.timeout(15000)});
    const headers=Object.fromEntries(response.headers);delete headers["content-encoding"];delete headers["content-length"];
    res.writeHead(response.status,headers);if(response.body)Readable.fromWeb(response.body).pipe(res);else res.end();
  } catch(error) {json({code:"fixture_error",detail:String(error)},500);}
});
server.listen(0,"127.0.0.1");await once(server,"listening");
console.log(JSON.stringify({fixture:`http://127.0.0.1:${server.address().port}`,nextPort,id,eventId}));
child.once("exit",code=>{server.close();process.exitCode=code||0;});
