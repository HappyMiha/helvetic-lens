"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { auctionCopy } from "@/lib/auction-copy";
import { auctionTrackingCopy } from "@/lib/auction-tracking-copy";
import type {
  AuctionMonitor,
  AuctionPage,
  AuctionProfile,
} from "@/lib/auction-watch";
import { useData, useMutation } from "./auction-client";
import { BusinessItemWork, AssignmentFilter } from "./business-item-work";
import styles from "./commute-watch.module.css";

export type Facts = {
  title: string;
  description: string | null;
  canton: string;
  auction_id: string;
  lot_id: string | null;
  authority: string;
  category: AuctionProfile["categories"][number] | null;
  asset_location: string | null;
  brand: string | null;
  prices: {
    kind: AuctionProfile["budget_price_kind"];
    amount_minor: number;
    currency: string;
  }[];
  status:
    "announced" | "open" | "closed" | "cancelled" | "postponed" | "unknown";
  ends_at: string | null;
  observed_at: string;
  source_url: string;
  documents: { state: string; items: { official_id: string; title: string }[] };
};
export type Item = {
  id: string;
  version: number;
  following: boolean;
  decision: "inspect" | "bid" | "no_bid" | "monitor" | null;
  needs_review: boolean;
  state: string;
  can_review: boolean;
  state_hash?: string;
  facts: Facts | null;
  attribution?: string;
  assessment: {
    status: "match" | "excluded" | "unknown";
    reasons: { field: string; status: "match" | "excluded" | "unknown" }[];
  } | null;
};
type Preview = {
  start_available: boolean;
  source_attributions: string[];
  unverified_cantons: string[];
};

export function Timestamp({ value }: { value: string | null }) {
  const { locale } = useI18n();
  return value ? (
    <time dateTime={value}>
      {new Intl.DateTimeFormat(locale === "rm-CH" ? "de-CH" : locale, {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "Europe/Zurich",
      }).format(new Date(value))}
    </time>
  ) : (
    <>{auctionTrackingCopy[locale].unknown}</>
  );
}

export function Evidence({ facts }: { facts: Facts }) {
  const { locale } = useI18n(),
    c = auctionCopy[locale],
    w = auctionTrackingCopy[locale];
  const money = new Intl.NumberFormat(locale === "rm-CH" ? "de-CH" : locale, {
    style: "currency",
    currency: "CHF",
  });
  return (
    <div data-auction-evidence>
      <h4>{facts.title}</h4>
      <p>
        {facts.authority} · {facts.canton} · {facts.auction_id}
        {facts.lot_id ? ` / ${facts.lot_id}` : ""}
      </p>
      <dl>
        <dt>{w.status}</dt>
        <dd>{w.statuses[facts.status]}</dd>
        <dt>{w.deadline}</dt>
        <dd>
          <Timestamp value={facts.ends_at} />
        </dd>
        <dt>{w.observed}</dt>
        <dd>
          <Timestamp value={facts.observed_at} />
        </dd>
        <dt>{w.fields.category}</dt>
        <dd>{facts.category ? c[facts.category] : w.unknown}</dd>
        <dt>{w.fields.asset_location}</dt>
        <dd>{facts.asset_location || w.unknown}</dd>
        <dt>{w.fields.brand}</dt>
        <dd>{facts.brand || w.unknown}</dd>
        <dt>{w.price}</dt>
        <dd>
          {facts.prices.length ? (
            <ul>
              {facts.prices.map((price) => (
                <li key={price.kind}>
                  {c[price.kind]}:{" "}
                  {price.currency === "CHF"
                    ? money.format(price.amount_minor / 100)
                    : `${price.currency} ${price.amount_minor} ${w.minorUnits}`}
                </li>
              ))}
            </ul>
          ) : (
            w.unknown
          )}
        </dd>
      </dl>
      <a href={facts.source_url} target="_blank" rel="noreferrer">
        {w.official}
      </a>
      {facts.description && (
        <details>
          <summary>{w.description}</summary>
          <p>{facts.description}</p>
        </details>
      )}
      <details>
        <summary>{w.documents}</summary>
        {facts.documents.state !== "complete" && <p>{w.partial}</p>}
        <ul>
          {facts.documents.items.map((document) => (
            <li key={document.official_id}>{document.title}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function SourceHistory({ path }: { path: string }) {
  const { locale } = useI18n(),
    c = auctionCopy[locale],
    w = auctionTrackingCopy[locale];
  const [anchors, setAnchors] = useState<(number | null)[]>([null]);
  const before = anchors.at(-1),
    result = useData<
      AuctionPage<{
        id: string;
        sequence: number;
        state: string;
        facts?: Facts;
      }>
    >(`${path}/history?limit=5${before ? `&before=${before}` : ""}`);
  return (
    <section data-auction-source-history>
      <h4>{w.history}</h4>
      {result.error ? (
        <p role="alert">{w.unavailable}</p>
      ) : !result.data ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          {result.data.items.map((row) => (
            <details key={row.id}>
              <summary>
                {w.sourceVersion} {row.sequence}
              </summary>
              {row.state === "available" && row.facts ? (
                <Evidence facts={row.facts} />
              ) : (
                <p>{w.unavailableVersion}</p>
              )}
            </details>
          ))}
          <div className={styles.actions}>
            <button
              disabled={anchors.length === 1}
              onClick={() => setAnchors((v) => v.slice(0, -1))}
            >
              {c.back}
            </button>
            <button
              disabled={!result.data.next_cursor}
              onClick={() =>
                setAnchors((v) => [...v, Number(result.data!.next_cursor)])
              }
            >
              {c.next}
            </button>
          </div>
        </>
      )}
    </section>
  );
}

export function Lot({
  row,
  monitor,
  canManage,
  changed,
}: {
  row: Item;
  monitor: AuctionMonitor;
  canManage: boolean;
  changed: () => void;
}) {
  const { locale } = useI18n(),
    w = auctionTrackingCopy[locale];
  const [history, setHistory] = useState(false),
    mutation = useMutation();
  const path = `/monitors/${monitor.id}/items/${row.id}`,
    canAct = canManage && monitor.status !== "archived";
  const version = {
    expected_version: row.version,
    expected_state_hash: row.state_hash ?? null,
  };
  return (
    <article className={styles.card} data-auction-item={row.id}>
      <BusinessItemWork
        domain="auctions"
        monitorId={monitor.id}
        itemId={row.id}
        version={row.version}
        canManage={canAct}
        changed={changed}
      />
      <p>
        <strong>{row.needs_review ? w.needsReview : w.reviewed}</strong>
      </p>
      {row.state === "available" && row.facts ? (
        <>
          <Evidence facts={row.facts} />
          <p>
            {w.source}: {row.attribution}
          </p>
          {row.assessment && (
            <section>
              <h4>
                {w.explanation}: {w[row.assessment.status]}
              </h4>
              <ul>
                {row.assessment.reasons.map((reason) => (
                  <li key={reason.field}>
                    {
                      w.fields[
                        reason.field.startsWith("prices.")
                          ? "budget"
                          : (reason.field as keyof typeof w.fields)
                      ]
                    }
                    : {w[reason.status]}
                  </li>
                ))}
              </ul>
            </section>
          )}
          {!row.can_review && <p>{w.noDecisionAccess}</p>}
        </>
      ) : (
        <p role="status">{w.unavailable}</p>
      )}
      <p>
        {w.decision}: {row.decision ? w[row.decision] : w.unknown}
      </p>
      <div className={styles.actions}>
        {canAct && (row.following || row.can_review) && (
          <button
            disabled={mutation.busy}
            aria-pressed={row.following}
            onClick={() =>
              void mutation.run(
                `${path}/follow`,
                { ...version, following: !row.following },
                changed,
              )
            }
          >
            {row.following ? w.unfollow : w.follow}
          </button>
        )}
        {canAct &&
          row.can_review &&
          (["inspect", "bid", "no_bid", "monitor"] as const).map((decision) => (
            <button
              key={decision}
              disabled={mutation.busy}
              aria-pressed={row.decision === decision && !row.needs_review}
              onClick={() =>
                void mutation.run(
                  `${path}/decision`,
                  { ...version, decision },
                  changed,
                )
              }
            >
              {w[decision]}
            </button>
          ))}
        <button onClick={() => setHistory((v) => !v)} aria-expanded={history}>
          {w.history}
        </button>
      </div>
      {mutation.error && <p role="alert">{mutation.error}</p>}
      {history &&
        (row.state === "available" ? (
          <SourceHistory path={path} />
        ) : (
          <p>{w.unavailable}</p>
        ))}
    </article>
  );
}

export function AuctionTracking({
  monitor,
  canManage,
  changed,
}: {
  monitor: AuctionMonitor;
  canManage: boolean;
  changed: () => void;
}) {
  const { locale } = useI18n(),
    c = auctionCopy[locale],
    w = auctionTrackingCopy[locale];
  const [preview, setPreview] = useState<Preview | null>(null),
    [revision, setRevision] = useState(0);
  const [onlyFollowed, setOnlyFollowed] = useState(false),
    [anchors, setAnchors] = useState<(string | null)[]>([null]);
  const [assignment, setAssignment] = useState("");
  const mutation = useMutation(),
    after = anchors.at(-1);
  const result = useData<AuctionPage<Item>>(
    monitor.status !== "draft"
      ? `/monitors/${monitor.id}/items?limit=20&following_only=${onlyFollowed}${after ? `&after_id=${after}` : ""}${assignment ? `&assignment=${assignment}` : ""}`
      : null,
    revision,
  );
  useEffect(() => {
    if (monitor.status !== "active") return;
    const timer = window.setInterval(() => {
      if (!document.hidden) setRevision((v) => v + 1);
    }, 60000);
    return () => window.clearInterval(timer);
  }, [monitor.status]);
  const reload = () => setRevision((v) => v + 1);
  return (
    <section data-auction-tracking>
      <div className={styles.actions}>
        {canManage &&
          (monitor.status === "draft" || monitor.status === "paused") && (
            <>
              <button
                disabled={mutation.busy}
                onClick={() =>
                  void mutation.run<Preview>(
                    "/preview",
                    { configuration: monitor.configuration },
                    setPreview,
                  )
                }
              >
                {w.check}
              </button>
              {preview?.start_available && (
                <button
                  disabled={mutation.busy}
                  onClick={() =>
                    void mutation.run(
                      `/monitors/${monitor.id}/start`,
                      { expected_version: monitor.version },
                      changed,
                    )
                  }
                >
                  {monitor.status === "paused" ? w.resume : w.start}
                </button>
              )}
            </>
          )}
        {canManage && monitor.status === "active" && (
          <>
            <button
              disabled={mutation.busy}
              onClick={() =>
                void mutation.run(
                  `/monitors/${monitor.id}/pause`,
                  { expected_version: monitor.version },
                  changed,
                )
              }
            >
              {w.pause}
            </button>
            <button
              disabled={mutation.busy}
              onClick={() =>
                void mutation.run(`/monitors/${monitor.id}/refresh`, {}, () => {
                  reload();
                  changed();
                })
              }
            >
              {w.refreshItems}
            </button>
          </>
        )}
      </div>
      {preview && (
        <div role="status">
          <p>{preview.start_available ? w.sourceReady : w.missing}</p>
          <p>{w.partial}</p>
          {!!preview.source_attributions?.length && (
            <p>{preview.source_attributions.join(" · ")}</p>
          )}
          {!!preview.unverified_cantons?.length && (
            <p>
              {w.cantons}: {preview.unverified_cantons.join(", ")}
            </p>
          )}
        </div>
      )}
      {mutation.error && <p role="alert">{mutation.error}</p>}
      {monitor.runtime && (
        <dl>
          <dt>{w.lastCheck}</dt>
          <dd>
            <Timestamp value={monitor.runtime.last_check_at} />
          </dd>
          <dt>{w.nextCheck}</dt>
          <dd>
            <Timestamp value={monitor.runtime.next_check_at} />
          </dd>
        </dl>
      )}
      <p>{w.internal}</p>
      {monitor.status !== "draft" && (
        <section>
          <h3>{w.items}</h3>
          <p>{w.partial}</p>
          <label className={styles.check}>
            <input
              type="checkbox"
              checked={onlyFollowed}
              onChange={(e) => {
                setOnlyFollowed(e.target.checked);
                setAnchors([null]);
              }}
            />
            {w.onlyFollowed}
          </label>
          <AssignmentFilter
            value={assignment}
            changed={(value) => {
              setAssignment(value);
              setAnchors([null]);
            }}
          />
          <button onClick={reload}>{c.refresh}</button>
          {result.error ? (
            <p role="alert">{w.unavailable}</p>
          ) : !result.data ? (
            <p role="status">{c.loading}</p>
          ) : (
            <>
              {!result.data.items.length && <p>{w.empty}</p>}
              {result.data.items.map((row) => (
                <Lot
                  key={`${row.id}:${row.version}`}
                  row={row}
                  monitor={monitor}
                  canManage={canManage}
                  changed={reload}
                />
              ))}
              <div className={styles.actions}>
                <button
                  disabled={anchors.length === 1}
                  onClick={() => setAnchors((v) => v.slice(0, -1))}
                >
                  {c.back}
                </button>
                <button
                  disabled={!result.data.next_cursor}
                  onClick={() =>
                    setAnchors((v) => [...v, String(result.data!.next_cursor)])
                  }
                >
                  {c.next}
                </button>
              </div>
            </>
          )}
        </section>
      )}
    </section>
  );
}
