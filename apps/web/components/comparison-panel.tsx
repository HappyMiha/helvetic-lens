"use client";

import { type ReactNode, useLayoutEffect, useRef, useState } from "react";

// Match the existing comparison drawer breakpoint. Keep the same subtree mounted
// in both modes: switching viewport must not reset an Ask draft or pending job.
const OVERLAY_QUERY = "(max-width: 1350px)";

export function ComparisonPanel({
  children,
  label,
  open,
  onClose,
}: {
  children: ReactNode;
  label: string;
  open: boolean;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const outsidePress = useRef(false);
  const [overlay, setOverlay] = useState(false);

  useLayoutEffect(() => {
    const query = window.matchMedia(OVERLAY_QUERY);
    const update = () => setOverlay(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useLayoutEffect(() => {
    const panel = ref.current;
    if (!panel) return;
    if (!overlay) {
      // Setting open directly gives the desktop panel no modal/focus effects.
      panel.open = true;
      return () => {
        panel.open = false;
      };
    }
    if (!open) return;
    const previous =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const main = panel.closest<HTMLElement>("main.main");
    const root = document.documentElement;
    const rootOverflow = root.style.overflow;
    const mainOverflow = main?.style.overflow;
    root.style.overflow = "hidden";
    if (main) main.style.overflow = "hidden";
    // Native modal isolation also makes navigation and Marvin behind it inert.
    panel.showModal();
    (
      panel.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]') ||
      panel
    ).focus({ preventScroll: true });
    return () => {
      panel.close();
      root.style.overflow = rootOverflow;
      if (main) main.style.overflow = mainOverflow || "";
      if (previous?.isConnected && previous.getClientRects().length)
        previous.focus({ preventScroll: true });
    };
  }, [overlay, open]);

  function outside(event: React.PointerEvent<HTMLDialogElement>) {
    const box = event.currentTarget.getBoundingClientRect();
    return (
      event.target === event.currentTarget &&
      (event.clientX < box.left ||
        event.clientX > box.right ||
        event.clientY < box.top ||
        event.clientY > box.bottom)
    );
  }

  return (
    <dialog
      ref={ref}
      className="analysis-column"
      aria-label={label}
      role="dialog"
      aria-modal={overlay && open ? true : undefined}
      data-comparison-overlay={overlay && open ? "true" : undefined}
      onCancel={(event) => {
        event.preventDefault();
        if (overlay) onClose();
      }}
      onPointerDown={(event) => {
        outsidePress.current = outside(event);
      }}
      onPointerUp={(event) => {
        if (overlay && outsidePress.current && outside(event)) onClose();
        outsidePress.current = false;
      }}
      onKeyDown={(event) => {
        if (!overlay) return;
        if (event.key === "Escape") event.stopPropagation();
        if (event.key !== "Tab") return;
        const elements = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>(
            "a[href], button, input, select, textarea, [tabindex]",
          ),
        ).filter(
          (el) =>
            el.tabIndex >= 0 &&
            !el.matches(":disabled") &&
            el.getClientRects().length > 0 &&
            !el.closest("[hidden], [inert]"),
        );
        const first = elements[0],
          last = elements.at(-1);
        if (!first) {
          event.preventDefault();
          event.currentTarget.focus();
        } else if (
          event.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === event.currentTarget)
        ) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }}
    >
      {children}
    </dialog>
  );
}
