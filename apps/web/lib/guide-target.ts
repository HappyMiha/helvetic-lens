import type { GuideControl } from "./section-guides";

// Deliberately reads labels, not user-entered values. Never activates a control.
export function guideTarget(
  control: GuideControl,
  root: ParentNode,
): HTMLElement | undefined {
  const visible = (element: Element): element is HTMLElement => {
    if (
      !(element instanceof HTMLElement) ||
      element.closest("[data-section-help], [data-section-guide]")
    )
      return false;
    return (
      element.getClientRects().length > 0 &&
      getComputedStyle(element).visibility !== "hidden"
    );
  };
  if (control.selector) {
    const match = Array.from(root.querySelectorAll(control.selector)).find(
      visible,
    );
    if (match) return match;
  }
  const names = control.names?.map((name) => name.toLocaleLowerCase());
  if (!names?.length) return undefined;
  return Array.from(
    root.querySelectorAll("button, a[href], input, select, textarea, summary"),
  ).find((element) => {
    if (!visible(element)) return false;
    const labelledBy = element
      .getAttribute("aria-labelledby")
      ?.split(/\s+/)
      .map((id) => document.getElementById(id)?.textContent || "")
      .join(" ");
    const label =
      element.getAttribute("aria-label") ||
      labelledBy ||
      element.textContent ||
      "";
    return names.includes(
      label.replace(/\s+/g, " ").trim().toLocaleLowerCase(),
    );
  }) as HTMLElement | undefined;
}

export function guideTargetDisabled(target: HTMLElement) {
  return (
    target.matches(":disabled, [aria-disabled='true']") ||
    Boolean(target.closest("[inert]"))
  );
}
