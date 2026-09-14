"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { monitoringNavigation } from "@/lib/monitoring-navigation";
import { centreCopy } from "@/lib/monitoring-centre-copy";
import { monitoringNotificationsCopy } from "@/lib/monitoring-notifications-copy";
import { documentHistoryCopy } from "@/lib/document-history-copy";
import { pollenDraftCopy } from "@/lib/pollen-draft-copy";
import { Button } from "./ui/button";

type Page = {
  state: "available" | "unavailable";
  domain: string;
  next_cursor: string | null;
  items: Array<{
    id: string;
    href: string;
    monitor_name: string;
    detected_at: string;
    allergen: string | null;
  }>;
};

export function MonitoringNotificationQueue({
  domain,
  onNavigate,
}: {
  domain: string;
  onNavigate: () => void;
}) {
  const { locale, t, dateTime } = useI18n();
  const copy = monitoringNotificationsCopy[locale],
    paging = documentHistoryCopy[locale];
  const section = monitoringNavigation.find((item) => item.id === domain);
  const [page, setPage] = useState<Page | null>(null),
    [busy, setBusy] = useState(true),
    [failed, setFailed] = useState(false);
  const [cursors, setCursors] = useState<string[]>([]),
    [revision, setRevision] = useState(0);
  const request = useRef<AbortController | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const cursor = cursors.at(-1) || "";
  useEffect(() => {
    const controller = new AbortController();
    request.current = controller;
    setPage(null);
    setBusy(true);
    setFailed(false);
    void api<Page>(
      `/monitoring-centre/notifications?domain=${encodeURIComponent(domain)}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
      { signal: controller.signal },
    )
      .then((result) => {
        if (!controller.signal.aborted) setPage(result);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setPage(null);
          setFailed(true);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setBusy(false);
          heading.current?.focus({ preventScroll: true });
        }
      });
    return () => controller.abort();
  }, [domain, cursor, revision]);
  useEffect(() => {
    const changed = () => {
      request.current?.abort();
      setPage(null);
      setCursors([]);
      setRevision((v) => v + 1);
    };
    window.addEventListener("helvetic-lens:today-changed", changed);
    return () =>
      window.removeEventListener("helvetic-lens:today-changed", changed);
  }, []);
  if (!section) return null;
  const name =
    domain === "pollen"
      ? t("nav.pollenWatch")
      : domain === "air"
        ? t("nav.airWatch")
        : domain === "river"
          ? t("nav.riverWatch")
          : centreCopy[locale].templates[section.id][0];
  return (
    <section
      aria-busy={busy}
      data-monitoring-notification-queue={domain}
      className="min-w-0 space-y-4 text-sm"
    >
      <h2 ref={heading} tabIndex={-1} className="font-semibold text-base">
        {name}
      </h2>
      {busy && <p role="status">{paging.loading}</p>}
      {failed && <p role="alert">{copy.failed}</p>}
      {page?.state === "unavailable" && <p>{copy.unavailable}</p>}
      {!busy && page?.state === "available" && !page.items.length && (
        <p>{page.next_cursor ? copy.sparse : copy.empty}</p>
      )}
      <ul className="space-y-3">
        {page?.items.map((item) => (
          <li
            key={item.id}
            data-monitoring-notification
            className="rounded-lg border p-3 break-words"
          >
            <p className="font-semibold">
              {item.monitor_name}
              {item.allergen
                ? ` · ${pollenDraftCopy[locale].allergens[item.allergen] || pollenDraftCopy[locale].unknown}`
                : ""}
            </p>
            <p>{copy.saved}</p>
            <p>
              {t("feed.detected")}:{" "}
              {dateTime(item.detected_at, {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </p>
            <Link
              className="min-h-11 inline-flex items-center underline"
              href={item.href}
              onClick={onNavigate}
            >
              {copy.open}
            </Link>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          className="min-h-11 h-auto whitespace-normal"
          disabled={busy || !cursors.length}
          onClick={() => setCursors((value) => value.slice(0, -1))}
        >
          {paging.previous}
        </Button>
        <Button
          variant="outline"
          className="min-h-11 h-auto whitespace-normal"
          disabled={busy || !page?.next_cursor}
          onClick={() =>
            page?.next_cursor &&
            setCursors((value) => [...value, page.next_cursor!])
          }
        >
          {paging.next}
        </Button>
        <Button
          variant="outline"
          className="min-h-11 h-auto whitespace-normal"
          disabled={busy}
          onClick={() => {
            setCursors([]);
            setRevision((value) => value + 1);
          }}
        >
          {failed ? paging.retry : paging.restart}
        </Button>
      </div>
      <Link
        href={section.href}
        onClick={onNavigate}
        className="inline-flex min-h-11 items-center underline"
      >
        {name}
      </Link>
    </section>
  );
}
