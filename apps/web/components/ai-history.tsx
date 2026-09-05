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
import { resources } from "@/lib/resource-keys";
import type {
  AIHistoryItem,
  AIHistoryPage,
  Change,
  Citation,
  Impact,
  ResponseMode,
} from "@/lib/types";
import { ErrorNote, Loading, Status } from "./common";
import { AnalysisModeNotice } from "./analysis-mode-notice";
import { localeNames, type Locale, useI18n } from "@/lib/i18n";

export function AIHistory({
  lawId,
  comparisonId,
  compact = false,
  hidden,
  evidenceItems = [],
  onEvidence,
}: {
  lawId?: string;
  comparisonId?: string;
  compact?: boolean;
  hidden?: boolean;
  evidenceItems?: Change[];
  onEvidence?: (changeId: string) => void;
}) {
  const { t } = useI18n();
  const resource = comparisonId
    ? resources.comparisonHistory(comparisonId)
    : lawId
      ? resources.lawHistory(lawId)
      : null;
  const history = useResource<AIHistoryPage>(resource);
  return (
    <section
      id={comparisonId ? "companion-history" : undefined}
      role={comparisonId ? "tabpanel" : undefined}
      aria-label={comparisonId ? t("history.title") : undefined}
      hidden={hidden}
      className={
        compact
          ? "panel ai-history compact companion-tab-panel"
          : "panel ai-history mt-6"
      }
    >
      <div className="panel-header">
        <div className="flex items-center gap-3">
          <History size={18} />
          <h2>{t("history.title")}</h2>
          <span className="count-pill">{history.data?.total ?? "—"}</span>
        </div>
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label={t("history.refresh")}
          onClick={history.reload}
          disabled={history.loading}
        >
          <RefreshCw className={history.loading ? "animate-spin" : ""} />
        </Button>
      </div>
      <ErrorNote message={history.error} />
      {history.loading && !history.data ? (
        <Loading text={t("history.loading")} />
      ) : history.data?.items.length ? (
        <div className="ai-history-list">
          {history.data.items.map((item) => (
            <HistoryItem
              item={item}
              evidenceItems={evidenceItems}
              onEvidence={onEvidence}
              key={`${item.type}-${item.id}`}
            />
          ))}
        </div>
      ) : (
        <div className="empty-state !py-10">
          <Sparkles size={25} className="muted" />
          <h3>{t("history.empty")}</h3>
          <p className="muted">{t("history.emptyBody")}</p>
        </div>
      )}
    </section>
  );
}

function HistoryItem({
  item,
  evidenceItems,
  onEvidence,
}: {
  item: AIHistoryItem;
  evidenceItems: Change[];
  onEvidence?: (changeId: string) => void;
}) {
  const { locale, t, number } = useI18n();
  const impact = item.type === "impact" ? (item.result as Impact | null) : null;
  const answer =
    item.type === "question"
      ? (item.result as {
          supported: boolean;
          answer: string;
          citations: Citation[];
          context_mode?: string;
          response_mode?: ResponseMode;
        } | null)
      : null;
  const title =
    item.type === "question"
      ? item.question || t("history.savedQuestion")
      : impact?.headline || impact?.summary || t("history.assessment");
  const plan = item.analysis_plan;
  const actual = plan?.actual;
  const tokenTotal = Object.values(actual?.token_counts || {}).reduce(
    (sum, value) => sum + value,
    0,
  );
  const repairs = Number(actual?.validation?.repair_count || 0);
  const outputLocale = String(
    (item.result as { output_locale?: string } | null)?.output_locale ||
      plan?.output_locale ||
      "",
  );
  const outputLanguage = localeNames[outputLocale as Locale] || outputLocale;
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
            {item.type === "impact"
              ? t("history.impact")
              : t("history.question")}{" "}
            · {dateTime(item.created_at)} · {item.model}
            {outputLanguage
              ? ` · ${t("history.outputLanguage", { language: outputLanguage })}`
              : ""}
          </span>
        </span>
        <Status value={item.status} />
      </summary>
      <div className="ai-history-body">
        <div className="ai-history-facts">
          <Link href={`/compare/${item.comparison.id}`} className="text-link">
            {t("history.comparison", { mode: label(item.comparison.mode) })} ·{" "}
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
            {t("history.earlierOriginal")} <ArrowUpRight size={12} />
          </a>
          <a
            href={item.comparison.after.artifact_url}
            target="_blank"
            rel="noreferrer"
            className="text-link"
          >
            {t("history.currentOriginal")} <ArrowUpRight size={12} />
          </a>
          <span>
            {t("history.prompt", { revision: item.prompt_revision })} ·{" "}
            {t("history.reuse", { count: item.use_count - 1 })}
          </span>
          {item.last_used_at && (
            <span className="inline-flex items-center gap-1">
              <Clock3 size={12} />{" "}
              {t("history.lastOpened", { date: dateTime(item.last_used_at) })}
            </span>
          )}
        </div>
        {item.error && <ErrorNote message={item.error} />}
        {plan?.limits && (
          <div className="coverage-note mb-0" aria-label={t("history.plan")}>
            <strong>{t("history.plan")}</strong>
            <span>
              {" "}
              ·{" "}
              {t("history.expectedCalls", {
                count: plan.estimates.planned_generation_calls,
              })}
            </span>
            <span>
              {" "}
              ·{" "}
              {t("history.actualCalls", { count: actual?.provider_calls ?? 0 })}
            </span>
            <span>
              {" "}
              ·{" "}
              {t("history.callLimit", {
                count: plan.limits.provider_call_budget,
              })}
            </span>
            <span>
              {" "}
              ·{" "}
              {t("history.evidenceGroups", {
                count: plan.execution.batch_count,
              })}
            </span>
            <span>
              {" "}
              ·{" "}
              {t(
                plan.coverage.limited
                  ? "history.limitedCoverage"
                  : "history.completeCoverage",
              )}
            </span>
            {actual && (
              <>
                <span>
                  {" "}
                  ·{" "}
                  {t("history.queue", {
                    value: Math.round(actual.queue_wait_ms),
                  })}
                </span>
                <span>
                  {" "}
                  ·{" "}
                  {t("history.inference", {
                    value: Math.round(actual.inference_duration_ms),
                  })}
                </span>
              </>
            )}
            {tokenTotal ? (
              <span>
                {" "}
                · {t("history.tokens", { count: number(tokenTotal) })}
              </span>
            ) : null}
            {actual ? (
              <span> · {t("history.repairs", { count: repairs })}</span>
            ) : null}
          </div>
        )}
        {impact && (
          <div className="ai-history-result">
            <AnalysisModeNotice mode={impact.response_mode} />
            <div className="flex items-center gap-2 mb-2">
              <Status value={impact.impact} />
              <strong>{impact.headline || impact.summary}</strong>
            </div>
            <p>{impact.reason}</p>
            {impact.organization_applicability && (
              <p>
                <strong>
                  {t("history.applicability", {
                    value: label(impact.organization_applicability.status),
                  })}
                </strong>{" "}
                ·{" "}
                {t("history.evidenceGrade", {
                  value: label(
                    impact.organization_applicability.evidence_grade,
                  ),
                })}{" "}
                · {impact.organization_applicability.explanation}
              </p>
            )}
            {!!impact.material_changes?.length && (
              <p>
                {t("history.materialChanges", {
                  count: impact.material_changes.length,
                })}{" "}
                ·{" "}
                {t("history.evidenceGrade", {
                  value: label(impact.evidence_grade || "needs_review"),
                })}
              </p>
            )}
            {impact.actions?.length > 0 && (
              <ol>
                {impact.actions.map((action, index) => (
                  <li key={action.action_key || index}>
                    {action.title || action.text}
                    {action.owner_role
                      ? ` · ${action.owner_role} · ${action.due_date || action.due_basis}`
                      : ""}
                  </li>
                ))}
              </ol>
            )}
            <HistoryCitations
              values={impact.citations}
              items={evidenceItems}
              onEvidence={onEvidence}
            />
          </div>
        )}
        {item.type === "question" && (
          <div className="ai-history-result">
            <span className="eyebrow">{t("history.question")}</span>
            <p className="font-semibold">{item.question}</p>
            {answer && (
              <>
                <AnalysisModeNotice mode={answer.response_mode} />
                {!answer.supported && (
                  <strong className="text-sm">
                    {t("history.notSupported")}
                  </strong>
                )}
                <p>{answer.answer}</p>
                <HistoryCitations
                  values={answer.citations || []}
                  items={evidenceItems}
                  onEvidence={onEvidence}
                />
                <p className="text-xs muted mb-0">
                  {t("history.context", {
                    value: label(
                      answer.context_mode ||
                        item.context_mode ||
                        "saved evidence",
                    ),
                  })}
                </p>
              </>
            )}
          </div>
        )}
        {item.coverage?.available_passages ? (
          <p className="coverage-note mb-0">
            {t("history.reviewed", {
              included: item.coverage.included_passages || 0,
              available: item.coverage.available_passages,
              characters: number(item.coverage.included_characters || 0),
            })}
          </p>
        ) : null}
      </div>
    </details>
  );
}

function HistoryCitations({
  values,
  items,
  onEvidence,
}: {
  values: Citation[];
  items: Change[];
  onEvidence?: (changeId: string) => void;
}) {
  const { t } = useI18n();
  if (!values?.length) return null;
  return (
    <span className="history-citations">
      {t("history.evidence")}:{" "}
      {values.map((citation, index) => {
        const change = items.find(
          (item) =>
            item.old?.id === citation.passage_id ||
            item.new?.id === citation.passage_id,
        );
        return change && onEvidence ? (
          <button
            type="button"
            onClick={() => onEvidence(change.id)}
            key={`${citation.version_id}-${citation.passage_id}-${index}`}
            title={citation.quote}
          >
            [{index + 1}]
          </button>
        ) : (
          <Link
            href={citation.url}
            key={`${citation.version_id}-${citation.passage_id}-${index}`}
            title={citation.quote}
          >
            [{index + 1}]
          </Link>
        );
      })}
    </span>
  );
}
