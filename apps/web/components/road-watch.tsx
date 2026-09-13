"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useI18n, type Locale } from "@/lib/i18n";
import { centreCopy } from "@/lib/monitoring-centre-copy";
import { roadCopy, roadLabel, type RoadCopy } from "@/lib/road-copy";
import {
  newRoad,
  roadKinds,
  roadLink,
  type RoadDetail,
  type Corridor,
  type RoadConfiguration,
  type RoadEvent,
  type RoadEventVersion,
  type RoadMonitor,
  type RoadPage,
  type RoadPreview,
  type RoadRevision,
} from "@/lib/road-watch";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import { RoadFacts as Facts } from "./road-facts";
import { RoadEmail } from "./road-email";
import styles from "./commute-watch.module.css";

const base = "/road-watch";
const AccessFailure = createContext<(problem: unknown) => void>(() => {});
function failure(c: RoadCopy, problem: unknown) {
  const code = problem instanceof ApiError ? problem.code : "";
  return code === "road_watch_disabled"
    ? c.featureOff
    : code.includes("conflict")
      ? c.conflict
      : code.includes("source") ||
          code.includes("permission") ||
          code.includes("corridor")
        ? c.sourceOff
        : c.failed;
}
function stamp(locale: Locale, value?: string | null) {
  if (!value || !Number.isFinite(Date.parse(value))) return "—";
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Zurich",
  }).format(new Date(value));
}
function useData<T>(path: string | null, revision = 0) {
  const deny = useContext(AccessFailure);
  const key = `${path}:${revision}`;
  const [result, setResult] = useState<{
    key: string;
    data?: T;
    error?: unknown;
  }>({ key: "" });
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    api<T>(base + path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ key, data });
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          deny(error);
          setResult({ key, error });
        }
      });
    return () => controller.abort();
  }, [path, key, deny]);
  return result.key === key ? result : { key };
}
function useMutation(c: RoadCopy) {
  const deny = useContext(AccessFailure);
  const request = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => () => request.current?.abort(), []);
  async function run<T>(
    path: string,
    body: unknown,
    done: (value: T) => void,
    method = "POST",
  ) {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError("");
    try {
      const value = await api<T>(base + path, {
        method,
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!controller.signal.aborted) done(value);
    } catch (problem) {
      if (!controller.signal.aborted) {
        deny(problem);
        setError(failure(c, problem));
      }
    } finally {
      if (!controller.signal.aborted) {
        request.current = null;
        setBusy(false);
      }
    }
  }
  return { run, busy, error };
}
function Pages<T>({
  path,
  parameter = "after_id",
  children,
}: {
  path: string;
  parameter?: string;
  children: (items: T[]) => ReactNode;
}) {
  const { locale } = useI18n(),
    c = roadCopy[locale];
  const [anchors, setAnchors] = useState<(string | number | null)[]>([null]);
  const cursor = anchors[anchors.length - 1];
  const data = useData<RoadPage<T>>(
    `${path}${path.includes("?") ? "&" : "?"}limit=20${cursor == null ? "" : `&${parameter}=${encodeURIComponent(cursor)}`}`,
  );
  return (
    <>
      {data.error ? (
        <p role="alert">{failure(c, data.error)}</p>
      ) : !data.data ? (
        <p role="status">{c.loading}</p>
      ) : (
        children(data.data.items)
      )}
      <div className={styles.actions}>
        {anchors.length > 1 && (
          <button
            type="button"
            onClick={() => setAnchors((v) => v.slice(0, -1))}
          >
            {c.previous}
          </button>
        )}
        {data.data?.next_cursor != null && (
          <button
            type="button"
            onClick={() => setAnchors((v) => [...v, data.data!.next_cursor])}
          >
            {c.more}
          </button>
        )}
      </div>
    </>
  );
}
function Editor({
  row,
  initialLabels = [],
  done,
  cancel,
}: {
  row?: RoadMonitor;
  initialLabels?: Corridor[];
  done: (row: RoadMonitor) => void;
  cancel: () => void;
}) {
  const { locale } = useI18n(),
    c = roadCopy[locale],
    mutation = useMutation(c);
  const [draft, setDraft] = useState<RoadConfiguration>(() =>
    row ? structuredClone(row.configuration) : newRoad(),
  );
  const [labels, setLabels] = useState<Record<string, Corridor>>(() =>
    Object.fromEntries(initialLabels.map((i) => [i.id, i])),
  );
  const [query, setQuery] = useState(""),
    [search, setSearch] = useState("");
  const [preview, setPreview] = useState<RoadPreview | null>(null);
  const saveRequest = useRef({ payload: "", key: "" });
  function change(value: RoadConfiguration) {
    setDraft(value);
    setPreview(null);
  }
  const valid =
    !!draft.name.trim() &&
    draft.corridor_reference_ids.length > 0 &&
    draft.corridor_reference_ids.length <= 8 &&
    draft.materiality.event_kinds.length > 0 &&
    Number.isInteger(draft.materiality.minimum_delay_seconds) &&
    draft.materiality.minimum_delay_seconds >= 0 &&
    draft.materiality.minimum_delay_seconds <= 86400;
  function save() {
    const fingerprint = JSON.stringify(draft);
    if (saveRequest.current.payload !== fingerprint)
      saveRequest.current = { payload: fingerprint, key: crypto.randomUUID() };
    void mutation.run<RoadMonitor>(
      row ? `/monitors/${row.id}` : "/monitors",
      {
        configuration: draft,
        ...(row
          ? { expected_version: row.version }
          : { request_key: saveRequest.current.key }),
      },
      done,
      row ? "PATCH" : "POST",
    );
  }
  return (
    <section className={styles.card} aria-label={row ? c.edit : c.create}>
      <h2>{row ? c.edit : c.create}</h2>
      <fieldset disabled={mutation.busy}>
        <legend>{c.name}</legend>
        <input
          aria-label={c.name}
          value={draft.name}
          maxLength={100}
          onChange={(e) => change({ ...draft, name: e.target.value })}
        />
      </fieldset>
      <fieldset disabled={mutation.busy}>
        <legend>{c.corridors}</legend>
        <p>{c.catalogHelp}</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(query.trim());
          }}
        >
          <label>
            {c.search}
            <input
              value={query}
              maxLength={100}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <button>{c.search}</button>
        </form>
        <Pages<Corridor>
          key={search}
          path={`/catalog?query=${encodeURIComponent(search)}`}
        >
          {(items) =>
            items.length ? (
              items.map((item) => (
                <label key={item.id} className={styles.check}>
                  <input
                    type="checkbox"
                    checked={draft.corridor_reference_ids.includes(item.id)}
                    disabled={
                      !draft.corridor_reference_ids.includes(item.id) &&
                      draft.corridor_reference_ids.length >= 8
                    }
                    onChange={(e) => {
                      setLabels((v) => ({ ...v, [item.id]: item }));
                      change({
                        ...draft,
                        corridor_reference_ids: e.target.checked
                          ? [...draft.corridor_reference_ids, item.id]
                          : draft.corridor_reference_ids.filter(
                              (id) => id !== item.id,
                            ),
                      });
                    }}
                  />
                  <span>
                    {item.name || c.unavailable}
                    {item.attribution && <small> · {item.attribution}</small>}
                  </span>
                </label>
              ))
            ) : (
              <p>{c.noCatalog}</p>
            )
          }
        </Pages>
        <h3>{c.selected}</h3>
        <ul>
          {draft.corridor_reference_ids.map((id, index) => (
            <li key={id}>
              {labels[id]?.name || `${c.unavailable} (${index + 1})`}{" "}
              <button
                type="button"
                onClick={() =>
                  change({
                    ...draft,
                    corridor_reference_ids: draft.corridor_reference_ids.filter(
                      (v) => v !== id,
                    ),
                  })
                }
              >
                {c.removeSelection}
              </button>
            </li>
          ))}
        </ul>
      </fieldset>
      <fieldset disabled={mutation.busy}>
        <legend>{c.eventTypes}</legend>
        {roadKinds.map((kind) => (
          <label key={kind} className={styles.check}>
            <input
              type="checkbox"
              checked={draft.materiality.event_kinds.includes(kind)}
              onChange={(e) =>
                change({
                  ...draft,
                  materiality: {
                    ...draft.materiality,
                    event_kinds: e.target.checked
                      ? [...draft.materiality.event_kinds, kind]
                      : draft.materiality.event_kinds.filter((k) => k !== kind),
                  },
                })
              }
            />
            {roadLabel(locale, kind)}
          </label>
        ))}
        <label>
          {c.delay}
          <input
            type="number"
            min={0}
            max={1440}
            step={1}
            value={
              Number.isFinite(draft.materiality.minimum_delay_seconds)
                ? draft.materiality.minimum_delay_seconds / 60
                : ""
            }
            onChange={(e) =>
              change({
                ...draft,
                materiality: {
                  ...draft.materiality,
                  minimum_delay_seconds:
                    e.target.value === "" ? NaN : Number(e.target.value) * 60,
                },
              })
            }
          />
        </label>
        <p>{c.delayHelp}</p>
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={draft.materiality.include_planned}
            onChange={(e) =>
              change({
                ...draft,
                materiality: {
                  ...draft.materiality,
                  include_planned: e.target.checked,
                },
              })
            }
          />
          {c.planned}
        </label>
      </fieldset>
      {preview && (
        <div role="status">
          <p>{preview.start_available ? c.ready : c.sourceOff}</p>
          <ul>
            {preview.corridors.map((item) => (
              <li key={item.id}>{item.name || c.unavailable}</li>
            ))}
          </ul>
        </div>
      )}
      {mutation.error && <p role="alert">{mutation.error}</p>}
      <div className={styles.actions}>
        <button
          disabled={!valid || mutation.busy}
          onClick={() => {
            setPreview(null);
            void mutation.run<RoadPreview>(
              "/preview",
              { configuration: draft },
              setPreview,
            );
          }}
        >
          {c.preview}
        </button>
        <button disabled={!valid || mutation.busy} onClick={save}>
          {c.save}
        </button>
        <button disabled={mutation.busy} onClick={cancel}>
          {c.cancel}
        </button>
      </div>
    </section>
  );
}
function EventCard({
  item,
  labels,
  canManage,
  changed,
}: {
  item: RoadEvent;
  labels: Corridor[];
  canManage: boolean;
  changed: () => void;
}) {
  const { locale } = useI18n(),
    c = roadCopy[locale],
    mutation = useMutation(c);
  const [history, setHistory] = useState(false);
  function review(muted?: boolean) {
    void mutation.run(
      `/events/${item.id}/review`,
      {
        expected_version: item.version,
        sequence: item.sequence,
        ...(muted === undefined ? {} : { muted }),
      },
      changed,
    );
  }
  return (
    <article className={styles.card}>
      <h3>
        {item.sequence > item.reviewed_sequence ? c.unread : c.reviewed} ·{" "}
        {c.version} {item.sequence}
      </h3>
      <p>
        {c.time}: {stamp(locale, item.updated_at)}
      </p>
      <Facts
        payload={item.payload}
        labels={labels}
        availability={item.availability}
        attribution={item.attribution}
      />
      {canManage && (
        <div className={styles.actions}>
          <button
            disabled={mutation.busy || item.sequence === item.reviewed_sequence}
            onClick={() => review()}
          >
            {c.review}
          </button>
          <button disabled={mutation.busy} onClick={() => review(!item.muted)}>
            {item.muted ? c.unmute : c.mute}
          </button>
        </div>
      )}
      {mutation.error && <p role="alert">{mutation.error}</p>}
      <details onToggle={(e) => setHistory(e.currentTarget.open)}>
        <summary>{c.history}</summary>
        {history && (
          <Pages<RoadEventVersion>
            path={`/events/${item.id}/history`}
            parameter="after_sequence"
          >
            {(items) =>
              items.map((version) => (
                <section key={version.sequence}>
                  <h4>
                    {c.version} {version.sequence} ·{" "}
                    {stamp(locale, version.created_at)}
                  </h4>
                  <Facts
                    payload={version.payload}
                    labels={labels}
                    availability={version.availability}
                    attribution={version.attribution}
                  />
                </section>
              ))
            }
          </Pages>
        )}
      </details>
    </article>
  );
}
function LinkedEvent({
  monitor,
  event,
  sequence,
  canManage,
  changed,
}: {
  monitor: string;
  event: string;
  sequence?: number;
  canManage: boolean;
  changed: () => void;
}) {
  const { locale } = useI18n(),
    c = roadCopy[locale];
  const [revision, setRevision] = useState(0);
  const data = useData<RoadDetail>(
    `/events/${event}?monitor_id=${encodeURIComponent(monitor)}${sequence === undefined ? "" : `&sequence=${sequence}`}`,
    revision,
  );
  if (data.error) return <p role="alert">{c.linkUnavailable}</p>;
  if (!data.data) return <p role="status">{c.loading}</p>;
  const item = data.data;
  return (
    <section className={styles.card} aria-label={c.selectedChange}>
      <h2>
        {c.selectedChange} · {c.version} {item.snapshot.sequence}
      </h2>
      {!item.current_configuration && <p role="status">{c.oldConfiguration}</p>}
      {item.newer_available && <p role="status">{c.newerAvailable}</p>}
      <p>
        {c.time}: {stamp(locale, item.snapshot.created_at)}
      </p>
      <h3>{c.beforeChange}</h3>
      {item.previous ? (
        <Facts {...item.previous} labels={item.corridors} />
      ) : (
        <p>{c.noPrevious}</p>
      )}
      <h3>{c.selectedChange}</h3>
      <Facts {...item.snapshot} labels={item.corridors} />
      <h3>{c.latestKnown}</h3>
      <EventCard
        item={item.event}
        labels={item.corridors}
        canManage={canManage}
        changed={() => {
          setRevision((v) => v + 1);
          changed();
        }}
      />
    </section>
  );
}
function Monitor({
  id,
  canManage,
  changed,
  removed,
}: {
  id: string;
  canManage: boolean;
  changed: () => void;
  removed: () => void;
}) {
  const { locale } = useI18n(),
    c = roadCopy[locale];
  const deny = useContext(AccessFailure);
  const [revision, setRevision] = useState(0),
    [editing, setEditing] = useState(false),
    [history, setHistory] = useState(false),
    [deleting, setDeleting] = useState(false);
  const data = useData<RoadMonitor>(`/monitors/${id}`, revision),
    labels = useData<RoadPage<Corridor>>(`/monitors/${id}/corridors`, revision);
  const mutation = useMutation(c),
    row = data.data;
  function reload() {
    setRevision((v) => v + 1);
    changed();
  }
  if (data.error) return <p role="alert">{failure(c, data.error)}</p>;
  if (!row) return <p role="status">{c.loading}</p>;
  const names = labels.data?.items || [];
  if (editing)
    return (
      <Editor
        row={row}
        initialLabels={names}
        cancel={() => setEditing(false)}
        done={() => {
          setEditing(false);
          reload();
        }}
      />
    );
  function command(action: string) {
    void mutation.run(
      `/monitors/${id}/commands`,
      { expected_version: row!.version, action },
      reload,
    );
  }
  return (
    <section className={styles.detail}>
      <div className={styles.card}>
        <h2>{row.configuration.name}</h2>
        <p>
          {roadLabel(locale, row.status)} · {roadLabel(locale, row.health)}
        </p>
        <p>
          {c.time}: {stamp(locale, row.last_check_at)}
        </p>
        <ul>
          {names.map((label, index) => (
            <li key={label.id}>
              {label.name || `${c.unavailable} (${index + 1})`}
            </li>
          ))}
        </ul>
        {!!labels.error && <p role="status">{c.unavailable}</p>}
        <p>
          {row.configuration.materiality.event_kinds
            .map((k) => roadLabel(locale, k))
            .join(" · ")}
        </p>
        <p>
          {c.delay}: {row.configuration.materiality.minimum_delay_seconds / 60}
        </p>
        {canManage && (
          <div className={styles.actions}>
            {(row.status === "draft" || row.status === "paused") && (
              <button disabled={mutation.busy} onClick={() => setEditing(true)}>
                {c.edit}
              </button>
            )}
            {row.status === "draft" && (
              <button disabled={mutation.busy} onClick={() => command("start")}>
                {c.start}
              </button>
            )}
            {row.status === "active" && (
              <button disabled={mutation.busy} onClick={() => command("pause")}>
                {c.pause}
              </button>
            )}
            {row.status === "paused" && (
              <button
                disabled={mutation.busy}
                onClick={() => command("resume")}
              >
                {c.resume}
              </button>
            )}
            {row.status !== "archived" && (
              <button
                disabled={mutation.busy}
                onClick={() => command("archive")}
              >
                {c.archive}
              </button>
            )}
            <button disabled={mutation.busy} onClick={() => setDeleting(true)}>
              {c.remove}
            </button>
          </div>
        )}
        {deleting && (
          <div role="group" aria-label={c.confirmDelete}>
            <p>{c.confirmDelete}</p>
            <div className={styles.actions}>
              <button
                disabled={mutation.busy}
                onClick={() =>
                  void mutation.run(
                    `/monitors/${id}`,
                    { expected_version: row.version },
                    removed,
                    "DELETE",
                  )
                }
              >
                {c.remove}
              </button>
              <button
                disabled={mutation.busy}
                onClick={() => setDeleting(false)}
              >
                {c.cancel}
              </button>
            </div>
          </div>
        )}
        {mutation.error && <p role="alert">{mutation.error}</p>}
        <details onToggle={(e) => setHistory(e.currentTarget.open)}>
          <summary>{c.revisions}</summary>
          {history && (
            <Pages<RoadRevision>
              key={revision}
              path={`/monitors/${id}/revisions`}
              parameter="after_revision"
            >
              {(items) =>
                items.map((item) => (
                  <section key={item.revision}>
                    <h3>
                      {c.version} {item.revision}: {item.configuration.name}
                    </h3>
                    <p>
                      {item.configuration.materiality.event_kinds
                        .map((k) => roadLabel(locale, k))
                        .join(" · ")}
                    </p>
                    <p>
                      {c.delay}:{" "}
                      {item.configuration.materiality.minimum_delay_seconds /
                        60}
                    </p>
                  </section>
                ))
              }
            </Pages>
          )}
        </details>
      </div>
      <RoadEmail
        key={`${row.id}:${row.version}`}
        monitorId={row.id}
        canManage={canManage}
        archived={row.status === "archived"}
        changed={reload}
        onAccessFailure={deny}
      />
      <h2>{c.events}</h2>
      <Pages<RoadEvent> key={revision} path={`/monitors/${id}/events`}>
        {(items) =>
          items.length ? (
            items.map((item) => (
              <EventCard
                key={`${item.id}:${item.version}`}
                item={item}
                labels={names}
                canManage={canManage}
                changed={reload}
              />
            ))
          ) : (
            <p>{c.noEvents}</p>
          )
        }
      </Pages>
    </section>
  );
}
export function RoadWatch() {
  const { session } = useAuth(),
    params = useSearchParams();
  const scope = session?.authenticated
    ? `${session.user?.id}:${session.organization?.id}:${session.role}`
    : "unavailable";
  const [visible, setVisible] = useState(true),
    [epoch, setEpoch] = useState(0);
  useEffect(() => {
    const hide = () => {
      setVisible(false);
      setEpoch((v) => v + 1);
    };
    const show = () => {
      setVisible(!document.hidden);
      setEpoch((v) => v + 1);
    };
    const visibility = () => (document.hidden ? hide() : show());
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    window.addEventListener("focus", show);
    return () => {
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
      window.removeEventListener("focus", show);
    };
  }, []);
  const link = roadLink(params);
  return (
    <Shell>
      <Workspace
        key={`${scope}:${link.monitor}:${link.event}:${link.sequence}:${link.invalid}:${epoch}:${visible}`}
        allowed={visible && scope !== "unavailable"}
        canManage={session?.role === "organization_admin"}
        initial={link.monitor}
        link={link}
      />
    </Shell>
  );
}
function Workspace({
  allowed,
  canManage,
  initial,
  link,
}: {
  allowed: boolean;
  canManage: boolean;
  initial: string;
  link: ReturnType<typeof roadLink>;
}) {
  const { locale } = useI18n(),
    c = roadCopy[locale];
  const [selected, setSelected] = useState(initial),
    [creating, setCreating] = useState(false),
    [revision, setRevision] = useState(0);
  const [blocked, setBlocked] = useState(false);
  const deny = useCallback((problem: unknown) => {
    if (
      problem instanceof ApiError &&
      [
        "authentication_required",
        "membership_required",
        "subject_role_denied",
        "road_watch_disabled",
      ].includes(problem.code)
    )
      setBlocked(true);
  }, []);
  const capabilities = useData<{ start_available: boolean }>(
    allowed && !blocked ? "/capabilities" : null,
    revision,
  );
  return (
    <AccessFailure.Provider value={deny}>
      <div className={styles.root}>
        <Link href="/monitoring">{centreCopy[locale].title}</Link>
        <h1>{c.title}</h1>
        <p>{c.intro}</p>
        <div className={styles.actions}>
          <button
            disabled={!allowed}
            onClick={() => {
              setBlocked(false);
              setRevision((v) => v + 1);
              setSelected("");
              setCreating(false);
            }}
          >
            {c.refresh}
          </button>
          {canManage && !blocked && capabilities.data && (
            <button
              onClick={() => {
                setCreating(true);
                setSelected("");
              }}
            >
              {c.create}
            </button>
          )}
        </div>
        {blocked && <p role="alert">{c.accessChanged}</p>}
        {link.invalid && <p role="alert">{c.linkUnavailable}</p>}
        {!canManage && <p>{c.readonly}</p>}
        {capabilities.error ? (
          <p role="alert">{failure(c, capabilities.error)}</p>
        ) : !capabilities.data && !blocked ? (
          <p role="status">{c.loading}</p>
        ) : null}
        {capabilities.data && !capabilities.data.start_available && (
          <p role="status">{c.sourceOff}</p>
        )}
        {allowed && !blocked && capabilities.data && (
          <div className={styles.layout}>
            <aside className={styles.list} aria-label={c.title}>
              <Pages<RoadMonitor> key={revision} path="/monitors">
                {(items) =>
                  items.length ? (
                    items.map((row) => (
                      <button
                        key={row.id}
                        aria-pressed={selected === row.id}
                        onClick={() => {
                          setSelected(row.id);
                          setCreating(false);
                        }}
                      >
                        {row.configuration.name} ·{" "}
                        {roadLabel(locale, row.status)}
                      </button>
                    ))
                  ) : (
                    <p>{c.empty}</p>
                  )
                }
              </Pages>
            </aside>
            {creating ? (
              <Editor
                cancel={() => setCreating(false)}
                done={(row) => {
                  setCreating(false);
                  setSelected(row.id);
                  setRevision((v) => v + 1);
                }}
              />
            ) : selected ? (
              <div className={styles.detail}>
                {link.event && selected === link.monitor && (
                  <LinkedEvent
                    key={`${selected}:${link.event}:${link.sequence}`}
                    monitor={selected}
                    event={link.event}
                    sequence={link.sequence}
                    canManage={canManage}
                    changed={() => setRevision((v) => v + 1)}
                  />
                )}
                <Monitor
                  key={selected}
                  id={selected}
                  canManage={canManage}
                  changed={() => setRevision((v) => v + 1)}
                  removed={() => {
                    setSelected("");
                    setRevision((v) => v + 1);
                  }}
                />
              </div>
            ) : null}
          </div>
        )}
      </div>
    </AccessFailure.Provider>
  );
}
