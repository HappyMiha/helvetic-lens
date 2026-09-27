# Dossier teams and workspace invitations

Status: DONE within the scoped workspace-collaboration release 1.11.
This is the workspace-collaboration part of dynamic dossier stage 2b. The full
[dynamic specification](DYNAMIC_DOSSIER_SPEC.md) remains IN PROGRESS.

Release 1.12 extends this historical workspace-collaboration baseline with
[private active monitoring](PRODUCT_PRIVATE_MONITORING.md); its acceptance is
tracked separately. The audience rules below describe release 1.11.

## Audience and compatibility

The creator explicitly enables team management on an existing or new dossier.
The migration leaves every dossier unmanaged, preserving existing author-private
drafts, shared activated dossiers and workspace administrator rights. Enabling
creates the first OWNER grant; the operational assignee remains a separate field.
No membership, publication, monitoring setting or email delivery is created by
an invitation. A departed creator's unmanaged dossier cannot be taken over by
another administrator through this feature.

A managed draft is readable by accepted dossier members only, including its
native monitoring-profile route, files, exports, workbench and workspace search.
Activation requires its owner, native workspace administrator authority, and an
explicit sharing confirmation once another colleague has accepted. Both clients
always disclose and ask to confirm the workspace audience before activation.
Activated dossiers retain their existing workspace audience, topics and feeds.
Removing an explicit role restores inherited workspace access there; it does not
make active monitoring private or remove existing downloads. This boundary is
visible beside the roster and in the guide.

## Roles and invitation workflow

- OWNER manages accepted members, invitations and explicit publication, and can
  hand ownership to another accepted member. The last active owner is protected.
- EDITOR edits dossier work and setup, reviews sources and starts/controls research.
- CONTRIBUTOR adds comments, URLs, files, corrections and research requests;
  contribution analysis uses the same private coordinator. They can control their
  own contribution investigations, while other investigations require EDITOR.
- VIEWER reads retained evidence, activity and exports without write permissions.

Explicit roles override inherited workspace write rights. Changes to shared topic
monitoring/page watches still require native workspace administrator authority;
this also applies through alternate native topic/history/review endpoints.

Owners select an existing active workspace account. The seven-day invitation is
bound to its recipient, product, dossier and organization. Its UUID is a reference,
not bearer authorization. The recipient accepts explicitly from the in-app inbox
or copied link using the invited account/workspace. No email is sent. Acceptance
never creates an organization membership or overwrites a subsequently changed
role. Wrong-account/product/tenant, expired, revoked and former-owner invitations
fail. Pending invitations from a demoted owner are revoked. At most 100 accepted
members and 100 pending invitations are permitted per dossier; the inbox is paged.

Both clients expose the roster, role descriptions, pending invitations, revocation,
explicit owner promotion and current audience. Drafts open directly as research
dossiers with a separate Monitoring setup action. The setup wizard can save and
open research without activating shared monitoring. Ownership transfer is: promote
an accepted colleague, then reduce/remove the former owner's role.

## Native boundaries and lifecycle

Migration `fcc495bef124` adds the explicit-management flag, access revision and two
contained tables. Composite foreign keys bind memberships/invitations to both the
dossier organization and a real native workspace membership. API mutations use the
existing organization lock, current account/session checks, CSRF and expected team
revision. Invite retries retain their request identity without duplicate grants.
HTTP action context selects the required capability; it never supplies a role.
Authorization always reads current database state. Workers pass an explicit
capability, recheck before and after each operation and pause after revocation;
late model findings cannot become claims. SSE keeps its existing live access checks.

The same SQL draft visibility predicate applies before paging/counts in both native
profile and product lists, workbench and workspace search. Product authorization
also guards original downloads, exports, saved evidence and contribution routes.
The public snapshot remains a separate explicit projection. No private draft
queries or annotations enter shared topics, feeds or digest contexts before the
owner's explicit activation. Independently shared source documents remain shared.

Native membership removal and account erasure protect last ownership. After
handover, removing the original creator retains the collaborative draft and its
original files; author references become former-member references. A transferred
draft belonging only to its remaining owner is included in that owner's authorized
erasure even when the original creator has already departed. Unrelated workspace
records and colleagues' evidence are retained. Account deactivation does not give
another user automatic access or ownership.

## Acceptance and remaining work

Local acceptance is complete: 30 final team/provenance cases pass after the new
account/session locking contract, alongside 118 passing affected native cases.
Earlier broad coverage exercised 381 cases with two conditional skips; all six
failures were addressed and retested in the focused runs. Both clients pass 83
tests each, source lint, strict type checking and final production builds. Each
build contains 121 files; configured provider secrets were absent from both.
Exact production acceptance passes on both custom domains: 63 HTTP/auth/gateway
checks and 39 exact emitted JS/CSS hashes each. Native `git-034f3a8344f2` activated
at 17:12:24 UTC. Pharma and Loyer published Sites version 14 at 17:11:57 and
17:12:33 UTC; both GitHub CI runs succeeded. All 25 native module hashes match,
migration `fcc495bef124` and the scoped foreign keys are present. API and CPU
worker health pass; the AI worker is running without a configured Docker health
check. Its local extraction fixture passes and local Laya is healthy.
[Exact release receipt](product-releases/2026-09-27-1.11.0.json). Automated
fixtures exercise native HTTP/database/job paths without reading production user
records or making paid provider calls. Browser interaction, whole-page visual QA,
professional factual-quality acceptance and a complete dynamic-spec DoD are not
claimed.

Still open: members-only active monitoring with scoped native topic/feed/digest
and derived-context access, invitations outside the current organization without
broad workspace grants, living public dossiers with the same coordinator, cross-run
claim reconciliation, automatic material-change reopening and native-platform
visual migration. This release changes no provider setup or source approval.
