"use client";

import type { MonitoringTopicPreview } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

export function TopicPreviewCoverage({
  preview,
  capturedAtLabel,
}: {
  preview: MonitoringTopicPreview;
  capturedAtLabel?: string;
}) {
  const { t } = useI18n();
  return (
    <div className="rounded-lg border bg-background p-4 text-sm mb-4" data-topic-preview-coverage={preview.count_is_complete ? "saved-sample" : "limited-sample"}>
      <p className="m-0">
        {typeof preview.scanned_event_count === "number"
          ? t("topicPreview.checked", { count: preview.scanned_event_count, limit: preview.scanned_event_limit })
          : t("topics.previewBoundary", { limit: preview.scanned_event_limit })}
      </p>
      {!preview.count_is_complete && <p className="m-0 mt-2 font-medium">{t("topicPreview.limited")}</p>}
      <p className="m-0 mt-2">{t("topicPreview.scope")}</p>
      {preview.sample_captured_at && capturedAtLabel && (
        <p className="m-0 mt-2">{t("topicPreview.checkedAt")} <time dateTime={preview.sample_captured_at}>{capturedAtLabel}</time></p>
      )}
      {preview.display_truncated && (
        <p className="m-0 mt-2">{t("topicPreview.shown", { shown: preview.items.length, total: preview.candidate_count })}</p>
      )}
    </div>
  );
}
