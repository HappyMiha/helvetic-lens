"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { auctionCopy } from "@/lib/auction-copy";
import { auctionFeedCopy, auctionChangeLabel } from "@/lib/auction-feed-copy";
import { useAuth } from "./auth-gate";
import { useData } from "./auction-client";
import { Timestamp } from "./auction-tracking";

type Page = {
  items: {
    id: string;
    name: string;
    title: string;
    canton: string;
    auction_id: string;
    lot_id: string | null;
    attribution: string;
    detected_at: string;
    change_codes: string[];
    href: string;
  }[];
  next_cursor: string | null;
  unavailable_count: number;
  has_active_monitors: boolean;
};

export function AuctionToday({ inbox = false }: { inbox?: boolean }) {
  const { session } = useAuth();
  const [visible, setVisible] = useState(true),
    [epoch, setEpoch] = useState(0);
  useEffect(() => {
    const show = () => {
      setVisible(!document.hidden);
      setEpoch((v) => v + 1);
    };
    const hide = () => {
      setVisible(false);
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
    <PrivateFeed
      inbox={inbox}
      key={`${session.user?.id}:${session.organization?.id}:${session.role}:${epoch}:${inbox}`}
    />
  ) : null;
}

function PrivateFeed({ inbox }: { inbox: boolean }) {
  const { locale } = useI18n(),
    c = auctionCopy[locale],
    f = auctionFeedCopy[locale];
  const [anchors, setAnchors] = useState<(string | null)[]>([null]),
    [revision, setRevision] = useState(0);
  const cursor = anchors.at(-1);
  const result = useData<Page>(
    `/${inbox ? "inbox" : "today"}?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    revision,
  );
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!document.hidden) setRevision((v) => v + 1);
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);
  const denied =
    result.error instanceof ApiError &&
    [
      "authentication_required",
      "membership_required",
      "subject_role_denied",
      "auction_watch_disabled",
    ].includes(result.error.code);
  if (denied) return null;
  return (
    <section
      className="rounded-xl border p-4 my-5 min-w-0 [overflow-wrap:anywhere]"
      data-auction-today={!inbox || undefined}
      data-auction-inbox={inbox || undefined}
    >
      <h2 className="font-semibold">{inbox ? f.inbox : f.today}</h2>
      <p>
        {f.scope}{" "}
        <Link className="underline" href="/auction-watch">
          {c.title}
        </Link>
      </p>
      {result.error ? (
        <p role="alert">{c.failed}</p>
      ) : !result.data ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          {!!result.data.unavailable_count && (
            <p role="status">{f.unavailable}</p>
          )}
          {!result.data.items.length && <p>{f.empty}</p>}
          <ul>
            {result.data.items.map((item) => (
              <li key={item.id} className="border-t py-3 mt-3">
                <h3 className="font-semibold">{item.title}</h3>
                <p>
                  {item.name} · {item.canton} · {item.auction_id}
                  {item.lot_id ? ` / ${item.lot_id}` : ""}
                </p>
                <ul>
                  {Array.from(
                    new Set(
                      item.change_codes.map((code) =>
                        auctionChangeLabel(locale, code),
                      ),
                    ),
                  ).map((label) => (
                    <li key={label}>{label}</li>
                  ))}
                </ul>
                <p>
                  {f.detected}: <Timestamp value={item.detected_at} />
                </p>
                <p>{item.attribution}</p>
                <Link
                  className="underline min-h-[44px] inline-flex items-center"
                  href={item.href}
                >
                  {f.open}
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
            {c.back}
          </button>
        )}
        {result.data?.next_cursor && (
          <button
            className="underline min-h-[44px]"
            onClick={() => setAnchors((v) => [...v, result.data!.next_cursor])}
          >
            {c.next}
          </button>
        )}
        <button
          className="underline min-h-[44px]"
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
