"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { interestBriefCopy, type DigestBrief, type BriefClaim } from "@/lib/interest-brief";
import { digestInterestCopy } from "@/lib/digest-interest-copy";

export function NotificationBrief({ brief, eventUrl, eventTitle, onNavigate, stale = false }: {
  brief?: DigestBrief; eventUrl: string; eventTitle: string; onNavigate?: () => void; stale?: boolean;
}) {
  const { locale, dateTime } = useI18n();
  if (!brief || stale) return null; // Failed refresh must not endorse old AI prose.
  const copy = interestBriefCopy[locale];
  const status = brief.locale === locale.slice(0, 2) ? brief.status : "not_scheduled";
  function claim(value?: BriefClaim) {
    if (!value) return null;
    return <div><p>{value.text}</p><div className="flex flex-wrap gap-x-3">
      {value.evidence_ids.map((id, index) => brief?.evidence_links?.[id] && <Link key={id}
        href={brief.evidence_links[id]} onClick={onNavigate}
        className="underline inline-flex min-h-11 items-center">{copy.source} {index + 1}</Link>)}
    </div></div>;
  }
  return <section data-notification-brief data-brief-status={status} className="mt-3 space-y-2 break-words" aria-label={`${copy.title}: ${eventTitle}`}>
    <p className="font-semibold">{copy.title}</p>
    {status !== "available" ? <p>{copy.status[status]}</p> : <div lang={brief.locale} className="space-y-2">
      {claim(brief.what_happened)}
      <p>{copy.importance}: <strong>{copy.level[brief.importance?.level || "undetermined"]}</strong></p>
      <details><summary className="min-h-11 py-2 cursor-pointer">{copy.why}</summary>
        <div className="space-y-3">
          <p>{copy.status.available}</p>
          <p>{copy.saved}: {dateTime(brief.saved_at)}</p>
          {claim(brief.importance)}
          <ul>{brief.why_in_radar?.map(reason => <li key={reason.interest_id}><strong>{reason.name}</strong>{claim(reason)}</li>)}</ul>
          {brief.more_reasons && <p>{digestInterestCopy[locale].brief_more}</p>}
          <p className="font-semibold">{copy.next}</p>{claim(brief.next_step)}
          <p className="font-semibold">{copy.limitations}</p><p>{brief.uncertainty}</p>
          <ul>{brief.input_limitations?.map((value, index) => <li key={index} lang="en">{value}</li>)}</ul>
          <Link href={eventUrl} onClick={onNavigate} className="underline inline-flex min-h-11 items-center">{digestInterestCopy[locale].open}</Link>
        </div>
      </details>
    </div>}
  </section>;
}
