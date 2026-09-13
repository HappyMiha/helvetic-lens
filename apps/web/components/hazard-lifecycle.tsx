"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import {
  hazardLifecycleCopy,
  readinessReason,
} from "@/lib/hazard-lifecycle-copy";
import { roadCopy, roadLabel } from "@/lib/road-copy";
import type { HazardMonitor, Page } from "@/lib/hazard-watch";
import { useData, useMutation } from "./hazard-data";
import styles from "./commute-watch.module.css";

type Readiness = {
  version: number;
  start_available: boolean;
  source_scope_verified: boolean;
  blocking_reasons: string[];
};
type Action = {
  id: string;
  action: "start" | "resume" | "pause" | "archive";
  status: string;
  version: number;
  created_at: string;
};

function History({ monitor }: { monitor: HazardMonitor }) {
  const { locale } = useI18n(),
    c = hazardLifecycleCopy[locale],
    r = roadCopy[locale];
  const [anchors, setAnchors] = useState<(number | null)[]>([null]);
  const before = anchors.at(-1);
  const result = useData<Page<Action>>(
    `/monitors/${monitor.id}/actions?limit=10${before ? `&before=${before}` : ""}`,
    monitor.version,
  );
  return (
    <section data-hazard-status-history>
      <h4>{c.history}</h4>
      {result.error ? (
        <p role="alert">{r.failed}</p>
      ) : !result.data ? (
        <p role="status">{r.loading}</p>
      ) : (
        <>
          {!result.data.items.length && <p>{c.empty}</p>}
          <ul>
            {result.data.items.map((row) => (
              <li key={row.id}>
                {r[row.action]} · {roadLabel(locale, row.status)} · {r.version}{" "}
                {row.version}
                <p>
                  <time dateTime={row.created_at}>
                    {new Intl.DateTimeFormat(locale, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    }).format(new Date(row.created_at))}
                  </time>
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className={styles.actions}>
        {anchors.length > 1 && (
          <button onClick={() => setAnchors((v) => v.slice(0, -1))}>
            {r.previous}
          </button>
        )}
        {result.data?.next_cursor != null && (
          <button
            onClick={() =>
              setAnchors((v) => [...v, Number(result.data!.next_cursor)])
            }
          >
            {r.more}
          </button>
        )}
      </div>
    </section>
  );
}

export function HazardLifecycle({
  row,
  canManage,
  changed,
}: {
  row: HazardMonitor;
  canManage: boolean;
  changed: () => void;
}) {
  const { locale } = useI18n(),
    c = hazardLifecycleCopy[locale],
    r = roadCopy[locale];
  const [showHistory, setShowHistory] = useState(false),
    [revision, setRevision] = useState(0);
  const result = useData<Readiness>(
    row.status !== "archived" ? `/monitors/${row.id}/readiness` : null,
    revision,
  );
  const mutation = useMutation();
  const current = result.data?.version === row.version ? result.data : null;
  const run = (action: string) =>
    void mutation.run(
      `/monitors/${row.id}/commands`,
      { expected_version: row.version, action },
      changed,
    );
  return (
    <section data-hazard-lifecycle>
      <h3>{c.title}</h3>
      {row.health && <p>{roadLabel(locale, row.health)}</p>}
      {row.last_poll_at && (
        <p>
          {c.checked}:{" "}
          <time dateTime={row.last_poll_at}>
            {new Intl.DateTimeFormat(locale, {
              dateStyle: "medium",
              timeStyle: "short",
            }).format(new Date(row.last_poll_at))}
          </time>
        </p>
      )}
      {row.status === "paused" && <p>{c.stopped}</p>}
      {row.status !== "archived" && (
        <>
          {result.error ? (
            <p role="alert">{r.failed}</p>
          ) : !current ? (
            <p role="status">{r.loading}</p>
          ) : current.blocking_reasons.length ? (
            <ul>
              {[
                ...new Set(
                  current.blocking_reasons.map((code) =>
                    readinessReason(locale, code),
                  ),
                ),
              ].map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : (
            current.start_available && <p>{c.prepared}</p>
          )}
          <p>{c.separate}</p>
        </>
      )}
      <div className={styles.actions}>
        {canManage && (row.status === "draft" || row.status === "paused") && (
          <button
            disabled={mutation.busy || !current?.start_available}
            onClick={() => run(row.status === "draft" ? "start" : "resume")}
          >
            {row.status === "draft" ? r.start : r.resume}
          </button>
        )}
        {canManage && row.status === "active" && (
          <button disabled={mutation.busy} onClick={() => run("pause")}>
            {r.pause}
          </button>
        )}
        {canManage && row.status !== "archived" && (
          <button disabled={mutation.busy} onClick={() => run("archive")}>
            {r.archive}
          </button>
        )}
        {row.status !== "archived" && (
          <button
            disabled={mutation.busy}
            onClick={() => setRevision((v) => v + 1)}
          >
            {r.refresh}
          </button>
        )}
        <button
          aria-expanded={showHistory}
          onClick={() => setShowHistory((v) => !v)}
        >
          {c.history}
        </button>
      </div>
      {mutation.error && <p role="alert">{mutation.error}</p>}
      {showHistory && <History key={row.version} monitor={row} />}
    </section>
  );
}
