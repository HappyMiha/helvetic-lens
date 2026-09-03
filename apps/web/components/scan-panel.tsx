"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Check, Loader2, RotateCcw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, errorText, label, refreshWorkspace } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Scan } from "@/lib/types";
import { ErrorNote, Status } from "./common";
import { AdminOnly } from "./auth-gate";

export function ScanPanel({
  scan,
  compact = false,
}: {
  scan: Scan;
  compact?: boolean;
}) {
  const { t, dateTime } = useI18n();
  const [jobBusy, setJobBusy] = useState("");
  const [jobError, setJobError] = useState("");
  const running = ["queued", "running"].includes(scan.status);
  const job = scan.job;
  async function jobAction(action: "cancel" | "retry") {
    if (!job) return;
    setJobBusy(action);
    setJobError("");
    try {
      await api(`/jobs/${job.id}/${action}`, { method: "POST" });
      refreshWorkspace();
    } catch (cause) {
      setJobError(errorText(cause));
    } finally {
      setJobBusy("");
    }
  }
  return (
    <section
      className="panel scan-panel"
      aria-label={t("scan.progress")}
      aria-live="polite"
    >
      <div className="panel-header">
        <div className="flex items-center gap-3">
          {running ? (
            <Loader2 size={18} className="animate-spin text-primary" />
          ) : (
            <Check size={18} />
          )}
          <div>
            <h2>{running ? t("scan.checking") : t("scan.result")}</h2>
            <p className="text-xs muted m-0 mt-1">
              {dateTime(scan.created_at)} · {t("scan.finished", { completed: scan.completed, total: scan.total })}
            </p>
          </div>
        </div>
        <Status value={scan.status} />
      </div>
      <progress
        className="scan-progress"
        value={scan.completed}
        max={scan.total || 1}
        aria-label={t("scan.documentsFinished")}
      />
      {job && (
        <div className="px-5 py-3 border-b text-xs muted">
          <div className="flex flex-wrap items-center gap-2">
            <Status value={job.state} />
            <span>{t("scan.queue", { name: label(job.queue) })}</span>
            {job.queue_position && <span>· {t("scan.position", { position: job.queue_position })}</span>}
            <span>
              · {t("scan.attempt", { attempts: job.attempts, maximum: job.max_attempts })}
            </span>
            <AdminOnly>{!["succeeded", "failed", "cancelled"].includes(job.state) && (
              <Button
                variant="outline"
                size="sm"
                className="ml-auto"
                disabled={!!jobBusy}
                onClick={() => jobAction("cancel")}
              >
                {jobBusy === "cancel" ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <X />
                )}
                {t("scan.cancel")}
              </Button>
            )}</AdminOnly>
            <AdminOnly>{["failed", "cancelled"].includes(job.state) && (
              <Button
                variant="outline"
                size="sm"
                className="ml-auto"
                disabled={!!jobBusy}
                onClick={() => jobAction("retry")}
              >
                {jobBusy === "retry" ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <RotateCcw />
                )}
                {t("scan.retry")}
              </Button>
            )}</AdminOnly>
          </div>
          {!compact && job.steps.length > 0 && (
            <ol className="event-list mt-2">
              {job.steps.map((step) => (
                <li key={step.id}>
                  {step.name} · {label(step.state)}
                </li>
              ))}
            </ol>
          )}
          <ErrorNote message={job.error?.detail || jobError} />
        </div>
      )}
      <div className="scan-items">
        {scan.items.map((item) => (
          <div className="scan-item" key={item.id}>
            <div className="flex justify-between gap-4 items-start">
              <div className="min-w-0">
                <Link
                  className="font-semibold hover:underline"
                  href={"/laws/" + item.law_id}
                >
                  {item.law_name}
                </Link>
                <p className="text-xs muted m-0 mt-1">
                  {["complete", "failed", "interrupted"].includes(item.stage)
                    ? t("scan.finishedStage")
                    : label(item.stage)}{" "}
                  · {t("scan.apertus", { status: label(item.analysis_status) })}
                </p>
              </div>
              <Status value={item.result || item.stage} />
            </div>
            {item.mode === "historical" && (
              <p className="text-xs historical-note">
                {t("scan.historical", { result: label(item.live_result) })}
              </p>
            )}
            <ErrorNote message={item.error} />
            <div className="flex items-center justify-between gap-3 mt-2">
              {!compact && (
                <details className="text-xs muted">
                  <summary>{t("scan.stages")}</summary>
                  <ol className="event-list">
                    {item.events.map((event, index) => (
                      <li key={index}>
                        {label(event.stage)} <time>{dateTime(event.at)}</time>
                      </li>
                    ))}
                  </ol>
                </details>
              )}
              {item.comparison_id && (
                <Link
                  className="text-primary text-xs flex items-center gap-1 ml-auto"
                  href={"/compare/" + item.comparison_id}
                >
                  {t("scan.openComparison")}
                  <ArrowUpRight size={13} />
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
