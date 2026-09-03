"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Clock3,
  Database,
  HardDrive,
  Loader2,
  PauseCircle,
  PlayCircle,
  RefreshCw,
  Save,
} from "lucide-react";
import { Shell } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  api,
  dateTime,
  errorText,
  label,
  refreshWorkspace,
  useResource,
} from "@/lib/api";
import type { ConnectorSchedule, ConnectorSchedulePage } from "@/lib/types";
import { ErrorNote, Loading, Status, SuccessNote } from "./common";
import { useAuth } from "./auth-gate";

function duration(value: number | null) {
  if (value === null) return "No completed run";
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0)} s`;
}

function freshness(value: number | null) {
  if (value === null) return "Never completed";
  if (value < 60) return "Less than a minute ago";
  if (value < 3600) return `${Math.floor(value / 60)} min ago`;
  if (value < 86_400) return `${Math.floor(value / 3600)} h ago`;
  return `${Math.floor(value / 86_400)} d ago`;
}

function connectorName(value: string) {
  return (
    {
      fedlex: "Fedlex",
      "swiss-parliament": "Swiss Parliament",
      "federal-supreme-court": "Federal Supreme Court",
    }[value] || label(value)
  );
}

function ScheduleCard({
  item,
  onChange,
}: {
  item: ConnectorSchedule;
  onChange: () => void;
}) {
  const [draft, setDraft] = useState(item);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => setDraft(item), [item]);

  async function save() {
    setBusy("save");
    setMessage("");
    setError("");
    try {
      await api(`/admin/connectors/${item.connector}/${item.stream}`, {
        method: "PUT",
        body: JSON.stringify({
          enabled: draft.enabled,
          interval_seconds: Number(draft.interval_seconds),
          jitter_seconds: Number(draft.jitter_seconds),
          window_start: draft.window_start || null,
          window_end: draft.window_end || null,
        }),
      });
      setMessage("Schedule saved.");
      refreshWorkspace();
      onChange();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  async function syncNow() {
    setBusy("sync");
    setMessage("");
    setError("");
    try {
      const result = await api<{ reused: boolean }>(
        `/admin/connectors/${item.connector}/${item.stream}/sync`,
        { method: "POST" },
      );
      setMessage(
        result.reused
          ? "This stream is already queued or running."
          : "One bounded synchronization page was queued.",
      );
      refreshWorkspace();
      onChange();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  const changed =
    draft.enabled !== item.enabled ||
    Number(draft.interval_seconds) !== item.interval_seconds ||
    Number(draft.jitter_seconds) !== item.jitter_seconds ||
    (draft.window_start || null) !== item.window_start ||
    (draft.window_end || null) !== item.window_end;

  return (
    <article className="panel overflow-visible">
      <div className="panel-header">
        <div>
          <div className="flex items-center gap-2">
            <h2>{label(item.stream)}</h2>
            <Status value={item.health} />
            {!item.enabled && <Status value="paused" />}
          </div>
          <p className="text-xs muted mt-1 mb-0">
            {item.policy.overlap || "Incremental overlap"} · request floor{" "}
            {item.policy.minimum_request_interval_seconds ?? "source"} s
          </p>
        </div>
        <Button
          size="sm"
          onClick={syncNow}
          disabled={!!busy}
          aria-label={`Synchronize ${item.stream} now`}
        >
          {busy === "sync" ? (
            <Loader2 className="animate-spin" />
          ) : (
            <RefreshCw />
          )}
          Sync now
        </Button>
      </div>
      <div className="panel-body grid gap-5">
        {item.health_message && item.health !== "healthy" && (
          <ErrorNote message={item.health_message} />
        )}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
          <div className="rounded-lg border p-3">
            <span className="eyebrow">LAST SUCCESS</span>
            <strong className="block mt-2">
              {freshness(item.freshness_lag_seconds)}
            </strong>
            <span className="muted">{dateTime(item.last_success_at)}</span>
          </div>
          <div className="rounded-lg border p-3">
            <span className="eyebrow">NEXT RUN</span>
            <strong className="block mt-2">
              {item.enabled ? dateTime(item.next_run_at) : "Paused"}
            </strong>
            <span className="muted">Europe/Zurich window</span>
          </div>
          <div className="rounded-lg border p-3">
            <span className="eyebrow">LAST RESULT</span>
            <strong className="block mt-2">
              {label(item.last_run?.status || "not run")}
            </strong>
            <span className="muted">
              {duration(item.last_run?.duration_ms ?? null)}
            </span>
          </div>
          <div className="rounded-lg border p-3">
            <span className="eyebrow">COUNTS</span>
            <strong className="block mt-2">
              {item.last_run?.new || 0} new · {item.last_run?.changed || 0}{" "}
              changed
            </strong>
            <span className="muted">
              {item.last_run?.failed || 0} failed · {item.last_run?.fanout || 0}{" "}
              feed deliveries
            </span>
          </div>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
          <label className="field-label">
            <span>Interval (seconds)</span>
            <Input
              type="number"
              min={60}
              max={2_592_000}
              value={draft.interval_seconds}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  interval_seconds: Number(event.target.value),
                })
              }
            />
          </label>
          <label className="field-label">
            <span>Jitter (seconds)</span>
            <Input
              type="number"
              min={0}
              value={draft.jitter_seconds}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  jitter_seconds: Number(event.target.value),
                })
              }
            />
          </label>
          <label className="field-label">
            <span>Window starts</span>
            <Input
              type="time"
              value={draft.window_start || ""}
              onChange={(event) =>
                setDraft({ ...draft, window_start: event.target.value || null })
              }
            />
          </label>
          <label className="field-label">
            <span>Window ends</span>
            <Input
              type="time"
              value={draft.window_end || ""}
              onChange={(event) =>
                setDraft({ ...draft, window_end: event.target.value || null })
              }
            />
          </label>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDraft({ ...draft, enabled: !draft.enabled })}
            >
              {draft.enabled ? <PauseCircle /> : <PlayCircle />}
              {draft.enabled ? "Pause" : "Resume"}
            </Button>
            <Button size="sm" onClick={save} disabled={!changed || !!busy}>
              {busy === "save" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Save />
              )}
              Save
            </Button>
          </div>
        </div>
        {item.partial_coverage && (
          <p className="text-xs text-amber-800 mb-0">
            Partial coverage is saved. The next run resumes from the safe
            checkpoint.
          </p>
        )}
        {error && <ErrorNote message={error} />}
        {message && <SuccessNote>{message}</SuccessNote>}
      </div>
    </article>
  );
}

export function ConnectorAdminPage() {
  const { isPlatformAdmin } = useAuth();
  const { data, error, loading, reload } = useResource<ConnectorSchedulePage>(
    isPlatformAdmin ? "/admin/connectors" : null,
    5000,
  );
  const groups = useMemo(() => {
    const values = new Map<string, ConnectorSchedule[]>();
    for (const item of data?.items || []) {
      values.set(item.connector, [...(values.get(item.connector) || []), item]);
    }
    return [...values.entries()];
  }, [data]);

  return (
    <Shell section="Source sync" wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">OFFICIAL SOURCE OPERATIONS</span>
          <h1>Synchronization control</h1>
          <p>
            Run each official stream once for the shared corpus, then deliver
            its saved events to every matching organization watchlist.
          </p>
        </div>
        <Button variant="outline" onClick={reload} disabled={loading}>
          <RefreshCw className={loading ? "animate-spin" : ""} /> Refresh
        </Button>
      </div>
      {!isPlatformAdmin ? (
        <ErrorNote message="A platform administrator manages shared source synchronization." />
      ) : (
        <>
          <ErrorNote message={error} />
          {loading && !data ? (
            <Loading text="Loading persisted synchronization state…" />
          ) : data ? (
            <>
              <section className="stats-grid mb-6">
                <div className="stat-card">
                  <Database size={18} />
                  <span className="eyebrow">STREAMS</span>
                  <strong>{data.items.length}</strong>
                  <small>
                    {data.items.filter((item) => item.enabled).length} enabled
                  </small>
                </div>
                <div className="stat-card">
                  <Clock3 size={18} />
                  <span className="eyebrow">INGEST WORK</span>
                  <strong>
                    {data.pressure.active}/{data.pressure.active_limit}
                  </strong>
                  <small>
                    {data.pressure.pending} waiting in durable outbox
                  </small>
                </div>
                <div className="stat-card">
                  <HardDrive size={18} />
                  <span className="eyebrow">DOCUMENT DISK</span>
                  <strong>
                    {Math.round(data.pressure.free_megabytes / 1024)} GB
                  </strong>
                  <small>
                    {data.pressure.minimum_free_megabytes} MB safety floor
                  </small>
                </div>
                <div className="stat-card">
                  {data.pressure.blocked ? (
                    <PauseCircle size={18} />
                  ) : (
                    <PlayCircle size={18} />
                  )}
                  <span className="eyebrow">BACKPRESSURE</span>
                  <strong>{data.pressure.blocked ? "Active" : "Clear"}</strong>
                  <small>
                    {data.pressure.reasons.map(label).join(" · ") ||
                      "Interactive reads protected"}
                  </small>
                </div>
              </section>
              <div className="grid gap-8">
                {groups.map(([connector, items]) => (
                  <section key={connector} className="grid gap-3">
                    <div>
                      <span className="eyebrow">AUTHORITY CONNECTOR</span>
                      <h2 className="mt-1">{connectorName(connector)}</h2>
                    </div>
                    {items.map((item) => (
                      <ScheduleCard
                        key={item.id}
                        item={item}
                        onChange={reload}
                      />
                    ))}
                  </section>
                ))}
              </div>
            </>
          ) : null}
        </>
      )}
    </Shell>
  );
}
