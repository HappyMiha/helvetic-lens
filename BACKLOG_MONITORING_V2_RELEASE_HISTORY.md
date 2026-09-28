# Completed Monitoring release commentary

Archived verbatim from the active backlog on 28 September 2026 to keep its
validated 512 KiB reader bound. The active queue and task acceptance remain in
[BACKLOG_MONITORING_V2.md](BACKLOG_MONITORING_V2.md); these are historical results.

## Research continuation — 1.37 conservative local rejection

DONE within uncertainty repair, evaluation and verified publication; recorded before code. MV2-002/020/023/051: preserve uncertain
candidate decisions, develop a versioned local Laya rejection guard, and measure
its extra review burden against reduced false exclusion. Existing provider,
worker, cumulative budgets and public NoMIRACL cache only; no private dossiers or
paid calls. Development uses dev hash offsets 12–13, validation uses test offsets
42–43, two questions per relevance subset/language (EN/DE/FR), all judged
candidates; verify no overlap with prior project query IDs. Development is capped at 121 and validation at 120 local calls; each has
240 seconds / 12 seconds per call (total 241 / 480). This pre-inference size
correction retains one development query with 11 candidates; no labels/results
were used to alter sample selection.
Raw source passages stay outside Git. Threshold candidates are fixed before calls:
0.50, 0.65, 0.80, 0.90, 0.95. Only low-score unrelated → uncertain is permitted;
never auto-admit uncertain records or label confidence as accuracy.
Selection: zero development positive exclusions, retain at least half the baseline
negative exclusions, extra uncertainty <=20% of all cases, retain most negative
exclusions, then lowest threshold. If no candidate qualifies, no promotion.
Freeze selection before opening validation labels/results. Validation promotion:
complete matched inputs/model, positive exclusions <= baseline and <=5% of positive
labels, retain >=50% of baseline negative exclusions, extra uncertainty <=20%,
at least one low-score rejection deferred. A failure prevents production promotion.
Independently preserve final uncertain review events instead of calling them rejected.
Acceptance: deterministic privacy/budget/uncertainty tests; frozen development and
fresh validation receipts; exact API/script lint, affected tests, native publication.
Clients stay at verified 1.36 unless a user-visible reader change is required.
No threshold passed development; validation stays unopened and no guard is
promoted. Worker activity now distinguishes uncertain/unavailable from rejected;
raw provider scores and policy version are retained. 65 affected cases pass.
Core git-09ab8bcfff5f is verified live; both clients retain verified 1.36 assets.
Native health, 25 module hashes, five containers, nine routes and schema passed.
See [scope](docs/PRODUCT_RESEARCH_GATE_POLICY.md). Parents and professional quality OPEN.

