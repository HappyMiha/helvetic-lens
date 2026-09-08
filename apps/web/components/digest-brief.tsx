"use client";

import Link from "next/link";
import type { DigestBrief as Brief, BriefClaim } from "@/lib/interest-brief";
import { interestBriefCopy } from "@/lib/interest-brief";
import { useI18n } from "@/lib/i18n";
import { digestInterestCopy } from "@/lib/digest-interest-copy";

export function DigestBrief({brief, eventUrl}: {brief?: Brief; eventUrl?: string}) {
  const {locale, dateTime} = useI18n();
  if (!brief) return null; // Older saved digests did not carry this projection.
  const copy = interestBriefCopy[locale];
  const status = brief.locale === locale.slice(0, 2) ? brief.status : "not_scheduled";
  function claim(value?: BriefClaim) {
    if (!value) return null;
    return <div className="space-y-1"><p>{value.text}</p><div className="flex flex-wrap gap-x-3">
      {value.evidence_ids.map((id, index) => brief?.evidence_links?.[id] && <Link key={id}
        className="underline inline-flex min-h-11 items-center" href={brief.evidence_links[id]}>{copy.source} {index + 1}</Link>)}
    </div></div>;
  }
  return <section data-digest-brief data-brief-status={status} className="mt-4 space-y-3 text-sm break-words" aria-label={copy.title}>
    <h4 className="font-semibold">{copy.title}</h4>
    <p>{copy.status[status]}</p>
    {status === "available" && <div lang={brief.locale} className="space-y-3">
      <p className="muted">{copy.saved}: {dateTime(brief.saved_at)}</p>
      {claim(brief.what_happened)}
      <p className="font-semibold">{copy.importance}: {copy.level[brief.importance?.level || "undetermined"]}</p>
      {claim(brief.importance)}
      <details><summary className="min-h-11 py-2 cursor-pointer">{copy.why}</summary>
        <ul className="space-y-3">{brief.why_in_radar?.map(reason => <li key={reason.interest_id}><strong>{reason.name}</strong>{claim(reason)}</li>)}</ul>
        {brief.more_reasons && <p>{digestInterestCopy[locale].brief_more}</p>}
      </details>
      <p className="font-semibold">{copy.next}</p>{claim(brief.next_step)}
      <details><summary className="min-h-11 py-2 cursor-pointer">{copy.limitations}</summary>
        <p>{brief.uncertainty}</p><ul>{brief.input_limitations?.map((value, index) => <li key={index} lang="en">{value}</li>)}</ul>
      </details>
    </div>}
    {eventUrl && <Link className="underline inline-flex min-h-11 items-center" href={eventUrl}>{digestInterestCopy[locale].open}</Link>}
  </section>;
}
