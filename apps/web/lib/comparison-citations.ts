import type { Change, Citation, Comparison } from "./types";

export type ComparisonCitationVersions = Pick<
  Comparison,
  "old_version" | "new_version"
>;

export function citationChange(
  items: Change[],
  citation: Citation,
  versions: ComparisonCitationVersions | null,
): Change | undefined {
  if (!versions) return undefined;
  // Passage IDs are local to one version and can identify different wording
  // on the opposite side. Unknown/ambiguous targets keep their evidence URL.
  const matches = items.filter(
    (item) =>
      (citation.version_id === versions.old_version.id &&
        item.old?.id === citation.passage_id) ||
      (citation.version_id === versions.new_version.id &&
        item.new?.id === citation.passage_id),
  );
  return matches.length === 1 ? matches[0] : undefined;
}
