"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { auctionCopy } from "@/lib/auction-copy";
import { auctionReminderCopy } from "@/lib/auction-reminder-copy";
import type { AuctionMonitor } from "@/lib/auction-watch";
import { useData, useMutation } from "./auction-client";
import { Lot, Timestamp, type Item } from "./auction-tracking";

type Reminder = {
  id: string;
  version: number;
  state: "scheduled" | "ready" | "acknowledged" | "invalidated";
  due_at: string | null;
  ends_at: string | null;
  hours: number;
  eligible: boolean;
  current: Item;
  href: string;
};
type Page = {
  items: Reminder[];
  next_cursor: string | null;
  unavailable_count: number;
};

function Summary({ row }: { row: Reminder }) {
  const { locale } = useI18n(),
    c = auctionReminderCopy[locale];
  return (
    <>
      <p>
        {c[row.state]}
        {row.state === "ready" && !row.eligible ? ` · ${c.waiting}` : ""}
      </p>
      <p>
        {c.hours}: {row.hours}
      </p>
      {row.due_at && (
        <p>
          {c.due}: <Timestamp value={row.due_at} />
        </p>
      )}
      {row.ends_at && (
        <p>
          {c.end}: <Timestamp value={row.ends_at} />
        </p>
      )}
    </>
  );
}

export function AuctionReminders({ monitor }: { monitor?: AuctionMonitor }) {
  const { locale } = useI18n(),
    c = auctionCopy[locale],
    r = auctionReminderCopy[locale];
  const [anchors, setAnchors] = useState<(string | null)[]>([null]),
    [revision, setRevision] = useState(0);
  const cursor = anchors.at(-1);
  const result = useData<Page>(
    `${monitor ? `/monitors/${monitor.id}` : ""}/reminders?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    revision,
  );
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!document.hidden) setRevision((v) => v + 1);
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <section
      data-auction-reminders
      className="my-5 min-w-0 [overflow-wrap:anywhere]"
    >
      <h3>{monitor ? r.schedule : r.title}</h3>
      <p>{r.note}</p>
      {result.error ? (
        <p role="alert">{c.failed}</p>
      ) : !result.data ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          {!!result.data.unavailable_count && (
            <p role="status">{r.unavailable}</p>
          )}
          {!result.data.items.length && <p>{r.empty}</p>}
          <ul>
            {result.data.items.map((row) => (
              <li key={row.id} className="my-3">
                {row.current.facts && <p>{row.current.facts.title}</p>}
                <Summary row={row} />
                <Link
                  href={row.href}
                  className="underline min-h-[44px] inline-block"
                >
                  {r.open}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
      {anchors.length > 1 && (
        <button onClick={() => setAnchors((v) => v.slice(0, -1))}>
          {c.back}
        </button>
      )}
      {result.data?.next_cursor && (
        <button
          onClick={() => setAnchors((v) => [...v, result.data!.next_cursor])}
        >
          {c.next}
        </button>
      )}
      <button
        onClick={() => {
          setAnchors([null]);
          setRevision((v) => v + 1);
        }}
      >
        {c.refresh}
      </button>
    </section>
  );
}

export function AuctionReminder({
  monitor,
  reminder,
  canManage,
}: {
  monitor: AuctionMonitor;
  reminder: string;
  canManage: boolean;
}) {
  const { locale } = useI18n(),
    c = auctionCopy[locale],
    r = auctionReminderCopy[locale];
  const [revision, setRevision] = useState(0);
  const path = `/monitors/${monitor.id}/reminders/${reminder}`;
  const result = useData<Reminder>(path, revision),
    mutation = useMutation();
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!document.hidden) setRevision((v) => v + 1);
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);
  const row = result.data;
  return (
    <section data-auction-reminder>
      <h3>{r.title}</h3>
      <p>{r.note}</p>
      <button onClick={() => setRevision((v) => v + 1)}>{c.refresh}</button>
      {result.error ? (
        <p role="alert">{c.failed}</p>
      ) : !row ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          <Summary row={row} />
          {canManage && row.state !== "acknowledged" && (
            <button
              disabled={mutation.busy}
              onClick={() =>
                void mutation.run(
                  path + "/acknowledge",
                  { expected_version: row.version },
                  () => setRevision((v) => v + 1),
                )
              }
            >
              {r.acknowledge}
            </button>
          )}
          {mutation.error && <p role="alert">{mutation.error}</p>}
          <Lot
            row={row.current}
            monitor={monitor}
            canManage={canManage}
            changed={() => setRevision((v) => v + 1)}
          />
        </>
      )}
    </section>
  );
}
