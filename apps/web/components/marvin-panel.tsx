"use client";

import {
  type ReactNode,
  type RefObject,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { lockOverlayScroll } from "@/lib/overlay-scroll";

export function MarvinPanel({
  children,
  label,
  onClose,
  fallbackFocusRef,
}: {
  children: ReactNode;
  label: string;
  onClose: () => void;
  fallbackFocusRef: RefObject<HTMLElement | null>;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const outsidePress = useRef(false);
  const unmounting = useRef(false);
  const lastFocused = useRef<HTMLElement | null>(null);
  const [overlay, setOverlay] = useState(false);

  useLayoutEffect(() => {
    unmounting.current = false;
    opener.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const query = window.matchMedia("(max-width: 1350px)");
    const update = () => setOverlay(query.matches);
    update();
    query.addEventListener("change", update);
    return () => {
      query.removeEventListener("change", update);
      unmounting.current = true;
    };
  }, []);

  useLayoutEffect(() => {
    const panel = ref.current;
    if (!panel) return;
    const focused = lastFocused.current || document.activeElement;
    const restoreInside =
      focused instanceof HTMLElement && panel.contains(focused)
        ? focused
        : null;
    const release = overlay ? lockOverlayScroll() : () => {};
    if (overlay) panel.showModal();
    else panel.open = true;
    (
      restoreInside ||
      panel.querySelector<HTMLElement>("[data-marvin-close]") ||
      panel
    ).focus({ preventScroll: true });
    return () => {
      const active = document.activeElement;
      lastFocused.current =
        active instanceof HTMLElement && panel.contains(active) ? active : null;
      panel.close();
      release();
      if (unmounting.current) {
        const previous = opener.current;
        const target =
          previous?.isConnected && previous.getClientRects().length
            ? previous
            : fallbackFocusRef.current;
        if (target?.isConnected && target.getClientRects().length)
          target.focus({ preventScroll: true });
      }
    };
  }, [overlay, fallbackFocusRef]);

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
      className="marvin-drawer"
      aria-label={label}
      aria-modal={overlay ? true : undefined}
      data-marvin-overlay={overlay ? "true" : undefined}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onPointerDown={(event) => {
        outsidePress.current = outside(event);
      }}
      onPointerUp={(event) => {
        if (overlay && outsidePress.current && outside(event)) onClose();
        outsidePress.current = false;
      }}
      onKeyDown={(event) => {
        // A nested dialog owns its Escape and Tab; never dismiss both layers.
        if (
          event.target instanceof Element &&
          event.target.closest('dialog, [role="dialog"]') !==
            event.currentTarget
        )
          return;
        if (event.key === "Escape") {
          event.stopPropagation();
          if (!overlay) {
            event.preventDefault();
            onClose();
          }
        }
        if (!overlay || event.key !== "Tab") return;
        const elements = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>(
            "a[href], button, input, select, textarea, [tabindex]",
          ),
        ).filter(
          (element) =>
            element.tabIndex >= 0 &&
            !element.matches(":disabled") &&
            element.getClientRects().length > 0 &&
            !element.closest("[hidden], [inert]"),
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
