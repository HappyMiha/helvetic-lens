"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { ipiSourceCopy } from "@/lib/ipi-source-copy";
import { useData } from "./trademark-client";

const sourceTimeZone = "Europe/Zurich";

type SourceState =
  | "disabled"
  | "permission_required"
  | "credentials_required"
  | "permission_unavailable"
  | "configured";
type Traversal = {
  state: "not_started" | "running" | "completed" | "abandoned";
  page_count?: number;
  unique_count?: number;
  duplicate_count?: number;
  next_attempt_at?: string;
  completed_at?: string | null;
  last_error?: string | null;
};

export function IPISourceStatus({ revision }: { revision: number }) {
  const { locale } = useI18n(),
    c = ipiSourceCopy[locale];
  const [refresh, setRefresh] = useState(0);
  const result = useData<{ state: SourceState; traversal: Traversal | null }>(
    "/source-status",
    revision + refresh,
  );
  const row = result.data?.traversal;
  function date(value: string) {
    return new Intl.DateTimeFormat(locale, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: sourceTimeZone,
    }).format(new Date(value));
  }
  return (
    <section aria-labelledby="ipi-source-heading" data-ipi-source-status>
      <h2 id="ipi-source-heading">{c.title}</h2>
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
              <p>{c[row.state]}</p>
              {row.last_error && <p role="status">{c.interruption}</p>}
              {row.page_count !== undefined && (
                <dl>
                  <dt>{c.pages}</dt>
                  <dd>{row.page_count.toLocaleString(locale)}</dd>
                  <dt>{c.unique}</dt>
                  <dd>{row.unique_count?.toLocaleString(locale)}</dd>
                  <dt>{c.repeated}</dt>
                  <dd>{row.duplicate_count?.toLocaleString(locale)}</dd>
                  {row.next_attempt_at && (
                    <>
                      <dt>{c.next}</dt>
                      <dd>
                        <time dateTime={row.next_attempt_at}>
                          {date(row.next_attempt_at)}
                          {" · " + sourceTimeZone}
                        </time>
                      </dd>
                    </>
                  )}
                  {row.completed_at && (
                    <>
                      <dt>{c.finished}</dt>
                      <dd>
                        <time dateTime={row.completed_at}>
                          {date(row.completed_at)}
                          {" · " + sourceTimeZone}
                        </time>
                      </dd>
                    </>
                  )}
                </dl>
              )}
            </>
          )}
        </>
      )}
      <p>{c.limit}</p>
    </section>
  );
}
