"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { ArrowUpRight, BookOpen, CircleHelp, Search, X } from "lucide-react";
import { Tabs } from "radix-ui";
import { useAuth } from "./auth-gate";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog";
import {
  guideForPath,
  permitted,
  SHARED_CONTROLS,
  type GuideControl,
  type SectionGuide,
} from "@/lib/section-guides";
import { guideTarget, guideTargetDisabled } from "@/lib/guide-target";
import styles from "./section-help.module.css";

export function SectionHelp({ standalone = false }: { standalone?: boolean }) {
  const pathname = usePathname();
  const { session, canManage, isPlatformAdmin } = useAuth();
  const guide = guideForPath(pathname);
  if (!guide) return null;
  return (
    <PageGuide
      key={`${pathname}:${session?.user?.id}:${session?.organization?.id}:${canManage}:${isPlatformAdmin}`}
      guide={guide}
      manager={canManage}
      platform={isPlatformAdmin}
      standalone={standalone}
    />
  );
}

function PageGuide({
  guide,
  manager,
  platform,
  standalone,
}: {
  guide: SectionGuide;
  manager: boolean;
  platform: boolean;
  standalone: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("start");
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const [locations, setLocations] = useState<
    Record<string, "available" | "disabled">
  >({});
  const trigger = useRef<HTMLButtonElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const destination = useRef<HTMLElement | null>(null);
  const cleanup = useRef<(() => void) | null>(null);
  const allowed = permitted(guide.access, manager, platform);
  const controls = allowed
    ? guide.controls.filter((control) =>
        permitted(control.access, manager, platform),
      )
    : [];
  const shared = standalone ? [] : SHARED_CONTROLS;

  function rootFor(sharedControl: boolean): ParentNode {
    return sharedControl
      ? document
      : document.getElementById("main-content") ||
          document.querySelector("main") ||
          document;
  }
  function locate() {
    const result: Record<string, "available" | "disabled"> = {};
    for (const [group, items] of [
      ["page", controls],
      ["shared", shared],
    ] as const) {
      for (const control of items) {
        const target = guideTarget(control, rootFor(group === "shared"));
        if (target)
          result[`${group}:${control.id}`] = guideTargetDisabled(target)
            ? "disabled"
            : "available";
      }
    }
    setLocations(result);
  }
  function changeOpen(value: boolean) {
    if (value) {
      cleanup.current?.();
      locate();
      setNotice("");
    }
    setOpen(value);
  }
  useEffect(() => {
    function keydown(event: KeyboardEvent) {
      // Do not stack this guide over an existing confirmation or editor dialog.
      if (
        event.key === "F1" &&
        !document.querySelector(
          'dialog[open], [role="dialog"], [role="alertdialog"]',
        )
      ) {
        event.preventDefault();
        trigger.current?.click();
      }
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      cleanup.current?.();
    };
  }, []);

  function show(control: GuideControl, sharedControl: boolean) {
    const target = guideTarget(control, rootFor(sharedControl));
    if (!target || guideTargetDisabled(target)) {
      locate();
      setNotice(
        target
          ? "This control is disabled. Read its prerequisites on the page before continuing."
          : "This control is not currently shown. It may require a record, an expanded form or different permissions.",
      );
      return;
    }
    destination.current = target;
    setOpen(false);
  }

  function restoreFocus(event: Event) {
    event.preventDefault();
    const target = destination.current;
    destination.current = null;
    if (!target?.isConnected || guideTargetDisabled(target)) {
      trigger.current?.focus();
      return;
    }
    // Highlight and focus only: no click, input event, navigation or submission.
    const oldTabIndex = target.getAttribute("tabindex");
    if (target.tabIndex < 0) target.setAttribute("tabindex", "-1");
    target.setAttribute("data-guide-highlight", "true");
    target.scrollIntoView({ block: "center", behavior: "instant" });
    target.focus({ preventScroll: true });
    setNotice("Highlighted on the page. No action was performed.");
    const clear = () => {
      target.removeAttribute("data-guide-highlight");
      if (oldTabIndex === null) target.removeAttribute("tabindex");
      else target.setAttribute("tabindex", oldTabIndex);
      target.removeEventListener("blur", clear);
      clearTimeout(timer);
    };
    const timer = window.setTimeout(clear, 6000);
    target.addEventListener("blur", clear, { once: true });
    cleanup.current = clear;
  }

  function controlCards(items: GuideControl[], group: "page" | "shared") {
    const filtered = items.filter((control) =>
      `${control.label} ${control.does} ${control.when}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
    );
    return filtered.map((control) => {
      const location = locations[`${group}:${control.id}`];
      return (
        <article
          key={control.id}
          className={styles.card}
          data-guide-control={`${group}:${control.id}`}
        >
          <div className={styles.cardHeader}>
            <h3>{control.label}</h3>
            <span className={styles.effect}>{control.effect}</span>
          </div>
          <p>{control.does}</p>
          <p className={styles.when}>{control.when}</p>
          {location === "available" ? (
            <button
              type="button"
              className={styles.show}
              onClick={() => show(control, group === "shared")}
              aria-label={`Show me: ${control.label}`}
            >
              Show me <ArrowUpRight size={15} aria-hidden="true" />
            </button>
          ) : (
            <p className={styles.availability}>
              {location === "disabled"
                ? "Currently disabled — check the prerequisites above and on the page."
                : "Not located in the current view. It may need a record or expanded form; translated labels may also prevent locating it."}
            </p>
          )}
        </article>
      );
    });
  }
  const matches = [...controls, ...shared].some((control) =>
    `${control.label} ${control.does} ${control.when}`
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );
  return (
    <aside
      className={styles.orientation}
      data-section-help={guide.id}
      aria-label={`${guide.title} help`}
      lang="en"
    >
      <div className={styles.intro}>
        <BookOpen size={18} aria-hidden="true" />
        <p>
          <strong>{guide.title}</strong>
          <span>{guide.purpose}</span>
        </p>
      </div>
      <Dialog open={open} onOpenChange={changeOpen}>
        <DialogTrigger asChild>
          <button
            ref={trigger}
            type="button"
            className={styles.trigger}
            data-page-guide-trigger
          >
            <CircleHelp size={16} aria-hidden="true" />
            Page guide
          </button>
        </DialogTrigger>
        <DialogContent
          className={`${styles.dialog} translate-x-0 translate-y-0 data-[state=open]:animate-none data-[state=closed]:animate-none`}
          overlayClassName={styles.overlay}
          showCloseButton={false}
          aria-describedby={undefined}
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            heading.current?.focus();
          }}
          onCloseAutoFocus={restoreFocus}
          data-section-guide={guide.id}
          lang="en"
        >
          <header className={styles.header}>
            <div>
              <span className={styles.eyebrow}>PAGE GUIDE · ENGLISH</span>
              <DialogTitle ref={heading} tabIndex={-1}>
                {guide.title}
              </DialogTitle>
            </div>
            <DialogClose asChild>
              <button
                type="button"
                className={styles.close}
                aria-label="Close page guide"
              >
                <X size={20} />
              </button>
            </DialogClose>
          </header>
          <p className={styles.purpose}>{guide.purpose}</p>
          {!allowed && (
            <p className={styles.permission}>
              This section requires{" "}
              {guide.access === "platform"
                ? "a platform administrator"
                : "an organization administrator"}
              . Ask your administrator for access or setup. The guide does not
              grant permissions.
            </p>
          )}
          <Tabs.Root value={tab} onValueChange={setTab} className={styles.tabs}>
            <Tabs.List aria-label="Guide chapters" className={styles.tabList}>
              <Tabs.Trigger value="start">Start here</Tabs.Trigger>
              <Tabs.Trigger value="controls">Controls</Tabs.Trigger>
              <Tabs.Trigger value="data">Data &amp; text</Tabs.Trigger>
              <Tabs.Trigger value="setup">Wait or set up</Tabs.Trigger>
            </Tabs.List>
            <Tabs.Content value="start" className={styles.chapter}>
              <h3>Your first useful action</h3>
              <ol className={styles.steps}>
                {guide.first.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <div className={styles.tip}>
                <strong>Unsure about a button?</strong>
                <p>
                  Open Controls to see what it changes. “Show me” finds a
                  visible control without pressing it.
                </p>
                <button
                  type="button"
                  className={styles.show}
                  onClick={() => setTab("controls")}
                >
                  Explain the controls{" "}
                  <ArrowUpRight size={15} aria-hidden="true" />
                </button>
              </div>
            </Tabs.Content>
            <Tabs.Content value="controls" className={styles.chapter}>
              <label className={styles.search}>
                <Search size={17} aria-hidden="true" />
                <span className="sr-only">Find a control in this guide</span>
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Find a button or action…"
                />
              </label>
              <p className={styles.when}>
                Related buttons and fields are grouped below. Availability
                reflects the view when you opened the guide.
              </p>
              <button type="button" className={styles.show} onClick={locate}>
                Check visible controls again
              </button>
              {!matches && (
                <p role="status">
                  No matching explanation. Try a shorter English term or clear
                  the search.
                </p>
              )}
              {controlCards(controls, "page")}
              {shared.length > 0 && (
                <>
                  <h3>Across the workspace</h3>
                  {controlCards(shared, "shared")}
                </>
              )}
            </Tabs.Content>
            <Tabs.Content value="data" className={styles.chapter}>
              <h3>Where the text comes from</h3>
              {guide.data.map((text) => (
                <p key={text}>{text}</p>
              ))}
              <div className={styles.tip}>
                This guide is reviewed product documentation bundled with the
                app. It is not generated by AI and does not inspect your
                document contents. The page itself shows current data and job
                status.
              </div>
            </Tabs.Content>
            <Tabs.Content value="setup" className={styles.chapter}>
              <h3>When to wait</h3>
              <p>{guide.wait}</p>
              <h3>When to configure something</h3>
              <p>{guide.setup}</p>
              <div className={styles.tip}>
                <strong>Waiting, empty and failed are different.</strong>
                <p>
                  A loading indicator means a request is in progress. “Queued”
                  needs an available worker. An empty result describes the
                  current scope. An error needs its stated recovery step;
                  waiting alone may not resolve it.
                </p>
              </div>
            </Tabs.Content>
          </Tabs.Root>
          {open && (
            <p className={styles.notice} role="status">
              {notice}
            </p>
          )}
          <footer className={styles.footer}>
            Open this guide anytime with Page guide or F1. Escape closes it. No
            model or setup is needed.
          </footer>
        </DialogContent>
      </Dialog>
      {!open && (
        <span className="sr-only" role="status">
          {notice}
        </span>
      )}
    </aside>
  );
}
