"use client";
import Link from "next/link";
import { useResource } from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { useI18n } from "@/lib/i18n";
import { Button } from "./ui/button";
import { ErrorNote, Loading, Status } from "./common";

export function FeedEmptyState({ more, nextHref, filtered, linked }: {
  more: boolean; nextHref?: string; filtered: boolean; linked: boolean;
}) {
  const { t, dateTime } = useI18n();
  const readiness = useResource(resources.feedReadiness());
  const data = readiness.data;
  const interrupted = data?.topics.some(topic => ["failed", "cancelled", "superseded", "unverified", "not_started"].includes(topic.history_status));
  const pending = data?.topics.some(topic => ["queued", "running", "retrying"].includes(topic.history_status));
  const emptyInterests = data && !data.active_document_watch && data.topics.length === 0 && !data.more_topics;
  const noPacks = data && !data.active_document_watch && data.enabled_pack_count_shown === 0;
  const reason = more ? "feedRecovery.page" : linked ? "feedRecovery.link" : filtered ? "feedRecovery.filters" :
    emptyInterests ? "feedRecovery.interests" : noPacks ? "feedRecovery.sources" :
    interrupted ? "feedRecovery.interrupted" : pending ? "feedRecovery.pending" :
    data?.sources_need_attention ? "feedRecovery.attention" : data?.sources_pending ? "feedRecovery.sync" : "feed.empty";
  const action = more && nextHref ? [nextHref, "feedRecovery.next"] : linked || filtered ? ["/", "feedRecovery.clear"] :
    emptyInterests ? ["/onboarding", "gettingStarted.title"] : ["feedRecovery.sources", "feedRecovery.attention", "feedRecovery.sync"].includes(reason) ? ["/sources#source-packs", "gettingStarted.sources"] :
    ["/topics", "feedRecovery.review"];
  const stamp = (value: string) => dateTime(value, {dateStyle: "medium", timeStyle: "short"});
  return <section className="rounded-xl border bg-card p-5 sm:p-6 my-5" data-feed-empty aria-labelledby="feed-empty-title">
    <h2 id="feed-empty-title" className="text-xl font-semibold">{t("feedRecovery.title")}</h2>
    <p className="mt-3 max-w-3xl" data-feed-empty-reason={reason}>{t(reason)}</p>
    <Link data-feed-recovery-action className="underline inline-flex min-h-11 items-center mt-3 font-medium" href={action[0]}>{t(action[1])}</Link>
    {readiness.loading && !data && <Loading />}
    {readiness.error && <div className="mt-3"><ErrorNote message={readiness.error} /><p>{t("feedRecovery.unavailable")}</p><Button variant="outline" onClick={() => void readiness.reload()}>{t("gettingStarted.retry")}</Button></div>}
    {data && <details className="mt-3 border-t pt-2" data-feed-readiness>
      <summary className="cursor-pointer min-h-11 flex items-center">{t("feedRecovery.details")}</summary>
      <p className="text-sm">{t("feedRecovery.boundary")}</p>
      <p className="text-sm mt-2">{t("topicSources.asOf")} <time dateTime={data.captured_at}>{stamp(data.captured_at)}</time></p>
      {data.sources_need_attention && <p className="mt-3">{t("feedRecovery.attention")}</p>}
      {data.sources_pending && <p className="mt-3">{t("feedRecovery.sync")}</p>}
      <p className="mt-3">{t("feedRecovery.packs", {count: data.enabled_pack_count_shown})}</p>
      {(data.more_topics || data.more_packs) && <p className="mt-3 font-medium">{t("feedRecovery.limited")}</p>}
      <ul className="mt-3 space-y-3">
        {data.topics.map(topic => <li key={topic.id} className="rounded-lg border p-3 text-sm" data-feed-history>
          <Link href={topic.url} className="underline min-h-11 inline-flex items-center font-medium">{topic.name}</Link>
          <p>{t("feedRecovery.history")} <Status value={topic.history_status} /></p>
          {topic.monitoring_from && <p>{t("feedRecovery.from")} {stamp(topic.monitoring_from)}</p>}
          {topic.captured_at && <p>{t("feedRecovery.capture")} {stamp(topic.captured_at)}</p>}
          {topic.processed_through && <p>{t("feedRecovery.through")} {stamp(topic.processed_through)}</p>}
          {topic.processed !== null && <p>{t("feedRecovery.processed", {count: topic.processed})}</p>}
          {topic.remaining !== null && <p>{t("feedRecovery.remaining", {count: topic.remaining})}</p>}
        </li>)}
      </ul>
      <p className="text-sm mt-3">{t("feedRecovery.notQuiet")}</p>
    </details>}
  </section>;
}
