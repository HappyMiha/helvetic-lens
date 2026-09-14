# Related developments — MV2-036

## Whole-feature scope — 14 September 2026

Deliver a private location-story workflow spanning retained Hazard, River and
Road developments. A story provides one entry point while preserving every
authority identifier, exact version, source reader and independent review state.
An association is a possible relationship, never a claim of common cause or an
all-clear. Users can inspect, group and split related events without sending
notifications or transferring decisions. The feature stays local until its
complete API, persistence, source adapters, user interface and checks are ready.

Use current domain readers and ownership/organization contracts. Recheck actual
source permissions, exact evidence hashes, expiry, configuration and geography
on every read. A denied member must not become a copied cached source payload.
Group records store references and their association provenance, not originals.

### Geographic and time contract

Hazard already retains a verified boundary identity. River stations have their
own catalogue identity. Road uses reviewed TMC topology/corridor identities, but
the current topology has no latitude/longitude or municipality mapping. Road
names, timestamps, code ordering and an unverified user-entered location cannot
bridge these namespaces. Do not change old topology fingerprints to add geometry.

A separately versioned, permitted geographic binding must connect the exact
source feature to a common reviewed area and boundary version/hash. Its accepted
scope, validity interval and evidence identity must remain auditable. Missing,
expired, revoked, changed or incompatible bindings leave a relationship unknown.
Common administrative coverage is possible co-location, not proof of causation.
Two events need overlapping explicit validity intervals as well as the verified
place match. A hydrological observation can instead be an explicit point in time
inside the other event's interval; this does not extend the measurement's state
until a later time. Detection time cannot replace an unknown source validity.
Actual source cross-references, where available, retain their namespaces/IDs.

### Required delivered outcome

- Three-source story and candidate inspection with verified location/time reasons.
  An unrelated nearby place and time-only coincidence do not create a match.
- Durable owner-private grouping, version conflicts, idempotent submissions,
  reversible splits and an audit trail. Viewers can read only their permitted
  records; unrelated owners/workspaces cannot be inferred through links/cursors.
- Exact source evidence and separate current/historical/unavailable states.
  A correction requires refreshed association evidence; a withdrawn warning
  cannot silently resolve River or Road. No review/decision/delivery transfer.
- Real domain adapters and an operational path for reviewed geographic bindings,
  with no automatic source permission or invented road geometry. Operator access
  and permitted live three-source evidence remain explicit acceptance gates.
- An accessible five-language interface with empty/error/revocation states,
  exact source links, keyboard/mobile operation and correction/split recovery.
- Three-source API/workflow fixtures, nearby/unrelated negatives, revocation,
  correction/split replay, durable concurrency and existing domain regressions;
  required lint/backlog/build/browser checks before commit and immediate push.

Dependencies: existing C1/C6/C3 source/version/private-read contracts provide
implementation interfaces while their live source and human gates remain open.
The complete MV2-036 criteria are retained; no scoped implementation closes the
parent or substitutes for real live source verification. C4 remains deferred.

## Delivered implementation and verification — 14 September 2026

The complete code feature is `/related-developments`, linked directly from the
Monitoring centre and shared desktop/mobile navigation. It has no rollout flag.
All nine existing directions remain visible; this shared view is not a tenth
direction and does not reactivate C4. Source rights and readiness remain explicit.

Users can inspect candidates from Hazard, River and Road, check every selected
pair, save an owner-private group, remove/re-add members, read immutable history,
reuse historical membership in a new checked version, archive/restore a group,
and load current source references after corrections. A split removes references
from the group; original events remain in their source section and history keeps
the prior membership. No source review, delivery, consent or source job is changed.
Groups remain separate from any source's status and do not suppress alerts.

The API at `/api/related-developments` uses the existing authentication, workspace
and CSRF middleware. Successful and denied/error responses are `no-store`.
Membership, owner, current source display/matching rights, exact evidence and
geography are rechecked. Bounded cursor pages cannot use foreign owners' anchors.
Writes use explicit versions and idempotency keys; immutable revisions retain
references and association provenance rather than source payload copies.

Real domain adapters call the retained CAP reader, current River condition and
measurement readers, and Road version/current-source readers. River observations
are explicit instants; missing Road end times remain unknown. Old River samples
changed by a correction cannot assert a current relationship. New River changes
refresh the exact UUID/sequence. Changed Road geometry invalidates old location
proof even when its material event sequence did not change. A cancelled warning
does not resolve the water or road record. Missing source access removes source
metadata and links while the owner's saved reference remains visible.

The additive migration `3c19fa035bde` follows `2b08e9a24acd`; it creates reviewed
bindings and two private story tables included in the central organization policy.
Existing topology fingerprints and source tables are unchanged.

### Geographic review operations

A platform administrator opens the candidate's **Review geographic binding**
form. **Inspect source feature** rechecks source rights and displays its exact
permitted station coordinates, CAP area geometry, or TMC location/mapping
descriptor. This operator-only descriptor is not copied into group records or
ordinary candidate responses. The operator verifies the feature against allowed
geographic evidence, selects a BFS municipality from the installed current
boundary edition, records the evidence SHA-256 and expiry, explicitly attests the
review, then saves. No inferred geometry, permission grant or source activation
is performed. Retain the referenced geographic evidence under its source rights.

Every association rechecks binding expiry/revocation, exact feature/geo revision
and current municipality boundary version/hash. Missing editions or ambiguous
simultaneous bindings remain unknown. Inspect shows existing binding IDs so an
operator can revoke an obsolete review before replacement. Only current BFS
municipalities are operationally supported; hazard-area namespaces fail closed.
No production geographic review or source approval was created for this release.

### Acceptance evidence

- Contract, migration, repository, real-reader, HTTP and backlog suite: **34 passed**
  (45.16 seconds), before the final operator-only descriptor assertion. Covers
  three-source grouping, unrelated places, time-only negatives, correction and
  cancellation, split/rejoin/history, request replay, ownership, viewer/CSRF,
  revoked membership/rights, malformed evidence and retained-data migration.
- Affected boundary, Hazard event, Road Today and River condition/delivery
  regressions: **79 passed** (74.41 seconds), including the new current-municipality
  identity check and expired/invalid boundary selection.
- Required root `npm run build`: passed, including i18n, shell, resource, report,
  contextual help and production Next/TypeScript gates. Isolated output:
  `HELVETIC_LENS_CHECK_BUILD=related`.
- `scripts/check-related-browser.mjs`: passed on the built product with synthetic
  HTTP fixtures in a disposable browser. Five locales, mobile overflow, private
  create/split/rejoin/history/archive/restore, refreshed references, viewer access,
  source/permission and page-return redaction, keyboard focus and explicit
  operator review form. **13 full-document axe checkpoints**, zero reported
  violations; other incomplete findings remain recorded, not certified accessible.
  JSON: `test-results/accessibility/related-developments.json` (local artifact).
- Final operator-descriptor privacy, real-adapter, HTTP and backlog checks:
  **9 passed** (39.67 seconds). Explicit official-danger observation (rather than
  deriving danger from water height): **1 passed** (5.64 seconds).
- Exact `ruff check services/api deploy/release_manager.py`: passed. No broad
  production test or live send is implied.

Reviewer: one development agent. Fixture sources are synthetic CAP/FOEN/DATEX
examples and explicitly synthetic geometry, not official alerts or live licences.
The UI is translated into de-CH/fr-CH/it-CH/rm-CH/en-CH; retained source identities
and source status codes preserve their original representation.

### Release and remaining acceptance

The feature is ready for code publication after its recorded checks. Successful
publication is separate from activation on **helveticlens.ch / HappySnowman**.
MV2-036 remains **IN PROGRESS** until exact release activation and permitted live
three-source/operator and human usefulness checks are recorded. The separate
Monitoring hostname is retired and must not be restarted. No licence, API key,
geographic review, email consent or human acceptance is implied by this code.
