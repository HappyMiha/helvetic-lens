"use client";

import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import type { Citation, Impact } from "@/lib/types";

export function ReportDates({ report, renderCitations }: {
  report: Pick<Impact, "important_dates" | "date_review">;
  renderCitations: (citations: Citation[]) => ReactNode;
}) {
  const { t } = useI18n();
  const entries = report.important_dates || [];
  const review = report.date_review;
  const statusLabels = {
    found: t("dateReview.found"), not_found: t("dateReview.notFound"),
    uncertain: t("dateReview.uncertain"), not_reviewed: t("status.not_reviewed"),
  };
  if (!review && !entries.length) return null;
  return (
    <section className="impact-report-section" data-date-review={review?.method || "legacy"}>
      <h3 className="eyebrow">{t(review ? "dateReview.title" : "compare.datesDeadlines")}</h3>
      <p className="text-sm">{t(review ? "dateReview.scope" : "dateReview.legacy")}</p>
      {review && <p className="text-sm text-muted-foreground">
        {t("dateReview.counts", { shown: review.displayed_mentions, count: review.detected_mentions, passages: review.scanned_passages })}
        {review.display_limited && <> {t("dateReview.limited")}</>}
      </p>}
      {review && !entries.length && <p className="historical-note text-sm">{t("dateReview.noMatches")}</p>}
      <div className="space-y-3">
        {entries.map((item, index) => (
          <div className="rounded-md border p-3 break-words" key={`${item.change_id || item.kind}-${index}`}>
            <strong className="block text-sm">{item.mention || item.date || item.label}</strong>
            {item.version_side && <span className="text-sm text-muted-foreground">
              {t(item.version_side === "old" ? "dateReview.old" : "dateReview.new")}
              {" · "}{t("dateReview.unverified")}
            </span>}
            {!item.version_side && <span className="text-sm text-muted-foreground">{statusLabels[item.status]}</span>}
            {!!item.citations.length && <details className="mt-2 text-sm">
              <summary>{t("dateReview.source")}</summary>
              {item.citations.map((citation, citationIndex) => (
                <blockquote className="my-2 border-l-2 pl-3" key={citationIndex}>{citation.quote}</blockquote>
              ))}
              {renderCitations(item.citations)}
            </details>}
          </div>
        ))}
      </div>
    </section>
  );
}
