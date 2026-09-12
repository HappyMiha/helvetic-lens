# Monitoring backlog progress contract

[MV2-073](../BACKLOG_MONITORING_V2.md#mv2-073) owns implementation and acceptance. This document defines derived progress metadata and presentation rules; the backlog remains the sole manually maintained task source.

## API contract


The persisted API shape is:

```json
{
  "monitoring_progress": {
    "schema_version": 1,
    "source_path": "BACKLOG_MONITORING_V2.md",
    "updated_at": "<UTC ISO timestamp>",
    "branch": "main",
    "latest": {
      "sha": "<successfully fetched full commit SHA or null>",
      "state": "available",
      "reason": null,
      "tasks": [
        {
          "id": "MV2-073",
          "title": "Show Monitoring backlog completion and deployment progress",
          "status": "IN PROGRESS"
        }
      ]
    },
    "deployed": {
      "sha": "<actual deployed full commit SHA or null>",
      "state": "unavailable",
      "reason": "No verified deployment exists yet.",
      "tasks": []
    }
  }
}
```

The example task array illustrates the field shape, not the complete backlog. An available snapshot contains its complete validated task set. The only allowed status strings are `PLANNED`, `READY`, `IN PROGRESS`, `VERIFYING`, `DONE`, `BLOCKED`, and `DEFERRED`. Snapshot state is `available` or `unavailable`; reason is null for available data and a short safe explanation otherwise. Empty unavailable arrays must not be passed through as an available zero-task backlog.

`updated_at` describes the persisted observation. Preserve exact SHAs and never label an old successful fetch as a newly fetched head. If fetching or reading the latest commit fails, expose that unavailability; the deployed snapshot may remain independently available. Do not expose raw command output, filesystem secrets or credentials as failure reasons.

Only the versioned source backlog is manually edited. Persisting a derived snapshot is acceptable: it is generated from an identified immutable blob and must not be maintained by hand. The API does not need manual total/completed counters; the UI derives them from `tasks`.

The deployment journal identifies the last verified release, not proof that it is currently running after every failure. A failed rollback or an interruption after startup makes the deployed snapshot unavailable, retaining its journal SHA and explaining that runtime identity is unconfirmed. A verified successful rollback or a failure before runtime changes may preserve the prior available snapshot. During an active deployment, label the deployed measure **Last verified release**; do not imply the candidate is already running or accepted. This uses existing run state and snapshot availability without adding API fields.

## Counting and display rules

For an available snapshot:

```text
required = tasks whose status is not DEFERRED
completed = required tasks whose status is DONE
remaining = required tasks whose status is not DONE
completion_percent = completed_count / required_count * 100
```

Display whole percentages with an approximation marker or explanatory label, alongside the exact completed/required count. If rounding would show 100% while required tasks remain, display `<100%` or cap the displayed rounded value at 99%; 100% is reserved for all required tasks DONE. An unexpected available snapshot with zero required tasks renders a percentage as not applicable, never as product completion. A missing snapshot renders as unavailable, never 0%.

Use two separately labelled completion measures:

- **Completed in Git:** latest DONE / latest required; **Remaining:** latest required minus latest DONE.
- **Already on this site:** deployed DONE / deployed required. Caption: “Recorded as DONE in this site's deployed backlog.”

When the latest backlog has 64 required tasks and the deployed backlog has 63, show those different denominators. Do not project newly added work into an older snapshot or call the denominator difference an error. If the application SHA equals the latest SHA, the two independently read snapshots should agree; disagreement should be treated as invalid metadata, not hidden by the UI.

Suggested note: **“Approximate backlog completion: required tasks count equally, including deployment work. Deferred items are excluded. This is not a measure of effort, time or Pollen Watch readiness.”** The frozen MVP's existing capabilities are outside this v2 backlog percentage.

For tasks completed but awaiting deployment, compare by ID only when both snapshots are available:

```text
latest DONE and the same ID is not DONE in the deployed snapshot
```

A task absent from an older deployed revision can appear in this list, explicitly labelled **Not present in this revision**. If a previously deployed DONE task is reopened in latest Git, it belongs to latest Remaining; preserve its deployed DONE status. Do not use `latest_completed - deployed_completed`, because that loses reopened and newly introduced tasks.

Pollen Watch always displays the explicit six IDs, with separate latest and deployed states. Only a DONE status contributes to that snapshot's six-task count. Completing MV2-072 or MV2-073 contributes to overall backlog completion but never to the Pollen count. A six-of-six display summarizes recorded task completion; acceptance evidence in MV2-071 remains the source for the actual user-testing readiness decision.

## Integration and evidence notes

- The initial feature commit may legitimately show zero completed required tasks even though the MVP application is running. Do not invent credit for existing MVP functionality or mark IN PROGRESS/VERIFYING as implemented.
- The first feature commit can include MV2-073 IN PROGRESS. Once its checks and live acceptance pass, a later backlog status commit records DONE and its evidence; deployment of that later commit updates the site's recorded completion. This avoids claiming completion before the feature is verified.
- Deployment pipeline percentage, such as the current API test run's progress, is a different measure. Keep it in the existing deployment-run view and do not mix it with the backlog percentage.
- Source activity belongs exclusively to the dedicated Monitoring branch. This feature does not change `main`, HappySnowman, grants status or customs deferral.
- This contract is not a machine-readable backlog. The collector consumes only the active Markdown backlog; all counters and snapshots are derived from its exact Git blobs.
