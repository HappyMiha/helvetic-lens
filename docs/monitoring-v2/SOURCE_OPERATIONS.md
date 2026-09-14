# Monitoring source operations — active feature scope, 14 September 2026

Scoped MV2-025/052 contribution: a complete platform-admin read-only overview at
`/admin/monitoring-sources`, linked from Platform Admin, covering all nine active
directions in four source packs. Reuse stored source-channel/poll/permission state;
never start collection, renew permissions or expose private monitor data to build
the page. C4 remains deferred and absent.

Show section/collector configuration separately from source permission records,
successful acquisition, provider timestamps, scheduled retry and errors. A current
permission record is not proof of operational coverage. Unknown timestamps remain
unknown; provider timestamps, successful receipt and pending request times must not
be substituted for each other. Expired/revoked/unconfigured access is actionable;
source failures and future clocks remain visible. Link each direction to its own
source/coverage workflow. No token, password, endpoint query, user location, source
payload, private interest or raw provider error text appears in the response.

Dependencies are existing nine-domain collectors and source records. External
credentials/rights are unnecessary to implement or test this diagnostic feature;
their absence is a displayed state. Do not claim all MV2-025/052 requirements:
bounded reprocessing, historical lag charts, AI fairness and external operational
acceptance remain independent work. This feature provides the missing complete
cross-domain source-state inspection journey.

Acceptance: authenticated platform-admin-only no-store API; explicit all-nine/four-
pack inventory; bounded metadata-only reads; no collection/network/writes; no private
or secret disclosure on errors; timestamp/expiry/future-clock/revocation and partial
channel cases; five-language, narrow/mobile/keyboard reader with loading/empty/error
and fresh reload/access-redaction behavior; meaningful API/browser tests, required
Ruff/build/format/backlog checks and main commit/push. Production activation remains
separate from local verification.

## Execution evidence — 14 September 2026

Implemented the route and Platform Admin entry, metadata-only endpoint and five-
language reader. Configuration switches never remove a direction from this inventory.
The existing public nine-direction navigation remains available to every user.
Source operations requires platform administrator access; it contains no private
monitor, credential, policy payload, source content or raw provider error text.
No migration, collection request, permission change or email send is introduced.

The snapshot uses fixed-size SQL aggregates. All retained channels contribute to
oldest/latest receipt, missing-success and error counts; provider clocks and next
requests remain separate. Commute feeds are inspected separately. Road/Commute
records are bound to the configured permission; replaced Auction/IP generations
cannot supply current success. IP shows the latest traversal of the selected
generation. A future provider/receipt clock remains explicitly invalid, including
when the last poll also failed. Global Tender success is unknown because its lease
does not record successful acquisition. Hazard still needs an approved acquisition
channel; enabling its configured switch alone does not supply one.

Local verification on the feature commit (the Git commit introducing this evidence):

- Expanded source-operations, administration and Monitoring Centre regression run:
  **34 passed**. Final changed-source and required backlog consistency run:
  **16 passed**, including transport receipt/publication/retry separation, future
  clocks, old permission isolation and enabled/disabled Hazard source configuration.
- Required `ruff check services/api deploy/release_manager.py` passed. New reader,
  route, five-language copy and updated section guide passed Prettier checks.
- Root `HELVETIC_LENS_CHECK_BUILD=source-operations npm run build` passed, including
  frontend lint/type/guide gates. Generated isolated-build path changes were removed.
- `scripts/check-source-operations-browser.mjs` passed: all nine directions/four
  packs, five locales, narrow layouts, keyboard reload, read failure/recovery,
  revoked/non-admin redaction and Platform Admin entry. Six full-document axe
  checkpoints reported zero violations and passed the prohibited-ARIA gate;
  incomplete/manual checks are not an accessibility certification. API/browser
  fixtures are synthetic and versioned with these tests; no live data was changed.

Reviewer: the implementing single agent; no independent human/native-language or
operational acceptance is claimed. MV2-025 and MV2-052 remain IN PROGRESS. Source
policy enforcement/reprocessing management, historical ingestion/processing/delivery
lag charts, alerts/renewal reminders, AI fairness and provider/user acceptance remain
separate work. A current permission *record* is not a full rights validation, and a
recent acquisition is not proof of monitor coverage or an all-clear result. Push
and production activation must be verified separately.
