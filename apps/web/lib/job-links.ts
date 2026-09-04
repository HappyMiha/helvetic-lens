import type { Job } from "@/lib/types";

const comparisonTasks = new Set(["ask", "impact", "actions", "history"]);

export function jobResultHref(job: Job): string {
  const fallback =
    job.target_type === "comparison"
      ? `/compare/${job.target_id}`
      : job.type === "relation_impact_analysis"
        ? `/impact?candidate=${job.target_id}`
        : "/activity";
  const saved = job.result?.url || fallback;
  if (!saved.startsWith("/")) return fallback;
  const target = new URL(saved, "http://helvetic-lens.local");
  const task = target.hash.slice(1);
  if (target.pathname.startsWith("/compare/") && comparisonTasks.has(task)) {
    target.searchParams.set("task", task);
    target.hash = "";
  }
  return `${target.pathname}${target.search}${target.hash}`;
}
