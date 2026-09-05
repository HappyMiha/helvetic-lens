"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, dateTime, errorText, invalidateResources, resourceTag, useResource } from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "./auth-gate";
import { ErrorNote, Loading, Status } from "./common";
import { Shell } from "./shell";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";

type Match = {
  id: string; topic_id: string; is_current: boolean; validity: string; confidence: string | null;
  evaluation_fingerprint: string | null; review_id: string | null; decision: string; decision_is_current: boolean;
  matched_at: string; evidence: { work_title?: string; source_url?: string; detected_at?: string };
  reasons: Array<{ value?: string; values?: string[] }>;
};
type Review = { id: string; decision: string; note: string; created_at: string; actor_name?: string;
  snapshot: { evidence: Match["evidence"]; reasons: Match["reasons"]; confidence: string; matched_at: string } };
type ReviewPage = { match: Match; items: Review[]; has_more: boolean; next_cursor: string | null };
type MatchPage = { items: Match[]; has_more: boolean; next_cursor: string | null };
function officialUrl(value?: string) {
  if (!value) return undefined;
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) ? url.href : undefined; } catch { return undefined; }
}
function terms(reasons: Match["reasons"]) {
  return [...new Set(reasons.flatMap(reason => reason.values || (reason.value ? [reason.value] : [])))].join(" · ");
}

export function TopicSavedMatches({ topicId }: { topicId: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState("");
  const resource = useResource(open ? resources.topicMatchesPage<MatchPage>(topicId, cursor) : null);
  return <section className="mt-4 border-t pt-3">
    <Button variant="outline" onClick={() => setOpen(!open)} aria-expanded={open}>{t("topicReview.matches")}</Button>
    {open && <div className="mt-3 space-y-3">
      <p className="text-sm muted">{t("topicReview.matchesHelp")}</p>
      <ErrorNote message={resource.error} />
      {resource.loading && !resource.data && <Loading />}
      {resource.data?.items.length === 0 && <p>{t("topicReview.empty")}</p>}
      {resource.data?.items.map(match => <div key={match.id} className="rounded-lg border p-3 text-sm">
        <Link className="underline inline-flex items-center min-h-[44px]" href={`/topic-review?match=${encodeURIComponent(match.id)}`}>{match.evidence.work_title || t("topicReview.open")}</Link>
        <p>{dateTime(match.matched_at)} · <Status value={match.is_current ? (match.decision_is_current ? match.decision : "pending") : "stale"} /></p>
      </div>)}
      <div className="flex flex-wrap gap-3">
        {cursor && <Button variant="outline" onClick={() => setCursor("")}>{t("inboxPaging.newest")}</Button>}
        {resource.data?.next_cursor && <Button variant="outline" onClick={() => setCursor(resource.data!.next_cursor!)}>{t("inboxPaging.next")}</Button>}
      </div>
    </div>}
  </section>;
}

function ReviewContent({ matchId }: { matchId: string }) {
  const { t } = useI18n();
  const { canManage } = useAuth();
  const [cursor, setCursor] = useState("");
  const resource = useResource(resources.topicMatchReviews<ReviewPage>(matchId, cursor));
  const match = resource.data?.match;
  const [expected, setExpected] = useState<{ fingerprint: string | null; reviewId: string | null } | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [notice, setNotice] = useState("");
  const attempt = useRef<{ body: string; key: string } | null>(null);
  useEffect(() => {
    if (match && expected === null) setExpected({ fingerprint: match.evaluation_fingerprint, reviewId: match.review_id });
  }, [match, expected]);
  const stale = !match?.is_current || expected?.fingerprint !== match?.evaluation_fingerprint || expected?.reviewId !== match?.review_id;
  async function submit(decision: "confirmed" | "rejected") {
    if (!expected || !match || stale || busy) return;
    const values = { decision, note, expected_evaluation_fingerprint: expected.fingerprint, expected_review_id: expected.reviewId };
    const body = JSON.stringify(values);
    if (attempt.current?.body !== body) attempt.current = { body, key: crypto.randomUUID() };
    setBusy(true); setFailure(""); setNotice("");
    try {
      await api(`/topic-matches/${encodeURIComponent(matchId)}/reviews`, { method: "POST", body: JSON.stringify({ ...values, request_key: attempt.current!.key }) });
      await invalidateResources(resourceTag("topic-matches", "organization"), resourceTag("impact-inbox", "organization"), resourceTag("digests", "organization"));
      setExpected(null); setNote(""); attempt.current = null; setCursor(""); setNotice(t("topicReview.saved"));
    } catch (error) { setFailure(errorText(error)); }
    finally { setBusy(false); }
  }
  return <Shell section={t("topicReview.title")}>
    <header className="page-heading"><div><h1>{t("topicReview.title")}</h1><p className="muted max-w-3xl">{t("topicReview.help")}</p></div></header>
    <Link className="underline inline-flex min-h-[44px] items-center" href={match ? `/topics#topic-${match.topic_id}` : "/topics"}>{t("nav.topics")}</Link>
    <ErrorNote message={resource.error || failure} />
    <p role="status">{notice}</p>
    {cursor && !match && <Button variant="outline" onClick={() => setCursor("")}>{t("inboxPaging.newest")}</Button>}
    {resource.loading && !match && <Loading />}
    {match && <>
      <section className="rounded-xl border bg-white p-5 my-4 break-words" data-topic-review-evidence>
        <h2>{match.evidence.work_title}</h2>
        <p>{t("topics.matchReason", { reasons: terms(match.reasons) })}</p>
        <p>{t("feed.confidence")}: <Status value={match.confidence} /></p>
        <p>{t("topicReview.current")}: <Status value={match.is_current ? (match.decision_is_current ? match.decision : "pending") : "stale"} /></p>
        {officialUrl(match.evidence.source_url) && <a className="underline inline-flex min-h-[44px] items-center" target="_blank" rel="noopener noreferrer" href={officialUrl(match.evidence.source_url)}>{t("common.officialSource")}</a>}
        <details className="mt-2"><summary className="cursor-pointer min-h-[44px]">{t("common.evidence")}</summary><pre className="whitespace-pre-wrap break-words text-xs overflow-auto max-h-80">{JSON.stringify(match.evidence, null, 2)}</pre></details>
      </section>
      {canManage ? <section className="rounded-xl border bg-white p-5 my-4" data-topic-review-form>
        {stale && <p role="status">{t("topicReview.stale")}</p>}
        <Button variant="outline" disabled={busy} onClick={async () => { setBusy(true); setFailure(""); try { await invalidateResources(resourceTag("topic-matches", "organization")); setExpected(null); attempt.current = null; } finally { setBusy(false); } }}>{t("topicReview.reload")}</Button>
        <label className="block mt-4">{t("topicReview.note")}<Textarea value={note} minLength={3} maxLength={2000} disabled={busy} onChange={event => setNote(event.target.value)} className="mt-2" /></label>
        <p className="text-sm muted">{t("topicReview.shared")}</p>
        <div className="flex flex-wrap gap-3 mt-4">
          <Button disabled={busy || stale || note.trim().length < 3} onClick={() => void submit("confirmed")}>{t("topicReview.confirm")}</Button>
          <Button variant="outline" disabled={busy || stale || note.trim().length < 3} onClick={() => void submit("rejected")}>{t("topicReview.reject")}</Button>
        </div>
      </section> : <p>{t("topicReview.viewer")}</p>}
      <section className="my-5" data-topic-review-history>
        <h2>{t("topicReview.history")}</h2>
        {resource.data?.items.length === 0 && <p>{t("topicReview.noReviews")}</p>}
        <div className="space-y-4">{resource.data?.items.map(review => <article key={review.id} className="rounded-lg border p-4 break-words">
          <p><Status value={review.decision} /> · {dateTime(review.created_at)} · {review.actor_name || t("topicReview.localActor")}</p>
          <p className="whitespace-pre-wrap">{review.note}</p>
          <details><summary className="cursor-pointer min-h-[44px]">{t("topicReview.reviewedEvidence")}</summary><h3>{review.snapshot.evidence.work_title}</h3><p>{t("topics.matchReason", { reasons: terms(review.snapshot.reasons) })}</p><pre className="whitespace-pre-wrap break-words text-xs max-h-80 overflow-auto">{JSON.stringify(review.snapshot.evidence, null, 2)}</pre></details>
        </article>)}</div>
        <div className="flex gap-3 flex-wrap mt-4">{cursor && <Button variant="outline" onClick={() => setCursor("")}>{t("inboxPaging.newest")}</Button>}{resource.data?.next_cursor && <Button variant="outline" onClick={() => setCursor(resource.data!.next_cursor!)}>{t("inboxPaging.next")}</Button>}</div>
      </section>
    </>}
  </Shell>;
}

export function TopicMatchReviewPage() {
  const matchId = useSearchParams().get("match") || "";
  const { session } = useAuth();
  return <ReviewContent key={`${session?.user?.id || "local"}:${session?.organization?.id || "local"}:${matchId}`} matchId={matchId} />;
}
