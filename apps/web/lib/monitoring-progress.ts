export const monitoringBranch = "codex/HappyDucky02/monitoring-v2";
export const pollenTaskIds = ["MV2-001", "MV2-069", "MV2-070", "MV2-030", "MV2-031", "MV2-071"] as const;

export type MonitoringTaskStatus = "PLANNED" | "READY" | "IN PROGRESS" | "VERIFYING" | "DONE" | "BLOCKED" | "DEFERRED";
export type MonitoringTask = { id: string; title: string; status: MonitoringTaskStatus };
export type MonitoringSnapshot = {
  sha: string | null;
  state: "available" | "unavailable";
  reason: string | null;
  tasks: MonitoringTask[];
};
export type MonitoringProgress = {
  schema_version: 1;
  source_path: "BACKLOG_MONITORING_V2.md";
  updated_at: string;
  branch: string;
  latest: MonitoringSnapshot;
  deployed: MonitoringSnapshot;
};

// The API validates each immutable snapshot. Never turn unavailable metadata into
// an empty, apparently complete backlog or borrow another revision's denominator.
export function snapshotCounts(snapshot: MonitoringSnapshot | null | undefined) {
  if (snapshot?.state !== "available") return null;
  const required = snapshot.tasks.filter(task => task.status !== "DEFERRED");
  const completed = required.filter(task => task.status === "DONE");
  const remaining = required.filter(task => task.status !== "DONE");
  const percent = required.length === 0 ? null : remaining.length === 0 ? 100
    : Math.min(99, Math.round(completed.length / required.length * 100));
  return { required, completed, remaining, percent,
    inProgress: required.filter(task => task.status === "IN PROGRESS").length };
}

export function tasksAwaitingDeployment(
  latest: MonitoringSnapshot | null | undefined,
  deployed: MonitoringSnapshot | null | undefined,
) {
  const latestCounts = snapshotCounts(latest);
  if (!latestCounts || deployed?.state !== "available") return null;
  const deployedDone = new Set(deployed.tasks.filter(task => task.status === "DONE").map(task => task.id));
  return latestCounts.completed.filter(task => !deployedDone.has(task.id));
}

export function pollenCompleted(snapshot: MonitoringSnapshot | null | undefined) {
  if (snapshot?.state !== "available") return null;
  return pollenTaskIds.filter(id => snapshot.tasks.some(task => task.id === id && task.status === "DONE")).length;
}
