"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { riverCopy, riverAttribution } from "@/lib/river-copy";
import {
  configurationError,
  RIVER_RISE_UNIT,
  riverUnit,
  type RiverChange,
  type RiverConfiguration,
  type RiverCoverage,
  type RiverMetric,
  type RiverMonitor,
  type RiverPreview,
  type RiverRule,
  type RiverSample,
  type RiverStation,
} from "@/lib/river-watch";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import styles from "./river-watch.module.css";

const base = "/river-watch";
type Copy = (typeof riverCopy)["en-CH"];
const label = (copy: Copy, key: string) =>
  copy[key as keyof Copy] || copy.unknown;
const failure = (copy: Copy, error: unknown) =>
  error instanceof ApiError &&
  ["river_version_conflict", "river_newer_change"].includes(error.code)
    ? copy.conflict
    : error instanceof ApiError && error.code === "river_source_not_ready"
      ? copy.unavailable
      : copy.failed;
const post = (body: unknown, method = "POST") => ({
  method,
  body: JSON.stringify(body),
});

function Sample({ sample }: { sample: RiverSample }) {
  const { locale } = useI18n();
  const c = riverCopy[locale];
  return (
    <div className={styles.sample}>
      <strong>
        {label(c, sample.metric)}: {sample.value}{" "}
        {sample.unit === "official_level" ? "" : sample.unit}
      </strong>
      <span>
        {c.time}: {new Date(sample.timestamp).toLocaleString(locale)}
      </span>
      <span>
        {c.quality}: {label(c, sample.quality)}
      </span>
      {sample.datum && <span>{sample.datum}</span>}
      <a href={sample.source_url} target="_blank" rel="noreferrer">
        {c.source} · {riverAttribution[locale]}
      </a>
    </div>
  );
}

function Coverage({ coverage }: { coverage: RiverCoverage }) {
  const { locale } = useI18n();
  const c = riverCopy[locale];
  return (
    <div className={styles.coverage}>
      {Object.entries(coverage).map(([metric, entry]) => (
        <section key={metric} className={styles.card}>
          <h3>
            {label(c, metric)} · {label(c, entry.status)}
          </h3>
          {entry.sample ? <Sample sample={entry.sample} /> : <p>{c.unknown}</p>}
        </section>
      ))}
    </div>
  );
}

function Editor({
  stations,
  initial,
  monitor,
  onSaved,
  onCancel,
}: {
  stations: RiverStation[];
  initial?: RiverConfiguration;
  monitor?: RiverMonitor;
  onSaved: (row: RiverMonitor) => void;
  onCancel: () => void;
}) {
  const { locale } = useI18n();
  const c = riverCopy[locale];
  const [configuration, setConfiguration] = useState<RiverConfiguration>(
    initial || {
      name: "",
      station_id: "",
      metrics: ["W", "Q", "WT"],
      official_danger: true,
      rules: [],
    },
  );
  const [search, setSearch] = useState("");
  const [preview, setPreview] = useState<RiverPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [requestKey] = useState(() => crypto.randomUUID());
  function change(next: RiverConfiguration) {
    setConfiguration(next);
    setPreview(null);
    setError("");
  }
  function rule(index: number, next: RiverRule) {
    change({
      ...configuration,
      rules: configuration.rules.map((row, i) => (i === index ? next : row)),
    });
  }
  async function run(save: boolean) {
    if (configurationError(configuration)) {
      setError(c.invalid);
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (save) {
        const row = await api<RiverMonitor>(
          monitor ? `${base}/monitors/${monitor.id}` : `${base}/monitors`,
          post(
            monitor
              ? { configuration, expected_version: monitor.version }
              : { configuration, request_key: requestKey },
            monitor ? "PATCH" : "POST",
          ),
        );
        onSaved(row);
      } else
        setPreview(
          await api<RiverPreview>(`${base}/preview`, post({ configuration })),
        );
    } catch (err) {
      setError(failure(c, err));
    } finally {
      setBusy(false);
    }
  }
  const filtered = stations.filter(
    (row) =>
      row.id === configuration.station_id ||
      `${row.name} ${row.waterbody} ${row.id}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()),
  );
  return (
    <form
      className={styles.card}
      onSubmit={(event) => {
        event.preventDefault();
        void run(false);
      }}
    >
      <h2>{monitor ? c.edit : c.create}</h2>
      <label>
        {c.name}
        <input
          required
          maxLength={100}
          value={configuration.name}
          onChange={(e) => change({ ...configuration, name: e.target.value })}
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
      <label>
        {c.station}
        <select
          required
          value={configuration.station_id}
          onChange={(e) =>
            change({ ...configuration, station_id: e.target.value })
          }
        >
          <option value="">{c.choose}</option>
          {filtered.map((s) => (
            <option key={s.id} value={s.id}>
              {s.waterbody} · {s.name} · {s.id}
            </option>
          ))}
        </select>
      </label>
      <fieldset>
        <legend>{c.metrics}</legend>
        {(["W", "Q", "WT"] as RiverMetric[]).map((metric) => (
          <label className={styles.check} key={metric}>
            <input
              type="checkbox"
              checked={configuration.metrics.includes(metric)}
              onChange={(e) =>
                change({
                  ...configuration,
                  metrics: e.target.checked
                    ? [...configuration.metrics, metric]
                    : configuration.metrics.filter((m) => m !== metric),
                  rules: e.target.checked
                    ? configuration.rules
                    : configuration.rules.filter((r) => r.metric !== metric),
                })
              }
            />
            {c[metric]}
          </label>
        ))}
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={configuration.official_danger}
            onChange={(e) =>
              change({ ...configuration, official_danger: e.target.checked })
            }
          />
          {c.danger}
        </label>
      </fieldset>
      <p>{c.datum}</p>
      <h3>{c.rules}</h3>
      {configuration.rules.map((r, index) => (
        <fieldset className={styles.rule} key={index}>
          <legend>
            {c.threshold} {index + 1}
          </legend>
          <label>
            {c.metrics}
            <select
              value={r.metric}
              onChange={(e) => {
                const metric = e.target.value as RiverMetric;
                rule(index, { ...r, metric, unit: riverUnit(metric) });
              }}
            >
              {configuration.metrics.map((m) => (
                <option value={m} key={m}>
                  {c[m]}
                </option>
              ))}
            </select>
          </label>
          <label>
            {c.threshold}
            <select
              value={r.kind}
              onChange={(e) => {
                const kind = e.target.value as RiverRule["kind"];
                rule(index, {
                  ...r,
                  kind,
                  unit: riverUnit(r.metric),
                  window_minutes: kind === "rise" ? 60 : null,
                });
              }}
            >
              <option value="absolute">{c.absolute}</option>
              <option value="rise">{c.rise}</option>
            </select>
          </label>
          <label>
            {c.threshold}
            <input
              required
              type="number"
              step="any"
              value={r.threshold}
              onChange={(e) => rule(index, { ...r, threshold: e.target.value })}
            />
          </label>
          <label>
            {c.unit}
            <select
              value={r.unit}
              onChange={(e) =>
                rule(index, { ...r, unit: e.target.value as RiverRule["unit"] })
              }
            >
              <option value={riverUnit(r.metric)}>{riverUnit(r.metric)}</option>
              {r.metric === "W" && r.kind === "rise" && (
                <option value={RIVER_RISE_UNIT}>{RIVER_RISE_UNIT}</option>
              )}
            </select>
          </label>
          {r.kind === "rise" && (
            <label>
              {c.window}
              <input
                required
                type="number"
                min={10}
                max={1440}
                step={10}
                value={r.window_minutes || ""}
                onChange={(e) =>
                  rule(index, { ...r, window_minutes: Number(e.target.value) })
                }
              />
            </label>
          )}
          <button
            type="button"
            onClick={() =>
              change({
                ...configuration,
                rules: configuration.rules.filter((_, i) => i !== index),
              })
            }
          >
            {c.remove} {index + 1}
          </button>
        </fieldset>
      ))}
      <button
        type="button"
        disabled={
          !configuration.metrics.length || configuration.rules.length >= 6
        }
        onClick={() => {
          const metric = configuration.metrics[0];
          change({
            ...configuration,
            rules: [
              ...configuration.rules,
              {
                metric,
                kind: "absolute",
                threshold: "",
                unit: riverUnit(metric),
                window_minutes: null,
              },
            ],
          });
        }}
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

function Detail({
  id,
  canManage,
  stations,
  onChanged,
  onDeleted,
  refreshToken,
}: {
  id: string;
  canManage: boolean;
  stations: RiverStation[];
  onChanged: () => void;
  onDeleted: () => void;
  refreshToken: number;
}) {
  const { locale } = useI18n();
  const c = riverCopy[locale];
  const [row, setRow] = useState<RiverMonitor | null>(null);
  const [changes, setChanges] = useState<{
    items: RiverChange[];
    next_before: number | null;
  }>({ items: [], next_before: null });
  const [history, setHistory] = useState<{
    items: RiverSample[];
    next: { before: string; before_id: string } | null;
  }>({ items: [], next: null });
  const [revisions, setRevisions] = useState<{
    items: { revision: number; configuration: RiverConfiguration }[];
    next_before: number | null;
  }>({ items: [], next_before: null });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [preview, setPreview] = useState<RiverPreview | null>(null);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let stopped = false;
    async function load() {
      try {
        const [monitor, events] = await Promise.all([
          api<RiverMonitor>(`${base}/monitors/${id}`, {
            signal: controller.signal,
          }),
          api<typeof changes>(`${base}/monitors/${id}/changes`, {
            signal: controller.signal,
          }),
        ]);
        if (!stopped) {
          setRow(monitor);
          setChanges(events);
          setError("");
        }
      } catch (err) {
        if (!stopped) setError(failure(c, err));
      }
    }
    void load();
    const timer = setInterval(() => void load(), 60000);
    return () => {
      stopped = true;
      controller.abort();
      clearInterval(timer);
    };
    // Copy changes on a locale remount; only the saved reader polls.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, refresh, locale, refreshToken]);
  async function action(kind: string) {
    if (!row) return;
    setBusy(true);
    setError("");
    try {
      if (kind === "preview")
        setPreview(
          await api<RiverPreview>(
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
          onDeleted();
        }
      } else {
        setRow(
          await api<RiverMonitor>(
            `${base}/monitors/${id}/command`,
            post({ expected_version: row.version, action: kind }),
          ),
        );
        setPreview(null);
        onChanged();
      }
    } catch (err) {
      setError(failure(c, err));
    } finally {
      setBusy(false);
    }
  }
  async function readHistory(
    kind: "measurements" | "changes" | "revisions",
    more = false,
  ) {
    setBusy(true);
    setError("");
    try {
      if (kind === "measurements") {
        const query =
          more && history.next ? `?${new URLSearchParams(history.next)}` : "";
        const page = await api<typeof history>(
          `${base}/monitors/${id}/measurements${query}`,
        );
        setHistory({
          ...page,
          items: more ? [...history.items, ...page.items] : page.items,
        });
      } else if (kind === "changes") {
        const page = await api<typeof changes>(
          `${base}/monitors/${id}/changes${more ? `?before=${changes.next_before}` : ""}`,
        );
        setChanges({
          ...page,
          items: more ? [...changes.items, ...page.items] : page.items,
        });
      } else {
        const page = await api<typeof revisions>(
          `${base}/monitors/${id}/revisions${more ? `?before=${revisions.next_before}` : ""}`,
        );
        setRevisions({
          ...page,
          items: more ? [...revisions.items, ...page.items] : page.items,
        });
      }
    } catch (err) {
      setError(failure(c, err));
    } finally {
      setBusy(false);
    }
  }
  async function decide(event: RiverChange, decision: string) {
    setBusy(true);
    setError("");
    try {
      const changed = await api<RiverChange>(
        `${base}/monitors/${id}/changes/${event.id}/review`,
        post({ expected_version: event.review_version, decision }),
      );
      setChanges((old) => ({
        ...old,
        items: old.items.map((item) => (item.id === event.id ? changed : item)),
      }));
    } catch (err) {
      setError(failure(c, err));
    } finally {
      setBusy(false);
    }
  }
  if (!row) return <p role="status">{error || c.loading}</p>;
  if (editing)
    return (
      <Editor
        stations={stations}
        initial={row.configuration}
        monitor={row}
        onCancel={() => setEditing(false)}
        onSaved={(saved) => {
          setRow(saved);
          setEditing(false);
          setPreview(null);
          setHistory({ items: [], next: null });
          onChanged();
        }}
      />
    );
  return (
    <section className={styles.detail}>
      <div className={styles.card}>
        <h2>{row.configuration.name}</h2>
        <p>
          {label(c, row.status)} · {c.revision} {row.revision} ·{" "}
          {label(c, row.health)}
        </p>
        <p>
          {
            stations.find((s) => s.id === row.configuration.station_id)
              ?.waterbody
          }{" "}
          · {stations.find((s) => s.id === row.configuration.station_id)?.name}{" "}
          · {row.configuration.station_id}
        </p>
        <p>{c.datum}</p>
        {row.configuration.rules.map((r, i) => (
          <p key={i}>
            {c[r.metric]} · {r.kind === "rise" ? c.rise : c.absolute}{" "}
            {r.threshold} {r.unit}{" "}
            {r.window_minutes ? ` / ${r.window_minutes} min` : ""}
          </p>
        ))}
        <div className={styles.actions}>
          <button
            disabled={busy}
            onClick={() => {
              setRefresh((n) => n + 1);
              setPreview(null);
              onChanged();
            }}
          >
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
                <button disabled={busy} onClick={() => void action("archive")}>
                  {c.archive}
                </button>
              )}
              <button disabled={busy} onClick={() => void action("delete")}>
                {c.delete}
              </button>
            </>
          )}
        </div>
        {error && <p role="alert">{error}</p>}
        {busy && <p role="status">{c.loading}</p>}
        {(preview?.coverage || row.state.coverage) && (
          <Coverage coverage={preview?.coverage || row.state.coverage || {}} />
        )}
        {row.state.last_gap && <p>{c.gap}</p>}
      </div>
      <section className={styles.card}>
        <h2>{c.changes}</h2>
        {!changes.items.length && <p>{c.noChanges}</p>}
        {changes.items.map((event) => (
          <article className={styles.event} key={event.id}>
            <h3>
              {label(c, event.kind)} · {c.priority} {event.priority}
            </h3>
            <p>
              {c.development} {event.development_id.slice(0, 8)} · {c.revision}{" "}
              {event.revision}
            </p>
            <Sample sample={event.evidence.sample} />
            {event.evidence.rule && (
              <p>
                {event.evidence.evaluated_value} {event.evidence.rule.unit} ·{" "}
                {c.threshold}: {event.evidence.rule.threshold}{" "}
                {event.evidence.rule.unit}
                {event.evidence.rule.window_minutes
                  ? ` / ${event.evidence.rule.window_minutes} min`
                  : ""}
              </p>
            )}
            {event.evidence.baseline && (
              <Sample sample={event.evidence.baseline} />
            )}
            {event.evidence.recovered && <p>{c.recovered}</p>}
            {event.decision && <p>{label(c, event.decision)}</p>}
            {canManage &&
              !changes.items.some(
                (item) =>
                  item.development_id === event.development_id &&
                  item.sequence > event.sequence,
              ) && (
                <div
                  className={styles.actions}
                  role="group"
                  aria-label={c.review}
                >
                  {[
                    "reviewed",
                    "not_relevant",
                    "continue",
                    "action_required",
                  ].map((decision) => (
                    <button
                      disabled={busy}
                      key={decision}
                      onClick={() => void decide(event, decision)}
                    >
                      {label(c, decision)}
                    </button>
                  ))}
                </div>
              )}
          </article>
        ))}
        {changes.next_before && (
          <button
            disabled={busy}
            onClick={() => void readHistory("changes", true)}
          >
            {c.more}
          </button>
        )}
      </section>
      <section className={styles.card}>
        <h2>{c.measurements}</h2>
        <button
          disabled={busy}
          onClick={() => void readHistory("measurements")}
        >
          {c.measurements}
        </button>
        <div className={styles.samples}>
          {history.items.map((sample, i) => (
            <Sample
              key={`${sample.metric}-${sample.timestamp}-${i}`}
              sample={sample}
            />
          ))}
        </div>
        {history.next && (
          <button
            disabled={busy}
            onClick={() => void readHistory("measurements", true)}
          >
            {c.more}
          </button>
        )}
      </section>
      <section className={styles.card}>
        <h2>{c.settings}</h2>
        <button disabled={busy} onClick={() => void readHistory("revisions")}>
          {c.settings}
        </button>
        {revisions.items.map((r) => (
          <div key={r.revision}>
            <h3>
              {c.revision} {r.revision}: {r.configuration.name}
            </h3>
            <p>
              {r.configuration.station_id} ·{" "}
              {r.configuration.metrics.map((m) => c[m]).join(", ")}
            </p>
            {r.configuration.rules.map((rule, i) => (
              <p key={i}>
                {c[rule.metric]} {label(c, rule.kind)} {rule.threshold}{" "}
                {rule.unit}
                {rule.window_minutes ? ` / ${rule.window_minutes} min` : ""}
              </p>
            ))}
          </div>
        ))}
        {revisions.next_before && (
          <button
            disabled={busy}
            onClick={() => void readHistory("revisions", true)}
          >
            {c.more}
          </button>
        )}
      </section>
    </section>
  );
}

export function RiverWatch() {
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
  const c = riverCopy[locale];
  const [stations, setStations] = useState<RiverStation[]>([]);
  const [monitors, setMonitors] = useState<RiverMonitor[]>([]);
  const [selected, setSelected] = useState(initial);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    setSelected(initial);
    setCreating(false);
  }, [initial]);
  useEffect(() => {
    if (!allowed) return;
    const controller = new AbortController();
    Promise.all([
      api<{ stations: RiverStation[] }>(`${base}/stations`, {
        signal: controller.signal,
      }),
      api<{ items: RiverMonitor[] }>(`${base}/monitors`, {
        signal: controller.signal,
      }),
    ])
      .then(([catalog, list]) => {
        if (!controller.signal.aborted) {
          setStations(catalog.stations);
          setMonitors(list.items);
          setError("");
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(failure(c, err));
          setLoading(false);
        }
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allowed, refresh, locale]);
  return (
    <Shell>
      <div className={styles.root} data-river-watch>
        <header>
          <h1>{c.title}</h1>
          <p>{c.intro}</p>
        </header>
        {!canManage && <p>{c.readonly}</p>}
        {error && <p role="alert">{error}</p>}
        <div className={styles.actions}>
          {canManage && (
            <button
              onClick={() => {
                setCreating(true);
                setSelected("");
              }}
            >
              {c.create}
            </button>
          )}
          <button onClick={() => setRefresh((n) => n + 1)}>{c.refresh}</button>
        </div>
        {loading && allowed && <p role="status">{c.loading}</p>}
        {!loading && !monitors.length && <p>{c.empty}</p>}
        <div className={styles.layout}>
          <nav className={styles.list} aria-label={c.title}>
            {monitors.map((row) => (
              <button
                aria-pressed={selected === row.id}
                key={row.id}
                onClick={() => {
                  setSelected(row.id);
                  setCreating(false);
                }}
              >
                {row.configuration.name}
                <span>{label(c, row.status)}</span>
              </button>
            ))}
          </nav>
          <div>
            {creating && canManage && (
              <Editor
                stations={stations}
                onCancel={() => setCreating(false)}
                onSaved={(row) => {
                  setCreating(false);
                  setSelected(row.id);
                  setRefresh((n) => n + 1);
                }}
              />
            )}
            {selected && !creating && (
              <Detail
                key={`${selected}:${locale}`}
                id={selected}
                refreshToken={refresh}
                stations={stations}
                canManage={canManage}
                onChanged={() => setRefresh((n) => n + 1)}
                onDeleted={() => {
                  setSelected("");
                  setRefresh((n) => n + 1);
                }}
              />
            )}
          </div>
        </div>
        <footer>
          <p>{c.limits}</p>
          <a
            href="https://data.bafu.admin.ch/dataproduct-water-observations"
            target="_blank"
            rel="noreferrer"
          >
            {riverAttribution[locale]}
          </a>
        </footer>
      </div>
    </Shell>
  );
}
