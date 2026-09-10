"use client";

import {
  RefreshCw,
  Rocket,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { Shell } from "./shell";
import { DeploymentHistory } from "./deployment-history";
import { useAuth } from "./auth-gate";
import { ErrorNote, Loading } from "./common";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { label, resources, useResource } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { deploymentHistoryCopy } from "@/lib/deployment-history-copy";
import type {
  DeploymentRun,
  ProductionDeploymentStatus,
} from "@/lib/types";

function shortSha(value: string | null | undefined) {
  return value ? value.slice(0, 12) : "—";
}

function duration(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function statusVariant(value: string) {
  return value === "failed" || value === "error" || value === "rollback_failed"
    ? "destructive"
    : "outline";
}

function RunDetails({ run }: { run: DeploymentRun }) {
  const { t, dateTime, locale } = useI18n();
  const copy = deploymentHistoryCopy[locale];
  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <Badge variant={statusVariant(run.status)}>{copy.statuses[run.status] || label(run.status)}</Badge>
        <code>{shortSha(run.target_sha)}</code>
        <span className="text-sm muted">
          {dateTime(run.started_at, {dateStyle: "medium", timeStyle: "medium"})} · {duration(run.duration_seconds)}
        </span>
        {run.backup_id && (
          <span className="text-sm muted">
            {t("deploy.backup")}: <code>{run.backup_id}</code>
          </span>
        )}
        {run.model_id && (
          <span className="text-sm muted">
            {t("deploy.model")}: <code>{run.model_id}</code>
          </span>
        )}
      </div>

      <dl className="grid gap-3 sm:grid-cols-2 min-w-0 text-sm">
        {[[copy.started, run.started_at ? dateTime(run.started_at, {dateStyle: "medium", timeStyle: "medium"}) : null], [copy.finished, run.finished_at ? dateTime(run.finished_at, {dateStyle: "medium", timeStyle: "medium"}) : null], [copy.previousRelease,run.previous_sha],[copy.requested,run.target_sha],
          [copy.activated,run.activated_sha],[copy.host,[run.host,run.environment].filter(Boolean).join(" / ")]].map(([title,value]) =>
          <div key={title} className="min-w-0"><dt className="muted">{title}</dt><dd className="break-all font-medium">{value || copy.unknown}</dd></div>)}
      </dl>
      {run.details_truncated && <p className="notice">{copy.truncated}</p>}
      <section className="min-w-0">
        <h3>{copy.notes}</h3>
        {run.status !== "succeeded" && <p className="text-sm muted">{copy.planned}</p>}
        {run.release_notes?.text ? <>
          <p className="text-sm muted">{run.release_notes.kind === "commit_summary" ? copy.generated : copy.notes}</p>
          <pre className="whitespace-pre-wrap break-words text-sm max-h-80 overflow-auto rounded-md border p-3" role="group" tabIndex={0} aria-label={copy.notes}>{run.release_notes.text}</pre>
          {(run.release_notes.changes_may_be_truncated || run.release_notes.text_truncated) && <p className="text-sm">{copy.truncated}</p>}
        </> : <p className="muted">{copy.noNotes}</p>}
        {run.compare_url && <a className="inline-flex items-center min-h-11 underline" href={run.compare_url} target="_blank" rel="noreferrer">{copy.compare}</a>}
      </section>

      {run.error && (
        <div className="error-note">
          <strong>{t("deploy.error")}</strong>
          {run.error_step && <code className="block mt-2">{run.error_step}</code>}
          <pre className="mt-2 whitespace-pre-wrap text-xs overflow-x-auto">{run.error}</pre>
        </div>
      )}

      {run.rollback.status !== "not_required" && (
        <div className="card p-4 flex items-start justify-between gap-4">
          <div>
            <strong className="flex items-center gap-2">
              <RotateCcw size={17} /> {t("deploy.rollback")}
            </strong>
            <small className="block muted mt-1">
              {run.rollback.backup_restored
                ? t("deploy.rollbackRestored")
                : t("deploy.rollbackImages")}
            </small>
            {run.rollback.error && (
              <pre className="mt-3 whitespace-pre-wrap text-xs">{run.rollback.error}</pre>
            )}
          </div>
          <Badge variant={statusVariant(run.rollback.status)}>
            {label(run.rollback.status)}
          </Badge>
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-5">
        <section>
          <h3 className="mb-3">{t("deploy.steps")}</h3>
          <div className="divide-y">
            {run.steps.length ? (
              run.steps.map((step) => (
                <div className="py-3 flex justify-between gap-4" key={`${step.name}:${step.started_at}`}>
                  <span className="min-w-0">{label(step.name)}
                    {step.error && <pre className="whitespace-pre-wrap break-words text-xs mt-2">{step.error}</pre>}
                  </span>
                  <span className="text-right">
                    <Badge variant={statusVariant(step.status)}>{copy.statuses[step.status] || label(step.status)}</Badge>
                    <small className="block muted mt-1">{duration(step.duration_seconds)}</small>
                  </span>
                </div>
              ))
            ) : (
              <p className="muted">{t("deploy.noSteps")}</p>
            )}
          </div>
        </section>

        <section>
          <details>
          <summary className="min-h-11 cursor-pointer font-medium">{t("deploy.changes")} ({run.changes.length})</summary>
          <div className="divide-y">
            {run.changes.length ? (
              run.changes.map((change) => (
                <div className="py-3" key={change.sha}>
                  <strong className="block">{change.subject}</strong>
                  <small className="muted">
                    <code>{change.short_sha}</code> · {change.author} · {dateTime(change.committed_at)}
                  </small>
                </div>
              ))
            ) : (
              <p className="muted">{t("deploy.noChanges")}</p>
            )}
          </div>
          </details>
        </section>
      </div>
    </div>
  );
}

export function DeploymentManagerPage() {
  const { t, dateTime, locale } = useI18n();
  const copy = deploymentHistoryCopy[locale];
  const { isPlatformAdmin } = useAuth();
  const status = useResource(
    isPlatformAdmin ? resources.deployments() : null,
  );
  const data = status.data;
  const branch = data?.remote.branch?.trim() || null;
  const pending = Boolean(
    data?.remote.sha && data.current.sha && data.remote.sha !== data.current.sha,
  );

  return (
    <Shell section={t("nav.deployments")} wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("deploy.eyebrow")}</span>
          <h1>{t("deploy.title")}</h1>
          <p className="break-words" data-deployment-branch-description>
            {branch ? t("deploy.body", { branch }) : t("deploy.bodyUnavailable")}
          </p>
        </div>
        {isPlatformAdmin && (
          <Button variant="outline" onClick={status.reload} disabled={status.loading}>
            <RefreshCw className={status.loading ? "animate-spin" : ""} /> {t("logs.refresh")}
          </Button>
        )}
      </div>

      {!isPlatformAdmin ? (
        <ErrorNote message={t("admin.denied")} />
      ) : (
        <>
          <ErrorNote message={status.error} />
          {status.loading && !data ? (
            <Loading text={t("deploy.loading")} />
          ) : data ? (
            <div className="grid gap-5">
              <section className="stats-grid">
                <div className="stat-card">
                  <span className="eyebrow">{t("deploy.automation")}</span>
                  <strong>{label(data.service.state)}</strong>
                  <small>
                    {data.service.poll_interval_seconds
                      ? t("deploy.every", { count: data.service.poll_interval_seconds })
                      : t("deploy.notConfigured")}
                  </small>
                </div>
                <div className="stat-card">
                  <span className="eyebrow">{t("deploy.production")}</span>
                  <strong><code>{shortSha(data.current.sha)}</code></strong>
                  <small>{data.current.summary || data.current.release || t("deploy.unknown")}</small>
                </div>
                <div className="stat-card">
                  <span className="eyebrow break-all" data-deployment-branch>
                    {t("deploy.git")} · {branch || t("deploy.unknown")}
                  </span>
                  <strong><code>{shortSha(data.remote.sha)}</code></strong>
                  <small>{data.remote.summary || t("deploy.unknown")}</small>
                </div>
                <div className="stat-card">
                  <span className="eyebrow">{t("deploy.queue")}</span>
                  <strong>{pending ? t("deploy.pending") : t("deploy.current")}</strong>
                  <small>{t("deploy.checked", { date: dateTime(data.service.last_checked_at) })}</small>
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2>{t("deploy.lastRun")}</h2>
                    <p className="text-sm muted mb-0">{t("deploy.lastRunBody")}</p>
                  </div>
                  {data.last_run?.status === "succeeded" ? <ShieldCheck /> : <Rocket />}
                </div>
                <div className="panel-body">
                  {data.last_run ? <details data-deployment-latest>
                    <summary className="min-h-11 cursor-pointer">
                      <span className="inline-flex flex-wrap items-center gap-3 p-2">
                        <Badge variant={statusVariant(data.last_run.status)}>{copy.statuses[data.last_run.status] || label(data.last_run.status)}</Badge>
                        <code>{shortSha(data.last_run.target_sha)}</code>
                        <span>{copy.details}</span>
                      </span>
                    </summary>
                    <div className="mt-4"><RunDetails run={data.last_run} /></div>
                  </details> : <p className="muted">{t("deploy.noRuns")}</p>}
                </div>
              </section>

              <DeploymentHistory renderDetails={run => <RunDetails run={run} />} />
            </div>
          ) : null}
        </>
      )}
    </Shell>
  );
}
