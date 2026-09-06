"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Shell } from "./shell";
import { useAuth } from "./auth-gate";
import { ErrorNote, Loading, Status } from "./common";
import { Button } from "./ui/button";
import {
  api,
  ApiError,
  errorText,
  invalidateResources,
  primeResource,
  resources,
  useResource,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { reprocessingCopy } from "@/lib/reprocessing-copy";
import {
  canApplyReprocessing,
  readReprocessingIntent,
  reprocessingActive,
  reprocessingResult,
  type ReprocessingIntent,
} from "@/lib/reprocessing";
import type { Job } from "@/lib/types";

export function RelationReprocessingPage() {
  const { t, locale } = useI18n();
  const { session, isPlatformAdmin } = useAuth();
  const copy = reprocessingCopy[locale];
  const identity = `${session?.organization?.id || "development"}:${session?.user?.id || "anonymous"}`;
  return (
    <Shell section={copy.title} wide>
      <div className="page-heading">
        <div>
          <Link href="/admin" className="text-sm underline">
            {copy.back}
          </Link>
          <h1 className="mt-3">{copy.title}</h1>
          <p>{copy.body}</p>
        </div>
      </div>
      {isPlatformAdmin ? (
        <Maintenance key={identity} identity={identity} />
      ) : (
        <ErrorNote message={t("admin.denied")} />
      )}
    </Shell>
  );
}

function Maintenance({ identity }: { identity: string }) {
  const { locale, t, dateTime, number } = useI18n();
  const copy = reprocessingCopy[locale];
  const router = useRouter(),
    query = useSearchParams();
  const timestamp = (value: string) =>
    dateTime(value, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZoneName: "short",
    });
  const options = useResource(resources.relationReprocessingOptions());
  const history = useResource(resources.relationReprocessingJobs());
  const selectedId = query.get("job");
  const selected = useResource(
    selectedId ? resources.job(encodeURIComponent(selectedId)) : null,
  );
  const job =
    !selected.error && selected.data?.type === "relation_candidate_reprocess"
      ? selected.data
      : null;
  const result = reprocessingResult(job);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false),
    [acknowledged, setAcknowledged] = useState(false);
  const [intent, setIntent] = useState<ReprocessingIntent | null>(null);
  const submitting = useRef(false),
    alive = useRef(true);
  const confirmRef = useRef<HTMLHeadingElement>(null),
    resultRef = useRef<HTMLHeadingElement>(null);
  const storageKey = `helvetic:relation-reprocessing-intent:${identity}`;
  useEffect(() => {
    alive.current = true;
    try {
      setIntent(readReprocessingIntent(sessionStorage.getItem(storageKey)));
    } catch {
      /* Checked before submission. */
    }
    return () => {
      alive.current = false;
    };
  }, [storageKey]);
  useEffect(() => {
    setConfirming(false);
    setAcknowledged(false);
  }, [selectedId, options.data?.rule_revision]);
  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
  }, [confirming]);
  const active =
    Boolean(job && reprocessingActive(job)) ||
    Boolean(history.data?.some(reprocessingActive));
  const mayApply =
    !options.error &&
    !selected.error &&
    !history.error &&
    canApplyReprocessing(job, options.data?.rule_revision);

  async function submit(dryRun: boolean, recover = false) {
    if (
      submitting.current ||
      (!recover && (active || intent || options.error || !options.data))
    )
      return;
    if (!dryRun && !recover && (!mayApply || !acknowledged)) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      let saved: ReprocessingIntent;
      try {
        const previous = readReprocessingIntent(
          sessionStorage.getItem(storageKey),
        );
        saved = previous || {
          request_id: crypto.randomUUID(),
          dry_run: dryRun,
          rule_revision: options.data!.rule_revision,
        };
        if (previous && (!recover || previous.dry_run !== dryRun))
          throw new Error(copy.unknownRequest);
        sessionStorage.setItem(storageKey, JSON.stringify(saved));
      } catch (cause) {
        throw new Error(
          cause instanceof Error && cause.message === copy.unknownRequest
            ? copy.unknownRequest
            : copy.storageError,
        );
      }
      setIntent(saved);
      const updated = await api<Job>("/admin/relation-reprocessing", {
        method: "POST",
        body: JSON.stringify(saved),
      });
      try {
        sessionStorage.removeItem(storageKey);
      } catch {
        /* Replaying this same identity is still safe. */
      }
      if (!alive.current) return;
      setIntent(null);
      setConfirming(false);
      setAcknowledged(false);
      primeResource(resources.job(updated.id), updated);
      void invalidateResources(resources.relationReprocessingJobs());
      router.replace(
        `/admin/relation-reprocessing?job=${encodeURIComponent(updated.id)}`,
        { scroll: false },
      );
    } catch (cause) {
      if (alive.current) {
        if (
          cause instanceof ApiError &&
          cause.code === "relation_reprocess_rule_changed"
        ) {
          try {
            sessionStorage.removeItem(storageKey);
          } catch {
            /* Never replay under a different rule. */
          }
          setIntent(null);
          options.reload();
          setError(copy.obsolete);
        } else setError(errorText(cause));
      }
    } finally {
      submitting.current = false;
      if (alive.current) setBusy(false);
    }
  }

  async function act(action: "cancel" | "retry") {
    if (!job || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      const updated = await api<Job>(
        `/admin/relation-reprocessing/jobs/${encodeURIComponent(job.id)}/${action}`,
        { method: "POST" },
      );
      if (!alive.current) return;
      primeResource(resources.job(updated.id), updated);
      void invalidateResources(resources.relationReprocessingJobs());
    } catch (cause) {
      if (alive.current) setError(errorText(cause));
    } finally {
      submitting.current = false;
      if (alive.current) setBusy(false);
    }
  }

  return (
    <div className="grid gap-5" data-reprocessing>
      <section className="panel">
        <div className="panel-body grid gap-4">
          <p className="m-0 text-sm">{copy.scope}</p>
          <ErrorNote message={options.error || history.error || error} />
          {options.loading && !options.data ? (
            <Loading text={t("admin.loading")} />
          ) : (
            options.data && (
              <dl className="flex flex-wrap gap-6 text-sm">
                <div>
                  <dt className="muted">{copy.rule}</dt>
                  <dd className="font-medium break-all" data-current-rule>
                    {options.data.rule_revision}
                  </dd>
                </div>
                <div>
                  <dt className="muted">{copy.batch}</dt>
                  <dd>{number(options.data.batch_size)}</dd>
                </div>
              </dl>
            )
          )}
          <div className="flex flex-wrap gap-3">
            <Button
              data-reprocess-preview
              disabled={
                busy || active || !!intent || !!options.error || !options.data
              }
              onClick={() => submit(true)}
            >
              {copy.preview}
            </Button>
            <Button
              variant="outline"
              disabled={busy || options.loading || history.loading}
              onClick={() => {
                options.reload();
                history.reload();
                selected.reload();
              }}
            >
              <RefreshCw />
              {t("logs.refresh")}
            </Button>
          </div>
          {intent && (
            <div className="notice" data-pending-request>
              <p>{copy.unknownRequest}</p>
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => submit(intent.dry_run, true)}
                data-recover-request
              >
                {copy.retryRequest}
              </Button>
            </div>
          )}
        </div>
      </section>

      {selectedId && (
        <section className="panel" data-reprocess-result>
          <div className="panel-header">
            <h2 tabIndex={-1} ref={resultRef}>
              {job?.maintenance?.dry_run === true
                ? copy.previewMode
                : job?.maintenance?.dry_run === false
                  ? copy.applyMode
                  : copy.unknownMode}
            </h2>
            {job && <Status value={job.state} />}
          </div>
          <div className="panel-body grid gap-4">
            <ErrorNote message={selected.error || job?.error?.detail} />
            {selected.loading && !selected.data ? (
              <Loading text={t("admin.loading")} />
            ) : !job ? (
              <p>{copy.unavailable}</p>
            ) : (
              <>
                <p className="m-0 text-xs muted break-all">
                  {timestamp(job.created_at)} ·{" "}
                  {job.maintenance?.rule_revision || job.target_id}
                </p>
                <div
                  role="status"
                  aria-live="polite"
                  aria-atomic="true"
                  data-reprocess-progress
                >
                  {copy.progress}:{" "}
                  {number(result?.processed ?? job.progress.current)} /{" "}
                  {number(result?.eligible ?? job.progress.total)}
                  {result?.status === "complete"
                    ? ` · ${copy.complete}`
                    : result
                      ? ` · ${copy.partial}`
                      : ""}
                </div>
                <progress
                  className="scan-progress"
                  aria-label={copy.progress}
                  max={Math.max(1, result?.eligible ?? job.progress.total)}
                  value={result?.processed ?? job.progress.current}
                />
                {result ? (
                  <>
                    <dl
                      className="grid grid-cols-2 md:grid-cols-3 gap-4"
                      data-reprocess-counts
                    >
                      {(
                        ["changed", "retained", "rejected", "skipped"] as const
                      ).map((name) => (
                        <div key={name}>
                          <dt className="text-sm muted">{copy[name]}</dt>
                          <dd className="text-xl font-semibold">
                            {number(result[name])}
                          </dd>
                        </div>
                      ))}
                      {!!result.removed_since_capture && (
                        <div>
                          <dt className="text-sm muted">{copy.removed}</dt>
                          <dd>{number(result.removed_since_capture)}</dd>
                        </div>
                      )}
                    </dl>
                    <p className="text-sm m-0">
                      {copy.captured}:{" "}
                      {timestamp(
                        result.captured_at ||
                          job.maintenance?.captured_at ||
                          job.created_at,
                      )}
                    </p>
                    {result.status === "superseded" ? (
                      <p className="notice" data-superseded>
                        {copy.superseded}
                      </p>
                    ) : job.maintenance?.rule_revision !==
                        options.data?.rule_revision && options.data ? (
                      <p className="notice" data-obsolete>
                        {copy.obsolete}
                      </p>
                    ) : (
                      result.status === "complete" &&
                      result.changed === 0 && (
                        <p className="notice" data-no-changes>
                          {copy.noChanges}
                        </p>
                      )
                    )}
                    {!!result.examples.length && (
                      <details>
                        <summary>{copy.examples}</summary>
                        <p className="text-sm muted">{copy.examplesHelp}</p>
                        <ol className="grid gap-3 list-none p-0">
                          {result.examples.slice(0, 10).map((example) => (
                            <li
                              className="border rounded-lg p-4 min-w-0 break-words"
                              key={example.candidate_id}
                            >
                              <dl className="text-sm">
                                <dt className="muted">{copy.source}</dt>
                                <dd>
                                  {example.source_title || example.event_id}
                                </dd>
                                <dt className="muted mt-2">{copy.target}</dt>
                                <dd>
                                  {example.target_title ||
                                    example.target_work_id}
                                </dd>
                              </dl>
                              <p className="text-sm">
                                {example.outcome === "rejected"
                                  ? copy.rejected
                                  : copy.retained}{" "}
                                · {copy.score}: {number(example.old_score)} →{" "}
                                {number(example.new_score)}
                              </p>
                              <p className="text-xs muted">{copy.reasons}</p>
                              <ul className="text-sm list-disc pl-5">
                                {example.reason.map((reason, index) => (
                                  <li key={index}>{reason}</li>
                                ))}
                              </ul>
                            </li>
                          ))}
                        </ol>
                      </details>
                    )}
                  </>
                ) : (
                  <p>
                    {reprocessingActive(job) ? copy.noResult : copy.unavailable}
                  </p>
                )}
                <p className="text-xs muted m-0">{copy.preserved}</p>
                <div className="flex flex-wrap gap-3">
                  {reprocessingActive(job) && (
                    <Button
                      variant="outline"
                      disabled={busy}
                      onClick={() => act("cancel")}
                      data-reprocess-cancel
                    >
                      {t("jobs.cancel")}
                    </Button>
                  )}
                  {["failed", "cancelled"].includes(job.state) && (
                    <Button
                      variant="outline"
                      disabled={busy}
                      onClick={() => act("retry")}
                      data-reprocess-resume
                    >
                      {copy.resume}
                    </Button>
                  )}
                  {mayApply && !active && !intent && (
                    <Button
                      disabled={busy}
                      onClick={() => setConfirming(true)}
                      data-review-apply
                    >
                      {copy.apply}
                    </Button>
                  )}
                </div>
                {confirming && mayApply && !intent && (
                  <div
                    className="border rounded-xl p-4 grid gap-3"
                    data-apply-confirmation
                  >
                    <h3 className="m-0" ref={confirmRef} tabIndex={-1}>
                      {copy.confirmTitle}
                    </h3>
                    <p className="text-sm m-0" id="reprocess-apply-warning">
                      {copy.confirmBody}
                    </p>
                    <label className="flex items-start gap-3 text-sm">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={acknowledged}
                        onChange={(event) =>
                          setAcknowledged(event.target.checked)
                        }
                        aria-describedby="reprocess-apply-warning"
                        data-apply-acknowledge
                      />
                      {copy.acknowledge}
                    </label>
                    <div className="flex flex-wrap gap-3">
                      <Button
                        disabled={!acknowledged || busy || active}
                        onClick={() => submit(false)}
                        data-confirm-apply
                      >
                        {copy.confirm}
                      </Button>
                      <Button
                        variant="outline"
                        disabled={busy}
                        onClick={() => {
                          setConfirming(false);
                          setAcknowledged(false);
                          resultRef.current?.focus();
                        }}
                      >
                        {t("jobs.cancel")}
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>{copy.recent}</h2>
            <p className="text-sm muted mb-0">{copy.recentHelp}</p>
          </div>
        </div>
        <div className="panel-body">
          {history.loading && !history.data ? (
            <Loading text={t("admin.loading")} />
          ) : !history.data?.length ? (
            <p>{copy.empty}</p>
          ) : (
            <ul className="list-none p-0 divide-y" data-reprocess-history>
              {history.data.map((item) => (
                <li className="py-3" key={item.id}>
                  <Link
                    className="flex flex-wrap items-start justify-between gap-3 rounded p-2 hover:bg-muted"
                    href={`/admin/relation-reprocessing?job=${encodeURIComponent(item.id)}`}
                    scroll={false}
                    aria-current={selectedId === item.id ? "true" : undefined}
                  >
                    <span>
                      <strong className="block underline">
                        {item.maintenance?.dry_run === true
                          ? copy.previewMode
                          : item.maintenance?.dry_run === false
                            ? copy.applyMode
                            : copy.unknownMode}
                      </strong>
                      <span className="text-sm">
                        <time dateTime={item.created_at} data-job-time>
                          {timestamp(item.created_at)}
                        </time>
                      </span>
                    </span>
                    <Status value={item.state} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
