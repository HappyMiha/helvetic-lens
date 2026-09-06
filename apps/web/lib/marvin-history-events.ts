export const MARVIN_HISTORY_DELETED = "helvetic:marvin-history-deleted";
export const MARVIN_DELETION_STORAGE = "helvetic_lens_marvin_last_deletion";
export type MarvinDeletion = {
  id: string;
  organization: string;
  user: string;
  comparison: string;
};

export function clearDeletedDraft(value: MarvinDeletion) {
  if (!value.comparison) return;
  try {
    sessionStorage.removeItem(
      "helvetic_lens_companion_draft_v1:" +
        JSON.stringify([value.organization, value.user, value.comparison]),
    );
  } catch {
    /* Storage denial does not reverse a successful server deletion. */
  }
}

export function publishMarvinDeletion(value: MarvinDeletion) {
  clearDeletedDraft(value);
  window.dispatchEvent(
    new CustomEvent(MARVIN_HISTORY_DELETED, { detail: value }),
  );
  try {
    // Only identifiers, never private message text. Other open same-origin tabs
    // can discard their stale local draft and abort their current conversation.
    localStorage.setItem(
      MARVIN_DELETION_STORAGE,
      JSON.stringify({ ...value, at: Date.now() }),
    );
  } catch {
    /* Cross-tab notification is best effort, not server cancellation. */
  }
}
