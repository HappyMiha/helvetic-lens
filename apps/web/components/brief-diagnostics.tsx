"use client";
import Link from "next/link";
import {useState} from "react";
import {useI18n} from "@/lib/i18n";
import {resources,useResource} from "@/lib/api";
import {briefDiagnosticsCopy,type BriefDiagnosticsPage} from "@/lib/brief-diagnostics";
import {Button} from "./ui/button";
import {ErrorNote,Loading,Status} from "./common";

export function BriefDiagnostics(){
 const {locale}=useI18n(),[open,setOpen]=useState(false);
 return <details data-brief-diagnostics className="rounded-xl border p-4 mb-5" open={open} onToggle={event=>setOpen(event.currentTarget.open)}>
  <summary className="min-h-11 cursor-pointer font-semibold">{briefDiagnosticsCopy[locale].title}</summary>{open&&<Content/>}
 </details>;
}
function Content(){
 const {locale,t,number,dateTime}=useI18n(),copy=briefDiagnosticsCopy[locale];
 const [days,setDays]=useState(7),[status,setStatus]=useState(""),[cursor,setCursor]=useState("");
 const page=useResource(resources.briefDiagnostics<BriefDiagnosticsPage>(days,status,cursor));
 const data=!page.loading&&!page.error?page.data:null;
 const value=(n:number|null)=>n===null?copy.unknown:number(n);
 return <div className="space-y-4 min-w-0 break-words" aria-busy={page.loading}>
  <p className="text-sm muted">{copy.help}</p>
  <div className="flex flex-wrap gap-3"><label>{copy.days}<select data-diagnostic-days className="field block" value={days} onChange={e=>{setDays(Number(e.target.value));setCursor("");}}>{[1,7,30,90].map(n=><option key={n} value={n}>{number(n)}</option>)}</select></label>
  <label>{copy.all}<select data-diagnostic-state className="field block" value={status} onChange={e=>{setStatus(e.target.value);setCursor("");}}><option value="">{copy.all}</option>{["queued","running","succeeded","failed","superseded"].map(s=><option key={s} value={s}>{t(`status.${s}`)}</option>)}</select></label></div>
  {page.loading&&<Loading/>}<ErrorNote message={page.error}/>
  {data&&!data.items.length&&<p>{copy.empty}</p>}
  <ul className="space-y-4">{data?.items.map(row=><li key={row.id} data-brief-diagnostic={row.id} className="border rounded-lg p-4 space-y-3">
   <div className="flex flex-wrap justify-between gap-2"><time dateTime={row.created_at}>{dateTime(row.created_at)}</time><Status value={row.status}/></div>
   <p>{copy.model}: {row.model||copy.unknown} · <span lang={row.locale}>{row.locale}</span> · {copy.attempts}: {number(row.attempts)}</p>
   <dl className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">{[[copy.calls,row.measurement.provider_calls],[copy.tokens,row.measurement.input_tokens],[copy.duration,row.measurement.duration_ms],[copy.coverage,row.measurement.measured_calls]].map(([label,n])=><div key={String(label)}><dt className="text-sm muted">{label}</dt><dd className="font-semibold">{value(n as number|null)}</dd></div>)}</dl>
   {row.measurement.state==="invalid"&&<p>{copy.invalid}</p>}
   {row.measurement.state==="recorded"&&!row.measurement.complete_input_coverage&&<p>{copy.partial}</p>}
   <Link className="underline inline-block min-h-11 py-2" href={`/?event=${encodeURIComponent(row.event_id)}`}>{copy.event}</Link>
  </li>)}</ul>
  <div className="flex flex-wrap gap-2">{cursor&&<Button data-diagnostic-first variant="outline" disabled={page.loading} onClick={()=>setCursor("")}>{copy.first}</Button>}{data?.next_cursor&&<Button data-diagnostic-older variant="outline" disabled={page.loading} onClick={()=>setCursor(data.next_cursor!)}>{copy.older}</Button>}<Button data-diagnostic-refresh variant="outline" disabled={page.loading} onClick={page.reload}>{copy.refresh}</Button></div>
 </div>;
}
