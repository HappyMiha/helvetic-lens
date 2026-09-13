"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { commuteCopy } from "@/lib/commute-copy";
import {
  commuteStateLabel,
  commuteSources,
  commuteTimezone,
  type CommuteTodayItem,
  type Page,
} from "@/lib/commute-watch";
import { useAuth } from "./auth-gate";

export function CommuteToday() {
  const { session } = useAuth();
  const scope = session?.authenticated
    ? `${session.user?.id}:${session.organization?.id}:${session.role}`
    : null;
  return scope ? <PrivateCommuteToday key={scope} /> : null;
}
function PrivateCommuteToday() {
  const { locale } = useI18n(),
    c = commuteCopy[locale];
  const [page, setPage] = useState<Page<CommuteTodayItem> | null>(null),
    [failed, setFailed] = useState(false),
    [busy, setBusy] = useState(false);
  const [anchors, setAnchors] = useState<string[]>([]);
  const request = useRef<AbortController | null>(null),
    cursor = useRef<string | null>(null);
  const mounted = useRef(true);
  async function load(anchor: string | null = null) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    cursor.current = anchor;
    setPage(null);
    setFailed(false);
    setBusy(true);
    try {
      const result = await api<Page<CommuteTodayItem>>(
        `/commute-watch/today${anchor ? `?cursor=${encodeURIComponent(anchor)}` : ""}`,
        { signal: controller.signal },
      );
      if (!controller.signal.aborted && mounted.current) setPage(result);
    } catch (error) {
      if (!controller.signal.aborted && mounted.current) {
        const hidden =
          error instanceof ApiError &&
          [
            "commute_disabled",
            "authentication_required",
            "membership_required",
            "forbidden",
          ].includes(error.code);
        setFailed(!hidden);
        if (hidden) {
          setAnchors([]);
          cursor.current = null;
        }
      }
    } finally {
      if (!controller.signal.aborted && mounted.current) {
        setBusy(false);
        request.current = null;
      }
    }
  }
  useEffect(() => {
    mounted.current = true;
    void load();
    const refresh = () => {
      if (!document.hidden && !request.current) void load(cursor.current);
    };
    const clear = () => {
      request.current?.abort();
      request.current = null;
      setPage(null);
    };
    const restore = (event: PageTransitionEvent) => {
      if (event.persisted) window.location.reload();
    };
    const timer = window.setInterval(refresh, 60_000);
    window.addEventListener("focus", refresh);
    window.addEventListener("pagehide", clear);
    window.addEventListener("pageshow", restore);
    return () => {
      mounted.current = false;
      clear();
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("pagehide", clear);
      window.removeEventListener("pageshow", restore);
    };
    // Identity/workspace/role changes synchronously remount this private reader.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (!page?.items.length && !page?.next_cursor && !failed && !anchors.length)
    return null;
  return (
    <section
      className="rounded-xl border p-4 my-5 min-w-0 [overflow-wrap:anywhere]"
      data-commute-today
      aria-busy={busy}
    >
      <h2 className="font-semibold">{c.today}</h2>
      {failed && <p role="alert">{c.failed}</p>}
      {busy && <p role="status">{c.loading}</p>}
      {page && !page.items.length && <p>{c.todayEmpty}</p>}
      <ul>
        {page?.items.map((item) => (
          <li className="border-t py-3 mt-3" key={item.id}>
            <Link
              className="underline min-h-[44px] inline-flex items-center"
              href={item.href}
            >
              {item.name}
            </Link>
            <p>
              {item.service_day} · {commuteSources[item.source] || c.unknown}
            </p>
            {item.priority === "urgent" && (
              <p className="font-semibold">{c.urgent}</p>
            )}
            {Object.entries(item.states).map(([id, state]) => (
              <div className="my-2" key={id}>
                <p>
                  {item.reference_labels.find((value) => value.id === id)
                    ?.label || c.unknownLeg}
                </p>
                <p>
                  {commuteStateLabel(c, state.condition)} ·{" "}
                  {commuteStateLabel(c, state.availability)}
                </p>
                {state.availability !== "present" && <p>{c.lastKnown}</p>}
                {state.delay_seconds != null && (
                  <p>
                    {c.delay}:{" "}
                    {new Intl.NumberFormat(locale, {
                      maximumFractionDigits: 1,
                    }).format(state.delay_seconds / 60)}
                  </p>
                )}
                {state.observed_at && (
                  <p>
                    {c.observation}:{" "}
                    <time dateTime={state.observed_at}>
                      {new Intl.DateTimeFormat(locale, {
                        dateStyle: "medium",
                        timeStyle: "short",
                        timeZone: commuteTimezone,
                      }).format(new Date(state.observed_at))}
                    </time>
                  </p>
                )}
              </div>
            ))}
            <p className="font-medium">{c.why}</p>
            {item.reasons.map((reason) => (
              <p key={reason}>
                {c[reason as keyof typeof c] || c.unread_journey_change}
              </p>
            ))}
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-4 mt-3">
        {anchors.length > 0 && (
          <button
            type="button"
            className="underline min-h-[44px]"
            disabled={busy}
            onClick={() => {
              const previous = anchors.slice(0, -1);
              setAnchors(previous);
              void load(previous.at(-1) || null);
            }}
          >
            {c.previous}
          </button>
        )}
        {page?.next_cursor && (
          <button
            type="button"
            className="underline min-h-[44px]"
            disabled={busy}
            onClick={() => {
              const next = String(page.next_cursor);
              setAnchors((previous) => [...previous, next]);
              void load(next);
            }}
          >
            {c.more}
          </button>
        )}
        <button
          type="button"
          className="underline min-h-[44px]"
          disabled={busy}
          onClick={() => {
            setAnchors([]);
            void load();
          }}
        >
          {c.refresh}
        </button>
      </div>
    </section>
  );
}
