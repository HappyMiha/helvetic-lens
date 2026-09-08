"use client";

import Link from "next/link";
import type { DigestEvent } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { digestInterestCopy } from "@/lib/digest-interest-copy";

export function DigestInterests({ event }: { event: DigestEvent }) {
  const { locale, t } = useI18n();
  const copy = digestInterestCopy[locale];
  if (!event.event_url) return null;
  return (
    <div data-digest-interests className="space-y-3 mt-4 text-sm break-words">
      {!!event.topics?.length && (
        <>
          <p>{copy.boundary}</p>
          <ul className="space-y-3">
            {event.topics.map((topic) => (
              <li key={topic.match_id}>
                <strong>{topic.name}</strong>
                <p>
                  {copy.reason}: {topic.terms.join(" · ")}
                </p>
                <p>
                  {t("feed.confidence")}: {t(`status.${topic.confidence}`)}
                </p>
                <Link
                  className="underline inline-flex min-h-11 items-center"
                  href={`/topic-review?match=${encodeURIComponent(topic.match_id)}`}
                >
                  {t("topicReview.open")}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
      {!!event.monitored_documents?.length && (
        <p>
          {copy.documents}:{" "}
          {event.monitored_documents.map((doc) => doc.name).join(" · ")}
        </p>
      )}
      {(event.topics_truncated || event.monitored_documents_truncated) && (
        <p>{copy.more}</p>
      )}
      <Link
        className="underline inline-flex min-h-11 items-center"
        href={event.event_url}
      >
        {copy.open}
      </Link>
    </div>
  );
}
