"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  GitCompareArrows,
  Loader2,
  MessageSquare,
  Send,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  api,
  dateTime,
  errorText,
  label,
  refreshWorkspace,
  useResource,
} from "@/lib/api";
import type {
  AIHistoryItem,
  AIHistoryPage,
  Analysis,
  Answer,
  Change,
  Comparison,
  Coverage,
  Health,
  Job,
  Version,
} from "@/lib/types";
import { Citations, ErrorNote, Loading, Status } from "./common";
import { AIHistory } from "./ai-history";
import { Shell } from "./shell";

const PAGE_SIZE = 40;
const JOB_TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);

async function waitForJob(initial: Job): Promise<Job> {
  let current = initial;
  const deadline = Date.now() + 10 * 60 * 1000;
  while (!JOB_TERMINAL_STATES.has(current.state)) {
    if (Date.now() >= deadline)
      throw new Error(
        "The work is still queued. You can leave this page and follow it in Scan activity.",
      );
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    current = await api<Job>("/jobs/" + current.id);
  }
  return current;
}

export function ComparisonView({ id }: { id: string }) {
  const [polling, setPolling] = useState(true);
  const { data, error: loadError } = useResource<Comparison>(
    "/comparisons/" + id,
    polling ? 2000 : 0,
  );
  const { data: health } = useResource<Health>("/health", 15000);
  const [filter, setFilter] = useState("substantive"),
    [context, setContext] = useState(false),
    [page, setPage] = useState(0);
  const [jumpTarget, setJumpTarget] = useState(""),
    [analysing, setAnalysing] = useState(false),
    [confirmingIdentity, setConfirmingIdentity] = useState(""),
    [error, setError] = useState("");
  const identityBlocked = ["mismatch", "unknown"].includes(
    data?.identity?.effective_status || data?.identity?.status || "",
  );
  const analysis = identityBlocked ? null : data?.analysis;
  const classificationAvailable = !!data?.diff.classification_counts;
  const meaningfulChangeCount =
    data?.diff.material_count ??
    data?.diff.items.filter(
      (item) =>
        item.significance === "substantive" ||
        item.significance === "uncertain",
    ).length ??
    0;
  const hasMeaningfulChanges =
    data?.diff.material_changed ?? meaningfulChangeCount > 0;
  const canAnalyseMeaningfulChanges =
    classificationAvailable && hasMeaningfulChanges;
  const hiddenExactChangeCount = data?.diff.classification_counts
    ? data.diff.classification_counts.structural +
      data.diff.classification_counts.formatting
    : 0;
  useEffect(() => {
    setPolling(analysing || analysis?.status === "pending");
  }, [analysing, analysis?.status]);
  useEffect(() => {
    if (jumpTarget)
      document
        .getElementById(jumpTarget)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [jumpTarget, page]);
  const items =
    data?.diff.items.filter(
      (item) =>
        (context || item.kind !== "unchanged") &&
        (filter === "all" ||
          (filter === "substantive"
            ? item.significance === "substantive" ||
              item.significance === "uncertain"
            : item.kind === filter)),
    ) || [];
  const pages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const visible = items.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const changes =
    data?.diff.items.filter((item) => item.kind !== "unchanged") || [];
  async function analyse() {
    setAnalysing(true);
    setError("");
    try {
      const queued = await api<Job>("/comparisons/" + id + "/analyse-jobs", {
        method: "POST",
      });
      const job = await waitForJob(queued);
      const result = job.result?.data as Analysis | undefined;
      if (job.state !== "succeeded")
        setError(
          job.error?.detail || "Apertus could not analyse this change dossier.",
        );
      else if (result?.status === "failed")
        setError(
          result.error || "Apertus could not analyse this change dossier.",
        );
      refreshWorkspace();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setAnalysing(false);
    }
  }
  async function confirmIdentity(versionId: string) {
    setConfirmingIdentity(versionId);
    setError("");
    try {
      await api("/versions/" + versionId + "/identity-decision", {
        method: "POST",
        body: JSON.stringify({
          note: "Confirmed from the saved comparison identity review",
        }),
      });
      refreshWorkspace();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setConfirmingIdentity("");
    }
  }
  async function removeMistakenImport(versionId: string) {
    if (
      !window.confirm(
        "Remove this saved import and every comparison that uses it?",
      )
    )
      return;
    setConfirmingIdentity(versionId);
    setError("");
    try {
      await api("/versions/" + versionId, { method: "DELETE" });
      refreshWorkspace();
      window.location.href = "/laws/" + data?.law_id;
    } catch (cause) {
      setError(errorText(cause));
      setConfirmingIdentity("");
    }
  }
  function jump(value: string) {
    setFilter("all");
    setContext(false);
    setPage(
      Math.floor(changes.findIndex((item) => item.id === value) / PAGE_SIZE),
    );
    setJumpTarget(value);
  }
  return (
    <Shell section="Document comparison" wide>
      <Link className="back-link" href={data ? "/laws/" + data.law_id : "/"}>
        <ArrowLeft size={14} />
        Back to document
      </Link>
      <ErrorNote message={loadError} />
      {!data ? (
        !loadError && <Loading text="Loading saved comparison…" />
      ) : (
        <>
          <div className="page-heading">
            <div>
              <span className="eyebrow">KNOW WHAT CHANGED</span>
              <h1>{data.law.name}</h1>
              <div className="flex flex-wrap gap-3 items-center text-xs muted">
                <Status value={data.mode} />
                <span>Comparison saved {dateTime(data.created_at)}</span>
                {(data.old_version.synthetic || data.new_version.synthetic) && (
                  <span className="synthetic-label">
                    Contains synthetic demo content
                  </span>
                )}
              </div>
            </div>
            <span className="comparison-mark">
              <GitCompareArrows size={22} />
            </span>
          </div>
          {data.mode !== "monitoring" && (
            <div className="info-note mb-6">
              {data.mode === "historical"
                ? "An imported or selected baseline was compared with freshly fetched content. This historical difference is not reported as a new live amendment."
                : "These are two saved versions. No source website was contacted and the live monitoring state was not changed."}
            </div>
          )}
          {identityBlocked && data.identity && (
            <div
              className="identity-warning identity-mismatch mb-6"
              role="alert"
            >
              <strong>
                {data.identity.effective_status === "mismatch"
                  ? "Comparison paused: these files identify different legal works"
                  : "Comparison paused: confirm the unknown document assignment"}
              </strong>
              <p>{data.identity.reason}</p>
              <p>
                Tracked: <b>{data.law.name}</b>
                <br />
                Detected before:{" "}
                <b>
                  {data.identity.old.detected_identifier ||
                    data.identity.old.detected_title ||
                    "Not identified"}
                </b>
                <br />
                Detected after:{" "}
                <b>
                  {data.identity.new.detected_identifier ||
                    data.identity.new.detected_title ||
                    "Not identified"}
                </b>
              </p>
              <span>
                No new comparison or AI request can start while this gate is
                unresolved. Existing exact evidence remains available for
                inspection.
              </span>
              <div className="flex flex-wrap gap-2 mt-3">
                <Button asChild variant="outline" size="sm">
                  <a href={data.old_version.artifact_url} target="_blank">
                    Inspect before original <ArrowUpRight />
                  </a>
                </Button>
                <Button asChild variant="outline" size="sm">
                  <a href={data.new_version.artifact_url} target="_blank">
                    Inspect after original <ArrowUpRight />
                  </a>
                </Button>
                <Button asChild variant="outline" size="sm">
                  <Link href={"/laws/" + data.law_id}>
                    Select or attach another version
                  </Link>
                </Button>
                {[data.old_version, data.new_version]
                  .filter(
                    (version) =>
                      version.id !== data.law.current_version_id &&
                      version.origin !== "live",
                  )
                  .map((version) => (
                    <Button
                      key={"remove-" + version.id}
                      variant="destructive"
                      size="sm"
                      disabled={!!confirmingIdentity}
                      onClick={() => removeMistakenImport(version.id)}
                    >
                      Remove mistaken import {version.id.slice(0, 8)}
                    </Button>
                  ))}
              </div>
              {data.identity.status === "unknown" && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {[
                    { side: data.identity.old, version: data.old_version },
                    { side: data.identity.new, version: data.new_version },
                  ]
                    .filter(
                      ({ side }) =>
                        side.status === "unknown" && !side.user_confirmed,
                    )
                    .map(({ version }, index) => (
                      <Button
                        key={version.id}
                        variant="outline"
                        size="sm"
                        disabled={!!confirmingIdentity}
                        onClick={() => confirmIdentity(version.id)}
                      >
                        {confirmingIdentity === version.id && (
                          <Loader2 className="animate-spin" />
                        )}
                        Confirm {index === 0 ? "this" : "other"} unknown
                        assignment
                      </Button>
                    ))}
                </div>
              )}
            </div>
          )}
          <div className="comparison-layout">
            <div className="min-w-0">
              <section className="panel diff-panel">
                <div className="panel-header">
                  <h2>Meaningful changes</h2>
                  <div className="diff-counts">
                    <span className="count-added">
                      + {data.diff.counts.added} added
                    </span>
                    <span className="count-removed">
                      − {data.diff.counts.removed} removed
                    </span>
                    <span>{data.diff.counts.modified} modified</span>
                  </div>
                </div>
                {data.diff.classification_counts && (
                  <div className="triage-summary">
                    <div>
                      <span>Material</span>
                      <strong>
                        {data.diff.classification_counts.substantive}
                      </strong>
                      <small>Review first</small>
                    </div>
                    <div>
                      <span>Renumbered / moved</span>
                      <strong>
                        {data.diff.classification_counts.structural}
                      </strong>
                      <small>Kept out of AI</small>
                    </div>
                    <div>
                      <span>Formatting only</span>
                      <strong>
                        {data.diff.classification_counts.formatting}
                      </strong>
                      <small>Hidden by default</small>
                    </div>
                    <div>
                      <span>Needs review</span>
                      <strong>
                        {data.diff.classification_counts.uncertain}
                      </strong>
                      <small>Uncertain match</small>
                    </div>
                  </div>
                )}
                <div className="version-pair">
                  <VersionCard version={data.old_version} side="BEFORE" />
                  <VersionCard version={data.new_version} side="AFTER" />
                </div>
                <div className="diff-toolbar">
                  <div
                    className="segmented"
                    role="group"
                    aria-label="Change filters"
                  >
                    {["substantive", "all", "added", "removed", "modified"].map(
                      (value) => (
                        <button
                          key={value}
                          type="button"
                          aria-pressed={filter === value}
                          onClick={() => {
                            setFilter(value);
                            setPage(0);
                          }}
                          className={filter === value ? "selected" : ""}
                        >
                          {value === "substantive"
                            ? "Material first"
                            : value === "all"
                              ? "All exact changes"
                              : label(value)}
                        </button>
                      ),
                    )}
                  </div>
                  <label className="checkbox-label !text-xs">
                    <input
                      type="checkbox"
                      checked={context}
                      onChange={(event) => {
                        setContext(event.target.checked);
                        setPage(0);
                      }}
                    />
                    Show unchanged context
                  </label>
                </div>
                {changes.length > 0 && (
                  <div className="change-navigation">
                    <label htmlFor="jump-change">Jump to a change</label>
                    <select
                      id="jump-change"
                      value=""
                      onChange={(event) => jump(event.target.value)}
                    >
                      <option value="" disabled>
                        Select passage…
                      </option>
                      {changes.map((item, index) => (
                        <option key={item.id} value={item.id}>
                          {index + 1}. {label(item.kind)} —{" "}
                          {(item.new?.text || item.old?.text || "").slice(
                            0,
                            100,
                          )}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="diff-legend">
                  <span>
                    <del>Removed wording</del>
                  </span>
                  <span>
                    <ins>Added wording</ins>
                  </span>
                  <span className="muted">
                    Unchanged wording stays neutral.
                  </span>
                </div>
                {!data.diff.changed && (
                  <div className="unchanged-state">
                    <Check size={24} />
                    <h2>No text changes.</h2>
                    <p>
                      These versions contain the same normalised text. Enable
                      unchanged context to read it.
                    </p>
                  </div>
                )}
                {data.diff.changed && items.length === 0 && (
                  <div className="unchanged-state">
                    <Check size={24} />
                    <h2>
                      {filter === "substantive" && !classificationAvailable
                        ? "Meaningful-change classification unavailable"
                        : filter === "substantive"
                          ? "No substantive wording change detected"
                          : "No passages match this filter"}
                    </h2>
                    <p>
                      {filter === "substantive" && !classificationAvailable
                        ? "This older saved comparison has not been classified. Review All exact changes or create a fresh comparison before using AI."
                        : filter === "substantive"
                          ? `${hiddenExactChangeCount} formatting or renumbering ${hiddenExactChangeCount === 1 ? "difference remains" : "differences remain"} available under All exact changes. No model request is needed.`
                          : "Choose another filter to continue reviewing the exact comparison."}
                    </p>
                  </div>
                )}
                <div className="diff-rows">
                  {visible.map((item) => (
                    <div
                      id={item.id}
                      className={
                        "diff-row diff-" +
                        item.kind +
                        (jumpTarget === item.id ? " diff-focused" : "")
                      }
                      key={item.id}
                    >
                      <DiffSide
                        item={item}
                        side="old"
                        version={data.old_version}
                      />
                      <DiffSide
                        item={item}
                        side="new"
                        version={data.new_version}
                      />
                    </div>
                  ))}
                </div>
                {items.length > 0 && (
                  <div className="pagination">
                    <span>
                      {page * PAGE_SIZE + 1}–
                      {Math.min((page + 1) * PAGE_SIZE, items.length)} of{" "}
                      {items.length} passages
                    </span>
                    <div className="flex gap-2 items-center">
                      <Button
                        variant="outline"
                        size="icon-sm"
                        aria-label="Previous passages"
                        onClick={() =>
                          setPage((value) => Math.max(0, value - 1))
                        }
                        disabled={page === 0}
                      >
                        <ChevronLeft />
                      </Button>
                      <span>
                        {page + 1} / {pages}
                      </span>
                      <Button
                        variant="outline"
                        size="icon-sm"
                        aria-label="Next passages"
                        onClick={() =>
                          setPage((value) => Math.min(pages - 1, value + 1))
                        }
                        disabled={page >= pages - 1}
                      >
                        <ChevronRight />
                      </Button>
                    </div>
                  </div>
                )}
              </section>
            </div>
            <aside className="analysis-column">
              <section className="panel impact-panel">
                <div className="panel-header">
                  <div className="flex items-center gap-2">
                    <Sparkles size={18} className="text-primary" />
                    <h2>Apertus impact</h2>
                  </div>
                  {analysis?.result && (
                    <Status value={analysis.result.impact} />
                  )}
                </div>
                <div className="panel-body">
                  <span className="eyebrow">KNOW WHAT IT MEANS</span>
                  {!health?.apertus.configured && (
                    <div className="model-unavailable">
                      <Sparkles size={25} />
                      <h3>Connect Apertus to explain this change.</h3>
                      <p>
                        The source text and visual diff already work. Open
                        Settings to connect your model endpoint and generate an
                        actual assessment.
                      </p>
                      <span>No AI response has been generated.</span>
                      <Button
                        asChild
                        variant="outline"
                        size="sm"
                        className="mt-3"
                      >
                        <Link href="/settings">Configure Apertus</Link>
                      </Button>
                    </div>
                  )}
                  {identityBlocked && (
                    <div className="historical-note">
                      Impact analysis is unavailable until the document mismatch
                      above is resolved.
                    </div>
                  )}
                  {analysis?.stale && (
                    <div className="historical-note">
                      This assessment used earlier profile or model settings.
                      Rerun it before relying on its impact rating.
                    </div>
                  )}
                  {analysis?.status === "pending" || analysing ? (
                    <Loading text="Apertus is reviewing the meaningful-change dossier…" />
                  ) : analysis?.status === "succeeded" && analysis.result ? (
                    <>
                      <p className="impact-summary">
                        {analysis.result.summary}
                      </p>
                      <p className="text-sm muted">
                        {analysis.result.reason}{" "}
                        <Citations values={analysis.result.citations} />
                      </p>
                      <div className="area-tags">
                        {analysis.result.business_areas.map((area) => (
                          <span key={area}>{area}</span>
                        ))}
                      </div>
                      {analysis.result.actions.length > 0 ? (
                        <>
                          <div className="action-heading">
                            <span className="eyebrow">KNOW WHAT TO DO</span>
                            <h3>Suggested next steps</h3>
                          </div>
                          <ol className="action-list">
                            {analysis.result.actions.map((action, index) => (
                              <li key={index}>
                                <span>{index + 1}</span>
                                <div>
                                  {action.text}{" "}
                                  <Citations values={action.citations} />
                                </div>
                              </li>
                            ))}
                          </ol>
                        </>
                      ) : (
                        <div className="action-empty">
                          <span className="eyebrow">KNOW WHAT TO DO</span>
                          <strong>No concrete action established</strong>
                          <p>
                            The evidence did not support a specific task. Refine
                            the company profile or ask about applicability
                            before changing a process.
                          </p>
                        </div>
                      )}
                      <CoverageNote coverage={analysis.coverage} />
                      <p className="text-xs muted">
                        Generated {dateTime(analysis.created_at)} ·{" "}
                        {analysis.model}
                      </p>
                    </>
                  ) : (
                    health?.apertus.configured && (
                      <p className="text-sm muted">
                        {!data.diff.changed
                          ? "There are no changes to assess. You can still ask questions about this document."
                          : !classificationAvailable
                            ? "Create a fresh comparison to classify the exact changes before asking AI for impact."
                            : hasMeaningfulChanges
                              ? "Analyse the bounded dossier of substantive and uncertain changes against your company profile."
                              : "The exact differences are formatting or renumbering only. No AI analysis is needed."}
                      </p>
                    )
                  )}
                  <ErrorNote message={error || analysis?.error} />
                  <Button
                    className="w-full mt-3"
                    variant="outline"
                    disabled={
                      analysing ||
                      analysis?.status === "pending" ||
                      !health?.apertus.configured ||
                      identityBlocked ||
                      !canAnalyseMeaningfulChanges
                    }
                    onClick={analyse}
                  >
                    {analysing ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <Sparkles />
                    )}
                    {analysis?.stale || analysis?.status === "failed"
                      ? "Retry impact analysis"
                      : analysis?.status === "succeeded"
                        ? "Load saved assessment"
                        : "Analyse with Apertus"}
                  </Button>
                  <p className="review-note">
                    Indicative impact and actions support your review. Check the
                    evidence before making a legal or business decision.
                  </p>
                </div>
              </section>
              {identityBlocked ? (
                <section className="panel ask-panel">
                  <div className="panel-header">
                    <h2 className="flex items-center gap-2">
                      <MessageSquare size={17} />
                      Ask Apertus
                    </h2>
                  </div>
                  <div className="panel-body">
                    <div className="historical-note" role="status">
                      Questions and saved AI history are hidden until the
                      document mismatch is resolved.
                    </div>
                  </div>
                </section>
              ) : (
                <>
                  <AskPanel
                    comparisonId={id}
                    configured={!!health?.apertus.configured}
                  />
                  <AIHistory comparisonId={id} compact />
                </>
              )}
            </aside>
          </div>
        </>
      )}
    </Shell>
  );
}

function VersionCard({ version, side }: { version: Version; side: string }) {
  return (
    <div className="version-card">
      <div className="flex justify-between gap-2">
        <span className="eyebrow">{side}</span>
        <span className="text-xs muted">{version.id.slice(0, 8)}</span>
      </div>
      <strong>{version.declared_date || "Version date unknown"}</strong>
      <p>
        {label(version.origin)} ·{" "}
        {version.declared_date
          ? "date supplied by user"
          : "no verified publication date"}
        {version.synthetic ? " · synthetic demo" : ""}
      </p>
      <p>First saved {dateTime(version.created_at)}</p>
      <Link href={"/evidence/" + version.id} className="text-link">
        <FileText size={12} />
        Read saved evidence
        <ArrowUpRight size={12} />
      </Link>
    </div>
  );
}

function DiffSide({
  item,
  side,
  version,
}: {
  item: Change;
  side: "old" | "new";
  version: Version;
}) {
  const passage = side === "old" ? item.old : item.new;
  const parts = side === "old" ? item.old_parts : item.new_parts;
  return (
    <div className={"diff-side diff-side-" + side}>
      <div className="passage-meta">
        <span>
          {side === "old" ? "BEFORE" : "AFTER"} ·{" "}
          {label(item.classification || item.change_type || item.kind)}
        </span>
        {passage && (
          <Link
            href={"/evidence/" + version.id + "?passage=" + passage.id}
            target="_blank"
          >
            {passage.page ? "Page " + passage.page + " · " : ""}
            {passage.id}
            <ArrowUpRight size={10} />
          </Link>
        )}
      </div>
      {passage ? (
        <p>
          {parts.map((part, index) =>
            part.kind === "removed" ? (
              <del key={index}>{part.text}</del>
            ) : part.kind === "added" ? (
              <ins key={index}>{part.text}</ins>
            ) : (
              <span key={index}>{part.text}</span>
            ),
          )}
        </p>
      ) : (
        <p className="no-passage">No passage on this side</p>
      )}
    </div>
  );
}

function CoverageNote({ coverage }: { coverage?: Partial<Coverage> }) {
  if (!coverage) return null;
  if (coverage.material_items !== undefined) {
    return (
      <div
        className={coverage.limited ? "coverage-note limited" : "coverage-note"}
      >
        {coverage.limited ? "Limited AI review: " : "AI review: "}
        {coverage.reviewed_material_items ?? 0} of {coverage.material_items}{" "}
        meaningful change units
        {coverage.suppressed_non_material_items
          ? ` · ${coverage.suppressed_non_material_items} formatting or structural differences kept out of model context`
          : ""}
        {coverage.provider_calls !== undefined
          ? ` · ${coverage.provider_calls} model ${coverage.provider_calls === 1 ? "call" : "calls"}`
          : ""}
        . {coverage.scope}
      </div>
    );
  }
  if (!coverage.available_passages) return null;
  return (
    <div
      className={coverage.limited ? "coverage-note limited" : "coverage-note"}
    >
      {coverage.limited ? "Limited context: " : "Evidence reviewed: "}
      {coverage.included_passages ?? 0} of {coverage.available_passages}{" "}
      passages · {(coverage.included_characters ?? 0).toLocaleString()}{" "}
      characters
      {coverage.provider_calls !== undefined
        ? ` · ${coverage.provider_calls} model ${coverage.provider_calls === 1 ? "call" : "calls"}`
        : ""}
      . {coverage.scope}
    </div>
  );
}

function AskPanel({
  comparisonId,
  configured,
  blockedReason,
}: {
  comparisonId: string;
  configured: boolean;
  blockedReason?: string;
}) {
  const [question, setQuestion] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const savedHistory = useResource<AIHistoryPage>(
    `/comparisons/${comparisonId}/ai-history`,
    5000,
  );
  const history = (savedHistory.data?.items || [])
    .filter((item) => item.type === "question")
    .sort(
      (left, right) =>
        new Date(right.last_used_at || right.created_at).getTime() -
        new Date(left.last_used_at || left.created_at).getTime(),
    )
    .slice(0, 20)
    .reverse();
  const ready = configured && !blockedReason;
  const quickQuestions = [
    "Explain the material changes simply",
    "Does this affect our organization?",
    "Show new obligations or deadlines",
    "Create a review checklist",
  ];
  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const submittedQuestion = question.trim();
      const queued = await api<Job>(
        "/comparisons/" + comparisonId + "/ask-jobs",
        {
          method: "POST",
          body: JSON.stringify({
            question: submittedQuestion,
            history: history
              .filter((item) => item.status === "succeeded")
              .slice(-4)
              .map((item) => ({ question: item.question })),
          }),
        },
      );
      const job = await waitForJob(queued);
      if (job.state !== "succeeded")
        throw new Error(
          job.error?.detail || "Apertus could not answer this question.",
        );
      const answer = job.result?.data as Answer | undefined;
      if (!answer) throw new Error("The saved job did not include an answer.");
      setQuestion("");
      setNotice(
        answer.cached
          ? "Loaded the saved answer. No new provider request was made."
          : "Answer saved to this comparison's AI history.",
      );
      savedHistory.reload();
      refreshWorkspace();
    } catch (cause) {
      setError(errorText(cause));
      savedHistory.reload();
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel ask-panel">
      <div className="panel-header">
        <h2 className="flex items-center gap-2">
          <MessageSquare size={17} />
          Ask Apertus
        </h2>
        <span className="text-xs muted">This comparison</span>
      </div>
      <div className="panel-body">
        <p className="text-xs muted mt-0">
          Ask about the current wording, the earlier version, or what changed.
          Answers link to the exact saved evidence.
        </p>
        <div className="chat-history" aria-live="polite">
          {history.map((item) => (
            <SavedQuestionTurn
              item={item}
              key={item.id}
              onSuggestion={setQuestion}
            />
          ))}
        </div>
        {savedHistory.loading && !savedHistory.data && (
          <Loading text="Loading saved questions…" />
        )}
        <ErrorNote message={savedHistory.error} />
        {blockedReason && <ErrorNote message={blockedReason} />}
        <div
          className="ask-intents"
          role="group"
          aria-label="Suggested questions"
        >
          {quickQuestions.map((value) => (
            <button
              type="button"
              disabled={!ready}
              className="suggested-question"
              onClick={() => setQuestion(value)}
              key={value}
            >
              {value}
              <ArrowRight size={13} />
            </button>
          ))}
        </div>
        <form onSubmit={ask}>
          <label className="sr-only" htmlFor="apertus-question">
            Question for Apertus
          </label>
          <Textarea
            id="apertus-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={
              ready
                ? "Ask about these versions…"
                : blockedReason || "Connect Apertus to ask a question"
            }
            disabled={!ready || busy}
            maxLength={2000}
            rows={3}
          />
          <ErrorNote message={error} />
          {notice && <p className="saved-answer-note">{notice}</p>}
          <Button
            type="submit"
            className="mt-3 w-full"
            disabled={!ready || busy || !question.trim()}
          >
            {busy ? <Loader2 className="animate-spin" /> : <Send />}
            {busy ? "Reviewing targeted evidence…" : "Ask with citations"}
          </Button>
        </form>
      </div>
    </section>
  );
}

function SavedQuestionTurn({
  item,
  onSuggestion,
}: {
  item: AIHistoryItem;
  onSuggestion: (value: string) => void;
}) {
  const answer = item.result as Pick<
    Answer,
    "supported" | "answer" | "citations" | "suggestions"
  > | null;
  return (
    <div className="chat-turn">
      <p className="question-bubble">{item.question}</p>
      <div className="answer-bubble">
        {item.status === "failed" ? (
          <ErrorNote message={item.error || "This saved request failed."} />
        ) : answer ? (
          <>
            {!answer.supported && (
              <strong className="block mb-2">
                Not supported by the supplied evidence
              </strong>
            )}
            <p>{answer.answer}</p>
            <Citations values={answer.citations} />
            {!!answer.suggestions?.length && (
              <div className="answer-suggestions">
                {answer.suggestions.map((suggestion) => (
                  <button
                    type="button"
                    key={suggestion}
                    onClick={() => onSuggestion(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
            <CoverageNote coverage={item.coverage} />
            <p className="saved-answer-meta">
              {dateTime(item.created_at)} · {item.model}
              {item.use_count > 1
                ? ` · reused ${item.use_count - 1} ${item.use_count === 2 ? "time" : "times"}`
                : ""}
            </p>
          </>
        ) : (
          <Loading text="Apertus is answering…" />
        )}
      </div>
    </div>
  );
}
