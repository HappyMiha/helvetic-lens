"use client";

import { useEffect, useRef, useState } from "react";
import { api, errorText, invalidateResources, resourceTag, resources, useResource } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { ErrorNote, Status } from "./common";
import { Button } from "./ui/button";
import { useAuth } from "./auth-gate";
import type { BriefRecovery } from "@/lib/interest-brief";
import type { Job } from "@/lib/types";

export function InterestBriefRequest({eventId, canRequest, recovery}: {eventId: string; canRequest: boolean; recovery?: BriefRecovery | null}) {
  const {locale, t} = useI18n();
  const {canManage} = useAuth();
  const policy = useResource(resources.interestBriefPolicy());
  const [watchId, setWatchId] = useState<string | null>(null);
  const [lastId, setLastId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const nonce = useRef<string | null>(null);
  const progress = useResource(watchId ? resources.job(watchId) : null);
  useEffect(() => {
    const job = progress.data;
    if (!job || job.id !== watchId || !["succeeded", "failed", "cancelled"].includes(job.state)) return;
    if (job.state === "succeeded" && job.type === "interest_brief_admission") {
      const outcomes = (job.result?.data as {outcomes?: Array<{job_id?: string}>} | null)?.outcomes;
      const generation = outcomes?.[0]?.job_id;
      if (generation) { setWatchId(generation); setLastId(generation); setMessage(t("briefRequest.working")); return; }
    }
    setWatchId(null);
    setMessage(t(job.state === "succeeded" ? "briefRequest.finished" : "briefRequest.failed"));
    void invalidateResources(resourceTag(`interest-brief:${eventId}`)).catch(() => {});
  }, [progress.data, watchId, eventId, t]);
  async function request(retry = false) {
    setBusy(true); setError("");
    try {
      if (retry && recovery) {
        const job = await api<Job>(`/jobs/${encodeURIComponent(recovery.job_id)}/retry`, {method: "POST"});
        setWatchId(job.id); setLastId(job.id); setMessage(t("briefRequest.working"));
        return;
      }
      nonce.current ||= crypto.randomUUID();
      const result = await api<{job: Job}>(`/interest-feed/events/${encodeURIComponent(eventId)}/brief/requests`, {
        method: "POST", body: JSON.stringify({request_id: nonce.current, locale: locale.slice(0, 2)}),
      });
      nonce.current = null;
      setWatchId(result.job.id); setLastId(result.job.id); setMessage(t("briefRequest.working"));
    } catch (cause) { setError(errorText(cause)); } finally { setBusy(false); }
  }
  return <div data-brief-request className="space-y-2">
    <p className="text-sm muted">{t("briefRequest.help")}</p>
    <ErrorNote message={error || progress.error || policy.error} />
    {message && <p role="status">{message}</p>}
    {policy.data?.enabled ? canRequest && <Button data-request-brief className="min-h-11 whitespace-normal" disabled={busy || !!watchId}
      onClick={() => void request()}>{t(busy || watchId ? "briefRequest.working" : "briefRequest.prepare")}</Button>
      : policy.data && <p className="text-sm muted">{t("error.interest_auto_disabled")}</p>}
    {recovery && !canRequest && <div className="space-y-2">
      <p>{t("briefRecovery.attempts", {used: recovery.attempts_used, limit: recovery.attempt_limit})}</p>
      {recovery.retry_allowed ? canManage ? <Button data-retry-brief className="min-h-11 whitespace-normal" disabled={busy || !!watchId || !policy.data?.enabled}
        onClick={() => void request(true)}>{t(busy || watchId ? "briefRequest.working" : "briefRecovery.retry")}</Button>
        : <p>{t("briefRecovery.admin")}</p> : <p>{t("briefRecovery.exhausted")}</p>}
    </div>}
    {(lastId || recovery?.job_id) && <RequestDetails key={lastId || recovery?.job_id} jobId={(lastId || recovery?.job_id)!} />}
  </div>;
}


function RequestDetails({jobId}: {jobId: string}) {
  const {t, dateTime, number} = useI18n();
  const [open, setOpen] = useState(false);
  // Inspect this exact job on demand; no perpetual polling of terminal history.
  const data = useResource<Job>(open ? {...resources.job(jobId), pollMs: 0} : null);
  return <details onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="min-h-11 py-2 cursor-pointer">{t("briefRequest.details")}</summary>
    <ErrorNote message={data.error} />
    {data.data && <div className="space-y-2 text-sm">
      <Status value={data.data.state} />
      <p>{dateTime(data.data.created_at)}</p>
      <p>{t("jobs.attempt", {attempt: number(data.data.attempts), total: number(data.data.max_attempts)})}</p>
      <ErrorNote message={data.data.error?.detail} />
    </div>}
  </details>;
}
