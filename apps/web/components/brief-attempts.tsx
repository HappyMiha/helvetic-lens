"use client";
import { useState } from "react";
import { resources, useResource } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { briefAttemptCopy, type BriefAttempts } from "@/lib/brief-attempts";
import { briefDiagnosticsCopy } from "@/lib/brief-diagnostics";
import { ErrorNote, Loading, Status } from "./common";
import { Button } from "./ui/button";

export function BriefAttemptHistory({
  assessmentId,
}: {
  assessmentId: string;
}) {
  const { locale } = useI18n(),
    [open, setOpen] = useState(false);
  return (
    <details
      data-brief-attempts
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary className="min-h-11 py-2 cursor-pointer font-semibold">
        {briefAttemptCopy[locale].title}
      </summary>
      {open && <Content assessmentId={assessmentId} />}
    </details>
  );
}
function Content({ assessmentId }: { assessmentId: string }) {
  const { locale, number, dateTime } = useI18n(),
    copy = briefAttemptCopy[locale],
    common = briefDiagnosticsCopy[locale];
  const resource = useResource(
    resources.briefAttempts<BriefAttempts>(assessmentId),
  );
  const data = !resource.loading && !resource.error ? resource.data : null;
  const format = (n: number | null) =>
    n === null ? common.unknown : number(n);
  return (
    <div className="space-y-3" aria-busy={resource.loading}>
      <p className="text-sm muted">{copy.help}</p>
      {resource.loading && <Loading />}
      <ErrorNote message={resource.error} />
      {data && !data.items.length && <p>{copy.empty}</p>}
      <ol className="space-y-4">
        {data?.items.map((row) => (
          <li
            key={row.number}
            data-brief-attempt={row.number}
            className="rounded-lg border p-3 space-y-3"
          >
            <p>
              {common.attempts} {number(row.number)} ·{" "}
              <time dateTime={row.started_at}>{dateTime(row.started_at, {dateStyle: "medium", timeStyle: "medium"})}</time>{" "}
              · <Status value={row.status} />
            </p>
            {row.error_code && (
              <p>
                {copy.error}: <code>{row.error_code}</code>
              </p>
            )}
            {!row.measurement ? (
              <p>{common.unknown}</p>
            ) : (
              <>
                <p>
                  {copy.http}:{" "}
                  <strong>
                    {number(row.measurement.http_attempts_started)}
                  </strong>{" "}
                  · {copy.elapsed}: {number(row.measurement.elapsed_run_ms)}
                </p>
                <p className="text-sm muted">{copy.coverage}</p>
                <dl className="grid gap-3 sm:grid-cols-3">
                  {[
                    [
                      copy.input,
                      row.measurement.measured_input_tokens,
                      row.measurement.measured_input_requests,
                    ],
                    [
                      copy.output,
                      row.measurement.reported_output_tokens,
                      row.measurement.reported_output_requests,
                    ],
                    [
                      copy.queue,
                      row.measurement.observed_queue_ms,
                      row.measurement.observed_queue_requests,
                    ],
                  ].map(([label, total, count]) => (
                    <div key={String(label)}>
                      <dt className="text-sm">{label}</dt>
                      <dd>
                        <strong>{format(total as number | null)}</strong> ·{" "}
                        {number(count as number)} /{" "}
                        {number(row.measurement!.http_attempts_started)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
          </li>
        ))}
      </ol>
      <Button
        data-attempt-refresh
        variant="outline"
        disabled={resource.loading}
        onClick={resource.reload}
      >
        {common.refresh}
      </Button>
    </div>
  );
}
