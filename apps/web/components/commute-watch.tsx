"use client";

import { MonitoringEvidenceAsk } from "./monitoring-evidence-ask";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { centreCopy } from "@/lib/monitoring-centre-copy";
import { commuteInterchangeCopy } from "@/lib/commute-interchange-copy";
import {
  commuteCopy,
  commuteWeekdays,
  type CommuteCopy,
} from "@/lib/commute-copy";
import {
  commuteSources,
  commuteProvider,
  commuteTimezone,
  newCommute,
  sourceEdition,
  zurichDate,
  commuteStateLabel,
  savedConditions,
  savedLabels,
  type LinkedCommuteEvent,
  type Capabilities,
  type CatalogLeg,
  type CommuteConfiguration,
  type CommuteEvent,
  type CommuteMonitor,
  type Current,
  type EventVersion,
  type Page,
  type Preview,
  type ReferenceLabel,
  type Revision,
} from "@/lib/commute-watch";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import { CommuteEmail } from "./commute-email";
import { CommutePauseNotice } from "./commute-pause-notice";
import styles from "./commute-watch.module.css";

const base = "/commute-watch";
const label = commuteStateLabel;
function reason(c: CommuteCopy, code: string) {
  if (code.includes("transfer")) return c.transfer;
  if (
    code.includes("dated_reference") ||
    code.includes("timetable") ||
    code.includes("catalog")
  )
    return c.timetable;
  if (code === "departure_outside_saved_window") return c.outsideReason;
  if (code === "nonexistent_wall_time") return c.gap;
  return c.sourceOff;
}
function failure(c: CommuteCopy, error: unknown) {
  const code = error instanceof ApiError ? error.code : "";
  return code === "commute_disabled"
    ? c.featureOff
    : code.includes("conflict")
      ? c.conflict
      : code === "commute_configuration_invalid" || code === "invalid_input"
        ? c.invalid
        : code.includes("source") ||
            code.includes("feed") ||
            code.includes("timetable") ||
            code.includes("dated_reference")
          ? reason(c, code)
          : c.failed;
}
function useData<T>(path: string | null, revision = 0) {
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
        if (!controller.signal.aborted) setResult({ key, error });
      });
    return () => controller.abort();
  }, [path, key]);
  return result.key === key ? result : { key };
}
function useMutation(c: CommuteCopy) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function run<T>(
    path: string,
    body: unknown,
    done: (value: T) => void,
    method = "POST",
    denied?: () => void,
  ) {
    if (controller.current) return;
    const pending = new AbortController();
    controller.current = pending;
    setBusy(true);
    setError("");
    try {
      const value = await api<T>(base + path, {
        method,
        body: JSON.stringify(body),
        signal: pending.signal,
      });
      if (!pending.signal.aborted) done(value);
    } catch (problem) {
      if (!pending.signal.aborted) {
        setError(failure(c, problem));
        denied?.();
      }
    } finally {
      if (!pending.signal.aborted) {
        controller.current = null;
        setBusy(false);
      }
    }
  }
  return { busy, error, run };
}
function Pages<T>({
  path,
  parameter = "after_id",
  children,
  denied,
}: {
  path: string;
  parameter?: string;
  children: (items: T[]) => ReactNode;
  denied?: () => void;
}) {
  const { locale } = useI18n(),
    c = commuteCopy[locale];
  const [anchors, setAnchors] = useState<(string | number | null)[]>([null]);
  const cursor = anchors[anchors.length - 1];
  const data = useData<Page<T>>(
    `${path}${path.includes("?") ? "&" : "?"}limit=20${cursor === null ? "" : `&${parameter}=${encodeURIComponent(cursor)}`}`,
  );
  const deniedRef = useRef(denied);
  deniedRef.current = denied;
  useEffect(() => {
    if (data.error) deniedRef.current?.();
  }, [data.error]);
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
            onClick={() => setAnchors((values) => values.slice(0, -1))}
          >
            {c.previous}
          </button>
        )}
        {data.data?.next_cursor != null && (
          <button
            type="button"
            onClick={() =>
              setAnchors((values) => [...values, data.data!.next_cursor])
            }
          >
            {c.more}
          </button>
        )}
      </div>
    </>
  );
}
function Time({ value }: { value?: string | null }) {
  const { locale } = useI18n();
  if (!value || !Number.isFinite(Date.parse(value)))
    return <>{commuteCopy[locale].unknown}</>;
  return (
    <time dateTime={value}>
      {new Intl.DateTimeFormat(locale, {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "Europe/Zurich",
      }).format(new Date(value))}
    </time>
  );
}
function SettingsSummary({
  config,
  references = [],
}: {
  config: CommuteConfiguration;
  references?: ReferenceLabel[];
}) {
  const { locale } = useI18n(),
    c = commuteCopy[locale];
  return (
    <>
      <ol>
        {config.leg_reference_ids.map((id) => (
          <li key={id}>
            {references.find((item) => item.id === id)?.label || c.unknownLeg}
          </li>
        ))}
      </ol>
      <p>
        {config.weekdays.map((day) => commuteWeekdays[locale][day]).join(", ")}{" "}
        · {config.window_start}–{config.window_end} · {commuteTimezone}
      </p>
      <p>
        {c.threshold}: {config.delay_threshold_minutes} · {c.reset}:{" "}
        {config.delay_reset_minutes}
      </p>
    </>
  );
}
function Editor({
  monitor,
  saved,
  cancel,
}: {
  monitor?: CommuteMonitor;
  saved: (row: CommuteMonitor) => void;
  cancel: () => void;
}) {
  const { locale } = useI18n(),
    c = commuteCopy[locale];
  const [config, setConfig] = useState(
    () => monitor?.configuration || newCommute(),
  );
  const [day, setDay] = useState(zurichDate),
    [query, setQuery] = useState("");
  const [search, setSearch] = useState<{ query: string; tick: number } | null>(
    null,
  );
  const [references, setReferences] = useState<ReferenceLabel[]>(
    monitor?.reference_labels || [],
  );
  const [plan, setPlan] = useState<Preview | null>(null),
    mutation = useMutation(c);
  const request = useRef<{ key: string; fingerprint: string } | null>(null);
  function update(fields: Partial<CommuteConfiguration>) {
    setConfig((value) => ({ ...value, ...fields }));
    setPlan(null);
  }
  const valid =
    config.name.trim() &&
    config.leg_reference_ids.length > 0 &&
    config.weekdays.length > 0 &&
    config.window_start !== config.window_end &&
    Number.isInteger(config.delay_reset_minutes) &&
    Number.isInteger(config.delay_threshold_minutes) &&
    config.delay_reset_minutes < config.delay_threshold_minutes &&
    config.delay_reset_minutes >= 0 &&
    config.delay_threshold_minutes >= 1 &&
    config.delay_threshold_minutes <= 180;
  function save() {
    const fingerprint = JSON.stringify(config);
    if (!request.current || request.current.fingerprint !== fingerprint)
      request.current = { key: crypto.randomUUID(), fingerprint };
    void mutation.run<CommuteMonitor>(
      monitor ? `/monitors/${monitor.id}` : "/monitors",
      monitor
        ? { configuration: config, expected_version: monitor.version }
        : { configuration: config, request_key: request.current.key },
      saved,
      monitor ? "PATCH" : "POST",
    );
  }
  return (
    <section className={styles.card} data-commute-editor>
      <h2>{monitor ? c.edit : c.create}</h2>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (valid) save();
        }}
      >
        <fieldset disabled={mutation.busy}>
          <legend>{c.settings}</legend>
          <label>
            {c.name}
            <input
              required
              maxLength={100}
              value={config.name}
              onChange={(event) => update({ name: event.target.value })}
            />
          </label>
          <div className={styles.fields}>
            <label>
              {c.day}
              <input
                type="date"
                required
                value={day}
                onChange={(event) => {
                  setDay(event.target.value);
                  setSearch(null);
                  setPlan(null);
                }}
              />
            </label>
            <label>
              {c.query}
              <input
                maxLength={100}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
          </div>
          <button
            type="button"
            disabled={!day}
            onClick={() =>
              setSearch((previous) => ({
                query,
                tick: (previous?.tick || 0) + 1,
              }))
            }
          >
            {c.search}
          </button>
          <p>{c.coverage}</p>
          {search && (
            <Pages<CatalogLeg>
              key={`${day}:${search.tick}`}
              path={`/catalog?service_day=${day}&query=${encodeURIComponent(search.query)}`}
            >
              {(items) => (
                <ul>
                  {!items.length && <li>{c.noLegs}</li>}
                  {items.map((item) => (
                    <li key={item.id}>
                      <span>
                        {item.label} · {item.departure_wall_time}
                      </span>{" "}
                      <button
                        type="button"
                        disabled={
                          config.leg_reference_ids.includes(item.id) ||
                          config.leg_reference_ids.length >= 8
                        }
                        onClick={() => {
                          setReferences((previous) => [
                            ...previous.filter((ref) => ref.id !== item.id),
                            item,
                          ]);
                          update({
                            leg_reference_ids: [
                              ...config.leg_reference_ids,
                              item.id,
                            ],
                          });
                        }}
                      >
                        {c.select}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Pages>
          )}
          <h3>{c.selected}</h3>
          <ol>
            {config.leg_reference_ids.map((id, index) => (
              <li key={id}>
                {references.find((item) => item.id === id)?.label ||
                  c.unknownLeg}
                <div className={styles.actions}>
                  {index > 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        const values = [...config.leg_reference_ids];
                        [values[index - 1], values[index]] = [
                          values[index],
                          values[index - 1],
                        ];
                        update({ leg_reference_ids: values });
                      }}
                    >
                      {c.moveUp}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() =>
                      update({
                        leg_reference_ids: config.leg_reference_ids.filter(
                          (value) => value !== id,
                        ),
                      })
                    }
                  >
                    {c.remove}
                  </button>
                </div>
              </li>
            ))}
          </ol>
          {config.leg_reference_ids.length > 1 && (
            <p role="status">{c.transfer}</p>
          )}
          <fieldset>
            <legend>{c.weekdays}</legend>
            <div className={styles.choices}>
              {commuteWeekdays[locale].map((name, day) => (
                <label className={styles.check} key={day}>
                  <input
                    type="checkbox"
                    checked={config.weekdays.includes(day)}
                    onChange={(event) =>
                      update({
                        weekdays: event.target.checked
                          ? [...config.weekdays, day].sort()
                          : config.weekdays.filter((value) => value !== day),
                      })
                    }
                  />
                  {name}
                </label>
              ))}
            </div>
          </fieldset>
          <div className={styles.fields}>
            <label>
              {c.startTime}
              <input
                type="time"
                required
                value={config.window_start}
                onChange={(event) =>
                  update({ window_start: event.target.value })
                }
              />
            </label>
            <label>
              {c.endTime}
              <input
                type="time"
                required
                value={config.window_end}
                onChange={(event) => update({ window_end: event.target.value })}
              />
            </label>
            <label>
              {c.threshold}
              <input
                type="number"
                required
                min={1}
                max={180}
                value={config.delay_threshold_minutes}
                onChange={(event) =>
                  update({
                    delay_threshold_minutes: Number(event.target.value),
                  })
                }
              />
            </label>
            <label>
              {c.reset}
              <input
                type="number"
                required
                min={0}
                max={config.delay_threshold_minutes - 1}
                value={config.delay_reset_minutes}
                onChange={(event) =>
                  update({ delay_reset_minutes: Number(event.target.value) })
                }
              />
            </label>
          </div>
          <p>{c.timezone}</p>
          {(
            [
              ["cancellations", c.cancellation],
              ["skipped_boarding_or_alighting", c.skipped],
              ["service_notices", c.notices],
            ] as const
          ).map(([key, text]) => (
            <label className={styles.check} key={key}>
              <input
                type="checkbox"
                checked={config[key]}
                onChange={(event) => update({ [key]: event.target.checked })}
              />
              {text}
            </label>
          ))}
          <label>
            {c.outside}
            <select
              value={config.outside_window}
              onChange={(event) =>
                update({
                  outside_window: event.target.value as "ignore" | "digest",
                })
              }
            >
              <option value="ignore">{c.ignore}</option>
              <option value="digest">{c.digest}</option>
            </select>
          </label>
          {!valid && <p>{c.invalid}</p>}
          <div className={styles.actions}>
            <button
              type="button"
              disabled={!valid || !day}
              onClick={() => {
                setPlan(null);
                void mutation.run<Preview>(
                  "/preview",
                  { configuration: config, service_day: day },
                  setPlan,
                );
              }}
            >
              {c.check}
            </button>
            <button type="submit" disabled={!valid}>
              {c.save}
            </button>
            <button type="button" onClick={cancel}>
              {c.cancel}
            </button>
          </div>
        </fieldset>
      </form>
      {mutation.error && <p role="alert">{mutation.error}</p>}
      {plan && (
        <section aria-label={c.preview}>
          <h3>{c.preview}</h3>
          <p>{c.previewHelp}</p>
          <ol>
            {plan.legs.map((leg) => (
              <li key={leg.reference_id}>
                {leg.route_name}: {leg.boarding_name} → {leg.alighting_name}
                <p>
                  <Time value={leg.departure} /> — <Time value={leg.arrival} />
                </p>
              </li>
            ))}
          </ol>
          {!!plan.interchanges?.length && (
            <section data-commute-interchanges>
              <h4>{commuteInterchangeCopy[locale].title}</h4>
              <p>{commuteInterchangeCopy[locale].note}</p>
              <ol>
                {plan.interchanges.map((item) => {
                  const copy = commuteInterchangeCopy[locale];
                  return (
                    <li
                      key={`${item.from_reference_id}:${item.to_reference_id}`}
                    >
                      {
                        plan.legs.find(
                          (leg) => leg.reference_id === item.from_reference_id,
                        )?.alighting_name
                      }
                      {" → "}
                      {
                        plan.legs.find(
                          (leg) => leg.reference_id === item.to_reference_id,
                        )?.boarding_name
                      }
                      <p>
                        {copy[item.state as keyof typeof copy] ||
                          copy.unverified}
                      </p>
                      {item.scheduled_seconds != null && (
                        <p>
                          {copy.scheduled}: {item.scheduled_seconds}
                        </p>
                      )}
                      {item.min_transfer_time != null && (
                        <p>
                          {copy.minimum}: {item.min_transfer_time}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ol>
            </section>
          )}
          {plan.blocking_reasons.map((code) => (
            <p role="status" key={code}>
              {reason(c, code)}
            </p>
          ))}
        </section>
      )}
    </section>
  );
}
function Conditions({
  current,
  references = [],
}: {
  current: Current;
  references?: ReferenceLabel[];
}) {
  const { locale } = useI18n(),
    c = commuteCopy[locale];
  return (
    <>
      {Object.entries(current.states).map(([id, state]) => {
        const edition = current.editions[id],
          header = sourceEdition(edition?.header || [], locale),
          description = sourceEdition(edition?.description || [], locale);
        return (
          <section key={id} className={styles.condition}>
            <h4>
              {references.find((item) => item.id === id)?.label || c.unknownLeg}
            </h4>
            <p>
              <strong>{label(c, state.condition)}</strong> ·{" "}
              {label(c, state.availability)}
            </p>
            {state.availability !== "present" && <p>{c.lastKnown}</p>}
            {state.delay_seconds != null && (
              <p>
                {c.delay}:{" "}
                {new Intl.NumberFormat(locale, {
                  maximumFractionDigits: 1,
                }).format(state.delay_seconds / 60)}
              </p>
            )}
            {state.observed_at && (
              <p>
                {c.observation}: <Time value={state.observed_at} />
              </p>
            )}
            {header && (
              <p className={styles.source} lang={header[0] || undefined}>
                <strong>{header[1]}</strong>
              </p>
            )}
            {description && (
              <p className={styles.source} lang={description[0] || undefined}>
                {description[1]}
              </p>
            )}
          </section>
        );
      })}
    </>
  );
}
function EventCard({
  event,
  monitor,
  canManage,
  changed,
  onDenied,
}: {
  event: CommuteEvent;
  monitor: CommuteMonitor;
  canManage: boolean;
  changed: () => void;
  onDenied?: () => void;
}) {
  const { locale } = useI18n(),
    c = commuteCopy[locale],
    mutation = useMutation(c);
  const [history, setHistory] = useState(false),
    [hidden, setHidden] = useState(false);
  if (!event.available || hidden || !event.current)
    return (
      <article className={styles.card}>
        <p role="status">{c.unavailable}</p>
        {mutation.error && <p role="alert">{mutation.error}</p>}
      </article>
    );
  const reviewed = event.reviewed_sequence === event.sequence;
  const controls = canManage && monitor.status !== "archived";
  const denied = () => {
    setHidden(true);
    onDenied?.();
  };
  function review(muted?: boolean) {
    void mutation.run(
      `/events/${event.id}/review`,
      {
        expected_version: event.version,
        sequence: event.sequence,
        ...(muted === undefined ? {} : { muted }),
      },
      changed,
      "POST",
      () => {
        denied();
      },
    );
  }
  return (
    <article className={styles.card} data-commute-event>
      <MonitoringEvidenceAsk
        domain="commute"
        monitorId={monitor.id}
        itemId={event.id}
        sequence={event.sequence}
        contextVersion={`${monitor.version}:${event.version}`}
      />
      <h3>
        {event.service_day} · {reviewed ? c.reviewed : c.unread}
      </h3>
      <p>
        {c.revision}: {event.configuration_revision} ·{" "}
        {commuteSources[event.source || ""] || c.unknown}
      </p>
      <Conditions
        current={event.current}
        references={event.reference_labels || monitor.reference_labels}
      />
      {event.configuration_revision !== monitor.revision && (
        <p>{c.olderSettings}</p>
      )}
      <div className={styles.actions}>
        {controls && (
          <>
            <button
              disabled={mutation.busy || reviewed}
              onClick={() => review()}
            >
              {c.review}
            </button>
            <button
              disabled={mutation.busy}
              onClick={() => review(!event.muted)}
            >
              {event.muted ? c.unmute : c.mute}
            </button>
          </>
        )}
        <button
          aria-expanded={history}
          onClick={() => setHistory((value) => !value)}
        >
          {c.history}
        </button>
      </div>
      {mutation.error && <p role="alert">{mutation.error}</p>}
      {history && (
        <section aria-label={c.history}>
          <Pages<EventVersion>
            path={`/events/${event.id}/history`}
            parameter="after_sequence"
            denied={denied}
          >
            {(items) =>
              items.map((version) => (
                <section className={styles.card} key={version.id}>
                  <h4>
                    {version.sequence} · <Time value={version.created_at} />
                  </h4>
                  <Conditions
                    current={savedConditions(version)}
                    references={savedLabels(version)}
                  />
                  <p>
                    {c.observation}:{" "}
                    <Time value={version.evidence.feed_observed_at} />
                  </p>
                  <details>
                    <summary>{c.evidence}</summary>
                    <p>{c.normalized}</p>
                    <p>
                      {commuteSources[version.evidence.source] || c.unknown}
                    </p>
                    <code>SHA-256: {version.evidence.feed_sha256}</code>
                  </details>
                </section>
              ))
            }
          </Pages>
        </section>
      )}
    </article>
  );
}
function LinkedEvent({
  eventId,
  sequence,
  monitor,
  canManage,
  changed,
}: {
  eventId: string;
  sequence: number;
  monitor: CommuteMonitor;
  canManage: boolean;
  changed: () => void;
}) {
  const { locale } = useI18n(),
    c = commuteCopy[locale];
  const [hidden, setHidden] = useState(false);
  const result = useData<LinkedCommuteEvent>(
    `/events/${eventId}?monitor_id=${monitor.id}${sequence ? `&sequence=${sequence}` : ""}`,
  );
  // An exact link is independently authorized even when its event is outside
  // the current history page. Never silently replace an unavailable snapshot.
  if (hidden) return <p role="alert">{c.unavailable}</p>;
  if (result.error) return <p role="alert">{failure(c, result.error)}</p>;
  if (!result.data) return <p role="status">{c.loading}</p>;
  const { event, snapshot, newer_available, current_configuration } =
    result.data;
  if (
    !event.available ||
    event.id !== eventId ||
    (sequence && snapshot.sequence !== sequence)
  )
    return <p role="alert">{c.unavailable}</p>;
  return (
    <section data-commute-linked>
      <MonitoringEvidenceAsk
        domain="commute"
        monitorId={monitor.id}
        itemId={event.id}
        sequence={snapshot.sequence}
        contextVersion={`${monitor.version}:${event.version}`}
      />
      {newer_available && <p role="status">{c.newerUpdate}</p>}
      <section className={styles.card}>
        <h3>
          {c.savedUpdate} · {snapshot.sequence}
        </h3>
        {!current_configuration && <p>{c.olderSettings}</p>}
        <Conditions
          current={savedConditions(snapshot)}
          references={savedLabels(snapshot)}
        />
        <p>
          {c.observation}: <Time value={snapshot.evidence.feed_observed_at} />
        </p>
        <details>
          <summary>{c.evidence}</summary>
          <p>{c.normalized}</p>
          <p>{commuteSources[snapshot.evidence.source] || c.unknown}</p>
          <code>SHA-256: {snapshot.evidence.feed_sha256}</code>
        </details>
      </section>
      <h3>{c.latestState}</h3>
      <EventCard
        event={event}
        monitor={monitor}
        canManage={canManage}
        changed={changed}
        onDenied={() => setHidden(true)}
      />
    </section>
  );
}
function Monitor({
  id,
  canManage,
  canStart,
  changed,
  removed,
  linkedEvent,
  linkedSequence,
}: {
  id: string;
  canManage: boolean;
  canStart: boolean;
  changed: () => void;
  removed: () => void;
  linkedEvent: string;
  linkedSequence: number;
}) {
  const { locale } = useI18n(),
    c = commuteCopy[locale];
  const [revision, setRevision] = useState(0),
    [editing, setEditing] = useState(false),
    [deleting, setDeleting] = useState(false);
  const [history, setHistory] = useState(false),
    mutation = useMutation(c);
  const monitor = useData<CommuteMonitor>(`/monitors/${id}`, revision);
  const refresh = () => {
    setRevision((value) => value + 1);
    setEditing(false);
    setDeleting(false);
    changed();
  };
  if (monitor.error)
    return (
      <section className={styles.card}>
        <p role="alert">{failure(c, monitor.error)}</p>
        <button onClick={refresh}>{c.refresh}</button>
      </section>
    );
  if (!monitor.data) return <p role="status">{c.loading}</p>;
  const row = monitor.data;
  const command = (action: string) => {
    void mutation.run(
      `/monitors/${id}/commands`,
      { expected_version: row.version, action },
      refresh,
      "POST",
      refresh,
    );
  };
  return (
    <div className={styles.detail} data-commute-detail>
      <section className={styles.card}>
        <h2>{row.configuration.name}</h2>
        <p>
          {label(c, row.status)} · {label(c, row.health)}
        </p>
        <SettingsSummary
          config={row.configuration}
          references={row.reference_labels}
        />
        {row.status === "active" && (
          <CommutePauseNotice until={row.notification_pause_until} />
        )}
        <p>
          {c.lastCheck}: <Time value={row.last_check_at} />
        </p>
        {row.status === "active" && (
          <p>
            {c.nextCheck}: <Time value={row.next_check_at} />
          </p>
        )}
        {mutation.error && <p role="alert">{mutation.error}</p>}
        <div className={styles.actions}>
          <button onClick={refresh} disabled={mutation.busy}>
            {c.refresh}
          </button>
          {canManage && (
            <>
              {(row.status === "draft" || row.status === "paused") && (
                <button
                  disabled={mutation.busy}
                  onClick={() => setEditing((value) => !value)}
                >
                  {c.edit}
                </button>
              )}
              {(row.status === "draft" || row.status === "paused") && (
                <button
                  disabled={mutation.busy || !canStart}
                  onClick={() =>
                    command(row.status === "draft" ? "start" : "resume")
                  }
                >
                  {row.status === "draft" ? c.start : c.resume}
                </button>
              )}
              {row.status === "active" && (
                <>
                  <button
                    disabled={mutation.busy}
                    onClick={() => command("pause")}
                  >
                    {c.pause}
                  </button>
                  <button
                    disabled={mutation.busy}
                    onClick={() =>
                      command(
                        row.paused_on === zurichDate()
                          ? "unpause_today"
                          : "pause_today",
                      )
                    }
                  >
                    {row.paused_on === zurichDate()
                      ? c.unpause_today
                      : c.pause_today}
                  </button>
                </>
              )}
              {row.status !== "archived" && (
                <button
                  disabled={mutation.busy}
                  onClick={() => command("archive")}
                >
                  {c.archive}
                </button>
              )}
              <button
                disabled={mutation.busy}
                onClick={() => setDeleting(true)}
              >
                {c.delete}
              </button>
            </>
          )}
          <button
            aria-expanded={history}
            onClick={() => setHistory((value) => !value)}
          >
            {c.revisions}
          </button>
        </div>
        {deleting && (
          <div role="group" aria-label={c.deletePrompt}>
            <p>{c.deletePrompt}</p>
            <div className={styles.actions}>
              <button
                disabled={mutation.busy}
                onClick={() => {
                  void mutation.run(
                    `/monitors/${id}`,
                    { expected_version: row.version },
                    removed,
                    "DELETE",
                    refresh,
                  );
                }}
              >
                {c.confirmDelete}
              </button>
              <button onClick={() => setDeleting(false)}>{c.cancel}</button>
            </div>
          </div>
        )}
      </section>
      {editing && (
        <Editor
          monitor={row}
          saved={refresh}
          cancel={() => setEditing(false)}
        />
      )}
      {history && (
        <section className={styles.card}>
          <h3>{c.revisions}</h3>
          <Pages<Revision>
            key={revision}
            path={`/monitors/${id}/revisions`}
            parameter="after_revision"
          >
            {(items) =>
              items.map((item) => (
                <section key={item.revision}>
                  <h4>
                    {item.revision} · {item.configuration.name}
                  </h4>
                  <SettingsSummary
                    config={item.configuration}
                    references={item.reference_labels}
                  />
                </section>
              ))
            }
          </Pages>
        </section>
      )}
      <CommuteEmail
        key={`${row.id}:${row.version}`}
        monitorId={row.id}
        canManage={canManage}
        archived={row.status === "archived"}
        changed={refresh}
      />
      <section aria-label={c.events}>
        <h2>{c.events}</h2>
        {linkedEvent && (
          <LinkedEvent
            key={`${linkedEvent}:${revision}`}
            eventId={linkedEvent}
            sequence={linkedSequence}
            monitor={row}
            canManage={canManage}
            changed={refresh}
          />
        )}
        <Pages<CommuteEvent> key={revision} path={`/monitors/${id}/events`}>
          {(items) =>
            items.length
              ? items
                  .filter((event) => event.id !== linkedEvent)
                  .map((event) => (
                    <EventCard
                      key={`${event.id}:${event.version}`}
                      event={event}
                      monitor={row}
                      canManage={canManage}
                      changed={refresh}
                    />
                  ))
              : !linkedEvent && <p>{c.noEvents}</p>
          }
        </Pages>
      </section>
    </div>
  );
}
export function CommuteWatch() {
  const { session } = useAuth(),
    params = useSearchParams();
  const scope = session?.authenticated
    ? `${session.user?.id}:${session.organization?.id}:${session.role}`
    : "unavailable";
  const initial = params.get("monitor") || "";
  const event = params.get("event") || "";
  const sequence = Number(params.get("sequence"));
  return (
    <Workspace
      key={`${scope}:${initial}:${event}:${sequence}`}
      allowed={scope !== "unavailable"}
      canManage={session?.role === "organization_admin"}
      initial={/^[0-9a-f-]{36}$/i.test(initial) ? initial : ""}
      linkedEvent={/^[0-9a-f-]{36}$/i.test(event) ? event : ""}
      linkedSequence={
        Number.isSafeInteger(sequence) && sequence > 0 ? sequence : 0
      }
    />
  );
}
function Workspace({
  allowed,
  canManage,
  initial,
  linkedEvent,
  linkedSequence,
}: {
  allowed: boolean;
  canManage: boolean;
  initial: string;
  linkedEvent: string;
  linkedSequence: number;
}) {
  const { locale } = useI18n(),
    c = commuteCopy[locale];
  const [selected, setSelected] = useState(initial),
    [creating, setCreating] = useState(false),
    [revision, setRevision] = useState(0);
  const [capRevision, setCapRevision] = useState(0);
  const capabilities = useData<Capabilities>(
    allowed ? "/capabilities" : null,
    capRevision,
  );
  const changed = () => setRevision((value) => value + 1);
  const removed = () => {
    setSelected("");
    changed();
  };
  return (
    <Shell section={c.title}>
      <div className={styles.root} data-commute-watch>
        <header>
          <h1>{c.title}</h1>
          <p>{c.intro}</p>
        </header>
        <p className={styles.notice}>{c.privacy}</p>
        <p>{c.noMail}</p>
        <p>
          <a
            href="https://opentransportdata.swiss/"
            target="_blank"
            rel="noreferrer"
          >
            {c.source}: {commuteProvider}
          </a>
        </p>
        <div className={styles.actions}>
          <Link href="/monitoring">{centreCopy[locale].title}</Link>
          <button
            disabled={!allowed}
            onClick={() => {
              setSelected("");
              setCreating(false);
              changed();
              setCapRevision((value) => value + 1);
            }}
          >
            {c.refresh}
          </button>
          {canManage && capabilities.data && (
            <button
              onClick={() => {
                setSelected("");
                setCreating(true);
              }}
            >
              {c.create}
            </button>
          )}
        </div>
        {!canManage && <p>{c.readonly}</p>}
        {capabilities.error ? (
          <p role="alert">{failure(c, capabilities.error)}</p>
        ) : allowed && !capabilities.data ? (
          <p role="status">{c.loading}</p>
        ) : null}
        {capabilities.data && !capabilities.data.start_available && (
          <p role="status">{c.sourceOff}</p>
        )}
        {allowed && capabilities.data && (
          <div className={styles.layout}>
            <aside className={styles.list} aria-label={c.title}>
              <Pages<CommuteMonitor> key={revision} path="/monitors">
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
                        {row.configuration.name} · {label(c, row.status)}
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
                saved={(row) => {
                  setSelected(row.id);
                  setCreating(false);
                  changed();
                }}
                cancel={() => setCreating(false)}
              />
            ) : selected ? (
              <Monitor
                key={selected}
                id={selected}
                canManage={canManage}
                canStart={capabilities.data.start_available}
                changed={changed}
                removed={removed}
                linkedEvent={selected === initial ? linkedEvent : ""}
                linkedSequence={linkedSequence}
              />
            ) : null}
          </div>
        )}
      </div>
    </Shell>
  );
}
