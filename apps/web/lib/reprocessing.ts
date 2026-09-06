import type { Job } from "./types";

export type ReprocessingResult = {
  processed: number;
  eligible: number;
  changed: number;
  retained: number;
  rejected: number;
  skipped: number;
  batches: number;
  removed_since_capture?: number;
  rule_revision?: string;
  captured_at?: string;
  status: "pending" | "complete" | "superseded";
  has_more: boolean;
  dry_run?: boolean;
  examples: Array<{
    candidate_id: string;
    source_title?: string;
    target_title?: string;
    event_id: string;
    target_work_id: string;
    outcome: string;
    old_score: number;
    new_score: number;
    reason: string[];
  }>;
};

export function reprocessingResult(
  job: Job | null | undefined,
): ReprocessingResult | null {
  if (job?.type !== "relation_candidate_reprocess") return null;
  let value = job.result?.data as ReprocessingResult | undefined;
  if (
    !value ||
    !["pending", "complete", "superseded"].includes(value.status) ||
    typeof value.has_more !== "boolean"
  )
    return null;
  if (value.status === "superseded" && value.eligible === null)
    value = { ...value, eligible: value.processed };
  if (
    ![
      "processed",
      "eligible",
      "changed",
      "retained",
      "rejected",
      "skipped",
      "batches",
    ].every((key) => {
      const count = value[key as keyof ReprocessingResult];
      return (
        typeof count === "number" && Number.isSafeInteger(count) && count >= 0
      );
    })
  )
    return null;
  if (
    value.changed > value.processed ||
    value.retained + value.rejected + value.skipped !== value.processed
  )
    return null;
  if (
    !Array.isArray(value.examples) ||
    !value.examples.every(
      (example) =>
        example &&
        [example.candidate_id, example.event_id, example.target_work_id].every(
          (id) => typeof id === "string",
        ) &&
        [example.source_title, example.target_title].every(
          (title) => title === undefined || typeof title === "string",
        ) &&
        [example.old_score, example.new_score].every(
          (score) => typeof score === "number" && Number.isFinite(score),
        ) &&
        ["retained", "rejected"].includes(example.outcome) &&
        Array.isArray(example.reason) &&
        example.reason.every((reason) => typeof reason === "string"),
    )
  )
    return null;
  return value;
}

export function canApplyReprocessing(
  job: Job | null | undefined,
  rule: string | undefined,
): boolean {
  const result = reprocessingResult(job);
  return Boolean(
    rule &&
    job?.state === "succeeded" &&
    job.maintenance?.dry_run === true &&
    job.maintenance.rule_revision === rule &&
    result?.rule_revision === rule &&
    result.status === "complete" &&
    result.has_more === false &&
    result.dry_run === true &&
    result.changed > 0,
  );
}

export const reprocessingActive = (job: Job) =>
  ["queued", "dispatched", "running", "retrying", "waiting_for_model"].includes(
    job.state,
  );

export type ReprocessingIntent = {
  request_id: string;
  dry_run: boolean;
  rule_revision: string;
};
export function readReprocessingIntent(
  raw: string | null,
): ReprocessingIntent | null {
  try {
    const value = JSON.parse(raw || "null");
    return value &&
      typeof value.dry_run === "boolean" &&
      typeof value.request_id === "string" &&
      typeof value.rule_revision === "string" &&
      value.rule_revision.length > 0 &&
      value.rule_revision.length <= 160 &&
      /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/.test(value.request_id)
      ? {
          request_id: value.request_id,
          dry_run: value.dry_run,
          rule_revision: value.rule_revision,
        }
      : null;
  } catch {
    return null;
  }
}
