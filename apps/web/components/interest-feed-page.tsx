"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { api, errorText, invalidateResources, resourceTag, useResource, label } from "@/lib/api";
import { translate, useI18n } from "@/lib/i18n";
import { resources } from "@/lib/resource-keys";
import { Shell } from "./shell";
import { ErrorNote, Loading, Status } from "./common";
import { InboxPageNavigation } from "./inbox-page-navigation";
import { FeedEvidenceContext, type FeedEvidence } from "./feed-evidence-context";
import { Button } from "./ui/button";

type FeedEvent = FeedEvidence & {
  event_url?: string;
  event_id: string; title: string; type: string; document_kind: string; lifecycle_status: string | null;
  source: string; detected_at: string; source_url?: string; source_artifact_url?: string;
  official_dates: Array<{ kind: string; value: string; precision: string; provenance: string }>;
  severity: string; read_state: string;
  topic_matches: Array<{ id: string; name: string; url: string; confidence: string;
    reasons: Array<{ type: string; value?: string; values?: string[] }> }>;
  monitored_documents: Array<{ watch_id: string; name: string; url: string }>;
  law_impacts: Array<{ organization_candidate_id: string; law_title: string; status: string;
    severity: string; potential_effect: string; suggested_next_step: string; links: { timeline: string } }>;
};
type FeedPage = { items: FeedEvent[]; scanned_event_count: number; has_more: boolean; next_cursor: string | null };

const states = ["unread", "read", "dismissed", "muted"] as const;
function sourceLink(value?: string) {
  if (!value) return undefined;
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) ? url.href : undefined; }
  catch { return undefined; }
}

export function InterestFeedPage() {
  const { t, dateTime, locale } = useI18n();
  const periods = [["all", t("feed.all")], ["today", t("feed.today")], ["yesterday", t("feed.yesterday")], ["week", t("feed.week")], ["month", t("feed.month")]];
  const params = useSearchParams();
  const router = useRouter();
  const query = params.toString();
  const feed = useResource(resources.interestFeed<FeedPage>(query));
  const [busy, setBusy] = useState("");
  const [failure, setFailure] = useState("");
  const [notice, setNotice] = useState("");
  function href(patch: Record<string, string>) {
    const next = new URLSearchParams(query);
    for (const [key, value] of Object.entries(patch)) value ? next.set(key, value) : next.delete(key);
    return "/?" + next.toString();
  }
  async function setReadingState(item: FeedEvent, state: string) {
    setBusy(item.event_id); setFailure(""); setNotice("");
    try {
      await api(`/interest-feed/events/${item.event_id}/state`, { method: "PATCH", body: JSON.stringify({ state }) });
      await invalidateResources(resourceTag("impact-inbox", "organization"), resourceTag("digests", "organization"));
      setNotice(t("feed.saved"));
    } catch (error) { setFailure(errorText(error)); }
    finally { setBusy(""); }
  }
  return <Shell section={t("nav.today")}>
    <header className="page-heading">
      <div><h1>{t("feed.title")}</h1><p className="muted max-w-3xl">{t("feed.body")}</p></div>
      <Button variant="outline" onClick={() => { router.replace(href({ cursor: "" })); void invalidateResources(resourceTag("impact-inbox")); }}><RefreshCw size={16} />{t("inboxPaging.refresh")}</Button>
    </header>
    <nav className="flex flex-wrap gap-x-5 gap-y-2 mb-5 text-sm">
      <Link className="underline min-h-[44px] inline-flex items-center" href="/topics">{t("nav.topics")}</Link>
      <Link className="underline min-h-[44px] inline-flex items-center" href="/sources">{t("nav.sources")}</Link>
      <Link className="underline min-h-[44px] inline-flex items-center" href="/overview">{t("feed.overview")}</Link>
    </nav>
    <details className="rounded-lg border px-4 text-sm"><summary className="cursor-pointer min-h-[44px] flex items-center">{t("feed.coverage")}</summary><p>{t("feed.boundary")}</p></details>
    <div className="grid grid-cols-2 gap-4 my-5">
      <label className="text-sm">{t("feed.detected")}<select className="interest-feed-control w-full mt-2 min-h-[44px]" value={params.get("period") || "all"} onChange={event => router.push(href({ period: event.target.value, cursor: "" }))}>
        {periods.map(([period, text]) => <option key={period} value={period}>{text}</option>)}
      </select></label>
      <label className="text-sm">{t("filter.myState")}<select className="interest-feed-control w-full mt-2 min-h-[44px]" value={params.get("state") || ""} onChange={event => router.push(href({ state: event.target.value, cursor: "" }))}>
        <option value="">{t("filter.allStates")}</option>{states.map(state => <option key={state} value={state}>{t(`status.${state}`)}</option>)}
      </select></label>
    </div>
    {params.has("event") && <div className="rounded-lg border p-4 mb-4"><p>{t("feedEvidence.linked")}</p><Link data-feed-all className="underline min-h-[44px] inline-flex items-center" href={href({ event: "", cursor: "", period: "", state: "" })}>{t("feedEvidence.allEvents")}</Link></div>}
    <ErrorNote message={feed.error || failure} />
    <p role="status" className="text-sm">{notice}</p>
    {feed.loading && !feed.data && <Loading />}
    {feed.data?.items.length === 0 && <p className="card p-6">{t("feed.empty")}</p>}
    <div className="space-y-5">
      {feed.data?.items.map(item => <article key={item.event_id} data-feed-event={item.event_id} className="interest-feed-event rounded-xl border bg-white p-4 sm:p-6 min-w-0 break-words">
        <div className="flex flex-wrap items-center gap-2 text-sm"><Status value={item.read_state} /><span>{item.source}</span><span>{translate(locale, `topics.kind.${item.document_kind}`) || label(item.document_kind)}</span><span>{translate(locale, `topics.kind.${item.type}`) || label(item.type)}</span></div>
        <h2 className="text-xl mt-3 mb-3">{item.title}</h2>
        <dl className="text-sm grid gap-2 sm:grid-cols-2 mb-4">
          <div><dt className="muted">{t("feed.detected")}</dt><dd>{dateTime(item.detected_at, { dateStyle: "medium", timeStyle: "short" })}</dd></div>
          <div><dt className="muted">{t("feed.officialStatus")}</dt><dd><Status value={item.lifecycle_status} /></dd></div>
        </dl>
        <FeedEvidenceContext item={item} />
        {sourceLink(item.source_url) && <a href={sourceLink(item.source_url)} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-[44px] items-center underline font-semibold">{t("common.officialSource")}</a>}
        <Link data-feed-permalink className="underline inline-flex min-h-[44px] items-center ml-4" href={href({ event: item.event_id, cursor: "", period: "", state: "" })}>{t("feedEvidence.openEvent")}</Link>
        {item.monitored_documents?.length > 0 && <section className="border-t mt-3 pt-4"><h3 className="text-base font-semibold">{t("registry.monitored")}</h3>
          <ul>{item.monitored_documents.map(document => <li key={document.watch_id}><Link href={document.url} className="underline min-h-[44px] inline-flex items-center">{document.name}</Link></li>)}</ul>
        </section>}
        {item.topic_matches.length > 0 && <section className="border-t mt-3 pt-4">
          <h3 className="text-base font-semibold">{t("nav.topics")}</h3><p className="text-sm muted">{t("feed.topicBoundary")}</p>
          <ul className="space-y-3">{item.topic_matches.map(topic => <li key={topic.id}>
            <Link href={topic.url} className="underline min-h-[44px] inline-flex items-center">{topic.name}</Link>
            <p className="text-sm mt-0">{t("topics.matchReason", { reasons: [...new Set(topic.reasons.flatMap(reason => reason.values || (reason.value ? [reason.value] : [])))].join(" · ") })}</p><p className="text-sm muted">{t("feed.confidence")}: <Status value={topic.confidence} /></p>
            <Link className="underline inline-flex min-h-[44px] items-center text-sm" href={`/topic-review?match=${encodeURIComponent(topic.id)}`}>{t("topicReview.open")}</Link>
          </li>)}</ul>
        </section>}
        {item.law_impacts.length > 0 && <section className="border-t mt-3 pt-4"><h3 className="text-base font-semibold">{t("registry.monitored")}</h3>
          <ul className="space-y-4">{item.law_impacts.map(law => <li key={law.organization_candidate_id}>
            <Link href={law.links.timeline} className="font-semibold underline min-h-[44px] inline-flex items-center">{law.law_title}</Link>
            <div className="flex flex-wrap gap-2"><Status value={law.status} /><Status value={law.severity} /></div>
            <details className="text-sm mt-2"><summary className="cursor-pointer min-h-[44px]">{t("impact.effect")}</summary><p>{law.potential_effect}</p><p>{law.suggested_next_step}</p></details>
            <Link href={`/impact?candidate=${encodeURIComponent(law.organization_candidate_id)}`} className="underline min-h-[44px] inline-flex items-center">{t("feed.review")}</Link>
          </li>)}</ul>
        </section>}
        <label className="text-sm block border-t mt-4 pt-4">{t("filter.myState")}<select disabled={busy === item.event_id} value={item.read_state} className="interest-feed-control block mt-2 min-h-[44px] w-full sm:w-auto" onChange={event => void setReadingState(item, event.target.value)}>
          {states.map(state => <option key={state} value={state}>{t(`status.${state}`)}</option>)}
        </select></label>
      </article>)}
    </div>
    <InboxPageNavigation page={feed.data ? { ...feed.data, total_events: feed.data.items.length } : undefined}
      newestHref={params.has("cursor") ? href({ cursor: "" }) : undefined}
      nextHref={feed.data?.next_cursor ? href({ cursor: feed.data.next_cursor }) : undefined} />
  </Shell>;
}
