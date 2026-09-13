"use client";

import { useState } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { hazardCopy } from "@/lib/hazard-copy";
import { hazardEventCopy } from "@/lib/hazard-event-copy";
import {
  hazardHref,
  officialLink,
  type HazardEvent,
  type HazardMutes,
  type HazardReview,
  type HazardTarget,
} from "@/lib/hazard-events";
import { hazardKinds, type HazardMonitor, type Page } from "@/lib/hazard-watch";
import { roadCopy } from "@/lib/road-copy";
import { useData, useMutation } from "./hazard-data";
import styles from "./commute-watch.module.css";

function Stamp({ value }: { value?: string | null }) {
  const { locale } = useI18n();
  if (!value || !Number.isFinite(Date.parse(value))) return <span>—</span>;
  return (
    <time dateTime={value}>
      {new Intl.DateTimeFormat(locale, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))}
    </time>
  );
}
function EventState({ row }: { row: HazardEvent }) {
  const { locale } = useI18n(),
    c = hazardEventCopy[locale];
  return (
    <p>
      {c[row.state] || c.unavailable}
      {row.muted && <> · {c.muted}</>}
      {row.state !== "unavailable" && (
        <>
          {" "}
          ·{" "}
          {row.dismissed
            ? c.dismissed
            : row.reviewed
              ? c.reviewed
              : c.needsReview}
        </>
      )}
    </p>
  );
}
function EventHistory({
  monitor,
  event,
  refresh,
}: {
  monitor: string;
  event: string;
  refresh: number;
}) {
  const { locale } = useI18n(),
    c = hazardEventCopy[locale],
    r = roadCopy[locale];
  const [anchors, setAnchors] = useState<(number | null)[]>([null]),
    before = anchors.at(-1);
  const result = useData<Page<HazardEvent>>(
    `/monitors/${monitor}/events/${event}/history?limit=10${before ? `&before=${before}` : ""}`,
    refresh,
  );
  return (
    <section aria-label={c.history} data-hazard-event-history>
      <h4>{c.history}</h4>
      {result.error ? (
        <p role="alert">{r.failed}</p>
      ) : !result.data ? (
        <p role="status">{r.loading}</p>
      ) : (
        <ul>
          {result.data.items.map((row) => (
            <li key={row.revision}>
              <Link
                prefetch={false}
                href={hazardHref(monitor, event, row.revision)}
              >
                {r.version} {row.revision} · {c[row.state]}
              </Link>
              <EventState row={row} />
            </li>
          ))}
        </ul>
      )}
      <div className={styles.actions}>
        {anchors.length > 1 && (
          <button onClick={() => setAnchors((v) => v.slice(0, -1))}>
            {r.previous}
          </button>
        )}
        {result.data?.next_cursor != null && (
          <button
            onClick={() =>
              setAnchors((v) => [...v, Number(result.data!.next_cursor)])
            }
          >
            {r.more}
          </button>
        )}
      </div>
    </section>
  );
}
function ReviewHistory({
  monitor,
  event,
  refresh,
}: {
  monitor: string;
  event: string;
  refresh: number;
}) {
  const { locale } = useI18n(),
    c = hazardEventCopy[locale],
    r = roadCopy[locale];
  const [anchors, setAnchors] = useState<(string | null)[]>([null]),
    before = anchors.at(-1);
  const result = useData<Page<HazardReview>>(
    `/monitors/${monitor}/events/${event}/reviews?limit=10${before ? `&before_id=${encodeURIComponent(before)}` : ""}`,
    refresh,
  );
  return (
    <section aria-label={c.audit} data-hazard-review-history>
      <h4>{c.audit}</h4>
      {result.error ? (
        <p role="alert">{r.failed}</p>
      ) : !result.data ? (
        <p role="status">{r.loading}</p>
      ) : (
        <ul>
          {result.data.items.map((action) => (
            <li key={action.id}>
              {action.action === "reviewed" ? c.reviewed : c.dismissed} ·{" "}
              <Stamp value={action.created_at} /> · {r.version}{" "}
              {action.revision}
            </li>
          ))}
        </ul>
      )}
      <div className={styles.actions}>
        {anchors.length > 1 && (
          <button onClick={() => setAnchors((v) => v.slice(0, -1))}>
            {r.previous}
          </button>
        )}
        {result.data?.next_cursor && (
          <button
            onClick={() =>
              setAnchors((v) => [...v, String(result.data!.next_cursor)])
            }
          >
            {r.more}
          </button>
        )}
      </div>
    </section>
  );
}
function Reader({
  monitor,
  target,
  canManage,
}: {
  monitor: string;
  target: HazardTarget;
  canManage: boolean;
}) {
  const { locale } = useI18n(),
    c = hazardEventCopy[locale],
    r = roadCopy[locale];
  const [refresh, setRefresh] = useState(0),
    [history, setHistory] = useState(false),
    [audit, setAudit] = useState(false),
    [language, setLanguage] = useState(locale as string);
  const path = `/monitors/${monitor}/events/${target.event}`;
  const result = useData<HazardEvent>(
      path + (target.revision != null ? `?revision=${target.revision}` : ""),
      refresh,
    ),
    mutation = useMutation(),
    row = result.data;
  const infos = row?.source?.message.infos || [];
  const info =
    infos.find((i) => i.language === language) ||
    infos.find((i) => i.language.split("-")[0] === locale.split("-")[0]) ||
    infos[0];
  const link = officialLink(info?.web);
  return (
    <section data-hazard-event-reader>
      <div className={styles.actions}>
        <Link prefetch={false} href={hazardHref(monitor)}>
          {c.back}
        </Link>
        <button
          disabled={mutation.busy}
          onClick={() => setRefresh((v) => v + 1)}
        >
          {r.refresh}
        </button>
      </div>
      {result.error ? (
        <p role="alert">{r.failed}</p>
      ) : !row ? (
        <p role="status">{r.loading}</p>
      ) : (
        <>
          <h4>
            {row.historical ? c.historical : c.current} · {r.version}{" "}
            {row.revision}
          </h4>
          <EventState row={row} />
          {row.historical && (
            <Link prefetch={false} href={hazardHref(monitor, target.event)}>
              {c.openCurrent}
            </Link>
          )}
          {row.state === "unavailable" || !row.source ? (
            <p className={styles.notice}>{c.unavailableDetail}</p>
          ) : (
            <>
              {row.state === "cancelled" && (
                <p className={styles.notice}>{c.cancelledDetail}</p>
              )}
              {row.decision?.match?.basis === "administrative_filter" && (
                <p>{c.adminFilter}</p>
              )}
              {row.decision?.match?.basis === "explicit_geometry" && (
                <p>{c.geometryMatch}</p>
              )}

              {info && (
                <label>
                  {c.language}
                  <select
                    value={info.language}
                    onChange={(e) => setLanguage(e.target.value)}
                  >
                    {infos.map((item) => (
                      <option key={item.language} value={item.language}>
                        {item.language}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <p>{c.original}</p>
              <article
                lang={info?.language}
                aria-label={c.official}
                data-hazard-official
              >
                {info && <h5>{info.headline || info.event}</h5>}
                <div className={styles.notice}>
                  <h5>
                    <strong>{c.instructions}</strong>
                  </h5>
                  <p className={styles.source}>
                    {info?.instruction || c.noInstructions}
                  </p>
                </div>
                {info?.description && (
                  <p className={styles.source}>{info.description}</p>
                )}
                <p>{row.source.attribution}</p>
                {link && (
                  <a href={link} target="_blank" rel="noopener noreferrer">
                    {c.openOfficial}
                  </a>
                )}
              </article>
              <dl>
                {row.decision?.importance && (
                  <>
                    <dt>{c.importance}</dt>
                    <dd>{c[row.decision.importance]}</dd>
                  </>
                )}
                {row.decision?.certainty && (
                  <>
                    <dt>{c.certainty}</dt>
                    <dd>{c[row.decision.certainty]}</dd>
                  </>
                )}
                <dt>{c.published}</dt>
                <dd>
                  <Stamp value={row.source.message.identity.sent} />
                </dd>
                <dt>{c.fetched}</dt>
                <dd>
                  <Stamp value={row.source.last_seen_at} />
                </dd>
                {info?.effective && (
                  <>
                    <dt>{c.effective}</dt>
                    <dd>
                      <Stamp value={info.effective} />
                    </dd>
                  </>
                )}
                {info?.expires && (
                  <>
                    <dt>{c.expires}</dt>
                    <dd>
                      <Stamp value={info.expires} />
                    </dd>
                  </>
                )}
              </dl>
              {canManage && !row.historical && (
                <div className={styles.actions} data-hazard-review-actions>
                  <button
                    disabled={mutation.busy || row.reviewed}
                    onClick={() =>
                      void mutation.run(
                        path + "/review",
                        {
                          expected_version: row.version,
                          expected_revision: row.revision,
                          action: "reviewed",
                        },
                        () => setRefresh((v) => v + 1),
                      )
                    }
                  >
                    {c.markReviewed}
                  </button>
                  <button
                    disabled={mutation.busy || row.dismissed}
                    onClick={() =>
                      void mutation.run(
                        path + "/review",
                        {
                          expected_version: row.version,
                          expected_revision: row.revision,
                          action: "not_relevant",
                        },
                        () => setRefresh((v) => v + 1),
                      )
                    }
                  >
                    {c.dismiss}
                  </button>
                </div>
              )}
            </>
          )}
          <div className={styles.actions}>
            <button
              aria-expanded={history}
              onClick={() => setHistory((v) => !v)}
            >
              {c.history}
            </button>
            <button aria-expanded={audit} onClick={() => setAudit((v) => !v)}>
              {c.audit}
            </button>
          </div>
          {history && (
            <EventHistory
              monitor={monitor}
              event={target.event}
              refresh={refresh}
            />
          )}
          {audit && (
            <ReviewHistory
              monitor={monitor}
              event={target.event}
              refresh={refresh}
            />
          )}
        </>
      )}
      {mutation.error && <p role="alert">{mutation.error}</p>}
    </section>
  );
}
function EventList({ monitor }: { monitor: string }) {
  const { locale } = useI18n(),
    c = hazardEventCopy[locale],
    h = hazardCopy[locale],
    r = roadCopy[locale];
  const [anchors, setAnchors] = useState<(string | null)[]>([null]),
    after = anchors.at(-1);
  const result = useData<Page<HazardEvent>>(
    `/monitors/${monitor}/events?limit=10${after ? `&after_id=${encodeURIComponent(after)}` : ""}`,
  );
  return (
    <section data-hazard-events-list>
      {result.error ? (
        <p role="alert">{r.failed}</p>
      ) : !result.data ? (
        <p role="status">{r.loading}</p>
      ) : result.data.items.length ? (
        <ul>
          {result.data.items.map((row) => (
            <li key={row.id}>
              <Link prefetch={false} href={hazardHref(monitor, row.id)}>
                {row.decision?.hazards?.map((kind) => h[kind]).join(", ") ||
                  c.official}{" "}
                · {r.version} {row.revision}
              </Link>
              <EventState row={row} />
            </li>
          ))}
        </ul>
      ) : (
        <p>{c.empty}</p>
      )}
      <div className={styles.actions}>
        {anchors.length > 1 && (
          <button onClick={() => setAnchors((v) => v.slice(0, -1))}>
            {r.previous}
          </button>
        )}
        {result.data?.next_cursor && (
          <button
            onClick={() =>
              setAnchors((v) => [...v, String(result.data!.next_cursor)])
            }
          >
            {r.more}
          </button>
        )}
      </div>
    </section>
  );
}
function Mutes({
  row,
  canManage,
  changed,
}: {
  row: HazardMonitor;
  canManage: boolean;
  changed: () => void;
}) {
  const { locale } = useI18n(),
    c = hazardEventCopy[locale],
    h = hazardCopy[locale],
    r = roadCopy[locale];
  const result = useData<HazardMutes>(`/monitors/${row.id}/mutes`, row.version),
    mutation = useMutation();
  return (
    <section data-hazard-mutes>
      <h4>{c.muteTitle}</h4>
      <p>{c.muteHint}</p>
      {result.error ? (
        <p role="alert">{r.failed}</p>
      ) : !result.data ? (
        <p role="status">{r.loading}</p>
      ) : (
        <ul>
          {hazardKinds.map((kind) => {
            const muted = result.data!.muted_hazards.includes(kind);
            return (
              <li key={kind} className={styles.actions}>
                <span>
                  {h[kind]}
                  {muted && <> · {c.muted}</>}
                </span>
                {canManage && row.status !== "archived" && (
                  <button
                    disabled={mutation.busy}
                    onClick={() =>
                      void mutation.run(
                        `/monitors/${row.id}/mutes/${kind}`,
                        {
                          expected_version: result.data!.version,
                          muted: !muted,
                        },
                        changed,
                        "PATCH",
                      )
                    }
                  >
                    {muted ? c.unmute : c.mute}: {h[kind]}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {mutation.error && <p role="alert">{mutation.error}</p>}
    </section>
  );
}
export function HazardEvents({
  row,
  target,
  canManage,
  changed,
}: {
  row: HazardMonitor;
  target: HazardTarget;
  canManage: boolean;
  changed: () => void;
}) {
  const { locale } = useI18n(),
    c = hazardEventCopy[locale];
  return (
    <section className={styles.card} data-hazard-events>
      <h3>{c.events}</h3>
      <p className={styles.notice}>{c.coverage}</p>
      {target.invalid ? (
        <p role="alert">{c.invalidLink}</p>
      ) : target.event ? (
        <Reader
          key={`${target.event}:${target.revision}`}
          monitor={row.id}
          target={target}
          canManage={canManage}
        />
      ) : (
        <EventList monitor={row.id} />
      )}
      <Mutes row={row} canManage={canManage} changed={changed} />
    </section>
  );
}
