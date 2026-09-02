"use client";

import Link from "next/link";
import {
  ArrowUpRight,
  Clock3,
  History,
  MessageSquare,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { dateTime, label, useResource } from "@/lib/api";
import type {
  AIHistoryItem,
  AIHistoryPage,
  Citation,
  Impact,
} from "@/lib/types";
import { ErrorNote, Loading, Status } from "./common";

export function AIHistory({
  lawId,
  comparisonId,
  compact = false,
}: {
  lawId?: string;
  comparisonId?: string;
  compact?: boolean;
}) {
  const path = comparisonId
    ? `/comparisons/${comparisonId}/ai-history`
    : lawId
      ? `/laws/${lawId}/ai-history`
      : null;
  const history = useResource<AIHistoryPage>(path, 5000);
  return (
    <section
      className={compact ? "panel ai-history compact" : "panel ai-history mt-6"}
    >
      <div className="panel-header">
        <div className="flex items-center gap-3">
          <History size={18} />
          <h2>AI history</h2>
          <span className="count-pill">{history.data?.total ?? "—"}</span>
        </div>
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label="Refresh AI history"
          onClick={history.reload}
          disabled={history.loading}
        >
          <RefreshCw className={history.loading ? "animate-spin" : ""} />
        </Button>
      </div>
      <ErrorNote message={history.error} />
      {history.loading && !history.data ? (
        <Loading text="Loading saved AI conclusions…" />
      ) : history.data?.items.length ? (
        <div className="ai-history-list">
          {history.data.items.map((item) => (
            <HistoryItem item={item} key={`${item.type}-${item.id}`} />
          ))}
        </div>
      ) : (
        <div className="empty-state !py-10">
          <Sparkles size={25} className="muted" />
          <h3>No saved AI conclusions yet.</h3>
          <p className="muted">
            Run Impact analysis or ask a question. Results and failed attempts
            will remain attached to their exact comparison.
          </p>
        </div>
      )}
    </section>
  );
}

function HistoryItem({ item }: { item: AIHistoryItem }) {
  const impact = item.type === "impact" ? (item.result as Impact | null) : null;
  const answer =
    item.type === "question"
      ? (item.result as {
          supported: boolean;
          answer: string;
          citations: Citation[];
          context_mode?: string;
        } | null)
      : null;
  const title =
    item.type === "question"
      ? item.question || "Saved question"
      : impact?.summary || "Impact assessment";
  return (
    <details className="ai-history-item">
      <summary>
        <span className={`ai-history-icon ${item.type}`}>
          {item.type === "impact" ? (
            <Sparkles size={15} />
          ) : (
            <MessageSquare size={15} />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="ai-history-title">{title}</span>
          <span className="ai-history-meta">
            {item.type === "impact" ? "Impact" : "Question"} ·{" "}
            {dateTime(item.created_at)} · {item.model}
          </span>
        </span>
        <Status value={item.status} />
      </summary>
      <div className="ai-history-body">
        <div className="ai-history-facts">
          <Link href={`/compare/${item.comparison.id}`} className="text-link">
            {label(item.comparison.mode)} comparison ·{" "}
            {item.comparison.before.declared_date ||
              item.comparison.before.id.slice(0, 8)}{" "}
            →{" "}
            {item.comparison.after.declared_date ||
              item.comparison.after.id.slice(0, 8)}
            <ArrowUpRight size={12} />
          </Link>
          <a
            href={item.comparison.before.artifact_url}
            target="_blank"
            rel="noreferrer"
            className="text-link"
          >
            Earlier original <ArrowUpRight size={12} />
          </a>
          <a
            href={item.comparison.after.artifact_url}
            target="_blank"
            rel="noreferrer"
            className="text-link"
          >
            Current original <ArrowUpRight size={12} />
          </a>
          <span>
            Prompt revision {item.prompt_revision} · reused {item.use_count - 1}
            {item.use_count - 1 === 1 ? " time" : " times"}
          </span>
          {item.last_used_at && (
            <span className="inline-flex items-center gap-1">
              <Clock3 size={12} /> Last opened {dateTime(item.last_used_at)}
            </span>
          )}
        </div>
        {item.error && <ErrorNote message={item.error} />}
        {impact && (
          <div className="ai-history-result">
            <div className="flex items-center gap-2 mb-2">
              <Status value={impact.impact} />
              <strong>{impact.summary}</strong>
            </div>
            <p>{impact.reason}</p>
            {impact.actions?.length > 0 && (
              <ol>
                {impact.actions.map((action, index) => (
                  <li key={index}>{action.text}</li>
                ))}
              </ol>
            )}
            <HistoryCitations values={impact.citations} />
          </div>
        )}
        {item.type === "question" && (
          <div className="ai-history-result">
            <span className="eyebrow">QUESTION</span>
            <p className="font-semibold">{item.question}</p>
            {answer && (
              <>
                {!answer.supported && (
                  <strong className="text-sm">
                    Not supported by the saved evidence
                  </strong>
                )}
                <p>{answer.answer}</p>
                <HistoryCitations values={answer.citations || []} />
                <p className="text-xs muted mb-0">
                  Context:{" "}
                  {label(
                    answer.context_mode ||
                      item.context_mode ||
                      "saved evidence",
                  )}
                </p>
              </>
            )}
          </div>
        )}
        {item.coverage?.available_passages ? (
          <p className="coverage-note mb-0">
            Evidence reviewed: {item.coverage.included_passages} of{" "}
            {item.coverage.available_passages} passages ·{" "}
            {item.coverage.included_characters?.toLocaleString()} characters.
          </p>
        ) : null}
      </div>
    </details>
  );
}

function HistoryCitations({ values }: { values: Citation[] }) {
  if (!values?.length) return null;
  return (
    <span className="history-citations">
      Evidence:{" "}
      {values.map((citation, index) => (
        <Link
          href={citation.url}
          key={`${citation.version_id}-${citation.passage_id}`}
          title={citation.quote}
        >
          [{index + 1}]
        </Link>
      ))}
    </span>
  );
}
