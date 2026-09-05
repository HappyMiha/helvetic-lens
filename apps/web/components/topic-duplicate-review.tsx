"use client";

import type { MonitoringTopicPreview } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { Status } from "./common";

export function TopicDuplicateReview({ result, canManage, confirmed, onConfirm }: {
  result: NonNullable<MonitoringTopicPreview["matching_topics"]>;
  canManage: boolean;
  confirmed: boolean;
  onConfirm: (value: boolean) => void;
}) {
  const { t } = useI18n();
  return (
    <section className="mt-5 rounded-lg border p-4 text-sm" aria-live="polite" data-topic-duplicates>
      <h3 className="mb-2">{t(result.items.length ? "topicDuplicates.title" : "topicDuplicates.none")}</h3>
      <p>{t("topicDuplicates.basis")}</p>
      {!result.count_is_complete && <p className="font-medium">{t("topicDuplicates.limited", { count: result.scanned_count })}</p>}
      {result.items.length > 0 && (
        <ul className="my-3 space-y-2 list-none p-0">
          {result.items.map(item => (
            <li key={item.id} className="flex flex-wrap items-center gap-2">
              <a className="underline break-words min-w-0 max-w-full" href={`#topic-${encodeURIComponent(item.id)}`}>{item.name}</a>
              <Status value={item.status} />
            </li>
          ))}
        </ul>
      )}
      {result.display_truncated && <p>{t("topicDuplicates.more", { count: result.items.length })}</p>}
      {result.items.length > 0 && canManage && (
        <label className="flex min-h-11 items-start gap-3 cursor-pointer">
          <input type="checkbox" className="mt-1" checked={confirmed} data-topic-duplicate-confirm
            onChange={event => onConfirm(event.target.checked)} />
          <span>{t("topicDuplicates.confirm")}</span>
        </label>
      )}
    </section>
  );
}
