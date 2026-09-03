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
  errorText,
  label,
  refreshWorkspace,
  useResource,
} from "@/lib/api";
import type { ConnectorSchedule, ConnectorSchedulePage } from "@/lib/types";
import { ErrorNote, Loading, Status, SuccessNote } from "./common";
import { useAuth } from "./auth-gate";
import { useI18n } from "@/lib/i18n";

function duration(value: number | null, t: (key: string, values?: Record<string, string | number>) => string, number: (value: number, options?: Intl.NumberFormatOptions) => string) {
  if (value === null) return t("connectors.noRun");
  if (value < 1000) return `${value} ms`;
  return `${number(value / 1000, { maximumFractionDigits: value < 10_000 ? 1 : 0 })} s`;
}

function freshness(value: number | null, t: (key: string, values?: Record<string, string | number>) => string) {
  if (value === null) return t("connectors.never");
  if (value < 60) return t("connectors.lessMinute");
  if (value < 3600) return t("connectors.minutes", { count: Math.floor(value / 60) });
  if (value < 86_400) return t("connectors.hours", { count: Math.floor(value / 3600) });
  return t("connectors.days", { count: Math.floor(value / 86_400) });
}

function connectorName(value: string, t: (key: string) => string) {
  if (["fedlex", "finma-news"].includes(value)) return value === "fedlex" ? "Fedlex" : "FINMA";
  const key = `connectors.name.${value}`;
  const result = t(key);
  return result === key ? label(value) : result;
}

function ScheduleCard({
  item,
  onChange,
}: {
  item: ConnectorSchedule;
  onChange: () => void;
}) {
  const { t, dateTime, number } = useI18n();
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
      setMessage(t("connectors.saved"));
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
          ? t("connectors.already")
          : t("connectors.queued"),
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
            {t("connectors.requestFloor", { overlap: item.policy.overlap || t("connectors.overlap"), seconds: item.policy.minimum_request_interval_seconds ?? "source" })}
          </p>
        </div>
        <Button
          size="sm"
          onClick={syncNow}
          disabled={!!busy}
          aria-label={t("connectors.syncLabel", { stream: item.stream })}
        >
          {busy === "sync" ? (
            <Loader2 className="animate-spin" />
          ) : (
            <RefreshCw />
          )}
          {t("connectors.sync")}
        </Button>
      </div>
      <div className="panel-body grid gap-5">
        {item.health_message && item.health !== "healthy" && (
          <ErrorNote message={item.health_message} />
        )}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
          <div className="rounded-lg border p-3">
            <span className="eyebrow">{t("connectors.lastSuccess")}</span>
            <strong className="block mt-2">
              {freshness(item.freshness_lag_seconds, t)}
            </strong>
            <span className="muted">{dateTime(item.last_success_at)}</span>
          </div>
          <div className="rounded-lg border p-3">
            <span className="eyebrow">{t("connectors.nextRun")}</span>
            <strong className="block mt-2">
              {item.enabled ? dateTime(item.next_run_at) : t("connectors.pause")}
            </strong>
            <span className="muted">{t("connectors.window")}</span>
          </div>
          <div className="rounded-lg border p-3">
            <span className="eyebrow">{t("connectors.lastResult")}</span>
            <strong className="block mt-2">
              {label(item.last_run?.status || "not run")}
            </strong>
            <span className="muted">
              {duration(item.last_run?.duration_ms ?? null, t, number)}
            </span>
          </div>
          <div className="rounded-lg border p-3">
            <span className="eyebrow">{t("connectors.counts")}</span>
            <strong className="block mt-2">
              {t("connectors.newChanged", { newCount: item.last_run?.new || 0, changed: item.last_run?.changed || 0 })}
            </strong>
            <span className="muted">
              {t("connectors.failedDelivered", { failed: item.last_run?.failed || 0, delivered: item.last_run?.fanout || 0 })}
            </span>
          </div>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
          <label className="field-label">
            <span>{t("connectors.interval")}</span>
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
            <span>{t("connectors.jitter")}</span>
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
            <span>{t("connectors.windowStart")}</span>
            <Input
              type="time"
              value={draft.window_start || ""}
              onChange={(event) =>
                setDraft({ ...draft, window_start: event.target.value || null })
              }
            />
          </label>
          <label className="field-label">
            <span>{t("connectors.windowEnd")}</span>
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
              {draft.enabled ? t("connectors.pause") : t("connectors.resume")}
            </Button>
            <Button size="sm" onClick={save} disabled={!changed || !!busy}>
              {busy === "save" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Save />
              )}
              {t("connectors.save")}
            </Button>
          </div>
        </div>
        {item.partial_coverage && (
          <p className="text-xs text-amber-800 mb-0">
            {t("connectors.partial")}
          </p>
        )}
        {error && <ErrorNote message={error} />}
        {message && <SuccessNote>{message}</SuccessNote>}
      </div>
    </article>
  );
}

export function ConnectorAdminPage() {
  const { t, number } = useI18n();
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
    <Shell section={t("nav.sync")} wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("connectors.eyebrow")}</span>
          <h1>{t("connectors.title")}</h1>
          <p>
            {t("connectors.body")}
          </p>
        </div>
        <Button variant="outline" onClick={reload} disabled={loading}>
          <RefreshCw className={loading ? "animate-spin" : ""} /> {t("logs.refresh")}
        </Button>
      </div>
      {!isPlatformAdmin ? (
        <ErrorNote message={t("connectors.denied")} />
      ) : (
        <>
          <ErrorNote message={error} />
          {loading && !data ? (
            <Loading text={t("connectors.loading")} />
          ) : data ? (
            <>
              <section className="stats-grid mb-6">
                <div className="stat-card">
                  <Database size={18} />
                  <span className="eyebrow">{t("connectors.streams")}</span>
                  <strong>{data.items.length}</strong>
                  <small>
                    {t("connectors.enabled", { count: data.items.filter((item) => item.enabled).length })}
                  </small>
                </div>
                <div className="stat-card">
                  <Clock3 size={18} />
                  <span className="eyebrow">{t("connectors.work")}</span>
                  <strong>
                    {data.pressure.active}/{data.pressure.active_limit}
                  </strong>
                  <small>
                    {t("connectors.waiting", { count: data.pressure.pending })}
                  </small>
                </div>
                <div className="stat-card">
                  <HardDrive size={18} />
                  <span className="eyebrow">{t("connectors.disk")}</span>
                  <strong>
                    {Math.round(data.pressure.free_megabytes / 1024)} GB
                  </strong>
                  <small>
                    {t("connectors.floor", { size: number(data.pressure.minimum_free_megabytes) })}
                  </small>
                </div>
                <div className="stat-card">
                  {data.pressure.blocked ? (
                    <PauseCircle size={18} />
                  ) : (
                    <PlayCircle size={18} />
                  )}
                  <span className="eyebrow">{t("connectors.backpressure")}</span>
                  <strong>{data.pressure.blocked ? t("connectors.active") : t("connectors.clear")}</strong>
                  <small>
                    {data.pressure.reasons.map(label).join(" · ") ||
                      t("connectors.readsProtected")}
                  </small>
                </div>
              </section>
              <div className="grid gap-8">
                {groups.map(([connector, items]) => (
                  <section key={connector} className="grid gap-3">
                    <div>
                      <span className="eyebrow">{t("connectors.authority")}</span>
                      <h2 className="mt-1">{connectorName(connector, t)}</h2>
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
