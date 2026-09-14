"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { centreCopy } from "@/lib/monitoring-centre-copy";
import { monitoringNavigation } from "@/lib/monitoring-navigation";
import { todayCountsCopy } from "@/lib/today-counts-copy";
import { useAuth } from "./auth-gate";
import { Button } from "./ui/button";

type Counts = {
  total: number | null;
  evaluated_at: string;
  state: "complete" | "incomplete";
  items: Array<{
    domain: string;
    count: number | null;
    state: "complete" | "incomplete" | "unavailable";
  }>;
};

type Props = { onSelect?: (domain: string) => void };

export function TodayReviewCounts({ onSelect }: Props = {}) {
  const { session } = useAuth();
  const [visible, setVisible] = useState(true);
  const [epoch, setEpoch] = useState(0);
  useEffect(() => {
    const hide = () => setVisible(false);
    const show = () => {
      setVisible(true);
      setEpoch((value) => value + 1);
    };
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    return () => {
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
    };
  }, []);
  if (
    !visible ||
    !session?.authenticated ||
    !session.user?.id ||
    !session.organization?.id
  )
    return null;
  return (
    <PrivateCounts
      key={`${session.user.id}:${session.organization.id}:${session.role}:${epoch}`}
      onSelect={onSelect}
    />
  );
}

function PrivateCounts({ onSelect }: Props) {
  const heading = useId();
  const { locale, t, dateTime } = useI18n();
  const copy = todayCountsCopy[locale];
  const [page, setPage] = useState<Counts | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(true);
  const [revision, setRevision] = useState(0);
  const request = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    request.current = controller;
    // Clear old private numbers before every refresh, including review actions.
    setPage(null);
    setFailed(false);
    setBusy(true);
    void api<Counts>("/monitoring-centre/today-counts", {
      signal: controller.signal,
    })
      .then((result) => {
        if (
          !result ||
          !Array.isArray(result.items) ||
          result.items.length !== 10 ||
          !(result.total === null || Number.isSafeInteger(result.total))
        )
          throw new Error();
        if (!controller.signal.aborted) setPage(result);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setPage(null);
          setFailed(true);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [revision]);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const changed = () => {
      request.current?.abort();
      setPage(null);
      setFailed(false);
      setBusy(true);
      clearTimeout(timer);
      timer = setTimeout(() => setRevision((value) => value + 1), 300);
    };
    window.addEventListener("helvetic-lens:today-changed", changed);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("helvetic-lens:today-changed", changed);
    };
  }, []);
  const queues = [
    ...monitoringNavigation.map((item) => ({
      ...item,
      name:
        item.id === "pollen"
          ? t("nav.pollenWatch")
          : item.id === "river"
            ? t("nav.riverWatch")
            : item.id === "air"
              ? t("nav.airWatch")
              : centreCopy[locale].templates[item.id][0],
    })),
    { id: "legal", href: "/?state=unread#legal-feed", name: copy.legal },
  ];
  return (
    <section
      className="surface-card mb-6 p-4 sm:p-6"
      aria-labelledby={heading}
      data-testid="today-review-counts"
      aria-busy={busy}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2
          id={heading}
          tabIndex={onSelect ? -1 : undefined}
          className="text-lg font-semibold"
        >
          {copy.title}
        </h2>
        <Button
          variant="outline"
          className="min-h-11 h-auto whitespace-normal"
          onClick={() => setRevision((value) => value + 1)}
          disabled={busy}
        >
          {copy.refresh}
        </Button>
      </div>
      {!onSelect && <p className="muted mt-2 max-w-4xl text-sm">{copy.body}</p>}
      <div aria-live="polite" className="my-3">
        {busy ? (
          <p>{copy.loading}</p>
        ) : failed ? (
          <p role="alert">{copy.error}</p>
        ) : page?.total === null ? (
          <p>{copy.incomplete}</p>
        ) : page ? (
          <p className="text-lg font-semibold" data-testid="today-review-total">
            {copy.total}: {page.total.toLocaleString(locale)}
          </p>
        ) : null}
        {page?.total === 0 && <p className="muted text-sm">{copy.empty}</p>}
      </div>
      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {queues.map((queue) => {
          const row = page?.items.find((item) => item.domain === queue.id);
          const content = (
            <>
              <span>{queue.name}</span>
              <span className="font-semibold tabular-nums">
                {busy
                  ? "…"
                  : row?.count != null && row.state === "complete"
                    ? row.count.toLocaleString(locale)
                    : copy.unavailable}
              </span>
            </>
          );
          return (
            <li key={queue.id}>
              {onSelect ? (
                <button
                  type="button"
                  onClick={() => onSelect(queue.id)}
                  data-domain={queue.id}
                  className="flex min-h-11 w-full items-center justify-between gap-3 rounded border p-3 text-left text-sm hover:bg-muted/40"
                >
                  {content}
                </button>
              ) : (
                <Link
                  href={queue.href}
                  className="flex h-full items-center justify-between gap-3 rounded border p-3 text-sm hover:bg-muted/40"
                  data-domain={queue.id}
                >
                  {content}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
      {page && (
        <p className="muted mt-3 text-xs">
          {copy.checked}:{" "}
          {dateTime(page.evaluated_at, {
            dateStyle: "short",
            timeStyle: "short",
          })}
        </p>
      )}
    </section>
  );
}
