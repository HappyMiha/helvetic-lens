"use client";

import { useI18n } from "@/lib/i18n";
import { monitoringProgressCopy } from "@/lib/monitoring-progress-copy";
import {
  monitoringBranch, pollenCompleted, pollenTaskIds, snapshotCounts, tasksAwaitingDeployment,
  type MonitoringProgress, type MonitoringSnapshot, type MonitoringTask,
} from "@/lib/monitoring-progress";

export function MonitoringProgressPanel({ progress, branch, deploying }: {
  progress: MonitoringProgress | null | undefined;
  branch: string | null;
  deploying: boolean;
}) {
  const { locale, dateTime } = useI18n();
  const copy = monitoringProgressCopy[locale];
  if (branch !== monitoringBranch && (branch || progress?.branch !== monitoringBranch)) return null;
  const latest = progress?.latest;
  const deployed = progress?.deployed;
  const gitCounts = snapshotCounts(latest);
  const deployedCounts = snapshotCounts(deployed);
  const awaiting = tasksAwaitingDeployment(latest, deployed);
  const deployedLabel = deploying ? copy.verified : copy.deployed;
  const deployedStatusLabel = deploying ? copy.verified : copy.deployedStatus;

  function taskStatus(snapshot: MonitoringSnapshot | null | undefined, id: string) {
    if (snapshot?.state !== "available") return copy.unavailable;
    const task = snapshot.tasks.find(value => value.id === id);
    return task ? copy.statuses[task.status] : copy.absent;
  }

  function taskRow(id: string, task?: MonitoringTask, pollen = false) {
    return <li key={id} className="grid gap-2 py-3 min-w-0 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]" data-monitoring-task={id} data-monitoring-pollen={pollen || undefined}>
      <div className="min-w-0">
        <code className="text-xs">{id}</code>
        <div className="text-sm break-words" lang={task ? "en" : undefined}>{task?.title || copy.unknownTitle}</div>
      </div>
      <dl className="grid grid-cols-2 gap-3 min-w-0 text-xs">
        <div className="min-w-0"><dt className="muted">{copy.gitStatus}</dt><dd className="font-medium break-words" data-monitoring-latest-status>{taskStatus(latest, id)}</dd></div>
        <div className="min-w-0"><dt className="muted">{deployedStatusLabel}</dt><dd className="font-medium break-words" data-monitoring-deployed-status>{taskStatus(deployed, id)}</dd></div>
      </dl>
    </li>;
  }

  function completionCard(kind: "git" | "deployed", title: string, snapshot: MonitoringSnapshot | null | undefined) {
    const counts = kind === "git" ? gitCounts : deployedCounts;
    return <div className="rounded-lg border bg-white p-4 min-w-0" data-monitoring-card={kind}>
      <h3 className="text-sm font-medium">{title}</h3>
      <p className={`my-2 font-semibold break-words ${counts?.percent != null ? "text-2xl" : "text-base"}`} data-monitoring-percent>
        {counts ? counts.percent === null ? copy.notApplicable : `≈${counts.percent}%` : copy.unavailable}
      </p>
      {counts && <p className="text-sm mb-2" data-monitoring-ratio>{counts.completed.length}/{counts.required.length} {copy.completed}</p>}
      {counts && counts.required.length > 0 && <progress className="block w-full h-2 accent-[var(--primary)]" max={counts.required.length} value={counts.completed.length} aria-label={title} />}
      {counts?.required.length === 0 && <p className="text-xs muted">{copy.noRequired}</p>}
      {!counts && <p className="text-xs muted break-words" lang={snapshot?.reason ? "en" : undefined}>{snapshot?.reason || copy.missingNote}</p>}
      {snapshot?.sha && <p className="text-xs muted mt-3 mb-0">{copy.source}: <code className="block break-all" title={snapshot.sha}>{snapshot.sha.slice(0, 12)}</code></p>}
      {kind === "deployed" && <p className="text-xs muted mt-2 mb-0">{deploying ? copy.verifiedNote : copy.deployedNote}</p>}
    </div>;
  }

  return <section className="panel min-w-0" data-monitoring-progress aria-labelledby="monitoring-progress-title">
    <div className="panel-header"><div>
      <h2 id="monitoring-progress-title">{copy.title}</h2>
      {progress?.updated_at && <p className="text-xs muted mb-0">{copy.updated}: {dateTime(progress.updated_at, {dateStyle: "medium", timeStyle: "short"})}</p>}
    </div></div>
    <div className="panel-body grid gap-4 min-w-0">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 min-w-0">
        {completionCard("git", copy.git, latest)}
        {completionCard("deployed", deployedLabel, deployed)}
        <div className="rounded-lg border bg-white p-4 min-w-0 col-span-2 lg:col-span-1" data-monitoring-card="remaining">
          <h3 className="text-sm font-medium">{copy.remaining}</h3>
          <p className="my-2 text-2xl font-semibold" data-monitoring-remaining-count>{gitCounts ? gitCounts.remaining.length : copy.unavailable}</p>
          {gitCounts && <p className="text-sm mb-0" data-monitoring-in-progress>{gitCounts.inProgress} {copy.inProgress}</p>}
          {!gitCounts && <p className="text-xs muted">{copy.missingNote}</p>}
        </div>
      </div>
      <div className="text-xs muted"><p className="mb-1">{copy.note}</p><p className="mb-0">{copy.mvpNote}</p></div>
      <section className="min-w-0" aria-labelledby="monitoring-pollen-title">
        <h3 id="monitoring-pollen-title" className="font-medium">{copy.pollen}</h3>
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm mt-2 mb-1" data-monitoring-pollen-counts>
          <span>{copy.git}: {pollenCompleted(latest) === null ? copy.unavailable : `${pollenCompleted(latest)}/6`}</span>
          <span>{deployedLabel}: {pollenCompleted(deployed) === null ? copy.unavailable : `${pollenCompleted(deployed)}/6`}</span>
        </div>
        <p className="text-xs muted mb-1">{copy.pollenNote}</p>
        <details className="rounded-lg border px-3 mt-3 min-w-0" data-monitoring-pollen-steps>
          <summary className="min-h-11 cursor-pointer text-sm font-medium py-3">{copy.viewSteps}</summary>
          <ol className="divide-y list-none m-0 p-0">{pollenTaskIds.map(id => taskRow(id,
            latest?.tasks.find(task => task.id === id) || deployed?.tasks.find(task => task.id === id), true))}</ol>
        </details>
      </section>
      <details className="rounded-lg border px-3 min-w-0" data-monitoring-unfinished>
        <summary className="min-h-11 cursor-pointer text-sm font-medium py-3">{copy.unfinished} · {gitCounts ? gitCounts.remaining.length : copy.unavailable}</summary>
        {gitCounts ? gitCounts.remaining.length > 0 ? <ul className="divide-y list-none m-0 p-0">{gitCounts.remaining.map(task => taskRow(task.id, task))}</ul> : <p className="text-sm">{copy.noneRemaining}</p> : <p className="text-sm">{copy.missingNote}</p>}
      </details>
      <details className="rounded-lg border px-3 min-w-0" data-monitoring-awaiting>
        <summary className="min-h-11 cursor-pointer text-sm font-medium py-3">{copy.awaiting} · {awaiting ? awaiting.length : copy.unavailable}</summary>
        {awaiting ? awaiting.length > 0 ? <ul className="divide-y list-none m-0 p-0">{awaiting.map(task => taskRow(task.id, task))}</ul> : <p className="text-sm">{copy.noneAwaiting}</p> : <p className="text-sm">{copy.missingNote}</p>}
      </details>
    </div>
  </section>;
}
