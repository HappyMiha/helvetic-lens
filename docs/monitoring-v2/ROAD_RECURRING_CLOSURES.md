# Recurring Road Watch closures — 15 September 2026

Scope: MV2-040/041, planned repeated closures in the existing C3 workflow.
The implemented source-to-private-history scenario supports explicit-offset
DATEX II 2.2 recurring periods. It does not establish live ASTRA permission,
licensed corridor coverage, source deployment activation or human acceptance.
Both parent tasks remain IN PROGRESS. All nine categories stay visible; C4 and
grants remain deferred.

## Source semantics and boundaries

The inspected [Swiss DATEX II 2.2.3 schema archive](https://opentransportdata.swiss/wp-content/uploads/2025/03/DATEXIISchema_2_2_3-with-definitions.zip)
has SHA-256 `7bc85136799f28fa106265afcce08425e24988a05dfa58d93737389e6dc35d07`.
It was read from the previously downloaded local public archive and its hash
rechecked. Original source XML/XSD remains outside Git. The Period,
TimePeriodByHour, DayWeekMonth, OverallPeriod and enum definitions establish
repeated daily intervals, day/week/month intersection and overriding exceptions.
The version-2 fifth week denotes the final one to three days of a month; it is
not the newer calendar-week model. DATEX's [validity documentation](https://docs.datex2.eu/levels/mastering/common/validity/)
also explains that a night interval's applicable day belongs to its start.
The implementation uses the pinned version-2 structure, not version-3 selectors.

The decoder retains exact daily microseconds and explicit fixed UTC offsets.
Selectors within one dimension form alternatives; day/week/month dimensions
intersect. Repeated period alternatives are merged before exception subtraction.
Night windows preserve their start-day identity across midnight. Overall and
per-period bounds clip generated intervals. Date and offset changes are material;
reordered or duplicate equivalent declarations are not.

An offset in a source time is not an IANA time zone. The code never infers
Europe/Zurich from an overall timestamp or changes a fixed offset at DST.
Unqualified clocks, calendar-only periods without an explicit daily clock,
mixed start/end offsets, ambiguous equal start/end times and unsupported
extensions remain unknown. Malformed clocks, unknown enum values, duplicate
scalars and excessive selector counts fail decoding. Unsupported schedules
cannot establish a closure or a safe route. Existing source active/suspended/
overrunning overrides retain their original precedence; no interval is invented.

## End-to-end result

A retained Sunday 10:01–10:03 UTC closure first appears planned, becomes active
at 10:01 and points to the next Sunday's planned interval at 10:03. The private
development ID remains stable. The earlier reviewed version is preserved and
each material transition adds a version; repeat checks inside the same window
add none. Ending one recurrence does not emit a physical-road-clearance claim.
Current/future timing flows through the existing reader, Today and consented
email eligibility. No real email was sent in verification.

The five-language reader identifies an evaluated recurring interval and displays
it in Swiss local time. Both current and historical selected versions use the
same fact reader. Expired/revoked access and other-owner reads remain denied;
blocked source responses remove the displayed interval. Existing topology,
source freshness, retention, consent and owner gates remain required.

## Bounded work and compatibility

Periods allow at most 16 daily clauses and 16 calendar selectors, retaining the
existing limit of 128 valid and 128 exception periods. Evaluation searches at
most 370 days behind and ahead of its clock, spends at most 8,192 daily steps
per record and limits generated/combined intervals to 4,096. A shared 100,000-step
budget and temporal-result cache bound a private monitor pass across corridors.
Merged exception subtraction uses advancing cursors rather than a cross-product.
A budget exhaustion, unknown far-future interval or interval clipped by the
search horizon returns unknown; it cannot invent an end/start or an expiry.

Empty new recurrence fields are excluded from canonical serialization and
semantic hashes. A synthetic fixture produced by committed parser `f2d54cc`
proves that the previous bytes, record hash and situation hash remain readable
without rewriting retained evidence or a database migration.

## Verification

- 139 decoder/recurrence/evaluation/reconciliation checks passed.
- 110 source-storage/private-worker/delivery/Today checks passed, including
  compatibility and the planned→active→next-window private workflow.
- After linear exception subtraction, 73 final affected checks passed.
- The root isolated frontend build passed with
  `HELVETIC_LENS_CHECK_BUILD=road-recurring`; generated Next files were restored.
- 12 full-document axe checkpoints passed across five locales and 390/1440px
  widths, active/planned presentation and denied-source redaction. Localized
  Swiss timestamps were verified. Other incomplete axe findings stay in JSON;
  this is not an accessibility certification. The actual interval was visually
  inspected at 390px.

Evidence logs: `.tmp/road-recurring-core.log`,
`.tmp/road-recurring-integrated.log`, `.tmp/road-recurring-final.log`,
`.tmp/road-recurring-build.log`, `.tmp/road-recurring-browser-final.log`;
`test-results/accessibility/road-recurring.json` and
`test-results/road-recurring-mobile.png`. Tests use synthetic private accounts,
source grants/topology and SMTP; browser API responses are intercepted fixtures.
No production source data or credentials are included in tests or Git.

Final exact Ruff, scoped Prettier, browser syntax, backlog integrity (1 test)
and diff checks passed. The additional mapping guard is recorded below.
Production activation remains separate.

Only verified matching corridors spend the shared expansion budget. The final
mixed opposite/unverified mapping fixtures exercise the worker without calling
the temporal evaluator; known source-readiness requirements remain in force.
At final authenticated release inspection, production was still `d961ebd54998`
with `7fd0c80a2686` recorded as deploying. No active deployment was restarted.

Final compatibility/private-workflow/mapping checks: **4 passed** in 6.54 seconds,
recorded in `.tmp/road-recurring-mapping-final.log`. Required backlog and final
private workflow checks also passed (3) in `.tmp/road-recurring-publication.log`.
