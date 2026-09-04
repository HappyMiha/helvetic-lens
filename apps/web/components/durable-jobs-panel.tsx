"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Loader2, RotateCcw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  api,
  errorText,
  invalidateResources,
  label,
  mutateResource,
  primeResource,
} from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { jobResultHref } from "@/lib/job-links";
import { translate, useI18n } from "@/lib/i18n";
import type { Job } from "@/lib/types";
import { ErrorNote, Status } from "./common";
import { AdminOnly } from "./auth-gate";

export function DurableJobsPanel({ jobs }: { jobs: Job[] }) {
  const { t, locale, dateTime, number } = useI18n();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function act(job: Job, action: "cancel" | "retry") {
    setBusy(job.id + action);
    setError("");
    try {
      const updated = await api<Job>(`/jobs/${job.id}/${action}`, {
        method: "POST",
      });
      primeResource(resources.job(updated.id), updated);
      const updatedJobs = mutateResource(resources.jobs(), (current) =>
        current?.map((item) => (item.id === updated.id ? updated : item)) ||
        null,
      );
      if (updatedJobs === null) void invalidateResources(resources.jobs());
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>{t("jobs.title")}</h2>
          <p className="text-xs muted m-0 mt-1">
            {t("jobs.body")}
          </p>
        </div>
        <span className="text-xs muted">{t("jobs.recent", { count: number(jobs.length) })}</span>
      </div>
      <ErrorNote message={error} />
      <div className="scan-items">
        {jobs.map((job) => {
          const active = !["succeeded", "failed", "cancelled"].includes(
            job.state,
          );
          return (
            <div className="scan-item" key={job.id}>
              <div className="flex justify-between gap-4 items-start">
                <div>
                  <strong>{translate(locale, `status.${job.type}`) || label(job.type)}</strong>
                  <p className="text-xs muted m-0 mt-1">
                    {dateTime(job.created_at)} · {translate(locale, `status.${job.queue}`) || label(job.queue)}
                    {job.queue_position
                      ? ` · ${t("jobs.position", { position: number(job.queue_position) })}`
                      : ""}{" "}
                    · {t("jobs.attempt", { attempt: number(job.attempts), total: number(job.max_attempts) })}
                  </p>
                </div>
                <Status value={job.state} />
              </div>
              <progress
                className="scan-progress mt-3"
                value={job.progress.current}
                max={job.progress.total || 1}
                aria-label={t("jobs.progress")}
              />
              <details className="text-xs muted mt-2">
                <summary>{t("jobs.steps")}</summary>
                <ol className="event-list">
                  {job.steps.map((step) => (
                    <li key={step.id}>
                      {translate(locale, `status.${step.name}`) || label(step.name)} · {translate(locale, `status.${step.state}`) || label(step.state)}
                    </li>
                  ))}
                </ol>
              </details>
              <ErrorNote message={job.error?.detail} />
              <div className="flex justify-end gap-2 mt-2">
                {job.result?.url && (
                  <Button asChild variant="outline" size="sm">
                    <Link href={jobResultHref(job)}>
                      {t("jobs.openResult")} <ArrowUpRight />
                    </Link>
                  </Button>
                )}
                <AdminOnly>{active && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!!busy}
                    onClick={() => act(job, "cancel")}
                  >
                    {busy === job.id + "cancel" ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <X />
                    )}
                    {t("jobs.cancel")}
                  </Button>
                )}</AdminOnly>
                <AdminOnly>{!active && ["failed", "cancelled"].includes(job.state) && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!!busy}
                    onClick={() => act(job, "retry")}
                  >
                    {busy === job.id + "retry" ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <RotateCcw />
                    )}
                    {t("jobs.retry")}
                  </Button>
                )}</AdminOnly>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
