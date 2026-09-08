"use client";

import { useState } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { invalidateResources, resourceTag, resources, useResource } from "@/lib/api";
import { interestBriefCopy, type BriefClaim, type SavedInterestBrief } from "@/lib/interest-brief";
import { ErrorNote, Loading } from "./common";
import { Button } from "./ui/button";
import { BriefRecoveryHistory } from "./brief-recovery-history";
import { InterestBriefRequest } from "./interest-brief-request";

export function FeedInterestBrief({eventId}: {eventId: string}) {
  const [open, setOpen] = useState(false);
  const {locale} = useI18n();
  return <details data-feed-brief className="border-t mt-4 pt-3" open={open}
    onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="min-h-11 cursor-pointer font-semibold py-2"><h3 className="inline text-base">{interestBriefCopy[locale].title}</h3></summary>
    {open && <Content key={`${eventId}:${locale}`} eventId={eventId} />}
  </details>;
}

function Content({eventId}: {eventId: string}) {
  const {locale, dateTime, t} = useI18n();
  const copy = interestBriefCopy[locale];
  const page = useResource(resources.interestBrief<SavedInterestBrief>(eventId, locale.slice(0, 2)));
  const data = !page.error && !page.loading ? page.data : undefined;
  const result = data?.status === "available" ? data.result : null;
  const refs = Object.keys(data?.evidence_links || {});
  function claim(value: BriefClaim) {
    return <><p>{value.text}</p><div className="flex flex-wrap gap-x-3">{value.evidence_ids.map(id =>
      data?.evidence_links?.[id] && <Link key={id} href={data.evidence_links[id]}
        className="inline-flex min-h-11 items-center underline">{copy.source} {refs.indexOf(id) + 1}</Link>)}</div></>;
  }
  return <div className="space-y-3 min-w-0 break-words" aria-busy={page.loading}>
    <p className="text-sm muted">{copy.help}</p>
    {page.loading && <Loading />}
    <ErrorNote message={page.error} />
    {data && <p className="text-sm muted">{t("briefPolicy.locale")}: <span lang={data.locale}>{({de:"Deutsch",fr:"Français",it:"Italiano",rm:"Rumantsch",en:"English"} as Record<string,string>)[data.locale] || data.locale}</span></p>}
    {data && <p role="status" data-brief-status={data.status} className="text-sm">{copy.status[data.status]}</p>}
    {data?.error_code && <ErrorNote message={t(({
      invalid_model_output: "briefRecovery.invalidOutput", invalid_citation: "briefRecovery.invalidOutput",
      model_timeout: "briefRecovery.timeout", cancelled: "briefRecovery.cancelled",
    } as Record<string, string>)[data.error_code] || "briefRecovery.unavailable")} />}
    {result && <section lang={data?.locale} className="space-y-4" data-brief-result>
      <p className="text-sm muted">{copy.saved}: {data?.saved_at ? dateTime(data.saved_at) : "—"}</p>
      <div className="font-semibold">{claim(result.what_happened)}</div>
      <div><h4 className="font-semibold">{copy.importance} · {copy.level[result.importance.level]}</h4>{claim(result.importance)}</div>
      <details><summary className="min-h-11 py-2 cursor-pointer font-semibold"><h4 className="inline">{copy.why}</h4></summary>
        <ul className="space-y-3">{result.why_in_radar.map(reason => <li key={reason.interest_id}>
          <h5 className="font-semibold">{data?.interest_names?.[reason.interest_id]}</h5>{claim(reason)}</li>)}</ul></details>
      <div><h4 className="font-semibold">{copy.next}</h4>{claim(result.next_step)}</div>
      <details><summary className="min-h-11 py-2 cursor-pointer font-semibold"><h4 className="inline">{copy.limitations}</h4></summary>
        <p>{result.uncertainty}</p><ul>{result.input_limitations.map((item, index) => <li key={index} lang="en">{item}</li>)}</ul></details>
    </section>}
    {data && !result && <InterestBriefRequest eventId={eventId} canRequest={data.status !== "failed"} recovery={data.recovery} />}
    {data?.recovery && <BriefRecoveryHistory recovery={data.recovery} />}
    <Button data-refresh-brief variant="outline" className="min-h-11 whitespace-normal" disabled={page.loading}
      onClick={() => void invalidateResources(resourceTag(`interest-brief:${eventId}`)).catch(() => {})}>{copy.refresh}</Button>
  </div>;
}
