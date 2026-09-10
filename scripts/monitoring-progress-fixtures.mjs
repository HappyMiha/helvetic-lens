// Synthetic metadata only; never a second source of real backlog completion.
const pollen=["MV2-001","MV2-069","MV2-070","MV2-030","MV2-031","MV2-071"];
const titles={"MV2-001":"Extension contracts and MVP compatibility","MV2-069":"Confirm Pollen Watch sources and delivery contract","MV2-070":"Shared platform for Pollen Watch","MV2-030":"Official pollen observations and forecasts","MV2-031":"Complete Pollen Watch scenario","MV2-071":"Accept the scenario for testing with real users"};
const task=(id,status)=>({id,title:id==="MV2-074"?"Synthetic <img src=x onerror=alert(1)> task":`Synthetic: ${titles[id]||id}`,status});
const deferred=[26,27,61,63,64,65,66,67,68].map(id=>task(`MV2-0${id}`,"DEFERRED"));
const snapshot=(sha,tasks)=>({sha:sha.repeat(40),state:"available",reason:null,tasks});
const unavailable=()=>({sha:null,state:"unavailable",reason:"Synthetic progress source unavailable",tasks:[]});
export function monitoringProgressFixture(kind="divergent"){
  if(kind==="missing")return null;
  const latest=snapshot("a",[...pollen.map((id,index)=>task(id,["DONE","IN PROGRESS","PLANNED","READY","VERIFYING","BLOCKED"][index])),task("MV2-072","DONE"),task("MV2-073","IN PROGRESS"),task("MV2-074","DONE"),...deferred]);
  const deployed=snapshot("b",[...pollen.map((id,index)=>task(id,["PLANNED","READY","PLANNED","READY","VERIFYING","DONE"][index])),task("MV2-072","DONE"),task("MV2-073","PLANNED"),...deferred]);
  if(kind==="zero")for(const value of latest.tasks)if(value.status==="DONE")value.status="PLANNED";
  if(kind==="no-required")latest.tasks=[...deferred];
  if(kind==="older-pollen")deployed.tasks=deployed.tasks.filter(value=>value.id!=="MV2-071");
  return {schema_version:1,source_path:"BACKLOG_MONITORING_V2.md",updated_at:"2026-09-10T10:00:00Z",branch:"codex/HappyDucky02/monitoring-v2",latest:kind==="latest-unavailable"?unavailable():latest,deployed:kind==="deployed-unavailable"?unavailable():deployed};
}
