"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { roadCopy } from "@/lib/road-copy";
import type { RoadPage, RoadTodayItem } from "@/lib/road-watch";
import { useAuth } from "./auth-gate";
import { RoadFacts } from "./road-facts";

type RoadFeed = RoadPage<RoadTodayItem> & {
  has_active_routes?: boolean;
  source_available?: boolean;
  unverified_routes?: boolean;
  unverified_count?: number;
};

export function RoadToday({ inbox = false }: { inbox?: boolean }) {
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
    const visibility = () => (document.hidden ? hide() : show());
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    window.addEventListener("focus", show);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
      window.removeEventListener("focus", show);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  return visible && session?.authenticated ? (
    <PrivateRoadToday
      key={`${session.user?.id}:${session.organization?.id}:${session.role}:${epoch}:${inbox}`}
      inbox={inbox}
    />
  ) : null;
}

function PrivateRoadToday({ inbox }: { inbox: boolean }) {
  const { canManage } = useAuth();
  const { locale } = useI18n(),
    c = roadCopy[locale];
  const [anchors, setAnchors] = useState<(string | null)[]>([null]),
    [revision, setRevision] = useState(0);
  const cursor = anchors[anchors.length - 1],
    key = `${cursor}:${revision}`;
  const [result, setResult] = useState<{
    key: string;
    page?: RoadFeed;
    error?: unknown;
  }>({ key: "" });
  const current = result.key === key ? result : null;
  const mutation = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => () => mutation.current?.abort(), []);
  const denied =
    current?.error instanceof ApiError &&
    [
      "road_watch_disabled",
      "authentication_required",
      "membership_required",
      "subject_role_denied",
    ].includes(current.error.code);
  useEffect(() => {
    const controller = new AbortController();
    api<RoadFeed>(
      `/road-watch/${inbox ? "inbox" : "today"}?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
      { signal: controller.signal },
    )
      .then((page) => {
        if (!controller.signal.aborted) setResult({ key, page });
      })
      .catch((error) => {
        if (!controller.signal.aborted) setResult({ key, error });
      });
    return () => controller.abort();
  }, [cursor, key, inbox]);
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!document.hidden && !mutation.current) setRevision((v) => v + 1);
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);
  const page = current?.page;
  async function review(item: RoadTodayItem, muted = false) {
    if (mutation.current || !canManage) return;
    const controller = new AbortController();
    mutation.current = controller;
    setBusy(true);
    try {
      await api(`/road-watch/events/${item.event_id}/review`, {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          expected_version: item.event.version,
          sequence: item.sequence,
          ...(muted ? { muted: true } : {}),
        }),
      });
      if (!controller.signal.aborted) {
        setAnchors([null]);
        setRevision((v) => v + 1);
      }
    } catch (error) {
      if (!controller.signal.aborted) setResult({ key, error });
    } finally {
      if (!controller.signal.aborted) {
        mutation.current = null;
        setBusy(false);
      }
    }
  }
  if (
    denied ||
    (!current?.error &&
      !page?.items.length &&
      !page?.next_cursor &&
      anchors.length === 1 &&
      (!inbox || !page?.has_active_routes))
  )
    return null;
  return (
    <section
      className="rounded-xl border p-4 my-5 min-w-0 [overflow-wrap:anywhere]"
      data-road-today={!inbox || undefined}
      data-road-inbox={inbox || undefined}
      aria-busy={!current}
    >
      <h2 className="font-semibold">{inbox ? c.inbox : c.today}</h2>
      {inbox && (
        <p>
          {c.inboxScope}{" "}
          <Link className="underline" href="/road-watch">
            {c.title}
          </Link>
        </p>
      )}
      {!!current?.error && <p role="alert">{c.failed}</p>}
      {!current && <p role="status">{c.loading}</p>}
      {inbox &&
        page &&
        (!page.source_available ||
          page.unverified_routes ||
          !!page.unverified_count) && <p role="status">{c.inboxUnverified}</p>}
      {page && !page.items.length && (
        <p>{inbox ? c.inboxEmpty : c.todayEmpty}</p>
      )}
      <ul>
        {page?.items.map((item) => (
          <li key={item.id} className="border-t py-3 mt-3">
            <Link
              className="underline min-h-[44px] inline-flex items-center"
              href={item.href}
            >
              {item.name}
            </Link>
            {item.priority === "urgent" && (
              <p className="font-semibold">{c.urgent}</p>
            )}
            <RoadFacts
              headingLevel={3}
              payload={item.event.payload}
              availability={item.event.availability}
              attribution={item.event.attribution}
              labels={item.corridors}
            />
            <p className="font-semibold">{c.why}</p>
            <p>{c.unreadRoadChange}</p>
            {inbox && canManage && (
              <div className="flex flex-wrap gap-4">
                <button
                  className="underline min-h-[44px]"
                  disabled={busy}
                  onClick={() => void review(item)}
                >
                  {c.review}
                </button>
                <button
                  className="underline min-h-[44px]"
                  disabled={busy}
                  onClick={() => void review(item, true)}
                >
                  {c.mute}
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-4 mt-3">
        {anchors.length > 1 && (
          <button
            className="underline min-h-[44px]"
            disabled={!current || busy}
            onClick={() => setAnchors((v) => v.slice(0, -1))}
          >
            {c.previous}
          </button>
        )}
        {page?.next_cursor && (
          <button
            className="underline min-h-[44px]"
            disabled={!current || busy}
            onClick={() => setAnchors((v) => [...v, String(page.next_cursor)])}
          >
            {c.more}
          </button>
        )}
        <button
          className="underline min-h-[44px]"
          disabled={!current || busy}
          onClick={() => {
            setAnchors([null]);
            setRevision((v) => v + 1);
          }}
        >
          {c.refresh}
        </button>
      </div>
    </section>
  );
}
