"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowUpRight,
  BellOff,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Clock3,
  Eye,
  EyeOff,
  FileSearch,
  Inbox,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  api,
  dateTime,
  errorText,
  invalidateResources,
  label,
  resourceTag,
  useResource,
} from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { ErrorNote, Loading, Status, SuccessNote } from "./common";
import { Shell } from "./shell";
import { useAuth } from "./auth-gate";
import { useI18n } from "@/lib/i18n";

type InboxState = "unread" | "read" | "dismissed" | "muted";
type InboxLaw = {
  organization_candidate_id: string;
  candidate_id: string;
  watch_id: string;
  law_id: string;
  law_title: string;
  law_active: boolean;
  status: "confirmed_relation" | "possible_impact" | "awaiting_analysis" | "analysis_failed" | "no_supported_impact";
  severity: string;
  why: Array<Record<string, unknown> | string>;
  potential_effect: string;
  suggested_next_step: string;
  coverage: Record<string, unknown>;
  current_analysis_id?: string;
  latest_attempt_id?: string;
  latest_attempt_status?: string;
  latest_attempt_error?: string;
  analysis_history_count: number;
  official_relation?: { id: string; type: string; provenance: string };
  organization_review?: { id: string; decision: "confirmed" | "rejected"; note: string; created_at: string };
  latest_review?: { id: string; decision: "confirmed" | "rejected" | "annotated"; note: string; created_at: string };
  review_history_count: number;
  replacement?: {
    predecessor: { title: string; timeline: string };
    successor: { title: string; url?: string; monitored: boolean; timeline?: string };
  };
  links: {
    timeline: string;
    comparison?: string;
    relation_evidence?: string;
    analysis_history: string;
  };
};
type InboxEvent = {
  event_id: string;
  title: string;
  source: string;
  authority: string;
  type: string;
  document_kind: string;
  detected_at: string;
  source_url?: string;
  source_artifact_url?: string;
  read_state: InboxState;
  severity: string;
  coverage: { analysed: number; total: number };
  items: InboxLaw[];
};
type InboxResponse = {
  items: InboxEvent[];
  total_events: number;
  total_impacts: number;
  unread: number;
};
type AnalysisHistory = {
  items: Array<{
    id: string;
    status: string;
    created_at: string;
    model: string;
    error?: string;
    result?: { potential_severity?: string; explanation?: string; supported?: boolean };
  }>;
};
type ReviewHistoryResponse = {
  items: Array<{
    id: string;
    decision: "confirmed" | "rejected" | "annotated";
    note: string;
    created_at: string;
    actor?: { id: string; name: string };
  }>;
  total: number;
};

function whyText(items: InboxLaw["why"], fallback: string) {
  if (!items.length) return fallback;
  return items
    .slice(0, 3)
    .map((item) => {
      if (typeof item === "string") return item;
      return String(item.reason || item.label || item.kind || JSON.stringify(item));
    })
    .join(" · ");
}

function History({ item }: { item: InboxLaw }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const history = useResource(
    open
      ? resources.relationAnalyses<AnalysisHistory>(
          item.organization_candidate_id,
        )
      : null,
  );
  return (
    <div className="mt-4 border-t pt-3">
      <button className="text-sm font-medium flex items-center gap-2" onClick={() => setOpen(!open)}>
        <ChevronDown size={14} className={open ? "rotate-180" : ""} />
        {t("impact.history", { count: item.analysis_history_count })}
      </button>
      {open && (
        <div className="mt-3 space-y-2">
          {history.loading && <span className="muted text-sm">{t("impact.historyLoading")}</span>}
          <ErrorNote message={history.error} />
          {history.data?.items.map((record) => (
            <div className="rounded-md border bg-white p-3 text-sm" key={record.id}>
              <div className="flex flex-wrap justify-between gap-2">
                <span><Status value={record.status} /> {dateTime(record.created_at)}</span>
                <span className="muted">{record.model}</span>
              </div>
              <p className="mb-0 mt-2">{record.result?.explanation || record.error || t("impact.noConclusion")}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

type InboxMutation = "review" | "reanalysis" | "successor";

function ReviewPanel({ item, onChanged }: { item: InboxLaw; onChanged: (change: InboxMutation) => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [failure, setFailure] = useState("");
  const [reviewStartedAt, setReviewStartedAt] = useState<number | null>(null);
  const [evidenceOpened, setEvidenceOpened] = useState(false);
  const history = useResource<ReviewHistoryResponse>(
    open ? resources.relationReviews<ReviewHistoryResponse>(item.organization_candidate_id) : null,
  );

  async function submit(decision: "confirmed" | "rejected" | "annotated") {
    if (note.trim().length < 3) return;
    setBusy(decision);
    setMessage("");
    setFailure("");
    try {
      await api(`/relation-candidates/${item.organization_candidate_id}/reviews`, {
        method: "POST",
        body: JSON.stringify({
          decision,
          note: note.trim(),
          workflow_variant: "inbox_list_v1",
          review_duration_ms: reviewStartedAt === null
            ? null
            : Math.min(1_800_000, Math.max(0, Date.now() - reviewStartedAt)),
          evidence_opened: evidenceOpened,
        }),
      });
      setNote("");
      setReviewStartedAt(Date.now());
      setEvidenceOpened(false);
      setMessage(
        decision === "confirmed"
          ? t("impact.reviewSaved.confirmed")
          : decision === "rejected"
            ? t("impact.reviewSaved.rejected")
            : t("impact.reviewSaved.annotated"),
      );
      void invalidateResources(resources.relationReviews(item.organization_candidate_id));
      onChanged("review");
    } catch (cause) {
      setFailure(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="mt-4 rounded-md border bg-white p-3">
      <button
        className="flex w-full items-center justify-between gap-3 text-left text-sm font-medium"
        onClick={() => {
          if (!open && reviewStartedAt === null) setReviewStartedAt(Date.now());
          setOpen(!open);
        }}
        aria-expanded={open}
      >
        <span>{t("impact.reviewLead")}</span>
        <span className="flex items-center gap-2 muted">
          {t("impact.reviewEntries", { count: item.review_history_count })}
          <ChevronDown size={14} className={open ? "rotate-180" : ""} />
        </span>
      </button>
      {open && (
        <div className="mt-3 space-y-3 border-t pt-3">
          <p className="muted mb-0 text-sm">{t("impact.reviewHelp")}</p>
          {item.links.relation_evidence && (
            <Button asChild size="sm" variant="outline">
              <a
                href={item.links.relation_evidence}
                target="_blank"
                rel="noreferrer"
                onClick={() => setEvidenceOpened(true)}
              >
                {t("impact.inspectReviewEvidence")} <ArrowUpRight size={13} />
              </a>
            </Button>
          )}
          <textarea
            className="min-h-24 w-full rounded-md border bg-white p-3 text-sm"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder={t("impact.reviewReasonPlaceholder")}
            maxLength={2000}
          />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" disabled={!!busy || note.trim().length < 3} onClick={() => submit("confirmed")}>
              {t("impact.confirm")}
            </Button>
            <Button size="sm" variant="outline" disabled={!!busy || note.trim().length < 3} onClick={() => submit("rejected")}>
              {t("impact.reject")}
            </Button>
            <Button size="sm" variant="ghost" disabled={!!busy || note.trim().length < 3} onClick={() => submit("annotated")}>
              {t("impact.addAnnotation")}
            </Button>
          </div>
          <ErrorNote message={failure} />
          {message && <SuccessNote>{message}</SuccessNote>}
          {history.loading && <span className="muted text-sm">{t("impact.reviewHistoryLoading")}</span>}
          <ErrorNote message={history.error} />
          {history.data?.items.map((review) => (
            <div className="rounded-md border bg-[#fbfcf8] p-3 text-sm" key={review.id}>
              <div className="flex flex-wrap justify-between gap-2">
                <strong>
                  {review.decision === "confirmed"
                    ? t("impact.reviewDecision.confirmed")
                    : review.decision === "rejected"
                      ? t("impact.reviewDecision.rejected")
                      : t("impact.reviewDecision.annotated")}
                </strong>
                <span className="muted">
                  {review.actor?.name || t("impact.reviewSystemActor")} · {dateTime(review.created_at)}
                </span>
              </div>
              <p className="mb-0 mt-2 whitespace-pre-wrap">{review.note}</p>
            </div>
          ))}
          {history.data?.total === 0 && <p className="muted mb-0 text-sm">{t("impact.noReviews")}</p>}
        </div>
      )}
    </div>
  );
}

function LawImpact({
  item,
  canManage,
  onChanged,
}: {
  item: InboxLaw;
  canManage: boolean;
  onChanged: (change: InboxMutation) => void;
}) {
  const { t, locale } = useI18n();
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [failure, setFailure] = useState("");
  async function command(path: string, success: string, change: Exclude<InboxMutation, "review">, body?: Record<string, unknown>) {
    setBusy(path);
    setFailure("");
    setMessage("");
    try {
      await api(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
      setMessage(success);
      onChanged(change);
    } catch (cause) {
      setFailure(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  return (
    <section className="rounded-lg border bg-[#fbfcf8] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap gap-2 mb-2">
            <Status value={item.severity} />
            <span className="status-badge">{t(`status.${item.status}`)}</span>
            {item.official_relation && <span className="status-badge status-green">{t("impact.officialMetadata")}</span>}
            {item.organization_review && <span className="status-badge status-amber">{t("impact.organizationReview", { decision: item.organization_review.decision })}</span>}
          </div>
          <h3 className="m-0 text-lg">{item.law_title}</h3>
        </div>
        <span className="text-xs muted">
          {t("impact.coverage", { selected: String(item.coverage.selected_rows || item.coverage.selected || "saved"), total: String(item.coverage.total_rows || item.coverage.total || "bounded") })}
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-3 mt-4">
        <div>
          <span className="eyebrow">{t("impact.why")}</span>
          <p className="text-sm mb-0 mt-1">{whyText(item.why, t("impact.reasonFallback"))}</p>
        </div>
        <div>
          <span className="eyebrow">{t("impact.effect")}</span>
          <p className="text-sm mb-0 mt-1">{item.potential_effect}</p>
        </div>
        <div>
          <span className="eyebrow">{t("impact.next")}</span>
          <p className="text-sm mb-0 mt-1">{item.suggested_next_step}</p>
        </div>
      </div>
      {item.latest_attempt_status === "failed" && item.current_analysis_id && (
        <p className="mt-3 mb-0 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {t("impact.latestFailed")}
        </p>
      )}
      {item.replacement && (
        <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm">
          <strong>{t("impact.officialReplacement")}</strong> {item.replacement.predecessor.title} → {item.replacement.successor.title}.{" "}
          {item.replacement.successor.monitored ? t("impact.replacementMonitored") : t("impact.replacementAvailable")}
        </div>
      )}
      <div className="flex flex-wrap gap-2 mt-4">
        <Button asChild size="sm"><Link href={item.links.timeline}><BookOpen size={14} /> {t("impact.documentTimeline")}</Link></Button>
        {item.links.comparison && <Button asChild size="sm" variant="outline"><Link href={item.links.comparison}>{t("common.comparison")}</Link></Button>}
        {item.links.relation_evidence && <Button asChild size="sm" variant="outline"><a href={item.links.relation_evidence} target="_blank" rel="noreferrer">{t("impact.relationEvidence")} <ArrowUpRight size={13} /></a></Button>}
        {canManage && (
          <Button
            size="sm"
            variant="outline"
            disabled={!!busy}
            onClick={() => command(
              `/relation-candidates/${item.organization_candidate_id}/reanalyse-jobs`,
              t("impact.reanalysisQueued"),
              "reanalysis",
              { output_locale: locale },
            )}
          >
            <RefreshCw size={14} /> {t("impact.reanalyse")}
          </Button>
        )}
        {canManage && item.replacement && !item.replacement.successor.monitored && (
          <Button
            size="sm"
            disabled={!!busy}
            onClick={() => command(`/relation-candidates/${item.organization_candidate_id}/monitor-successor`, "The successor was added without removing the predecessor history.", "successor")}
          >
            {t("impact.monitorSuccessor")}
          </Button>
        )}
      </div>
      <ErrorNote message={failure || item.latest_attempt_error || ""} />
      {message && <SuccessNote>{message}</SuccessNote>}
      {canManage && !item.official_relation && <ReviewPanel item={item} onChanged={onChanged} />}
      <History item={item} />
    </section>
  );
}

const FILTERS = [
  ["source", "Source", [["", "All sources"], ["fedlex", "Fedlex"], ["swiss-parliament", "Swiss Parliament"], ["federal-supreme-court", "Federal Supreme Court"]]],
  ["severity", "Severity", [["", "All severities"], ["high", "High"], ["medium", "Medium"], ["low", "Low"], ["none", "None"], ["unknown", "Unknown"]]],
  ["item_type", "Type", [["", "All event types"], ["created", "Created"], ["new_version", "New version"], ["amended", "Amended"], ["repealed", "Repealed"], ["replaced", "Replaced"], ["decided", "Decided"], ["notice_published", "Notice"]]],
  ["state", "My state", [["", "All states"], ["unread", "Unread"], ["read", "Read"], ["dismissed", "Dismissed"], ["muted", "Muted"]]],
] as const;
const ALL_FILTER_KEYS: Record<string, string> = {
  source: "filter.allAuthorities", severity: "filter.allSeverities",
  item_type: "filter.allTypes", state: "filter.allStates",
};

export function ImpactInboxPage() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { canManage } = useAuth();
  const { t } = useI18n();
  const [busy, setBusy] = useState("");
  const [failure, setFailure] = useState("");
  const query = new URLSearchParams(params.toString()).toString();
  const resource = useResource(
    resources.impactInbox<InboxResponse>(query),
  );
  function refreshAfterMutation(change: InboxMutation) {
    if (change === "successor") {
      void invalidateResources(
        resourceTag("impact-inbox", "organization"),
        resources.laws(),
        resourceTag("registry", "organization"),
        resources.organizationStatus(),
      );
      return;
    }
    if (change === "reanalysis") {
      void invalidateResources(
        resourceTag("impact-inbox", "organization"),
        resources.jobs(),
      );
      return;
    }
    void invalidateResources(resourceTag("impact-inbox", "organization"));
  }
  function update(key: string, value: string) {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    router.push(pathname + "?" + next.toString());
  }
  async function setState(event: InboxEvent, state: InboxState) {
    setBusy(event.event_id + state);
    setFailure("");
    try {
      await api(`/impact-inbox/events/${event.event_id}/state`, {
        method: "PATCH",
        body: JSON.stringify({ state }),
      });
      void invalidateResources(resourceTag("impact-inbox", "organization"));
    } catch (cause) {
      setFailure(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  return (
    <Shell section={t("nav.impact")} wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("impact.eyebrow")}</span>
          <h1>{t("impact.title")}</h1>
          <p className="muted m-0">{t("impact.body")}</p>
        </div>
      </div>
      {resource.data && (
        <div className="grid grid-cols-3 gap-3 mb-5">
          <div className="stat-card"><Inbox size={18} /><strong>{resource.data.total_events}</strong><span>{t("impact.sourceEvents")}</span></div>
          <div className="stat-card"><Sparkles size={18} /><strong>{resource.data.total_impacts}</strong><span>{t("impact.lawImpacts")}</span></div>
          <div className="stat-card"><CircleAlert size={18} /><strong>{resource.data.unread}</strong><span>{t("impact.unread")}</span></div>
        </div>
      )}
      <section className="card p-4 mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {FILTERS.map(([key, title, values]) => (
          <label className="text-xs muted" key={key}>{key === "source" ? t("filter.authority") : key === "severity" ? t("filter.severity") : key === "item_type" ? t("filter.type") : key === "state" ? t("filter.myState") : title}
            <select className="input mt-1 w-full" value={params.get(key) || ""} onChange={(event) => update(key, event.target.value)}>
              {values.map(([value, text]) => <option value={value} key={value}>{value ? text : t(ALL_FILTER_KEYS[key] || "common.clear")}</option>)}
            </select>
          </label>
        ))}
        <label className="text-xs muted">{t("filter.watchedLaw")}
          <select className="input mt-1 w-full" value={params.get("watched_law") || ""} onChange={(event) => update("watched_law", event.target.value)}>
            <option value="">{t("filter.allWatchedLaws")}</option>
            {Array.from(new Map(resource.data?.items.flatMap((event) => event.items.map((item) => [item.law_id, item.law_title])) || [])).map(([id, title]) => <option key={id} value={id}>{title}</option>)}
          </select>
        </label>
      </section>
      <ErrorNote message={failure || resource.error} />
      {resource.loading && !resource.data && <Loading text={t("impact.loading")} />}
      {!resource.loading && resource.data?.total_events === 0 && (
        <section className="empty-state card"><FileSearch size={28} /><h2>{t("impact.empty")}</h2><p className="muted">{t("impact.emptyBody")}</p></section>
      )}
      <div className="space-y-5">
        {resource.data?.items.map((event) => (
          <article className={`card p-5 ${event.read_state === "dismissed" || event.read_state === "muted" ? "opacity-70" : ""}`} key={event.event_id}>
            <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
              <div>
                <div className="flex flex-wrap gap-2 mb-2"><Status value={event.type} /><Status value={event.severity} /><span className="status-badge">{label(event.read_state)}</span></div>
                <h2 className="text-xl m-0">{event.title}</h2>
                <p className="muted text-sm mt-1 mb-0">{event.authority} · {label(event.document_kind)} · {t("impact.detected", { date: dateTime(event.detected_at) })}</p>
              </div>
              <span className="text-sm muted"><Clock3 size={14} className="inline mr-1" />{t("impact.lawsAnalysed", { done: event.coverage.analysed, total: event.coverage.total })}</span>
            </div>
            <div className="space-y-3">
              {event.items.map((item) => <LawImpact item={item} canManage={canManage} onChanged={refreshAfterMutation} key={item.organization_candidate_id} />)}
            </div>
            <div className="flex flex-wrap gap-2 mt-4">
              {event.source_artifact_url && <Button asChild size="sm" variant="outline"><Link href={event.source_artifact_url}>{t("impact.savedArtifact")}</Link></Button>}
              {event.source_url && <Button asChild size="sm" variant="ghost"><a href={event.source_url} target="_blank" rel="noreferrer">{t("common.officialSource")} <ArrowUpRight size={13} /></a></Button>}
              <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => setState(event, event.read_state === "read" ? "unread" : "read")}><Eye size={14} /> {t("registry.markRead", { state: t(`status.${event.read_state === "read" ? "unread" : "read"}`) })}</Button>
              <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => setState(event, "dismissed")}><EyeOff size={14} /> {t("impact.dismiss")}</Button>
              <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => setState(event, "muted")}><BellOff size={14} /> {t("impact.mute")}</Button>
              {event.read_state !== "unread" && <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => setState(event, "unread")}><CheckCircle2 size={14} /> {t("impact.restore")}</Button>}
            </div>
          </article>
        ))}
      </div>
    </Shell>
  );
}
