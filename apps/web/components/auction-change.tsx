"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { auctionCopy } from "@/lib/auction-copy";
import { auctionTrackingCopy } from "@/lib/auction-tracking-copy";
import { auctionChangeLabel, auctionFeedCopy } from "@/lib/auction-feed-copy";
import type { AuctionMonitor } from "@/lib/auction-watch";
import { useData } from "./auction-client";
import {
  Evidence,
  Lot,
  Timestamp,
  type Facts,
  type Item,
} from "./auction-tracking";

type Snapshot = { state: string; facts: Facts | null };
type Change = {
  id: string;
  detected_at: string;
  change_codes: string[];
  current_configuration: boolean;
  newer_available: boolean;
  snapshot: Snapshot;
  previous: Snapshot | null;
  current: Item;
};

export function AuctionChange({
  monitor,
  event,
  canManage,
}: {
  monitor: AuctionMonitor;
  event: string;
  canManage: boolean;
}) {
  const { locale } = useI18n(),
    c = auctionCopy[locale],
    f = auctionFeedCopy[locale],
    w = auctionTrackingCopy[locale];
  const [revision, setRevision] = useState(0);
  const result = useData<Change>(
    `/monitors/${monitor.id}/events/${event}`,
    revision,
  );
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!document.hidden) setRevision((v) => v + 1);
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);
  const data = result.data;
  return (
    <section data-auction-change>
      <h3>{f.selected}</h3>
      <button onClick={() => setRevision((v) => v + 1)}>{c.refresh}</button>
      {result.error ? (
        <p role="alert">{c.failed}</p>
      ) : !data ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          <p>
            {f.detected}: <Timestamp value={data.detected_at} />
          </p>
          <ul>
            {Array.from(
              new Set(
                data.change_codes.map((code) =>
                  auctionChangeLabel(locale, code),
                ),
              ),
            ).map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
          {data.newer_available && <p role="status">{f.newer}</p>}
          {!data.current_configuration && <p role="status">{f.profile}</p>}
          <details>
            <summary>{f.before}</summary>
            {data.previous === null ? (
              <p>{f.first}</p>
            ) : data.previous.facts ? (
              <Evidence facts={data.previous.facts} />
            ) : (
              <p>{w.unavailableVersion}</p>
            )}
          </details>
          <details open>
            <summary>{f.after}</summary>
            {data.snapshot.facts ? (
              <Evidence facts={data.snapshot.facts} />
            ) : (
              <p>{w.unavailableVersion}</p>
            )}
          </details>
          <h3>{f.current}</h3>
          <Lot
            row={data.current}
            monitor={monitor}
            canManage={canManage}
            changed={() => setRevision((v) => v + 1)}
          />
        </>
      )}
    </section>
  );
}
