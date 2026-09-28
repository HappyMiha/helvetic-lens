/** Shared keyboard boundary; a nested dialog keeps ownership of its keys. */
export function isAskShortcut(
  event: Pick<
    KeyboardEvent,
    | "key"
    | "ctrlKey"
    | "metaKey"
    | "altKey"
    | "shiftKey"
    | "isComposing"
    | "repeat"
    | "defaultPrevented"
  >,
  dialog: Pick<Element, "getAttribute"> | null,
) {
  return (
    !event.defaultPrevented &&
    !event.repeat &&
    !event.isComposing &&
    !event.altKey &&
    !event.shiftKey &&
    (event.ctrlKey || event.metaKey) &&
    event.key.toLowerCase() === "k" &&
    (!dialog || dialog.getAttribute("data-helvetic-ask") === "true")
  );
}

export type AskDraftDecision = "ready" | "conflict" | "unavailable";

/** Preparing a question is local. Never replace a different existing draft. */
export function askDraftDecision(
  current: string,
  incoming: string,
  allowed: boolean,
): AskDraftDecision {
  const question = incoming.trim();
  if (!allowed || !question || question.length > 2000) return "unavailable";
  return current.trim() && current.trim() !== question ? "conflict" : "ready";
}

export function askBoundary(
  path: string,
  organization = "",
  user = "",
  locale = "",
  permissions = "",
) {
  return JSON.stringify([path, organization, user, locale, permissions]);
}
