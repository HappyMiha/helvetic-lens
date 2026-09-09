"use client";
import { useState } from "react";
import { resources, useResource } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { briefReuseCopy, type BriefReuse } from "@/lib/brief-reuse";
import { briefDiagnosticsCopy } from "@/lib/brief-diagnostics";
import { ErrorNote, Loading } from "./common";
import { Button } from "./ui/button";

export function BriefReuseHistory({ assessmentId }: { assessmentId: string }) {
  const { locale } = useI18n(),
    [open, setOpen] = useState(false);
  return (
    <details
      data-brief-reuse
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="min-h-11 py-2 cursor-pointer font-semibold">
        {briefReuseCopy[locale].title}
      </summary>
      {open && <Content assessmentId={assessmentId} />}
    </details>
  );
}
function Content({ assessmentId }: { assessmentId: string }) {
  const { locale, number } = useI18n(),
    copy = briefReuseCopy[locale],
    common = briefDiagnosticsCopy[locale];
  const [days, setDays] = useState(7);
  const resource = useResource(
    resources.briefReuse<BriefReuse>(assessmentId, days),
  );
  const data = !resource.loading && !resource.error ? resource.data : null;
  return (
    <div className="space-y-3" aria-busy={resource.loading}>
      <p className="text-sm muted">{copy.help}</p>
      <label>
        {common.days}
        <select
          data-reuse-days
          className="field block"
          value={days}
          onChange={(event) => setDays(Number(event.target.value))}
        >
          {[1, 7, 30, 90].map((n) => (
            <option key={n} value={n}>
              {number(n)}
            </option>
          ))}
        </select>
      </label>
      {resource.loading && <Loading />}
      <ErrorNote message={resource.error} />
      {data && !data.items.length && <p data-reuse-empty>{copy.empty}</p>}
      {data && (
        <p>
          {data.start_day} – {data.end_day} {data.calendar_timezone}
        </p>
      )}
      <dl className="space-y-3">
        {data?.items.map((row) => (
          <div key={row.surface} data-reuse-surface={row.surface}>
            <dt>{copy[row.surface]}</dt>
            <dd>
              {copy.count}: <strong>{number(row.projections)}</strong>
            </dd>
          </div>
        ))}
      </dl>
      <Button
        data-reuse-refresh
        variant="outline"
        disabled={resource.loading}
        onClick={resource.reload}
      >
        {common.refresh}
      </Button>
    </div>
  );
}
