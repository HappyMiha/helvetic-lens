"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { pollenDraftCopy } from "@/lib/pollen-draft-copy";
import { pollenRuntimeCopy } from "@/lib/pollen-runtime-copy";
import type {
  ActivityPage,
  PollenActivity,
  PollenSample,
  PollenState,
  RuntimeAction,
  RuntimeCommand,
} from "@/lib/pollen-runtime";
import styles from "./pollen-draft-reader.module.css";

export function PollenRuntime({
  id,
  canManage,
  onDenied,
  onChanged,
}: {
  id: string;
  canManage: boolean;
  onDenied: (error: unknown) => void;
  onChanged: () => void;
}) {
  const { locale } = useI18n(),
    copy = pollenRuntimeCopy[locale],
    labels = pollenDraftCopy[locale];
  const [state, setState] = useState<PollenState | null>(null);
  const [activity, setActivity] = useState<ActivityPage>({
    items: [],
    next_cursor: null,
  });
  const [busy, setBusy] = useState(false),
    [consent, setConsent] = useState(false);
  const [notice, setNotice] = useState<
    "failed" | "conflict" | "uncertain" | null
  >(null);
  const [allHistory, setAllHistory] = useState(false);
  const [pending, setPending] = useState<RuntimeCommand | null>(null);
  const request = useRef<AbortController | null>(null),
    inFlight = useRef(false);
  const handlers = useRef({ onDenied, onChanged });
  const poll = useRef(() => {});
  handlers.current = { onDenied, onChanged };
  const base = `/monitoring-subjects/${encodeURIComponent(id)}`;

  function denied(error: unknown) {
    if (
      error instanceof ApiError &&
      [
        "authentication_required",
        "membership_required",
        "subject_role_denied",
        "forbidden",
        "subject_not_found",
        "monitoring_not_enabled",
      ].includes(error.code)
    ) {
      setState(null);
      setActivity({ items: [], next_cursor: null });
      setPending(null);
      handlers.current.onDenied(error);
      return true;
    }
    return false;
  }
  async function load(
    controller: AbortController,
    all: boolean,
    cursor?: string,
  ) {
    const [current, page] = await Promise.all([
      api<PollenState>(`${base}/state`, { signal: controller.signal }),
      api<ActivityPage>(
        `${base}/activity?limit=20&material_only=${!all}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
        { signal: controller.signal },
      ),
    ]);
    if (controller.signal.aborted) return;
    setState(current);
    setActivity((old) => ({
      items: cursor
        ? [
            ...old.items,
            ...page.items.filter(
              (item) => !old.items.some((row) => row.id === item.id),
            ),
          ]
        : page.items,
      next_cursor: page.next_cursor,
    }));
  }
  async function reload(all = allHistory, cursor?: string) {
    if (inFlight.current) return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    inFlight.current = true;
    setBusy(true);
    setNotice(null);
    try {
      await load(controller, all, cursor);
    } catch (error) {
      if (!controller.signal.aborted) {
        setState(null);
        setActivity({ items: [], next_cursor: null });
        if (!denied(error)) setNotice("failed");
      }
    } finally {
      if (!controller.signal.aborted) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  }
  useEffect(() => {
    void reload(false);
    const interval = window.setInterval(() => poll.current(), 60000);
    return () => {
      request.current?.abort();
      window.clearInterval(interval);
    };
    // The parent remounts this private component for identity, monitor or revision changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  poll.current = () => {
    if (
      state?.status === "active" &&
      !pending &&
      !inFlight.current &&
      activity.items.length <= 20 &&
      document.visibilityState === "visible" &&
      !document.querySelector("[data-pollen-runtime] details[open]")
    )
      void reload();
  };

  async function act(action: RuntimeAction, retry?: RuntimeCommand) {
    if (!state || inFlight.current || !canManage) return;
    if (action === "archive" && !retry && !window.confirm(copy.confirmArchive))
      return;
    const body = retry || {
      action,
      expected_revision: state.revision,
      expected_version: state.runtime.version,
      request_key: crypto.randomUUID(),
      email_consent:
        ["start", "resume", "consent_email"].includes(action) && consent,
    };
    const controller = new AbortController();
    request.current?.abort();
    request.current = controller;
    inFlight.current = true;
    setBusy(true);
    setNotice(null);
    setPending(body);
    try {
      await api(`${base}/commands`, {
        method: "POST",
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      setPending(null);
      setConsent(false);
      await load(controller, allHistory);
      if (!controller.signal.aborted) handlers.current.onChanged();
    } catch (error) {
      if (controller.signal.aborted || denied(error)) return;
      if (
        error instanceof ApiError &&
        [
          "monitoring_version_conflict",
          "monitoring_state_conflict",
          "pollen_source_not_ready",
          "monitoring_live_not_enabled",
          "pollen_category_not_ready",
        ].includes(error.code)
      ) {
        setPending(null);
        setState(null);
        setActivity({ items: [], next_cursor: null });
        setNotice("conflict");
      } else setNotice("uncertain");
    } finally {
      if (!controller.signal.aborted) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  }
  async function review(
    entry: PollenActivity,
    decision: "reviewed" | "not_relevant" | "continue" | "action_required",
  ) {
    if (inFlight.current || !canManage || pending) return;
    const controller = new AbortController();
    request.current?.abort();
    request.current = controller;
    inFlight.current = true;
    setBusy(true);
    setNotice(null);
    try {
      await api(`${base}/activity/${encodeURIComponent(entry.id)}/review`, {
        method: "POST",
        body: JSON.stringify({
          decision,
          expected_version: entry.review?.version || 0,
        }),
        signal: controller.signal,
      });
      await load(controller, allHistory);
    } catch (error) {
      if (!controller.signal.aborted && !denied(error)) {
        setActivity({ items: [], next_cursor: null });
        setNotice("conflict");
      }
    } finally {
      if (!controller.signal.aborted) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  }
  const label = (value: string) =>
    copy[value as keyof typeof copy] || copy.unverified;
  const date = (value: string) =>
    new Intl.DateTimeFormat(locale, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: state?.configuration.timezone || "Europe/Zurich",
    }).format(new Date(value));
  const sampleView = (sample: PollenSample) => (
    <>
      <p>
        <strong>
          {labels.allergens[sample.series.allergen] || labels.unknown} ·{" "}
          {sample.series.station_id}
        </strong>
      </p>
      <p>
        {sample.value === null
          ? copy.missing
          : `${sample.value} ${sample.series.unit}`}
      </p>
      <p>
        {sample.series.forecast ? copy.forecast : copy.measured} ·{" "}
        {labels.periods[sample.series.period] || labels.unknown}
      </p>
      {sample.series.forecast && (
        <p>
          {copy.issuedAt}:{" "}
          <time dateTime={sample.series.forecast.issue_at}>
            {date(sample.series.forecast.issue_at)}
          </time>
        </p>
      )}
      <p>
        {sample.series.forecast ? copy.validAt : copy.observedAt}:{" "}
        <time dateTime={sample.valid_at}>{date(sample.valid_at)}</time>
      </p>
    </>
  );
  return (
    <section data-pollen-runtime className={styles.runtime} aria-busy={busy}>
      <h2>{copy.title}</h2>
      <p>{copy.limit}</p>
      <button
        type="button"
        className={styles.button}
        disabled={busy}
        onClick={() => void reload()}
      >
        {copy.load}
      </button>
      {busy && <p role="status">{labels.loading}</p>}
      {notice && <p role="alert">{copy[notice]}</p>}
      {pending && notice === "uncertain" && (
        <button
          className={styles.button}
          type="button"
          disabled={busy}
          onClick={() => void act(pending.action, pending)}
        >
          {copy.retry}
        </button>
      )}
      {state && (
        <>
          {state.status !== "draft" && (
            <p role="status">{label(state.status)}</p>
          )}
          {state.runtime.health === "source_unavailable" && (
            <p role="status">{copy.source_unavailable}</p>
          )}
          {!state.current.length && <p>{copy.waiting}</p>}
          {state.current.map((item) => (
            <article className={styles.rule} key={item.stream_id}>
              <h3>{label(item.availability)}</h3>
              {sampleView(item.sample)}
              {item.category?.category && (
                <p>
                  {label(item.category.category)} ·{" "}
                  {item.category.scale_version}
                </p>
              )}
            </article>
          ))}
          {state.coverage
            .filter((channel) => channel.status !== "approved")
            .map((channel) => (
              <p key={`${channel.allergen}:${channel.period}`}>
                {labels.allergens[channel.allergen]} ·{" "}
                {labels.periods[channel.period]}: {copy.unverified}
              </p>
            ))}
          {canManage && (
            <fieldset
              disabled={busy || pending !== null}
              className={styles.rule}
            >
              <legend>{copy.controls}</legend>
              {state.configuration.delivery.email !== "off" &&
                !state.runtime.email_consent &&
                state.status !== "archived" && (
                  <>
                    <label>
                      <input
                        type="checkbox"
                        checked={consent}
                        onChange={(event) => setConsent(event.target.checked)}
                      />{" "}
                      {copy.consent}
                    </label>
                    <p>{copy.consentNote}</p>
                  </>
                )}
              {state.status === "draft" && (
                <button
                  type="button"
                  className={styles.button}
                  data-pollen-start
                  aria-describedby={
                    !state.start_available ? "pollen-start-blocked" : undefined
                  }
                  disabled={!state.start_available}
                  onClick={() => void act("start")}
                >
                  {copy.start}
                </button>
              )}
              {state.status === "paused" && (
                <button
                  type="button"
                  className={styles.button}
                  disabled={!state.start_available}
                  onClick={() => void act("resume")}
                >
                  {copy.resume}
                </button>
              )}
              {state.status === "active" && (
                <>
                  <button
                    type="button"
                    className={styles.button}
                    onClick={() => void act("pause")}
                  >
                    {copy.pause}
                  </button>
                  <button
                    type="button"
                    className={styles.button}
                    onClick={() =>
                      void act(state.runtime.muted ? "unmute" : "mute")
                    }
                  >
                    {state.runtime.muted ? copy.unmute : copy.mute}
                  </button>
                  {state.runtime.email_consent ? (
                    <button
                      type="button"
                      className={styles.button}
                      onClick={() => void act("unsubscribe")}
                    >
                      {copy.unsubscribe}
                    </button>
                  ) : (
                    state.configuration.delivery.email !== "off" && (
                      <button
                        type="button"
                        className={styles.button}
                        disabled={!consent || !state.start_available}
                        onClick={() => void act("consent_email")}
                      >
                        {copy.consent_email}
                      </button>
                    )
                  )}
                </>
              )}
              {["active", "paused"].includes(state.status) && (
                <button
                  type="button"
                  className={styles.button}
                  onClick={() => void act("archive")}
                >
                  {copy.archive}
                </button>
              )}
              {!state.start_available && state.status === "draft" && (
                <p id="pollen-start-blocked" className={styles.notice}>
                  {labels.blocked}
                </p>
              )}
            </fieldset>
          )}
          {!canManage && state.status === "draft" && !state.start_available && (
            <>
              <button
                className={styles.button}
                type="button"
                disabled
                aria-describedby="pollen-start-blocked"
              >
                {copy.start}
              </button>
              <p id="pollen-start-blocked" className={styles.notice}>
                {labels.blocked}
              </p>
            </>
          )}
          <h2>{copy.today}</h2>
          {Object.values(state.delivery_counts || {}).some(
            (count) => count > 0,
          ) && (
            <details>
              <summary>{copy.emailStatus}</summary>
              <ul>
                {Object.entries(state.delivery_counts || {}).map(
                  ([status, count]) => (
                    <li key={status}>
                      {status === "uncertain"
                        ? copy.uncertainDelivery
                        : label(status)}
                      : {count}
                    </li>
                  ),
                )}
              </ul>
            </details>
          )}
          <p>
            <a className={styles.button} href={`/api${base}/export`} download>
              {copy.exportHistory}
            </a>
          </p>
          <p>{copy.exportNote}</p>
          <label>
            <input
              type="checkbox"
              disabled={busy || pending !== null}
              checked={allHistory}
              onChange={(event) => {
                setAllHistory(event.target.checked);
                void reload(event.target.checked);
              }}
            />{" "}
            {copy.history}
          </label>
          {!activity.items.length && <p>{copy.noChanges}</p>}
          {activity.items.map((entry) => (
            <article
              className={styles.history}
              key={entry.id}
              data-pollen-activity
            >
              <h3>
                {label(entry.kind)} ·{" "}
                {entry.review
                  ? label(entry.review.decision)
                  : entry.material_id
                    ? copy.new
                    : copy.state}
              </h3>
              {sampleView(entry.current)}
              {entry.reasons.length > 0 && (
                <>
                  <h4>{copy.why}</h4>
                  <ul>
                    {entry.reasons.map((reason) => (
                      <li key={reason}>{label(reason)}</li>
                    ))}
                  </ul>
                </>
              )}
              <details>
                <summary>{copy.evidence}</summary>
                <p>
                  {labels.revision}: {entry.configuration_revision}
                </p>
                {entry.previous && (
                  <>
                    <h4>{copy.previous}</h4>
                    {sampleView(entry.previous)}
                  </>
                )}
                {entry.baseline && (
                  <>
                    <h4>{labels.rapid}</h4>
                    {sampleView(entry.baseline)}
                  </>
                )}
                {entry.binding.rule?.threshold && (
                  <p>
                    {labels.threshold}:{" "}
                    {entry.binding.rule.threshold.trigger_at_or_above}{" "}
                    {entry.current.series.unit} · {labels.reset}:{" "}
                    {entry.binding.rule.threshold.reset_at_or_below}
                  </p>
                )}
                <p>
                  {copy.retrieved}:{" "}
                  <time dateTime={entry.current.fetched_at}>
                    {date(entry.current.fetched_at)}
                  </time>
                </p>
                <p>
                  {entry.current.series.source_id} ·{" "}
                  {entry.current.series.method_version}
                </p>
                <p>{copy.artifactHash}</p>
                <ul>
                  {entry.current.artifact_hashes.map((hash) => (
                    <li key={hash} style={{ overflowWrap: "anywhere" }}>
                      {entry.raw_export_available ? (
                        <a
                          href={`/api${base}/activity/${encodeURIComponent(entry.id)}/artifacts/${encodeURIComponent(hash)}`}
                          download
                        >
                          <code>{hash}</code>
                        </a>
                      ) : (
                        <code>{hash}</code>
                      )}
                    </li>
                  ))}
                </ul>
                <p>
                  <a
                    href="https://opendatadocs.meteoswiss.ch/general/terms-of-use"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {copy.attribution}
                  </a>
                </p>
                <ReviewHistory
                  key={`${entry.id}:${entry.review?.version || 0}`}
                  base={base}
                  entry={entry.id}
                  onDenied={onDenied}
                />
              </details>
              {canManage && entry.material_id && (
                <div>
                  {(
                    [
                      "reviewed",
                      "not_relevant",
                      "continue",
                      "action_required",
                    ] as const
                  ).map((decision) => (
                    <button
                      type="button"
                      className={styles.button}
                      key={decision}
                      disabled={busy || pending !== null}
                      aria-pressed={entry.review?.decision === decision}
                      onClick={() => void review(entry, decision)}
                    >
                      {copy[decision]}
                    </button>
                  ))}
                </div>
              )}
            </article>
          ))}
          {activity.next_cursor && (
            <button
              type="button"
              className={styles.button}
              disabled={busy || pending !== null}
              onClick={() => void reload(allHistory, activity.next_cursor!)}
            >
              {labels.more}
            </button>
          )}
        </>
      )}
    </section>
  );
}

function ReviewHistory({
  base,
  entry,
  onDenied,
}: {
  base: string;
  entry: string;
  onDenied: (error: unknown) => void;
}) {
  const { locale } = useI18n(),
    copy = pollenRuntimeCopy[locale],
    labels = pollenDraftCopy[locale];
  type Page = {
    items: {
      version: number;
      decision: "reviewed" | "not_relevant" | "continue" | "action_required";
      created_at: string;
    }[];
    next_before_version: number | null;
  };
  const [page, setPage] = useState<Page | null>(null),
    [busy, setBusy] = useState(false),
    [failed, setFailed] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  async function load(before?: number) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setFailed(false);
    try {
      const result = await api<Page>(
        `${base}/activity/${encodeURIComponent(entry)}/reviews${before ? `?before_version=${before}` : ""}`,
        { signal: controller.signal },
      );
      if (!controller.signal.aborted)
        setPage((old) => ({
          items: before
            ? [...(old?.items || []), ...result.items]
            : result.items,
          next_before_version: result.next_before_version,
        }));
    } catch (error) {
      if (!controller.signal.aborted) {
        setPage(null);
        setFailed(true);
        if (
          error instanceof ApiError &&
          [
            "authentication_required",
            "membership_required",
            "subject_role_denied",
            "forbidden",
            "subject_not_found",
            "monitoring_not_enabled",
          ].includes(error.code)
        )
          onDenied(error);
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  return (
    <details
      onToggle={(event) => {
        if (event.currentTarget.open && !page && !busy) void load();
      }}
    >
      <summary>{copy.reviews}</summary>
      {page && (
        <ol>
          {page.items.map((item) => (
            <li key={item.version}>
              {copy[item.decision]} ·{" "}
              <time dateTime={item.created_at}>
                {new Intl.DateTimeFormat(locale, {
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(new Date(item.created_at))}
              </time>
            </li>
          ))}
        </ol>
      )}
      {failed && <p role="alert">{copy.failed}</p>}
      {(page?.next_before_version || failed) && (
        <button
          type="button"
          className={styles.button}
          disabled={busy}
          onClick={() => void load(page?.next_before_version || undefined)}
        >
          {failed ? copy.load : labels.more}
        </button>
      )}
    </details>
  );
}
