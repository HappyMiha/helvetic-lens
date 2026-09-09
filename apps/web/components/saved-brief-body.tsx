"use client";

import Link from "next/link";
import {useI18n} from "@/lib/i18n";
import {interestBriefCopy, type BriefClaim, type SavedInterestBrief} from "@/lib/interest-brief";

export function SavedBriefBody({data,historical=false}: {data:Pick<SavedInterestBrief,"result"|"locale"|"evidence_links"|"interest_names"|"saved_at">;historical?:boolean}) {
  const {locale,dateTime}=useI18n(),copy=interestBriefCopy[locale];
  const result=data.result,refs=Object.keys(data.evidence_links||{});
  if(!result) return null;
  function claim(value:BriefClaim) {
    return <><p>{value.text}</p><div className="flex flex-wrap gap-x-3">{value.evidence_ids.map(id=>data.evidence_links?.[id]&&<Link key={id} href={data.evidence_links[id]} className="inline-flex min-h-11 items-center underline">{copy.source} {refs.indexOf(id)+1}</Link>)}</div></>;
  }
  return <section lang={data.locale} className="space-y-4" data-brief-result={historical?undefined:true} data-historical-result={historical?true:undefined}>
    <p className="text-sm muted">{copy.saved}: {data.saved_at?dateTime(data.saved_at):"—"}</p>
    <div className="font-semibold">{claim(result.what_happened)}</div>
    <div><h4 className="font-semibold">{copy.importance} · {copy.level[result.importance.level]}</h4>{claim(result.importance)}</div>
    <details><summary className="min-h-11 py-2 cursor-pointer font-semibold"><h4 className="inline">{copy.why}</h4></summary>
      <ul className="space-y-3">{result.why_in_radar.map(reason=><li key={reason.interest_id}><h5 className="font-semibold">{data.interest_names?.[reason.interest_id]}</h5>{claim(reason)}</li>)}</ul></details>
    <div><h4 className="font-semibold">{copy.next}</h4>{claim(result.next_step)}</div>
    <details><summary className="min-h-11 py-2 cursor-pointer font-semibold"><h4 className="inline">{copy.limitations}</h4></summary><p>{result.uncertainty}</p><ul>{result.input_limitations.map((item,index)=><li key={index} lang="en">{item}</li>)}</ul></details>
  </section>;
}
