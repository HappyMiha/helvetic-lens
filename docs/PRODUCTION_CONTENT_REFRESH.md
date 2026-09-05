# Controlled production content refresh — 5 September 2026

Operator: `HappySnowman`. Task branch: `codex/HappySnowman/production-data-refresh`.
Initial application release: `7566992279d83e610866923c77426922ba7c8ce7`.
This was an explicitly requested production **data** operation, not an application deployment.

## Scope and recovery

The production database had two users, both members of the same workspace, plus
the empty legacy workspace. Both users, passwords, roles, organizations,
memberships, invitations, sessions, account tokens, security/administrative audits,
provider credentials and prompt settings were preserved. The reset checked a
SHA-256 digest of all protected records before and after deletion inside the same
transaction. It did not drop or truncate schema, run migrations, or delete files.

Pre-refresh backup: `20260905T070759Z` on the dedicated backup disk. Its file
checksums and PostgreSQL custom archive were verified. Use the normal production
restore procedure, with writers stopped, if recovery is necessary. Restoring the
whole backup also restores accounts to that point in time; do not overwrite later
account activity casually. Raw old artifacts remain subject to normal orphan
retention and the protected backup; they are no longer exposed as old library rows.
Post-refresh backup: `20260905T071959Z`.

Deleted content included 10 old monitored documents, 18 extracted versions,
19 comparisons, 3 AI reports, 2 Ask answers, old chats/drafts and scan history,
the old shared connector corpus (787 works / 1,600 events), and associated
diagnostic/job records. The exact content-table allowlist is in the operator script.

The host deployment lock was held during the data operation. Public web access,
scheduler and workers were stopped for the backup/reset/initial seed window and
then restarted. The existing cron auto-deployer was not changed.

## Replacement content

Ten official monitored sources cover federal data protection (LPD and OPDa),
information security (LSIn), Ticino personal-data protection, Ticino innovation
law and startup investment guidance, Lugano's 2025–2030 digital strategy, Ticino's
digital strategy, federal AI regulatory preparatory work, and cyber incident
notification guidance. Strategies/preparatory work are explicitly not labelled
as enacted law. A newly monitored snapshot is not labelled as a new enactment.

Thirteen original artifacts passed fresh extraction. Nine PDFs use
`native-pdfminer-v1`; the remaining four are official HTML. Six additional Fedlex
HTML artifacts provide cleaner legal comparisons without PDF pagination noise.
All PDF originals remain available. The three primary historical pairs are:

| Work | Historical version | Current official version returned by Fedlex |
| --- | --- | --- |
| [LPD](https://fedlex.admin.ch/eli/cc/2022/491/it) | 2023-09-01 | 2025-07-07 |
| [OPDa](https://fedlex.admin.ch/eli/cc/2022/568/it) | 2025-04-01 | 2025-12-01 |
| [LSIn](https://fedlex.admin.ch/eli/cc/2022/232/it) | 2024-01-01 | 2025-10-01 |

Five topics cover AI governance, privacy engineering, cybersecurity, startup
incentives and Lugano/Ticino digital public services. Five source packs are active,
including an explicitly bounded curated official selection. Three native source
listing pages support discovery (Lugano, Ticino innovation law, federal AI work).
The company profile retains its factual description and uses four business areas
to reduce matrix width. No user profile was edited.

Ten current-feed streams are scheduled: Fedlex DE/FR/IT RSS and consultations,
Parliament recent/active, federal notices IT/EN, and FINMA IT/EN. Broad historical
catalogue crawls and unrelated court feeds are paused for this curated workspace.
This is not exhaustive coverage. The native fetching provider needs no API key;
no paid/cloud provider account or credential was invented or purchased.

## Validation and known limitations

- The exact initial seed/reset was rehearsed in an isolated SQLite database using
  the fetched official artifacts, preserving all test accounts.
- `scripts/test_content_refresh.py` checks the allowlist, protected-record identity,
  changed tenant/user refusal, active-job refusal and transaction rollback.
- All 19 stored artifact checksums and 186 citation references in six generated
  reports were checked against saved source passages during the operation.
- The three primary matrix rows have current saved reports. Seven single-version
  reference documents correctly remain unanalysed; historical evidence was not
  fabricated to fill those cells.
- Both GTX 1080 GPUs were observed active; report provenance confirms local
  `apertus-8b-q4km`. No source/company evidence was sent to a cloud model.
- **Current local-AI limitation:** `structured_completion` reduces local impact
  generation to `LocalImpactSignal` (citation rows plus impact), and
  `local_impact_synthesis` cannot provide substantive generated review actions.
  The six completed reports therefore have empty action lists and generic
  applicability summaries. Successful inference is not substantive legal review.
  A non-persistent full-protocol probe against the same local endpoint failed
  structured-output validation; production model settings were left unchanged.
  This needs a separately tested application fix, not fabricated seed answers.
- Fedlex RSS streams each reported one empty-extraction item; three other native
  source listings verified 4, 3 and 5 documents, respectively. Lugano's listing
  retained two failed candidates. These failures remain visible, not hidden.
- Public readiness passed. Authenticated UI visual verification was not available
  in the agent's browser session; backend matrix/topic/evidence reads were checked.

## Concurrent integration checkpoint

During final verification, HappyDucky02 published
`04040a6ffc2eb864ae6092ea71a53862e4f5c327` (HL-091). The existing auto-deployer
installed it successfully; this task did not trigger a separate application
deployment or overwrite that work. The operator branch fast-forwarded to that
commit. Seven content-refresh safety tests and sixteen selected-evidence tests
passed together against the combined checkout.

HL-091 changes the report schema to `impact-report-v3` and labels local results
`selected_evidence` / `not_assessed`, with unknown impact/applicability rather than
unjustified High values. It does **not** add generated explanations or actions.
The three primary HTML comparisons were submitted again after this deployment;
old v2 reports are history, not current assessments. The preserved original PDF
comparisons are optional alternative-format history, not the primary matrix rows.

## Operator tool boundary

`scripts/refresh_production_content.py` is not an HTTP endpoint, scheduler task,
migration or automatic seeder. Never run `reset` as part of ordinary deployment.
It deliberately requires an organization, prepared artifact cache, expected user
count, backup reference and explicit reset flag. It refuses additional member
tenants or unfinished jobs. Backup verification and deployment/writer locking are
operator prerequisites, not claims inferred from a supplied backup ID.

Commands are separate checkpoints: `prepare`, `rehearse`, `reset`, `seed`,
`refine-federal`, `sources`, `schedules`, `analyse`, `verify`. `seed` requires empty
monitored content and commits individual items; on failure inspect/continue
carefully or restore the verified backup — do not blindly repeat `reset`.
