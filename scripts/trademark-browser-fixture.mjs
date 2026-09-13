// Disposable localhost UI fixture; synthetic identities and brands, no IPI access.
import {createServer} from "node:http";
import {spawn} from "node:child_process";
import {once} from "node:events";
import {Readable} from "node:stream";
import {resolve} from "node:path";
import {readFile,writeFile,mkdir} from "node:fs/promises";
const root=resolve(import.meta.dirname,".."),id="00000000-0000-4000-8000-000000000071";
const reserve=createServer();reserve.listen(0,"127.0.0.1");await once(reserve,"listening");
const nextPort=reserve.address().port;await new Promise(done=>reserve.close(done));
const child=spawn(process.execPath,[resolve(root,"node_modules/next/dist/bin/next"),"start","-H","127.0.0.1","-p",String(nextPort)],
  {cwd:resolve(root,"apps/web"),env:process.env,windowsHide:true,stdio:["ignore","pipe","pipe"]});
child.stdout.on("data",data=>process.stdout.write(data));child.stderr.on("data",data=>process.stderr.write(data));
let state={locale:"en-CH",manager:true,denied:false,conflict:false},monitor=null,history=[];
const requests=[],audits=[];
const server=createServer(async(req,res)=>{
  const url=new URL(req.url,"http://127.0.0.1"),path=url.pathname;
  const json=(value,status=200)=>{res.writeHead(status,{"Content-Type":"application/json","Cache-Control":"no-store"});res.end(JSON.stringify(value));};
  try{
    if(path==="/__qa/axe.js"){res.writeHead(200,{"Content-Type":"text/javascript"});return res.end(await readFile(resolve(root,"node_modules/axe-core/axe.min.js")));}
    if(path.startsWith("/api/")||path.startsWith("/__qa/")){
      let text="";for await(const chunk of req){text+=chunk;if(text.length>1024*1024)throw Error("Fixture input limit");}
      const body=text?JSON.parse(text):{};
      if(path==="/__qa/state"){state={...state,...body};return json(state);}
      if(path==="/__qa/requests")return json(requests);
      if(path==="/__qa/audit"){audits.push(body);await mkdir(resolve(root,"test-results/accessibility"),{recursive:true});await writeFile(resolve(root,"test-results/accessibility/trademark-audit.json"),JSON.stringify(audits,null,2));return json({saved:true});}
      if(path==="/__qa/finish"){
        await writeFile(resolve(root,".tmp/trademark-browser-requests.json"),JSON.stringify(requests,null,2));
        json({finished:true});server.close();child.kill();return;
      }
      requests.push({path,method:req.method,body});
      if(path==="/api/auth/session")return json({authenticated:true,user:{id:"ip-qa",name:"IP QA",email:"synthetic@example.invalid",locale:state.locale},organization:{id:"ip-qa-org",name:"Synthetic QA"},role:state.manager?"organization_admin":"viewer",platform_admin:false,onboarding_required:false});
      if(path==="/api/health")return json({status:"ok",database:"synthetic",apertus:{configured:false},firecrawl:{configured:false}});
      if(path.startsWith("/api/trademark-watch")){
        if(state.denied)return json({code:"membership_required"},403);
        if(req.method!=="GET"&&!state.manager)return json({code:"subject_role_denied"},403);
        const route=path.slice("/api/trademark-watch".length);
        if(route==="/capabilities")return json({drafts_available:true,start_available:false,live_results_checked:false});
        if(route==="/monitors"){
          if(req.method==="POST"){
            monitor={id,status:"draft",configuration:body.configuration,version:1,revision:1};history=[{revision:1,configuration:structuredClone(body.configuration)}];return json(monitor,201);
          }
          return json({items:monitor?[monitor]:[],next_cursor:null});
        }
        if(!monitor)return json({code:"trademark_monitor_not_found"},404);
        if(route===`/monitors/${id}/revisions`)return json({items:history,next_cursor:null});
        if(req.method!=="GET"&&(body.expected_version!==monitor.version||state.conflict))return json({code:"trademark_version_conflict"},409);
        if(route===`/monitors/${id}/archive`){monitor={...monitor,status:"archived",version:monitor.version+1};return json(monitor);}
        if(route===`/monitors/${id}`){
          if(req.method==="DELETE"){monitor=null;history=[];return json({deleted:true});}
          if(req.method==="PATCH"){
            monitor={...monitor,configuration:body.configuration,version:monitor.version+1,revision:monitor.revision+1};
            history.unshift({revision:monitor.revision,configuration:structuredClone(body.configuration)});
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
server.listen(0,"127.0.0.1");await once(server,"listening");console.log(JSON.stringify({fixture:`http://127.0.0.1:${server.address().port}`,nextPort,id}));
child.once("exit",code=>{server.close();process.exitCode=code||0;});
