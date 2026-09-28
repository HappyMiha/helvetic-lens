import type { Comparison, Job } from "./types";

export function readableComparison(
  data: Comparison | null,
  error: string,
  id: string,
): Comparison | null {
  return !error && data?.id === id ? data : null;
}

export function comparisonJob(
  job: Job | null | undefined,
  id: string,
  locale: string,
): Job | null {
  return job?.target_type === "comparison" &&
    job.target_id === id &&
    job.type === "impact_analysis" &&
    (!job.request?.output_locale || job.request.output_locale === locale)
    ? job
    : null;
}
