"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { airCopy } from "@/lib/air-copy";
import {
  AIR_METRICS,
  AIR_UNIT,
  AIR_STATION_NAME,
  invalidAir,
  type AirChange,
  type AirConfiguration,
  type AirCoverage,
  type AirMetric,
  type AirMonitor,
  type AirPreview,
  type AirRule,
  type AirSample,
  type AirStation,
  type AirTodayEntry,
} from "@/lib/air-watch";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import styles from "./river-watch.module.css";

const base = "/air-watch";
const post = (body: unknown, method = "POST") => ({
  method,
  body: JSON.stringify(body),
});
type Copy = (typeof airCopy)["en-CH"];
const label = (c: Copy, key: string) => c[key as keyof Copy] || c.unknown;
const failure = (c: Copy, e: unknown) =>
  e instanceof ApiError && e.code === "air_source_not_ready"
    ? c.unavailable
    : e instanceof ApiError &&
        [
          "air_version_conflict",
          "air_newer_change",
          "air_state_conflict",
        ].includes(e.code)
      ? c.conflict
      : c.failed;

function Sample({ sample }: { sample: AirSample }) {
  const { locale } = useI18n();
  const c = airCopy[locale];
  return (
    <div className={styles.sample}>
      <strong>
        {c[sample.metric]}: {sample.value ?? c.unknown} {sample.unit}
      </strong>
      <span>
        {c.period}: {c[sample.period]}
      </span>
      <span>
        {c.time}: {new Date(sample.timestamp).toLocaleString(locale)}
      </span>
      <span>
        {c.quality}: {label(c, sample.quality)} · {c.revision} {sample.revision}
      </span>
      {sample.derived && <span>{c.derived}</span>}
      {sample.corrected && <span>{c.corrected}</span>}
      <a href={sample.source_url} target="_blank" rel="noreferrer">
        {c.source} · {c.attribution}
      </a>
      <a href={sample.license_url} target="_blank" rel="noreferrer">
        {c.license}
      </a>
    </div>
  );
}

function Coverage({ coverage }: { coverage: AirCoverage }) {
  const { locale } = useI18n();
  const c = airCopy[locale];
  return (
    <div className={styles.coverage}>
      {Object.entries(coverage).map(([key, entry]) => (
        <section key={key} className={styles.card}>
          <h3>
            {label(c, key.split(":")[0])} · {label(c, entry.status)}
          </h3>
          {entry.sample ? <Sample sample={entry.sample} /> : <p>{c.unknown}</p>}
        </section>
      ))}
    </div>
  );
}

function Editor({
  stations,
  monitor,
  onSaved,
  onCancel,
}: {
  stations: AirStation[];
  monitor?: AirMonitor;
  onSaved: (m: AirMonitor) => void;
  onCancel: () => void;
}) {
  const { locale } = useI18n();
  const c = airCopy[locale];
  const [config, setConfig] = useState<AirConfiguration>(
    monitor?.configuration || {
      name: "",
      station_id: "",
      metrics: [...AIR_METRICS],
      muted_metrics: [],
      rules: [],
    },
  );
  const [search, setSearch] = useState("");
  const [preview, setPreview] = useState<AirPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [requestKey] = useState(() => crypto.randomUUID());
  const change = (next: AirConfiguration) => {
    setConfig(next);
    setPreview(null);
    setError("");
  };
  const rule = (index: number, next: AirRule) =>
    change({
      ...config,
      rules: config.rules.map((r, i) => (i === index ? next : r)),
    });
  async function run(save: boolean) {
    if (invalidAir(config)) {
      setError(c.invalid);
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (save)
        onSaved(
          await api<AirMonitor>(
            monitor ? `${base}/monitors/${monitor.id}` : `${base}/monitors`,
            post(
              monitor
                ? { configuration: config, expected_version: monitor.version }
                : { configuration: config, request_key: requestKey },
              monitor ? "PATCH" : "POST",
            ),
          ),
        );
      else
        setPreview(
          await api<AirPreview>(
            `${base}/preview`,
            post({ configuration: config }),
          ),
        );
    } catch (e) {
      setError(failure(c, e));
    } finally {
      setBusy(false);
    }
  }
  const filtered = stations.filter(
    (s) =>
      `${s.name} ${s.area}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()) || s.id === config.station_id,
  );
  return (
    <form
      className={styles.card}
      onSubmit={(e) => {
        e.preventDefault();
        void run(false);
      }}
    >
      <h2>{monitor ? c.edit : c.create}</h2>
      <p>{c.scope}</p>
      <label>
        {c.name}
        <input
          required
          maxLength={100}
          value={config.name}
          onChange={(e) => change({ ...config, name: e.target.value })}
        />
      </label>
      <label>
        {c.search}
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </label>
      {!filtered.length && <p role="status">{c.noMatch}</p>}
      <label>
        {c.station}
        <select
          required
          value={config.station_id}
          onChange={(e) => change({ ...config, station_id: e.target.value })}
        >
          <option value="">{c.choose}</option>
          {filtered.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} · {s.area}
            </option>
          ))}
        </select>
      </label>
      <fieldset>
        <legend>{c.metrics}</legend>
        {AIR_METRICS.map((metric) => (
          <label key={metric} className={styles.check}>
            <input
              type="checkbox"
              checked={config.metrics.includes(metric)}
              onChange={(e) =>
                change({
                  ...config,
                  metrics: e.target.checked
                    ? [...config.metrics, metric]
                    : config.metrics.filter((m) => m !== metric),
                  rules: e.target.checked
                    ? config.rules
                    : config.rules.filter((r) => r.metric !== metric),
                  muted_metrics: config.muted_metrics.filter(
                    (m) => m !== metric,
                  ),
                })
              }
            />
            {c[metric]}
          </label>
        ))}
      </fieldset>
      <h3>{c.rules}</h3>
      <p>{c.ruleHelp}</p>
      {config.rules.map((r, i) => (
        <fieldset key={i}>
          <legend>
            {c.threshold} {i + 1}
          </legend>
          <label>
            {c.metrics}
            <select
              value={r.metric}
              onChange={(e) =>
                rule(i, { ...r, metric: e.target.value as AirMetric })
              }
            >
              {config.metrics.map((m) => (
                <option key={m} value={m}>
                  {c[m]}
                </option>
              ))}
            </select>
          </label>
          <label>
            {c.period}
            <select
              value={r.period}
              onChange={(e) =>
                rule(i, { ...r, period: e.target.value as AirRule["period"] })
              }
            >
              {(["hourly_mean", "rolling_24h_mean"] as const).map((p) => (
                <option key={p} value={p}>
                  {c[p]}
                </option>
              ))}
            </select>
          </label>
          <label>
            {c.threshold} ({AIR_UNIT})
            <input
              required
              type="number"
              min="0.0001"
              max="10000"
              step="any"
              value={r.threshold}
              onChange={(e) => rule(i, { ...r, threshold: e.target.value })}
            />
          </label>
          <label>
            {c.hysteresis}
            <input
              required
              type="number"
              min="0"
              max="10000"
              step="any"
              value={r.hysteresis}
              onChange={(e) => rule(i, { ...r, hysteresis: e.target.value })}
            />
          </label>
          <label>
            {c.cooldown}
            <input
              required
              type="number"
              min="1"
              max="48"
              step="1"
              value={r.cooldown_hours}
              onChange={(e) =>
                rule(i, { ...r, cooldown_hours: Number(e.target.value) })
              }
            />
          </label>
          <button
            type="button"
            onClick={() =>
              change({
                ...config,
                rules: config.rules.filter((_, n) => i !== n),
              })
            }
          >
            {c.remove} {i + 1}
          </button>
        </fieldset>
      ))}
      <button
        type="button"
        disabled={!config.metrics.length || config.rules.length >= 8}
        onClick={() =>
          change({
            ...config,
            rules: [
              ...config.rules,
              {
                metric: config.metrics[0],
                period: "hourly_mean",
                threshold: "",
                hysteresis: "0",
                cooldown_hours: 6,
              },
            ],
          })
        }
      >
        {c.add}
      </button>
      {error && <p role="alert">{error}</p>}
      {preview && (
        <>
          <Coverage coverage={preview.coverage} />
          {!preview.start_available && <p>{c.unavailable}</p>}
        </>
      )}
      <div className={styles.actions}>
        <button type="submit" disabled={busy}>
          {busy ? c.loading : c.preview}
        </button>
        <button
          type="button"
          disabled={busy || !preview}
          onClick={() => void run(true)}
        >
          {monitor ? c.saveEdit : c.save}
        </button>
        <button type="button" disabled={busy} onClick={onCancel}>
          {c.cancel}
        </button>
      </div>
    </form>
  );
}

export function AirEvent({
  event,
  canManage,
  busy,
  onReview,
}: {
  event: AirChange;
  canManage: boolean;
  busy: boolean;
  onReview: (e: AirChange, decision: string) => void;
}) {
  const { locale } = useI18n();
  const c = airCopy[locale];
  return (
    <article className={styles.event}>
      <h3>{label(c, event.kind)}</h3>
      <p>{c.why}</p>
      <p>
        {c.threshold}: {event.evidence.rule.threshold} {AIR_UNIT} ·{" "}
        {c[event.evidence.rule.period]}
      </p>
      <p>{c.currentValue}</p>
      <Sample sample={event.evidence.sample} />
      {event.evidence.baseline && (
        <>
          <p>{c.previous}</p>
          <Sample sample={event.evidence.baseline} />
        </>
      )}
      {event.evidence.corrected && <p>{c.corrected}</p>}
      {event.evidence.recovered && <p>{c.recovered}</p>}
      {event.decision && <p>{label(c, event.decision)}</p>}
      {canManage && (
        <div role="group" aria-label={c.review} className={styles.actions}>
          {["reviewed", "not_relevant", "continue", "action_required"].map(
            (d) => (
              <button
                key={d}
                disabled={busy}
                onClick={() => onReview(event, d)}
              >
                {label(c, d)}
              </button>
            ),
          )}
        </div>
      )}
    </article>
  );
}

type ChangePage = { items: AirChange[]; next_before: number | null };
type SamplePage = {
  items: AirSample[];
  next: { before: string; before_id: string } | null;
};
type RevisionPage = {
  items: { revision: number; configuration: AirConfiguration }[];
  next_before: number | null;
};

function Detail({
  id,
  stations,
  canManage,
  refreshToken,
  changed,
  deleted,
}: {
  id: string;
  stations: AirStation[];
  canManage: boolean;
  refreshToken: number;
  changed: () => void;
  deleted: () => void;
}) {
  const { locale } = useI18n();
  const c = airCopy[locale];
  const [row, setRow] = useState<AirMonitor | null>(null);
  const [changes, setChanges] = useState<ChangePage>({
    items: [],
    next_before: null,
  });
  const [history, setHistory] = useState<SamplePage>({ items: [], next: null });
  const [revisions, setRevisions] = useState<RevisionPage>({
    items: [],
    next_before: null,
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [preview, setPreview] = useState<AirPreview | null>(null);
  useEffect(() => {
    const abort = new AbortController();
    async function load() {
      try {
        const [r, events] = await Promise.all([
          api<AirMonitor>(`${base}/monitors/${id}`, { signal: abort.signal }),
          api<ChangePage>(`${base}/monitors/${id}/changes`, {
            signal: abort.signal,
          }),
        ]);
        if (!abort.signal.aborted) {
          setRow(r);
          setChanges(events);
          setError("");
        }
      } catch (e) {
        if (!abort.signal.aborted) setError(failure(c, e));
      }
    }
    void load();
    const timer = setInterval(() => void load(), 60000);
    return () => {
      abort.abort();
      clearInterval(timer);
    };
  }, [id, refreshToken, c]);
  async function action(kind: string, metric?: AirMetric) {
    if (!row) return;
    setBusy(true);
    setError("");
    try {
      if (kind === "preview")
        setPreview(
          await api<AirPreview>(
            `${base}/preview`,
            post({ configuration: row.configuration }),
          ),
        );
      else if (kind === "delete") {
        if (window.confirm(c.confirm)) {
          await api(
            `${base}/monitors/${id}`,
            post({ expected_version: row.version }, "DELETE"),
          );
          deleted();
        }
      } else {
        setRow(
          await api<AirMonitor>(
            `${base}/monitors/${id}/${metric ? "mute" : "command"}`,
            post(
              metric
                ? {
                    expected_version: row.version,
                    metric,
                    muted: !row.configuration.muted_metrics.includes(metric),
                  }
                : { expected_version: row.version, action: kind },
            ),
          ),
        );
        setPreview(null);
        changed();
      }
    } catch (e) {
      setError(failure(c, e));
    } finally {
      setBusy(false);
    }
  }
  async function review(event: AirChange, decision: string) {
    setBusy(true);
    try {
      const saved = await api<AirChange>(
        `${base}/monitors/${id}/changes/${event.id}/review`,
        post({ expected_version: event.review_version, decision }),
      );
      setChanges((old) => ({
        ...old,
        items: old.items.map((e) => (e.id === saved.id ? saved : e)),
      }));
    } catch (e) {
      setError(failure(c, e));
    } finally {
      setBusy(false);
    }
  }
  async function loadHistory(
    kind: "measurements" | "changes" | "revisions",
    more = false,
  ) {
    setBusy(true);
    setError("");
    try {
      if (kind === "measurements") {
        const page = await api<SamplePage>(
          `${base}/monitors/${id}/measurements${more && history.next ? `?${new URLSearchParams(history.next)}` : ""}`,
        );
        setHistory({
          ...page,
          items: more ? [...history.items, ...page.items] : page.items,
        });
      } else if (kind === "changes") {
        const page = await api<ChangePage>(
          `${base}/monitors/${id}/changes${more ? `?before=${changes.next_before}` : ""}`,
        );
        setChanges({
          ...page,
          items: more ? [...changes.items, ...page.items] : page.items,
        });
      } else {
        const page = await api<RevisionPage>(
          `${base}/monitors/${id}/revisions${more ? `?before=${revisions.next_before}` : ""}`,
        );
        setRevisions({
          ...page,
          items: more ? [...revisions.items, ...page.items] : page.items,
        });
      }
    } catch (e) {
      setError(failure(c, e));
    } finally {
      setBusy(false);
    }
  }
  if (!row) return <p role="status">{error || c.loading}</p>;
  if (editing)
    return (
      <Editor
        stations={stations}
        monitor={row}
        onCancel={() => setEditing(false)}
        onSaved={(r) => {
          setRow(r);
          setEditing(false);
          setPreview(null);
          setHistory({ items: [], next: null });
          changed();
        }}
      />
    );
  return (
    <section className={styles.detail}>
      <div className={styles.card}>
        <h2>{row.configuration.name}</h2>
        <p>
          {label(c, row.status)} · {label(c, row.health)} · {c.revision}{" "}
          {row.revision}
        </p>
        <p>
          {AIR_STATION_NAME} · {c.scope}
        </p>
        {row.configuration.rules.map((r, i) => (
          <p key={i}>
            {c[r.metric]} · {c[r.period]} · {c.threshold}: {r.threshold}{" "}
            {AIR_UNIT} · {c.hysteresis}: {r.hysteresis} · {c.cooldown}:{" "}
            {r.cooldown_hours}
          </p>
        ))}
        <div className={styles.actions}>
          <button disabled={busy} onClick={changed}>
            {c.refresh}
          </button>
          {canManage && (
            <>
              {(row.status === "draft" || row.status === "paused") && (
                <>
                  <button
                    disabled={busy}
                    onClick={() => void action("preview")}
                  >
                    {c.preview}
                  </button>
                  <button
                    disabled={busy || !preview?.start_available}
                    onClick={() =>
                      void action(row.status === "draft" ? "start" : "resume")
                    }
                  >
                    {row.status === "draft" ? c.start : c.resume}
                  </button>
                  <button disabled={busy} onClick={() => setEditing(true)}>
                    {c.edit}
                  </button>
                </>
              )}
              {row.status === "active" && (
                <button disabled={busy} onClick={() => void action("pause")}>
                  {c.pause}
                </button>
              )}
              {row.status !== "archived" && (
                <>
                  <button
                    disabled={busy}
                    onClick={() => void action("archive")}
                  >
                    {c.archive}
                  </button>
                  {row.configuration.metrics.map((m) => (
                    <button
                      key={m}
                      disabled={busy}
                      onClick={() => void action("mute", m)}
                    >
                      {row.configuration.muted_metrics.includes(m)
                        ? c.unmute
                        : c.mute}
                      : {c[m]}
                    </button>
                  ))}
                </>
              )}
              <button disabled={busy} onClick={() => void action("delete")}>
                {c.delete}
              </button>
            </>
          )}
        </div>
        {error && <p role="alert">{error}</p>}
        {busy && <p role="status">{c.loading}</p>}
        <Coverage coverage={preview?.coverage || row.state.coverage || {}} />
        {Boolean(row.state.last_gap) && <p>{c.gap}</p>}
      </div>
      <section className={styles.card}>
        <h2>{c.changes}</h2>
        {!changes.items.length && <p>{c.noChanges}</p>}
        {changes.items.map((e) => (
          <AirEvent
            key={e.id}
            event={e}
            busy={busy}
            canManage={
              canManage &&
              !changes.items.some(
                (n) =>
                  n.development_id === e.development_id &&
                  n.sequence > e.sequence,
              )
            }
            onReview={(event, decision) => void review(event, decision)}
          />
        ))}
        {changes.next_before && (
          <button
            disabled={busy}
            onClick={() => void loadHistory("changes", true)}
          >
            {c.more}
          </button>
        )}
      </section>
      <section className={styles.card}>
        <h2>{c.measurements}</h2>
        <button
          disabled={busy}
          onClick={() => void loadHistory("measurements")}
        >
          {c.measurements}
        </button>
        <div className={styles.samples}>
          {history.items.map((s, i) => (
            <Sample key={i} sample={s} />
          ))}
        </div>
        {history.next && (
          <button
            disabled={busy}
            onClick={() => void loadHistory("measurements", true)}
          >
            {c.more}
          </button>
        )}
      </section>
      <section className={styles.card}>
        <h2>{c.settings}</h2>
        <button disabled={busy} onClick={() => void loadHistory("revisions")}>
          {c.settings}
        </button>
        {revisions.items.map((r) => (
          <div key={r.revision}>
            <h3>
              {c.revision} {r.revision}: {r.configuration.name}
            </h3>
            {r.configuration.rules.map((rule, i) => (
              <p key={i}>
                {c[rule.metric]} · {c[rule.period]} · {c.threshold}:{" "}
                {rule.threshold} {AIR_UNIT} · {c.hysteresis}: {rule.hysteresis}{" "}
                · {c.cooldown}: {rule.cooldown_hours}
              </p>
            ))}
            <p>
              {c.muted}:{" "}
              {r.configuration.muted_metrics.map((m) => c[m]).join(", ") || "—"}
            </p>
          </div>
        ))}
        {revisions.next_before && (
          <button
            disabled={busy}
            onClick={() => void loadHistory("revisions", true)}
          >
            {c.more}
          </button>
        )}
      </section>
    </section>
  );
}

export function AirWatch() {
  const { session } = useAuth();
  const params = useSearchParams();
  const scope = session?.authenticated
    ? `${session.user?.id}:${session.organization?.id}:${session.role}`
    : "unavailable";
  return (
    <Reader
      key={scope}
      allowed={scope !== "unavailable"}
      canManage={session?.role === "organization_admin"}
      initial={params.get("monitor") || ""}
    />
  );
}
function Reader({
  allowed,
  canManage,
  initial,
}: {
  allowed: boolean;
  canManage: boolean;
  initial: string;
}) {
  const { locale } = useI18n();
  const c = airCopy[locale];
  const [stations, setStations] = useState<AirStation[]>([]);
  const [rows, setRows] = useState<AirMonitor[]>([]);
  const [selected, setSelected] = useState(initial);
  const [creating, setCreating] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setSelected(initial);
  }, [initial]);
  useEffect(() => {
    if (!allowed) return;
    const abort = new AbortController();
    Promise.all([
      api<{ stations: AirStation[] }>(`${base}/stations`, {
        signal: abort.signal,
      }),
      api<{ items: AirMonitor[] }>(`${base}/monitors`, {
        signal: abort.signal,
      }),
    ])
      .then(([catalog, monitors]) => {
        if (!abort.signal.aborted) {
          setStations(catalog.stations);
          setRows(monitors.items);
          setError("");
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!abort.signal.aborted) {
          setError(failure(c, e));
          setLoading(false);
        }
      });
    return () => abort.abort();
  }, [allowed, refresh, c]);
  const changed = () => setRefresh((n) => n + 1);
  return (
    <Shell section={c.title}>
      <div className={styles.root} data-air-watch>
        <header className="page-heading">
          <div>
            <h1>{c.title}</h1>
            <p>{c.intro}</p>
          </div>
        </header>
        <p>{c.scope}</p>
        <p>{c.limits}</p>
        <div className={styles.actions}>
          <button disabled={!allowed} onClick={changed}>
            {c.refresh}
          </button>
          {canManage && (
            <button
              disabled={!stations.length}
              onClick={() => {
                setCreating(true);
                setSelected("");
              }}
            >
              {c.create}
            </button>
          )}
          <Link href="/">{c.today}</Link>
        </div>
        {!canManage && <p>{c.readonly}</p>}
        {loading && allowed && <p role="status">{c.loading}</p>}
        {error && <p role="alert">{error}</p>}
        <div className={styles.layout}>
          <aside className={styles.list} aria-label={c.title}>
            {!loading && !rows.length && <p>{c.empty}</p>}
            {rows.map((r) => (
              <button
                key={r.id}
                aria-pressed={r.id === selected}
                onClick={() => {
                  setSelected(r.id);
                  setCreating(false);
                }}
              >
                {r.configuration.name} · {label(c, r.status)}
              </button>
            ))}
          </aside>
          {creating ? (
            <Editor
              stations={stations}
              onCancel={() => setCreating(false)}
              onSaved={(r) => {
                setCreating(false);
                setSelected(r.id);
                changed();
              }}
            />
          ) : selected ? (
            <Detail
              key={selected}
              id={selected}
              stations={stations}
              canManage={canManage}
              refreshToken={refresh}
              changed={changed}
              deleted={() => {
                setSelected("");
                changed();
              }}
            />
          ) : null}
        </div>
      </div>
    </Shell>
  );
}

export function AirToday() {
  const { session } = useAuth();
  const scope = session?.authenticated
    ? `${session.user?.id}:${session.organization?.id}:${session.role}`
    : "unavailable";
  return (
    <TodayReader
      key={scope}
      allowed={scope !== "unavailable"}
      canManage={session?.role === "organization_admin"}
    />
  );
}
function TodayReader({
  allowed,
  canManage,
}: {
  allowed: boolean;
  canManage: boolean;
}) {
  const { locale } = useI18n();
  const c = airCopy[locale];
  const [page, setPage] = useState<{
    items: AirTodayEntry[];
    next: { before: string; before_id: string } | null;
  }>({ items: [], next: null });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!allowed) return;
    const abort = new AbortController();
    api<typeof page>(`${base}/today`, { signal: abort.signal })
      .then((p) => {
        if (!abort.signal.aborted) setPage(p);
      })
      .catch((e) => {
        if (
          !abort.signal.aborted &&
          !(e instanceof ApiError && e.code === "air_disabled")
        )
          setError(c.failed);
      });
    return () => abort.abort();
  }, [allowed, c]);
  async function review(
    entry: AirTodayEntry,
    event: AirChange,
    decision: string,
  ) {
    setBusy(true);
    try {
      const saved = await api<AirChange>(
        `${base}/monitors/${entry.monitor_id}/changes/${event.id}/review`,
        post({ expected_version: event.review_version, decision }),
      );
      setPage((p) => ({
        ...p,
        items: p.items.map((i) => (i.id === event.id ? { ...i, ...saved } : i)),
      }));
    } catch (e) {
      setError(failure(c, e));
    } finally {
      setBusy(false);
    }
  }
  async function more() {
    if (!page.next) return;
    setBusy(true);
    try {
      const p = await api<typeof page>(
        `${base}/today?${new URLSearchParams(page.next)}`,
      );
      setPage({ ...p, items: [...page.items, ...p.items] });
    } catch (e) {
      setError(failure(c, e));
    } finally {
      setBusy(false);
    }
  }
  if (!page.items.length && !error) return null;
  return (
    <section className={`${styles.root} ${styles.card}`} data-air-today>
      <h2>{c.today}</h2>
      {error && <p role="alert">{error}</p>}
      {page.items.map((e) => (
        <section key={e.id}>
          <h3>
            <Link href={`/air-watch?monitor=${e.monitor_id}`}>
              {e.monitor_name} · {c.open}
            </Link>
          </h3>
          <p>
            {label(c, e.monitor_status)} · {label(c, e.health)}
            {e.muted ? ` · ${c.muted}` : ""}
          </p>
          <AirEvent
            event={e}
            canManage={canManage}
            busy={busy}
            onReview={(event, decision) => void review(e, event, decision)}
          />
        </section>
      ))}
      {page.next && (
        <button disabled={busy} onClick={() => void more()}>
          {c.more}
        </button>
      )}
    </section>
  );
}
