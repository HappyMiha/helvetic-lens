"use client";

import Link from "next/link";
import { useFeedInterestPage } from "@/lib/feed-interest-page";
import { resources } from "@/lib/resource-keys";
import { useI18n } from "@/lib/i18n";
import { ErrorNote, Status } from "./common";
import { Button } from "./ui/button";

type Topic = {id: string; name: string; url: string; confidence: string;
  reasons: Array<{type: string; value?: string; values?: string[]}>};

export function FeedTopicList({eventId, items, nextCursor}: {
  eventId: string; items: Topic[]; nextCursor: string | null;
}) {
  const { t } = useI18n();
  const {shown, next, cursors, busy, error, move} = useFeedInterestPage(items, nextCursor,
    cursor => resources.feedTopics(eventId, cursor));
  return <section data-feed-topics className="border-t mt-3 pt-4" aria-busy={busy}>
    <h3 className="text-base font-semibold">{t("nav.topics")}</h3>
    {(next || cursors.length > 0) && <p className="text-sm muted">{t("feedTopics.boundary")}</p>}
    <p className="text-sm muted">{t("feed.topicBoundary")}</p>
    <ul className="space-y-3">{shown.map(topic => <li key={topic.id}>
      <Link href={topic.url} className="underline min-h-[44px] inline-flex items-center">{topic.name}</Link>
      <p className="text-sm mt-0">{t("topics.matchReason", {reasons: [...new Set(topic.reasons.flatMap(reason => reason.values || (reason.value ? [reason.value] : [])))].join(" · ")})}</p>
      <p className="text-sm muted">{t("feed.confidence")}: <Status value={topic.confidence} /></p>
      <Link className="underline inline-flex min-h-[44px] items-center text-sm" href={`/topic-review?match=${encodeURIComponent(topic.id)}`}>{t("topicReview.open")}</Link>
    </li>)}</ul>
    {!shown.length && !error && <p role="status">{t("feedTopics.empty")}</p>}
    <ErrorNote message={error} />
    <div className="flex flex-wrap gap-2 mt-2">
      {cursors.length > 0 && <Button data-topic-back variant="outline" disabled={busy}
        onClick={() => void move(cursors.slice(0, -1))}>{t("feedTopics.previous")}</Button>}
      {next && <Button data-topic-next variant="outline" disabled={busy}
        onClick={() => void move([...cursors, next])}>{t("feedTopics.next")}</Button>}
      {cursors.length > 0 && <Button data-topic-first variant="outline" disabled={busy}
        onClick={() => void move([])}>{t("feedTopics.first")}</Button>}
    </div>
  </section>;
}
