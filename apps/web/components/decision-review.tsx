"use client";

import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import { decisionCopy } from "@/lib/decision-copy";
import type { Citation, Impact } from "@/lib/types";

type Props = {
  report: Impact;
  renderCitations: (values: Citation[]) => ReactNode;
};

export function ChangeExplanationBasis({
  basis,
}: {
  basis?: "saved_comparison" | "model_interpretation";
}) {
  const { locale } = useI18n();
  if (!basis) return null;
  return (
    <p className="text-sm historical-note" data-explanation-basis={basis}>
      {basis === "model_interpretation"
        ? decisionCopy[locale].modelExplanation
        : decisionCopy[locale].savedWording}
    </p>
  );
}

export function DecisionReview({ report, renderCitations }: Props) {
  const { locale, t } = useI18n();
  const copy = decisionCopy[locale];
  if (
    report.response_mode === "selected_evidence" ||
    report.response_mode === "deterministic"
  )
    return null;
  const reviewed = report.decision_review?.basis === "model_interpretation";
  const status = report.official_status;
  return (
    <section
      className="impact-report-section space-y-3"
      data-decision-review={reviewed ? "interpreted" : "legacy"}
    >
      <h3 className="eyebrow">{copy.title}</h3>
      <p className="text-sm historical-note">
        {reviewed ? copy.interpretation : copy.legacy}
      </p>
      {reviewed && (
        <>
          {report.decision_review?.limited && (
            <p className="historical-note text-sm">
              {t("history.limitedCoverage")}
            </p>
          )}
          <p className="text-sm">
            {copy.coverage
              .replace(
                "{explained}",
                String(report.decision_review!.explained_changes),
              )
              .replace(
                "{total}",
                String(
                  report.evidence_coverage?.material_items ??
                    report.decision_review!.available_changes,
                ),
              )}
          </p>
          {!!report.organization_applicability?.conditions?.length && (
            <div>
              <h4 className="text-sm font-semibold">{copy.conditions}</h4>
              <ul className="list-disc pl-5 text-sm">
                {report.organization_applicability.conditions.map(
                  (condition, index) => (
                    <li key={index}>{condition}</li>
                  ),
                )}
              </ul>
            </div>
          )}
          {status && (
            <div className="text-sm" data-official-status={status.status}>
              <h4 className="font-semibold">
                {copy.official}: {copy.statuses[status.status]}
              </h4>
              <p>{status.explanation}</p>
              {!!status.citations.length && (
                <details>
                  <summary>{copy.source}</summary>
                  {renderCitations(status.citations)}
                </details>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

export function ActionReviewNotice({ report, renderCitations }: Props) {
  const { locale } = useI18n();
  const copy = decisionCopy[locale];
  const review =
    report.decision_review?.basis === "model_interpretation"
      ? report.action_review
      : undefined;
  const label =
    review?.status === "no_action_now"
      ? copy.noAction
      : review?.status === "review_actions"
        ? copy.reviewActions
        : copy.notReviewed;
  return (
    <section
      className="action-empty text-sm"
      data-action-review={review?.status || "not_reviewed"}
    >
      <h3 className="eyebrow">{copy.actionTitle}</h3>
      <strong>{label}</strong>
      <p>{review?.explanation || copy.missing}</p>
      {!!review?.citations.length && (
        <details>
          <summary>{copy.source}</summary>
          {renderCitations(review.citations)}
        </details>
      )}
    </section>
  );
}
