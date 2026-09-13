"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { hazardEventCopy } from "@/lib/hazard-event-copy";
import { hazardHref, type HazardEvent } from "@/lib/hazard-events";
import { roadCopy } from "@/lib/road-copy";
import { useAuth } from "./auth-gate";
import { useData } from "./hazard-data";

type Feed = {
  items: {
    id: string;
    monitor_id: string;
    name: string;
    event_id: string;
    revision: number;
    state: HazardEvent["state"];
    importance: "information" | "warning" | "alarm" | null;
    attribution: string;
    last_seen_at: string;
    detected_at: string;
  }[];
  next_cursor: string | null;
  has_active_places: boolean;
  coverage_verified: boolean;
  unavailable_count: number;
};

export function HazardToday({ inbox = false }: { inbox?: boolean }) {
  const { session } = useAuth();
  const [visible, setVisible] = useState(true),
    [epoch, setEpoch] = useState(0);
  useEffect(() => {
    const hide = () => {
      setVisible(false);
      setEpoch((v) => v + 1);
    };
    const show = () => {
      setVisible(!document.hidden);
      setEpoch((v) => v + 1);
    };
    const change = () => (document.hidden ? hide() : show());
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    window.addEventListener("focus", show);
    document.addEventListener("visibilitychange", change);
    return () => {
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
      window.removeEventListener("focus", show);
      document.removeEventListener("visibilitychange", change);
    };
  }, []);
  return visible && session?.authenticated ? (
    <PrivateFeed
      inbox={inbox}
      key={`${session.user?.id}:${session.organization?.id}:${session.role}:${epoch}:${inbox}`}
    />
  ) : null;
}

function PrivateFeed({ inbox }: { inbox: boolean }) {
  const { locale } = useI18n(),
    c = hazardEventCopy[locale],
    r = roadCopy[locale];
  const [anchors, setAnchors] = useState<(string | null)[]>([null]),
    [revision, setRevision] = useState(0);
  const cursor = anchors.at(-1);
  const result = useData<Feed>(
    `/${inbox ? "inbox" : "today"}?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    revision,
  );
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!document.hidden) setRevision((v) => v + 1);
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);
  if (
    result.error instanceof ApiError &&
    [
      "hazard_watch_disabled",
      "authentication_required",
      "membership_required",
      "subject_role_denied",
    ].includes(result.error.code)
  )
    return null;
  const page = result.data;
  if (
    !result.error &&
    !page?.items.length &&
    !page?.next_cursor &&
    !page?.has_active_places &&
    anchors.length === 1
  )
    return null;
  const stamp = (value: string) => (
    <time dateTime={value}>
      {Number.isFinite(Date.parse(value))
        ? new Intl.DateTimeFormat(locale, {
            dateStyle: "medium",
            timeStyle: "short",
          }).format(new Date(value))
        : "—"}
    </time>
  );
  return (
    <section
      data-hazard-today={!inbox || undefined}
      data-hazard-inbox={inbox || undefined}
      className="rounded-xl border p-4 my-5 min-w-0 [overflow-wrap:anywhere]"
      aria-busy={!page && !result.error}
    >
      <h2 className="font-semibold">{inbox ? c.inbox : c.today}</h2>
      <p>{inbox ? c.inboxScope : c.todayScope}</p>
      <p className="my-3">{c.coverage}</p>
      {result.error ? (
        <p role="alert">{r.failed}</p>
      ) : !page ? (
        <p role="status">{r.loading}</p>
      ) : (
        <>
          {!!page.unavailable_count && (
            <p role="status">{c.unavailableDetail}</p>
          )}
          {!page.items.length && <p>{c.feedEmpty}</p>}
          <ul>
            {page.items.map((item) => (
              <li key={item.id} className="border-t py-3 mt-3">
                <h3 className="font-semibold">{item.name}</h3>
                <p>
                  {c[item.state]}
                  {item.importance && <> · {c[item.importance]}</>}
                </p>
                <p>{item.attribution}</p>
                <p>
                  {c.detected}: {stamp(item.detected_at)}
                </p>
                <p>
                  {c.fetched}: {stamp(item.last_seen_at)}
                </p>
                <Link
                  prefetch={false}
                  className="underline min-h-[44px] inline-flex items-center"
                  href={hazardHref(
                    item.monitor_id,
                    item.event_id,
                    item.revision,
                  )}
                >
                  {c.openInstructions}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="flex flex-wrap gap-4 mt-3">
        {anchors.length > 1 && (
          <button
            className="underline min-h-[44px]"
            onClick={() => setAnchors((v) => v.slice(0, -1))}
          >
            {r.previous}
          </button>
        )}
        {page?.next_cursor && (
          <button
            className="underline min-h-[44px]"
            onClick={() => setAnchors((v) => [...v, page.next_cursor])}
          >
            {r.more}
          </button>
        )}
        <button
          className="underline min-h-[44px]"
          onClick={() => {
            setAnchors([null]);
            setRevision((v) => v + 1);
          }}
        >
          {r.refresh}
        </button>
      </div>
    </section>
  );
}
