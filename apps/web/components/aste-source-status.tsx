"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { asteSourceCopy } from "@/lib/aste-source-copy";
import { useData } from "./auction-client";

type Collection = {
  known_items: number;
  failed_items: number;
  pending_listing_pages: number;
  last_record_at: string | null;
  last_completed_at: string | null;
  next_request_at: string | null;
  last_error: string | null;
  source_categories: string[];
};
type SourceState =
  | "disabled"
  | "permission_required"
  | "permission_unavailable"
  | "waiting"
  | "configured";
const zone = "Europe/Zurich";

export function AsteSourceStatus({ revision }: { revision: number }) {
  const { locale } = useI18n(),
    c = asteSourceCopy[locale];
  const [refresh, setRefresh] = useState(0);
  const result = useData<{ state: SourceState; collection: Collection | null }>(
    "/source-status",
    revision + refresh,
  );
  const row = result.data?.collection;
  const times = row
    ? [
        [c.lastRecord, row.last_record_at],
        [c.completed, row.last_completed_at],
        [c.next, row.next_request_at],
      ]
    : [];
  return (
    <section aria-labelledby="aste-source-heading" data-aste-source-status>
      <h2 id="aste-source-heading">{c.title}</h2>
      <button type="button" onClick={() => setRefresh((v) => v + 1)}>
        {c.refresh}
      </button>
      {result.error ? (
        <p role="alert">{c.failed}</p>
      ) : !result.data ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          <p>{c[result.data.state]}</p>
          {row && (
            <>
              {(row.last_error || row.failed_items > 0) && (
                <p role="status">{c.interruption}</p>
              )}
              <dl>
                <dt>{c.known}</dt>
                <dd>{row.known_items.toLocaleString(locale)}</dd>
                <dt>{c.failedItems}</dt>
                <dd>{row.failed_items.toLocaleString(locale)}</dd>
                <dt>{c.pages}</dt>
                <dd>{row.pending_listing_pages.toLocaleString(locale)}</dd>
              </dl>
              {times.map(
                ([label, value]) =>
                  value && (
                    <p key={label}>
                      {label}:{" "}
                      <time dateTime={value}>
                        {new Intl.DateTimeFormat(locale, {
                          dateStyle: "medium",
                          timeStyle: "short",
                          timeZone: zone,
                        }).format(new Date(value))}{" "}
                        · {zone}
                      </time>
                    </p>
                  ),
              )}
              {row.source_categories.length > 0 && (
                <p>
                  {c.categories}: {row.source_categories.join(", ")}
                </p>
              )}
            </>
          )}
        </>
      )}
      <p>{c.limit}</p>
    </section>
  );
}
