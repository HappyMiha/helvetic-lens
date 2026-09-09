"use client";

import {useState} from "react";
import {invalidateResources,resourceTag,resources,useResource} from "@/lib/api";
import {briefHistoryCopy,type BriefHistoryPage,type HistoricalBrief,type HistoryItem} from "@/lib/brief-history";
import {briefReviewCopy} from "@/lib/brief-review";
import {useI18n} from "@/lib/i18n";
import {ErrorNote,Loading} from "./common";
import {Button} from "./ui/button";
import {SavedBriefBody} from "./saved-brief-body";

export function BriefHistory({eventId}:{eventId:string}) {
  const {locale}=useI18n(),[open,setOpen]=useState(false);
  return <details data-brief-history className="border-t mt-3 pt-3" open={open} onToggle={event=>setOpen(event.currentTarget.open)}>
    <summary className="min-h-11 py-2 cursor-pointer font-semibold">{briefHistoryCopy[locale].title}</summary>
    {open&&<HistoryPage key={`${eventId}:${locale}`} eventId={eventId}/>}
  </details>;
}

function HistoryPage({eventId}:{eventId:string}) {
  const {locale}=useI18n(),copy=briefHistoryCopy[locale],[cursor,setCursor]=useState("");
  const page=useResource(resources.briefHistory<BriefHistoryPage>(eventId,locale.slice(0,2),cursor));
  const data=!page.error&&!page.loading?page.data:null;
  return <div className="space-y-3 min-w-0 break-words" aria-busy={page.loading}>
    <p className="text-sm muted">{copy.help}</p>
    {page.loading&&<Loading/>}<ErrorNote message={page.error?copy.error:""}/>
    {data&&data.items.length===0&&<p>{copy.empty}</p>}
    <ul className="space-y-4">{data?.items.map(item=><li key={item.id}><HistoryRow item={item}/></li>)}</ul>
    <div className="flex flex-wrap gap-2">{cursor&&<Button data-history-first variant="outline" disabled={page.loading} onClick={()=>setCursor("")}>{copy.first}</Button>}{data?.next_cursor&&<Button data-history-older variant="outline" disabled={page.loading} onClick={()=>setCursor(data.next_cursor!)}>{copy.older}</Button>}
      <Button data-history-refresh variant="outline" disabled={page.loading} onClick={()=>void invalidateResources(resourceTag(`brief-history:${eventId}`))}>{copy.refresh}</Button></div>
  </div>;
}

function HistoryRow({item}:{item:HistoryItem}) {
  const {locale,dateTime}=useI18n(),copy=briefHistoryCopy[locale],[open,setOpen]=useState(false);
  return <article className="rounded-lg border p-3 space-y-2" data-history-item={item.id}>
    <p className="font-semibold"><time dateTime={item.finished_at||item.created_at}>{dateTime(item.finished_at||item.created_at)}</time> · {copy[item.status]}</p>
    <p className="text-sm">{copy.model}: {item.model||"—"} · {copy.profile}: {item.profile_revision} · {copy.attempts}: {item.attempts}</p>
    {item.status==="succeeded"&&<details open={open} onToggle={event=>setOpen(event.currentTarget.open)} data-history-inspect>
      <summary className="min-h-11 cursor-pointer py-2 underline">{copy.open}</summary>
      {open&&<HistoryDetail id={item.id}/>}</details>}
  </article>;
}

function HistoryDetail({id}:{id:string}) {
  const {locale}=useI18n(),copy=briefHistoryCopy[locale];
  const page=useResource(resources.historicalBrief<HistoricalBrief>(id)),data=!page.error&&!page.loading?page.data:null;
  return <div className="space-y-3 min-w-0 break-words" aria-busy={page.loading}>
    {page.loading&&<Loading/>}<ErrorNote message={page.error?copy.error:""}/>
    {data&&<p role="status" data-history-status={data.status} className="rounded-lg border p-3 text-sm">{copy[data.status]}</p>}
    {data?.review&&<p className="font-semibold">{briefReviewCopy[locale][data.review.decision]}</p>}
    {data?.status==="historical"&&data.result&&<SavedBriefBody data={data} historical/>}
    {data?.provenance&&<details><summary className="min-h-11 py-2 cursor-pointer">{copy.provenance}</summary>
      <p className="text-sm">{copy.model}: {data.provenance.model.model} ({data.provenance.model.route}) · {copy.profile}: {data.provenance.profile_revision}</p>
      <code className="text-xs break-all">{data.provenance.input_fingerprint}</code></details>}
    <Button data-history-detail-refresh variant="outline" disabled={page.loading} onClick={()=>void invalidateResources(resourceTag(`historical-brief:${id}`))}>{copy.refresh}</Button>
  </div>;
}
