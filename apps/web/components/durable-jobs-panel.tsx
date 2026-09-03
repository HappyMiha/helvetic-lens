"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Loader2, RotateCcw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, dateTime, errorText, label, refreshWorkspace } from "@/lib/api";
import type { Job } from "@/lib/types";
import { ErrorNote, Status } from "./common";
import { AdminOnly } from "./auth-gate";

export function DurableJobsPanel({ jobs }: { jobs: Job[] }) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function act(job: Job, action: "cancel" | "retry") {
    setBusy(job.id + action);
    setError("");
    try {
      await api(`/jobs/${job.id}/${action}`, { method: "POST" });
      refreshWorkspace();
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
          <h2>Durable work queue</h2>
          <p className="text-xs muted m-0 mt-1">
            Work survives API, worker, and queue restarts. Completed evidence
            stays available.
          </p>
        </div>
        <span className="text-xs muted">{jobs.length} recent jobs</span>
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
                  <strong>{label(job.type)}</strong>
                  <p className="text-xs muted m-0 mt-1">
                    {dateTime(job.created_at)} · {label(job.queue)}
                    {job.queue_position
                      ? ` · queue position ${job.queue_position}`
                      : ""}{" "}
                    · attempt {job.attempts}/{job.max_attempts}
                  </p>
                </div>
                <Status value={job.state} />
              </div>
              <progress
                className="scan-progress mt-3"
                value={job.progress.current}
                max={job.progress.total || 1}
                aria-label="Job progress"
              />
              <details className="text-xs muted mt-2">
                <summary>Persisted steps</summary>
                <ol className="event-list">
                  {job.steps.map((step) => (
                    <li key={step.id}>
                      {step.name} · {label(step.state)}
                    </li>
                  ))}
                </ol>
              </details>
              <ErrorNote message={job.error?.detail} />
              <div className="flex justify-end gap-2 mt-2">
                {job.result?.url && (
                  <Button asChild variant="outline" size="sm">
                    <Link href={job.result.url}>
                      Open result <ArrowUpRight />
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
                    Cancel
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
                    Retry safely
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
