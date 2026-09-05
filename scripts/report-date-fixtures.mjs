import { createElement } from "react";
import { renderLocalizedComponent } from "./analysis-mode-fixtures.mjs";

const review = { method: "date-mentions-v1", scope: "selected_material_evidence",
  legal_meaning_status: "not_reviewed", scanned_passages: 2, detected_mentions: 2,
  displayed_mentions: 2, display_limited: false };
const entries = ["old", "new"].map((side, index) => ({
  kind: "other", label: "Literal source date", mention: `1 January ${2026 + index}`,
  date: null, version_side: side, change_id: "c1", status: "uncertain", evidence_grade: "needs_review",
  citations: [{ version_id: side, passage_id: "p1", quote: `Proposed date: 1 January ${2026 + index}.`,
    url: `/evidence/${side}?passage=p1` }],
}));

export function reportDateFixtures() {
  return ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"].flatMap((locale) => [
    ["mentions", { date_review: review, important_dates: entries }],
    ["empty", { date_review: { ...review, detected_mentions: 0, displayed_mentions: 0 }, important_dates: [] }],
    ["limited", { date_review: { ...review, detected_mentions: 12, display_limited: true }, important_dates: entries }],
    ["legacy", { important_dates: [{ kind: "deadline", label: "Original historical label", date: null,
      status: "not_found", evidence_grade: "needs_review", citations: [] }] }],
  ].map(([state, report]) => ({
    locale, state,
    html: renderLocalizedComponent("report-dates.tsx", "ReportDates", locale, {
      report,
      renderCitations: (citations) => createElement("nav", null, ...citations.map((citation) =>
        createElement("a", { key: citation.url, href: citation.url }, citation.passage_id))),
    }),
  })));
}
