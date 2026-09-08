# Saved Impact matrix

The `/matrix` page is a read-only organization view of saved Impact reports. It does not call a model, create a second assessment, or infer that a missing assessment means low impact.

Rows are active monitored laws. Columns are the current company-profile business areas. Every row points to the latest saved comparison for that law, and every assessed cell points back to that same comparison and its evidence.

## Cell states

- `assessed`: a current, validated Impact report explicitly names the business area and contains a valid high, medium, or low rating.
- `unknown`: a current report exists but does not assess that business area. No rating is invented.
- `stale`: the last valid report was produced with an earlier company profile, prompt, model/runtime setting, or output locale. The old value may be shown as historical context but is not presented as current.
- `unanalysed`: no saved valid Impact report exists for the latest comparison.
- `failed`: the latest analysis attempt failed and no earlier valid report can be shown.

The matrix reuses the same cache fingerprint as comparison Impact analysis. A profile revision therefore invalidates displayed values consistently with the comparison page. Changing the interface language requests matching saved output-locale results and does not silently reuse an assessment in another language.

## Scope and access

The API reads through the active organization-scoped database session. It returns active watches, their latest comparisons, and existing analysis records only for that organization. Viewers can inspect the matrix; mutations continue to use the existing comparison, profile, and monitoring permissions.

The feature does not change scanning, version creation, comparison, or AI-analysis workflows. Users review or rerun an assessment from the linked comparison page.

## Saved-history reads — HL-099, 8 September 2026

The reader no longer materializes every historical comparison and every analysis
attempt. It processes active laws in batches of 50:

1. Rank visible comparison IDs by saved timestamp and ID in SQL; load only the
   newest comparison per law. Its full diff still supplies the existing cache
   fingerprint, so changing evidence does not silently preserve an obsolete report.
2. Rank attempt metadata per selected comparison: current successful JSON object,
   previous successful JSON object, then other attempts. Select the newest attempt
   separately in the same query, retaining a later failure beside a valid report.
3. Read only the selected successful result and its timestamp/status/cache key.
   Archived plans, provenance and coverage are never transferred for this matrix.
   An absent or scalar/list/null result is not presented as an assessed report.

This searches the complete accessible history without a last-N cutoff. A new
comparison never borrows the older comparison's report. Equal timestamps use ID
ordering. Profile, active watch, law, comparison and analysis scope are explicit,
including privileged sessions; watch and ownership constraints are repeated during
result loading. The loaded cache key is checked again before labelling a result
current. This is not a transactional snapshot across the whole matrix: concurrent
edits can affect subsequent batches or require a refresh.

The populated HTTP tests observe nine SELECTs for one law (including three
request-configuration reads), versus thirteen for 51 laws. Only one Comparison
body per law is hydrated; no Analysis ORM objects are loaded. The large-history
fixture includes 151 archived comparisons and 1,001 later failed AI attempts.
The response, severity ordering, totals, current/stale/failed/unknown states and
comparison links remain compatible, with no read-time inference.

**Remaining:** active-watch enumeration, the complete matrix response and Python
sorting still scale with the number of monitored documents. Each selected diff
and result can be large. SQL window sorting/JSON inspection still costs work over
eligible metadata; this is not an index/planner or 100-user capacity certification.
Complete UI pagination/projections and target-host overlap measurements remain
open in HL-099. No migration, new persisted derived state, frontend change or
production deployment accompanies this reader change.
