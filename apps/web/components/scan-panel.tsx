"use client";

import Link from "next/link";
import { ArrowUpRight, Check, Loader2 } from "lucide-react";
import { dateTime, label } from "@/lib/api";
import type { Scan } from "@/lib/types";
import { ErrorNote, Status } from "./common";

export function ScanPanel({
  scan,
  compact = false,
}: {
  scan: Scan;
  compact?: boolean;
}) {
  const running = ["queued", "running"].includes(scan.status);
  return (
    <section
      className="panel scan-panel"
      aria-label="Scan progress"
      aria-live="polite"
    >
      <div className="panel-header">
        <div className="flex items-center gap-3">
          {running ? (
            <Loader2 size={18} className="animate-spin text-primary" />
          ) : (
            <Check size={18} />
          )}
          <div>
            <h2>{running ? "Checking your sources" : "Scan result"}</h2>
            <p className="text-xs muted m-0 mt-1">
              {dateTime(scan.created_at)} · {scan.completed} of {scan.total}{" "}
              documents finished
            </p>
          </div>
        </div>
        <Status value={scan.status} />
      </div>
      <progress
        className="scan-progress"
        value={scan.completed}
        max={scan.total || 1}
        aria-label="Documents finished"
      />
      <div className="scan-items">
        {scan.items.map((item) => (
          <div className="scan-item" key={item.id}>
            <div className="flex justify-between gap-4 items-start">
              <div className="min-w-0">
                <Link
                  className="font-semibold hover:underline"
                  href={"/laws/" + item.law_id}
                >
                  {item.law_name}
                </Link>
                <p className="text-xs muted m-0 mt-1">
                  {["complete", "failed", "interrupted"].includes(item.stage)
                    ? "Finished"
                    : label(item.stage)}{" "}
                  · Apertus: {label(item.analysis_status)}
                </p>
              </div>
              <Status value={item.result || item.stage} />
            </div>
            {item.mode === "historical" && (
              <p className="text-xs historical-note">
                Historical comparison · the current live check was{" "}
                {label(item.live_result)}. This is not a newly observed
                amendment.
              </p>
            )}
            <ErrorNote message={item.error} />
            <div className="flex items-center justify-between gap-3 mt-2">
              {!compact && (
                <details className="text-xs muted">
                  <summary>Actual processing stages</summary>
                  <ol className="event-list">
                    {item.events.map((event, index) => (
                      <li key={index}>
                        {label(event.stage)} <time>{dateTime(event.at)}</time>
                      </li>
                    ))}
                  </ol>
                </details>
              )}
              {item.comparison_id && (
                <Link
                  className="text-primary text-xs flex items-center gap-1 ml-auto"
                  href={"/compare/" + item.comparison_id}
                >
                  Open comparison
                  <ArrowUpRight size={13} />
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
