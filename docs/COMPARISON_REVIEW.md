# Decision-ready comparison review

The comparison screen has two independent layers. The deterministic layer is available immediately and remains the audit source of truth. It groups legal-unit changes into material or uncertain clusters, counts added/removed, moved/renumbered, formatting-only, and needs-review changes, and keeps the complete passage and word diff under **All exact changes**.

The current Impact report is a saved, validated interpretation of that evidence. It is organized as **What changed**, **Why it may matter**, and **Review plan**. Material cards show the before and after units, evidence grade, organization applicability, supported dates or explicit unknowns, assumptions, citations, and a direct jump to the exact diff. The provenance block records versions, generation time, profile revision, model/runtime, prompt revision, output locale, coverage, call budget, and latency. Earlier reports remain in AI history.

Impact inference runs as a PostgreSQL-backed `impact_analysis` job. The API returns the current job with the comparison, so navigation and refresh recover the same state. The worker persists preparation, evidence-group progress, and validation separately. The UI renders queued position when known, real `n/N` group progress, validating, ready, limited, failed, and cancelled states. A failed rerun leaves the last valid report visible. Cancellation and resubmission reuse the durable job safely.

Suggested actions are proposals for human review. Organization administrators can append an accepted, assigned, scheduled, dismissed, or not-applicable decision. Every event retains organization, saved report, stable action key, actor, time, assignee/date where relevant, and rationale. The latest event is the current workflow state; the complete decision history remains inspectable. Decisions never modify the comparison, passages, citations, or AI report.

Comparison classifications, evidence states, job outcomes, and decision states always include text labels and do not rely on colour. This surface recognizes the five product language families (`de`, `fr`, `it`, `rm`, `en`) for its deterministic summary and stable state labels; the complete product catalogue and explicit persisted selector remain tracked by HL-057.


## Responsive comparison focus contract (HL-097, 5 September 2026)

The companion's existing 1350 px breakpoint now controls a native HTML dialog.
On phones/tablets `showModal()` isolates the rest of the page, including background
navigation and Marvin, while the panel keeps a localized accessible name. Tab and
Shift+Tab stay in visible enabled controls; Escape, close and tablet backdrop clicks
return focus and unlock document/main scrolling. A citation intentionally exits to
the exact evidence row. Closing removes `task` from the URL instead of leaving a
stale open-task deep link.

On a wide desktop the same dialog is open **nonmodally** within the normal layout.
Its child tree never remounts merely because the viewport crosses the breakpoint;
unsent Ask text and active job observation survive. Opening another comparison is
a separate document navigation, not a promise of persistent cross-document drafts.

Run `npm run build` then `npm run check:comparison:browser` to exercise the actual
compiled route with the committed synthetic fixture and intercepted APIs. The
checks are required and fail for missing comparison/citation content. They cover
five locales, overlay widths 390/768/1024 and desktop transitions to 1440 px.
Global/nested overlay interactions and physical assistive/mobile/browser sampling
remain separate gates, not implied by this Chromium regression.
