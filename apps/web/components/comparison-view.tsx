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
  Analysis,
  Answer,
  Change,
  Comparison,
  Coverage,
  Health,
  Version,
} from "@/lib/types";
import { Citations, ErrorNote, Loading, Status } from "./common";
import { Shell } from "./shell";

const PAGE_SIZE = 40;

export function ComparisonView({ id }: { id: string }) {
  const [polling, setPolling] = useState(true);
  const { data, error: loadError } = useResource<Comparison>(
    "/comparisons/" + id,
    polling ? 2000 : 0,
  );
  const { data: health } = useResource<Health>("/health", 15000);
  const [filter, setFilter] = useState("all"),
    [context, setContext] = useState(false),
    [page, setPage] = useState(0);
  const [jumpTarget, setJumpTarget] = useState(""),
    [analysing, setAnalysing] = useState(false),
    [error, setError] = useState("");
  const analysis = data?.analysis;
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
        (filter === "all" || item.kind === filter),
    ) || [];
  const pages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const visible = items.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const changes =
    data?.diff.items.filter((item) => item.kind !== "unchanged") || [];
  async function analyse() {
    setAnalysing(true);
    setError("");
    try {
      const result = await api<Analysis>("/comparisons/" + id + "/analyse", {
        method: "POST",
      });
      if (result.status === "failed")
        setError(result.error || "Apertus could not analyse these passages.");
      refreshWorkspace();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setAnalysing(false);
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
          <div className="comparison-layout">
            <div className="min-w-0">
              <section className="panel diff-panel">
                <div className="panel-header">
                  <h2>Exact text changes</h2>
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
                <div className="version-pair">
                  <VersionCard version={data.old_version} side="BEFORE" />
                  <VersionCard version={data.new_version} side="AFTER" />
                </div>
                <div className="diff-toolbar">
                  <div className="segmented">
                    {["all", "added", "removed", "modified"].map((value) => (
                      <button
                        key={value}
                        onClick={() => {
                          setFilter(value);
                          setPage(0);
                        }}
                        className={filter === value ? "selected" : ""}
                      >
                        {value === "all" ? "All changes" : label(value)}
                      </button>
                    ))}
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
                  <p className="text-center muted py-10">
                    No passages match this filter.
                  </p>
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
                        The source text and visual diff already work. Set the
                        model endpoint in the server environment to generate an
                        actual assessment.
                      </p>
                      <span>No AI response has been generated.</span>
                    </div>
                  )}
                  {analysis?.stale && (
                    <div className="historical-note">
                      This assessment used earlier profile or model settings.
                      Rerun it before relying on its impact rating.
                    </div>
                  )}
                  {analysis?.status === "pending" || analysing ? (
                    <Loading text="Apertus is reading the saved passages…" />
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
                      <CoverageNote coverage={analysis.coverage} />
                      <p className="text-xs muted">
                        Generated {dateTime(analysis.created_at)} ·{" "}
                        {analysis.model}
                      </p>
                    </>
                  ) : (
                    health?.apertus.configured && (
                      <p className="text-sm muted">
                        {data.diff.changed
                          ? "Analyse the changed passages against your company profile. The result will include evidence and suggested actions."
                          : "There are no changes to assess. You can still ask questions about this document."}
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
                      !data.diff.changed
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
              <AskPanel
                comparisonId={id}
                configured={!!health?.apertus.configured}
              />
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
          {side === "old" ? "BEFORE" : "AFTER"} · {label(item.kind)}
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

function CoverageNote({ coverage }: { coverage?: Coverage }) {
  if (!coverage?.available_passages) return null;
  return (
    <div
      className={coverage.limited ? "coverage-note limited" : "coverage-note"}
    >
      {coverage.limited ? "Limited context: " : "Evidence reviewed: "}
      {coverage.included_passages} of {coverage.available_passages} passages ·{" "}
      {coverage.included_characters.toLocaleString()} characters.{" "}
      {coverage.scope}
    </div>
  );
}

function AskPanel({
  comparisonId,
  configured,
}: {
  comparisonId: string;
  configured: boolean;
}) {
  const [question, setQuestion] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [history, setHistory] = useState<
    { question: string; answer: Answer }[]
  >([]);
  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    setError("");
    try {
      const answer = await api<Answer>(
        "/comparisons/" + comparisonId + "/ask",
        {
          method: "POST",
          body: JSON.stringify({
            question,
            history: history
              .slice(-4)
              .map((item) => ({ question: item.question })),
          }),
        },
      );
      setHistory((values) => [...values, { question, answer }]);
      setQuestion("");
    } catch (cause) {
      setError(errorText(cause));
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
          {history.map((item, index) => (
            <div key={index} className="chat-turn">
              <p className="question-bubble">{item.question}</p>
              <div className="answer-bubble">
                {!item.answer.supported && (
                  <strong className="block mb-2">
                    Not supported by the supplied evidence
                  </strong>
                )}
                <p>{item.answer.answer}</p>
                <Citations values={item.answer.citations} />
                <CoverageNote coverage={item.answer.coverage} />
              </div>
            </div>
          ))}
        </div>
        {history.length === 0 && (
          <button
            disabled={!configured}
            className="suggested-question"
            onClick={() =>
              setQuestion(
                "What changed between the earlier version and the current wording?",
              )
            }
          >
            What changed in this document?
            <ArrowRight size={13} />
          </button>
        )}
        <form onSubmit={ask}>
          <label className="sr-only" htmlFor="apertus-question">
            Question for Apertus
          </label>
          <Textarea
            id="apertus-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={
              configured
                ? "Ask about these versions…"
                : "Connect Apertus to ask a question"
            }
            disabled={!configured || busy}
            maxLength={2000}
            rows={3}
          />
          <ErrorNote message={error} />
          <Button
            type="submit"
            className="mt-3 w-full"
            disabled={!configured || busy || !question.trim()}
          >
            {busy ? <Loader2 className="animate-spin" /> : <Send />}
            {busy ? "Reading the evidence…" : "Ask with citations"}
          </Button>
        </form>
      </div>
    </section>
  );
}
