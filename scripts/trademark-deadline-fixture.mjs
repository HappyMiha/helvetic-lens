// Synthetic UI responses only. Date arithmetic and authorization use real API tests.
export function deadlineFixture(state) {
  if (state.sourceRevoked) return null;
  const unavailable = !!state.deadlineMissing;
  return {
    state: unavailable ? "unavailable" : "available",
    reason: unavailable ? "deadline_calendar_coverage_unavailable" : null,
    official_publication_date: "2026-06-11",
    calculated_review_deadline: unavailable ? null : "2026-09-15",
    days_remaining: unavailable ? null : 1,
    as_of_date: "2026-09-14",
    timezone: "Europe/Zurich",
    exclusive_end: unavailable ? null : "2026-09-16T00:00:00+02:00",
    applicable_deadline_rule: {
      id: "a".repeat(64),
      citations: [
        {
          url: "https://example.invalid/rule",
          sha256: "b".repeat(64),
          section: "Synthetic reviewed rule",
        },
      ],
    },
    calendar: {
      id: "c".repeat(64),
      name: "Synthetic Basel calendar",
      jurisdiction: "Synthetic Basel",
      domicile_basis: "representative",
      citations: [],
    },
    calculation_trace: unavailable
      ? []
      : [
          { step: "publication", date: "2026-06-11" },
          { step: "calendar_months", date: "2026-09-11" },
          { step: "non_working_day", date: "2026-09-14" },
          { step: "deadline", date: "2026-09-15" },
        ],
    publication_evidence: {
      identifier: "SYNTHETIC-PUBLICATION",
      source_sha256: "d".repeat(64),
      source_document_sha256: "e".repeat(64),
    },
  };
}
