"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp, RefreshCw } from "lucide-react";
import { invalidateResources, resourceTag, resources, useResource } from "@/lib/api";
import { deploymentHistoryCopy } from "@/lib/deployment-history-copy";
import { useI18n } from "@/lib/i18n";
import type { DeploymentRun } from "@/lib/types";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { ErrorNote, Loading } from "./common";

function Detail({ id, render }: { id: string; render: (run: DeploymentRun) => ReactNode }) {
  const { t } = useI18n();
  const detail = useResource(resources.deploymentRun(id));
  return <div id={`deployment-${id}`} data-deployment-detail={id} className="min-w-0 rounded-lg border p-4 mt-3">
    <ErrorNote message={detail.error} />
    {detail.error && <Button className="min-h-11" variant="outline" onClick={detail.reload}>{t("logs.refresh")}</Button>}
    {detail.loading && !detail.data ? <Loading text={t("deploy.loading")} /> : null}
    {detail.data ? render(detail.data) : null}
  </div>;
}

export function DeploymentHistory({ renderDetails }: { renderDetails: (run: DeploymentRun) => ReactNode }) {
  const { locale, t, dateTime } = useI18n();
  const copy = deploymentHistoryCopy[locale];
  const [filter, setFilter] = useState("");
  const [cursors, setCursors] = useState<string[]>([""]);
  const [selected, setSelected] = useState<string | null>(null);
  const current = cursors[cursors.length - 1];
  const history = useResource(resources.deploymentHistory(filter, current));
  async function latest() {
    setCursors([""]); setSelected(null);
    // Invalidate the destination page too, not only the older page being left.
    try { await invalidateResources(resourceTag("deployments", "platform")); }
    catch { /* The mounted resource renders its own retryable error state. */ }
  }
  return <section data-deployment-history className="panel min-w-0" aria-label={t("deploy.history")}>
    <div className="panel-header flex-wrap gap-3">
      <div className="min-w-0"><h2>{t("deploy.history")}</h2><p className="text-sm muted mb-0">{copy.body}</p></div>
      <Button className="min-h-11" variant="outline" onClick={latest} disabled={history.loading}><RefreshCw size={16} />{copy.latest}</Button>
    </div>
    <div className="panel-body min-w-0">
      <label className="grid gap-2 mb-4 text-sm font-medium">{copy.all}
        <select data-deployment-filter className="min-h-11 w-full sm:max-w-xs" value={filter} onChange={event => {
          setFilter(event.target.value); setCursors([""]); setSelected(null);
        }}>
          <option value="">{copy.all}</option>
          {Object.entries(copy.statuses).map(([value, title]) => <option key={value} value={value}>{title}</option>)}
        </select>
      </label>
      <p className="text-sm muted">{copy.retention}</p>
      <ErrorNote message={history.error} />
      {history.error && <Button className="min-h-11" variant="outline" onClick={history.reload}>{t("logs.refresh")}</Button>}
      {history.loading && !history.data ? <Loading text={t("deploy.loading")} /> : null}
      {history.data?.items.length === 0 ? <p>{t("deploy.noRuns")}</p> : null}
      <div className="divide-y">
        {history.data?.items.map(run => <article key={run.id} className="py-4 min-w-0">
          <button data-deployment-run={run.id} type="button" className="w-full min-h-11 text-left flex flex-wrap items-center justify-between gap-3 rounded-md p-2 hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2"
            aria-expanded={selected === run.id} aria-controls={selected === run.id ? `deployment-${run.id}` : undefined}
            onClick={() => setSelected(selected === run.id ? null : run.id)}>
            <span className="min-w-0"><strong className="block break-all"><code>{run.target_sha?.slice(0,12) || copy.unknown}</code></strong>
              <span className="text-sm muted block">{dateTime(run.started_at, {dateStyle: "medium", timeStyle: "medium"})}</span>
              <span className="text-sm block">{selected === run.id ? copy.close : copy.details}</span>
            </span>
            <span className="flex items-center gap-3"><Badge variant={["failed","rollback_failed"].includes(run.status) ? "destructive" : "outline"}>{copy.statuses[run.status] || run.status}</Badge>
              {selected === run.id ? <ChevronUp aria-hidden="true" size={18} /> : <ChevronDown aria-hidden="true" size={18} />}
            </span>
          </button>
          {selected === run.id ? <Detail id={run.id} render={renderDetails} /> : null}
        </article>)}
      </div>
      <nav className="flex flex-wrap items-center justify-between gap-3 pt-4 pb-16 border-t" aria-label={t("deploy.history")}>
        <Button className="min-h-11" data-deployment-back variant="outline" disabled={cursors.length === 1 || history.loading} onClick={() => {setCursors(old => old.slice(0,-1));setSelected(null);}}>{copy.previous}</Button>
        <span aria-live="polite">{cursors.length}</span>
        <Button className="min-h-11" data-deployment-next variant="outline" disabled={!history.data?.next_cursor || history.loading || Boolean(history.error)} onClick={() => {
          if (history.data?.next_cursor) {setCursors(old => [...old, history.data!.next_cursor!]);setSelected(null);}
        }}>{copy.next}</Button>
      </nav>
    </div>
  </section>;
}
