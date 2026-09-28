# Research reader repair — 1.36

Status: DONE within the reproduced client repair and verified publication scope.
Scope was recorded before code; human usability acceptance remains OPEN.

The owner supplied two Legal mobile screenshots showing a generic research read
failure and repeated saved-evidence forms. The shared Pharma client has the same
component structure. This repair contributes to MV2-002/020/023/024 without closing
those parent tasks or full architecture / professional acceptance.

## Diagnosis

EvidenceSearch and ClaimEvolution use the same sibling React key. Conditional
error/loading/history siblings force keyed reconciliation; duplicate keys can
leave orphan search UI. Prove the failure with the actual React reconciler before
changing keys, then require one retained instance across state transitions.

The first screenshot at 18:42 Zurich overlaps release 1.35's API and tunnel pause
(16:41:38–16:43:54 UTC). The deploy manager explicitly stops both during consistent
backup. A non-JSON upstream error loses its status in the current API helper.
This explains a possible failure path, not the exact unrecorded user's request.

## Acceptance and boundaries

- One search and one changes-over-time block across load/failure/recovery and
  repeated refresh. Preserve typed query state within the same dossier/user.
- Distinguish transient HTTP, connectivity, sign-in and access errors. Do not
  replay writes, searches, model requests or actions automatically.
- A retry reloads saved research and clears the error on success; failed reads
  never masquerade as empty or safe evidence. Access boundaries remain intact.
- Full affected client tests, lint, types and production builds; required backlog
  invariant; immediate main pushes and both existing public Sites deployments.
- Verify deployed assets and anonymous authorization boundaries. No private
  production dossiers, paid probes or browser inspection required.

Release activation and user acceptance remain separate until evidenced below.

## Verification and publication

The new reconciliation case failed on the original source (two host search
inputs instead of one). With distinct component keys it passes repeated failures
and three reloads, retains the typed question, produces one search and one history
reader, and emits no duplicate-key warnings. The actual parent is rendered by
React 19.2.6; stateful child doubles isolate the independent readers.

Seven API cases exercise gateway HTML/5xx, 401/403/404/408/429, native detail,
interrupted writes without replay and retained CSRF/request identity, network and
abort failures, malformed successful payloads and valid/empty success. Both
clients passed all 197 tests, lint, types and exact production builds. The required
backlog invariant passed. No core API behavior changed in this repair.

Both clients were immediately pushed to their GitHub main and existing Sites
source branches, then published as existing public Sites version 38. Canonical
Legal and Pharma origins each passed 33 public/access checks and 47 exact SHA-256
asset checks; compiled bundles contain both distinct keys and the recovery UI.

- Pharma: `7d25bca75943130b9907bf1685aeeab05f669186`; active 2026-09-28T17:00:25.847659+00:00.

- Legal: `f95f0fb1a24eb7f61cee9443fbe26a16562723c2`; active 2026-09-28T16:59:53.881427+00:00.

See the [frozen publication receipt](product-releases/2026-09-28-1.36-research-repair.json).
The final Core documentation commit's normal activation is observed in the parent
workspace checkpoint; it does not require another unchanged client publication.

## Remaining boundary

Core releases still stop API and tunnel while a consistent backup is made. The
client now explains temporary unavailability; zero-downtime native deployment is
not claimed. A previously open tab must reload to adopt the repaired component
identity and discard any existing orphan forms. No authenticated production
record or browser was used for verification. Full architecture, live professional
quality and human acceptance remain OPEN.
