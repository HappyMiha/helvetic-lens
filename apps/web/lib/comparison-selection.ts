import type { NativeComparisonPage, NativeSnapshot } from "./native-baseline";

export type BaselineDraft = { context: string; value: NativeSnapshot | null };
export type CommittedBaseline = {
  after: string;
  revision: number;
  comparison_id: string | null;
  previous: NativeComparisonPage;
};
const context = (page: NativeComparisonPage) =>
  JSON.stringify([page.event_id, page.after.id, page.revision]);

export function chooseBaseline(
  page: NativeComparisonPage,
  value: NativeSnapshot | null,
): BaselineDraft | null {
  return (value?.id || null) === (page.before?.id || null)
    ? null
    : { context: context(page), value };
}

export function comparisonSelection(
  page: NativeComparisonPage | null,
  draft: BaselineDraft | null,
  committed: CommittedBaseline | null,
) {
  return {
    value: draft ? draft.value : page?.before || null,
    dirty: draft !== null,
    conflict: !!draft && !!page && draft.context !== context(page),
    pending:
      !!committed &&
      (!page ||
        (page.after.id === committed.after &&
          (page === committed.previous ||
            page.revision < committed.revision ||
            (page.revision === committed.revision &&
              page.status === "ready" &&
              page.comparison_id !== committed.comparison_id)))),
  };
}

/** The same guard protects button state and the actual write boundary. */
export function baselineCommand(
  page: NativeComparisonPage | null,
  draft: BaselineDraft | null,
  committed: CommittedBaseline | null,
  allowed: boolean,
  clear = false,
) {
  const state = comparisonSelection(page, draft, committed);
  if (
    !page ||
    !allowed ||
    state.conflict ||
    state.pending ||
    (clear
      ? page.status === "unselected"
      : !state.dirty || !state.value || state.value.id === page.after.id)
  )
    return null;
  return {
    before_version_id: clear ? null : state.value!.id,
    after_version_id: page.after.id,
    expected_revision: page.revision,
  };
}

/** Links identify exactly the authorized saved version and passage. */
export function nativeSnapshotHref(
  snapshot: NativeSnapshot | null,
  passage?: string,
) {
  if (
    !snapshot?.id ||
    snapshot.evidence_url !==
      "/corpus-evidence/" + encodeURIComponent(snapshot.id)
  )
    return null;
  return (
    snapshot.evidence_url +
    (passage === undefined ? "" : "?passage=" + encodeURIComponent(passage))
  );
}
