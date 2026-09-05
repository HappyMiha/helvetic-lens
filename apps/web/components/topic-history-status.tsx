"use client";

import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import type { MonitoringTopic } from "@/lib/types";

export function TopicHistoryStatus({ topic, capturedAtLabel, renderResume }: {
  topic: Pick<MonitoringTopic, "status" | "history_scan">;
  capturedAtLabel?: string;
  renderResume?: () => ReactNode;
}) {
  const { t } = useI18n();
  const scan = topic.history_scan;
  const state = scan?.status || "not_started";
  const labels: Record<string, string> = {
    not_started: t("topicHistory.notStarted"), legacy_limited: t("topicHistory.legacyLimited"),
    superseded: t("topicHistory.superseded"), complete: t("topicHistory.complete"),
    queued: t("status.queued"), dispatched: t("status.queued"), retrying: t("status.retrying"),
    running: t("status.running"), failed: t("status.failed"), cancelled: t("status.cancelled"),
  };
  const recoverable = ["not_started", "legacy_limited", "superseded", "failed", "cancelled"].includes(state);
  const counted = typeof scan?.processed === "number" && typeof scan?.remaining === "number";
  const total = (scan?.processed || 0) + (scan?.remaining || 0);
  return (
    <section className="mt-4 rounded-md border bg-background p-4 space-y-2 text-sm break-words" data-topic-history={state}>
      <div className="flex flex-wrap justify-between gap-2">
        <h3 className="font-semibold">{t("topicHistory.title")}</h3>
        <span role="status">{labels[state] || t("topicHistory.unknown")}</span>
      </div>
      <p className="m-0 text-muted-foreground">{t("topicHistory.scope")}</p>
      {scan?.captured_at && <p className="m-0">
        {t("topicHistory.captured")} <time dateTime={scan.captured_at}>{capturedAtLabel || scan.captured_at}</time>
      </p>}
      {counted && <>
        <p className="m-0">{t("topicHistory.counts", { processed: scan!.processed!, remaining: scan!.remaining! })}</p>
        {total > 0 && <progress className="w-full h-2 accent-primary" max={total} value={scan!.processed!} aria-label={t("topicHistory.title")} />}
        <p className="m-0">{t("topicHistory.results", { matched: scan?.matched || 0, excluded: scan?.excluded || 0 })}</p>
      </>}
      {state === "complete" && counted && total === 0 && <p className="m-0">{t("topicHistory.empty")}</p>}
      {state === "legacy_limited" && <p className="m-0">{t("topicHistory.legacyHelp")}</p>}
      {(scan?.removed_since_capture || 0) > 0 && <p className="m-0">{t("topicHistory.removed", { count: scan!.removed_since_capture! })}</p>}
      {state === "failed" && <p className="m-0">{t("topicHistory.failureHelp")}</p>}
      {topic.status !== "active" && <p className="m-0">{t("topicHistory.inactive")}</p>}
      {topic.status === "active" && recoverable && renderResume?.()}
    </section>
  );
}
