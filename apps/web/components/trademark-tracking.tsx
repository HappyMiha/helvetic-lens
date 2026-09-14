"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useI18n } from "@/lib/i18n";
import { trademarkCopy } from "@/lib/trademark-copy";
import {
  trademarkReviewCopy,
  trademarkChangeLabel,
} from "@/lib/trademark-review-copy";
import type { TrademarkMonitor, TrademarkPage } from "@/lib/trademark-watch";
import { useData, useMutation } from "./trademark-client";
import { TrademarkExport } from "./trademark-export";
import { MonitoringEvidenceExport } from "./monitoring-evidence-export";
import { BusinessItemWork, AssignmentFilter } from "./business-item-work";
import { TrademarkDeadline, type DeadlineContext } from "./trademark-deadline";
import styles from "./commute-watch.module.css";

type Facts = {
  official_id: string;
  mark: string | null;
  owners: string[] | null;
  representatives: string[] | null;
  classes: number[] | null;
  status: string | null;
  source_url: string;
  origin: "national_ch" | "international_designating_ch";
  goods_services:
    | { text: string; language: string | null; class_number: number | null }[]
    | null;
  application_date: string | null;
  publication_date: string | null;
  registration_date: string | null;
  renewal_date: string | null;
  expiry_date: string | null;
  cancellation_date: string | null;
};
type Assessment = {
  state: string;
  priority: string | null;
  unavailable: string[];
  methods: {
    kind: "exact" | "lexical" | "phonetic" | "owner_interest";
    brand_variant?: string;
    source_mark?: string;
    score?: number;
    owners?: string[];
  }[];
  goods_services: {
    class_overlap: number[] | null;
    matches: { interest: string; phrase: string; language: string }[];
  };
};
type Decision =
  "reviewed" | "relevant" | "not_relevant" | "monitor" | "counsel";
type Candidate = {
  deadline_context?: DeadlineContext | null;
  id: string;
  brand_key: string;
  version: number;
  sequence: number;
  needs_review: boolean;
  decision: Decision | null;
  state: string;
  facts: Facts | null;
  assessment: Assessment | null;
  can_review: boolean;
  evaluation_hash?: string;
  attribution?: string;
};
type Event = {
  id: string;
  sequence: number;
  detected_at: string;
  change_codes: string[];
  profile_revision: number;
  href: string;
};
type EventDetail = Event & {
  deadline_context?: DeadlineContext | null;
  newer_available: boolean;
  assessment: Assessment | null;
  snapshot: { facts: Facts | null };
  previous: { facts: Facts | null } | null;
};
type Preview = {
  start_available: boolean;
  source_attributions: string[];
  similarity_unavailable_languages: string[];
};

export function TrademarkTime({ value }: { value?: string | null }) {
  const { locale } = useI18n();
  return value ? (
    <time dateTime={value}>
      {new Date(value).toLocaleString(locale === "rm-CH" ? "de-CH" : locale)}
    </time>
  ) : (
    <span>{trademarkReviewCopy[locale].unknown}</span>
  );
}
export function RegisterFacts({ facts }: { facts: Facts | null }) {
  const { locale } = useI18n(),
    c = trademarkReviewCopy[locale];
  if (!facts) return <p role="status">{c.unavailable}</p>;
  const fields = [
    "official_id",
    "mark",
    "owners",
    "representatives",
    "classes",
    "status",
    "application_date",
    "publication_date",
    "registration_date",
    "renewal_date",
    "expiry_date",
    "cancellation_date",
  ] as const;
  return (
    <div data-trademark-register-facts>
      <dl>
        {fields.map((field) => (
          <div key={field}>
            <dt className="font-semibold">{c[field]}</dt>
            <dd>
              {Array.isArray(facts[field])
                ? facts[field].join(", ") || c.unknown
                : facts[field] || c.unknown}
            </dd>
          </div>
        ))}
        <dt className="font-semibold">{c.origin}</dt>
        <dd>{c[facts.origin]}</dd>
      </dl>
      <details>
        <summary>{c.goods_services}</summary>
        {facts.goods_services?.length ? (
          <ul>
            {facts.goods_services.map((g, i) => (
              <li key={i}>
                {g.language?.toUpperCase() || c.unknown} ·{" "}
                {g.class_number ?? c.unknown}: {g.text}
              </li>
            ))}
          </ul>
        ) : (
          <p>{c.unknown}</p>
        )}
      </details>
      <a
        href={facts.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="underline"
      >
        {c.source}
      </a>
    </div>
  );
}
function Explanation({ value }: { value: Assessment | null }) {
  const { locale } = useI18n(),
    c = trademarkReviewCopy[locale];
  if (!value) return <p>{c.incomplete}</p>;
  return (
    <section data-trademark-explanation>
      <h4>{c.why}</h4>
      <p>
        {value.state === "not_selected"
          ? c.notSelected
          : value.priority === "high"
            ? c.high
            : c.review}
      </p>
      <ul>
        {value.methods.map((m, i) => (
          <li key={i}>
            {c[m.kind]}:{" "}
            {m.owners?.join(", ") || `${m.brand_variant} → ${m.source_mark}`}
            {m.score !== undefined ? ` (${m.score}/100)` : ""}
          </li>
        ))}
      </ul>
      <p>
        {c.classes}:{" "}
        {value.goods_services.class_overlap?.join(", ") || c.unknown}
      </p>
      <p>{c.goods}</p>
      <ul>
        {value.goods_services.matches.map((g, i) => (
          <li key={i}>
            {g.interest}: {g.phrase} ({g.language.toUpperCase()})
          </li>
        ))}
      </ul>
      <p>{c.classHelp}</p>
      {!!value.unavailable.length && <p role="status">{c.incomplete}</p>}
    </section>
  );
}
function ReviewHistory({ path }: { path: string }) {
  const { locale } = useI18n(),
    c = trademarkReviewCopy[locale],
    b = trademarkCopy[locale];
  const [before, setBefore] = useState<(number | null)[]>([null]);
  const result = useData<
    TrademarkPage<{
      id: string;
      decision: Decision;
      sequence: number;
      created_at: string;
    }>
  >(
    `${path}/reviews?limit=10${before.at(-1) ? `&before=${before.at(-1)}` : ""}`,
  );
  return (
    <section data-trademark-reviews>
      <h4>{c.reviews}</h4>
      {result.error ? (
        <p role="alert">{b.failed}</p>
      ) : !result.data ? (
        <p role="status">{b.loading}</p>
      ) : (
        <ul>
          {result.data.items.map((r) => (
            <li key={r.id}>
              {c[r.decision]} · {b.version} {r.sequence} ·{" "}
              <TrademarkTime value={r.created_at} />
            </li>
          ))}
        </ul>
      )}
      <button
        disabled={before.length === 1}
        onClick={() => setBefore((v) => v.slice(0, -1))}
      >
        {b.back}
      </button>
      <button
        disabled={!result.data?.next_cursor}
        onClick={() =>
          setBefore((v) => [...v, Number(result.data!.next_cursor)])
        }
      >
        {b.next}
      </button>
    </section>
  );
}
function Change({
  path,
  id,
  monitor,
  candidate,
}: {
  path: string;
  id: string;
  monitor: string;
  candidate: string;
}) {
  const { locale } = useI18n(),
    c = trademarkReviewCopy[locale],
    b = trademarkCopy[locale];
  const result = useData<EventDetail>(`${path}/events/${id}`);
  if (result.error) return <p role="alert">{b.failed}</p>;
  if (!result.data) return <p role="status">{b.loading}</p>;
  const e = result.data;
  return (
    <section data-trademark-change>
      <h4>{c.at}</h4>
      <p>
        {c.detected}: <TrademarkTime value={e.detected_at} /> · {b.version}{" "}
        {e.profile_revision}
      </p>
      <ul>
        {e.change_codes.map((code) => (
          <li key={code}>{trademarkChangeLabel(locale, code)}</li>
        ))}
      </ul>
      {e.newer_available && <p role="status">{c.newer}</p>}
      {e.previous && (
        <details open>
          <summary>{c.before}</summary>
          <RegisterFacts facts={e.previous.facts} />
        </details>
      )}
      <RegisterFacts facts={e.snapshot.facts} />
      <Explanation value={e.assessment} />
      <TrademarkDeadline value={e.deadline_context} />
      <MonitoringEvidenceExport
        domain="ip"
        monitorId={monitor}
        itemId={candidate}
        revisionId={id}
        contextVersion={e.sequence}
      />
    </section>
  );
}
function CandidateDetail({
  monitor,
  id,
  event,
  canManage,
}: {
  monitor: string;
  id: string;
  event?: string;
  canManage: boolean;
}) {
  const { locale } = useI18n(),
    c = trademarkReviewCopy[locale],
    b = trademarkCopy[locale];
  const path = `/monitors/${monitor}/candidates/${id}`;
  const [revision, setRevision] = useState(0),
    [selected, setSelected] = useState(event || ""),
    [before, setBefore] = useState<(number | null)[]>([null]);
  const result = useData<Candidate>(path, revision),
    mutation = useMutation();
  const history = useData<TrademarkPage<Event>>(
    `${path}/history?limit=10${before.at(-1) ? `&before=${before.at(-1)}` : ""}`,
    revision,
  );
  useEffect(() => {
    const timer = window.setInterval(() => setRevision((v) => v + 1), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  const row = result.data;
  return (
    <section data-trademark-candidate-detail className={styles.card}>
      <h3>{c.current}</h3>
      <button onClick={() => setRevision((v) => v + 1)}>{b.refresh}</button>
      {result.error ? (
        <p role="alert">{b.failed}</p>
      ) : !row ? (
        <p role="status">{b.loading}</p>
      ) : (
        <>
          <p>
            {row.needs_review ? c.needsReview : c.reviewed} ·{" "}
            {row.decision ? c[row.decision] : c.unknown} · {b.version}{" "}
            {row.sequence}
          </p>
          <RegisterFacts facts={row.facts} />
          <Explanation value={row.assessment} />
          <TrademarkDeadline value={row.deadline_context} />
          <p>{row.attribution}</p>
          <p>{c.internal}</p>
          <BusinessItemWork
            domain="ip"
            monitorId={monitor}
            itemId={id}
            version={row.version}
            canManage={canManage}
            changed={() => setRevision((v) => v + 1)}
          />
          <div className={styles.actions}>
            {(
              [
                "reviewed",
                "relevant",
                "not_relevant",
                "monitor",
                "counsel",
              ] as const
            ).map((decision) => (
              <button
                key={decision}
                data-trademark-decision={decision}
                disabled={!canManage || !row.can_review || mutation.busy}
                onClick={() =>
                  void mutation.run(
                    `${path}/review`,
                    {
                      expected_version: row.version,
                      expected_evaluation_hash: row.evaluation_hash,
                      decision,
                    },
                    () => setRevision((v) => v + 1),
                  )
                }
              >
                {c[decision]}
              </button>
            ))}
          </div>
          {mutation.error && <p role="alert">{mutation.error}</p>}
        </>
      )}
      {/* Remount all retained source evidence on each refresh; never retain a stale snapshot during a new request. */}
      {row && (
        <div key={revision}>
          {selected && (
            <Change
              key={selected}
              path={path}
              id={selected}
              monitor={monitor}
              candidate={id}
            />
          )}
          <ReviewHistory path={path} />
        </div>
      )}
      <TrademarkExport
        key={selected}
        path={path}
        version={row?.version}
        evaluationHash={row?.evaluation_hash}
        event={selected}
        canManage={canManage}
      />
      <h4>{c.history}</h4>
      {history.error ? (
        <p role="alert">{b.failed}</p>
      ) : !history.data ? (
        <p role="status">{b.loading}</p>
      ) : (
        <ul>
          {history.data.items.map((e) => (
            <li key={e.id}>
              <button onClick={() => setSelected(e.id)}>
                {c.detected}: <TrademarkTime value={e.detected_at} /> ·{" "}
                {b.version} {e.sequence}
              </button>{" "}
              · <Link href={e.href}>{c.open}</Link>
            </li>
          ))}
        </ul>
      )}
      <button
        disabled={before.length === 1}
        onClick={() => setBefore((v) => v.slice(0, -1))}
      >
        {b.back}
      </button>
      <button
        disabled={!history.data?.next_cursor}
        onClick={() =>
          setBefore((v) => [...v, Number(history.data!.next_cursor)])
        }
      >
        {b.next}
      </button>
    </section>
  );
}
export function TrademarkTracking({
  row,
  canManage,
  changed,
}: {
  row: TrademarkMonitor;
  canManage: boolean;
  changed: () => void;
}) {
  const { locale } = useI18n(),
    c = trademarkReviewCopy[locale],
    b = trademarkCopy[locale],
    params = useSearchParams();
  const [preview, setPreview] = useState<Preview | null>(null),
    [revision, setRevision] = useState(0),
    [anchors, setAnchors] = useState<(string | null)[]>([null]);
  const uuid = (name: string) =>
    params.getAll(name).length === 1 &&
    /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(params.get(name) || "")
      ? params.get(name)!
      : "";
  const [selected, setSelected] = useState(
    params.get("monitor") === row.id ? uuid("candidate") : "",
  );
  const event = params.get("candidate") === selected ? uuid("event") : "";
  const [assignment, setAssignment] = useState("");
  const mutation = useMutation(),
    cursor = anchors.at(-1);
  const result = useData<TrademarkPage<Candidate>>(
    `/monitors/${row.id}/candidates?limit=10${cursor ? `&after_id=${cursor}` : ""}${assignment ? `&assignment=${assignment}` : ""}`,
    revision,
  );
  useEffect(() => {
    const timer = window.setInterval(() => setRevision((v) => v + 1), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  function readiness() {
    setPreview(null);
    void mutation.run<Preview>(
      "/preview",
      { configuration: row.configuration },
      setPreview,
    );
  }
  const health =
    row.runtime?.health === "current"
      ? c.healthy
      : c[row.runtime?.health as keyof typeof c] || c.waiting;
  return (
    <section data-trademark-tracking>
      <h3>{c.tracking}</h3>
      <p>{c.scope}</p>
      <p role="status">{health}</p>
      <p>
        {c.last}: <TrademarkTime value={row.runtime?.last_check_at} /> ·{" "}
        {c.next}: <TrademarkTime value={row.runtime?.next_check_at} />
      </p>
      <div className={styles.actions}>
        <button disabled={mutation.busy} onClick={readiness}>
          {c.check}
        </button>
        {row.status !== "archived" && row.status !== "active" && (
          <button
            disabled={!canManage || mutation.busy || !preview?.start_available}
            onClick={() =>
              void mutation.run(
                `/monitors/${row.id}/start`,
                { expected_version: row.version },
                changed,
              )
            }
          >
            {c.start}
          </button>
        )}
        {row.status === "active" && (
          <>
            <button
              disabled={!canManage || mutation.busy}
              onClick={() =>
                void mutation.run(
                  `/monitors/${row.id}/pause`,
                  { expected_version: row.version },
                  changed,
                )
              }
            >
              {c.pause}
            </button>
            <button
              disabled={!canManage || mutation.busy}
              onClick={() =>
                void mutation.run(`/monitors/${row.id}/refresh`, {}, changed)
              }
            >
              {c.scan}
            </button>
          </>
        )}
      </div>
      {preview && (
        <div data-trademark-readiness role="status">
          <p>{preview.start_available ? c.ready : c.blocked}</p>
          {preview.source_attributions.map((a) => (
            <p key={a}>{a}</p>
          ))}
          {!!preview.similarity_unavailable_languages.length && (
            <p>
              {c.calibration}:{" "}
              {preview.similarity_unavailable_languages
                .join(", ")
                .toUpperCase()}
            </p>
          )}
        </div>
      )}
      {mutation.error && <p role="alert">{mutation.error}</p>}
      <h3>{c.candidates}</h3>
      <AssignmentFilter
        value={assignment}
        changed={(value) => {
          setAssignment(value);
          setAnchors([null]);
        }}
      />
      {result.error ? (
        <p role="alert">{b.failed}</p>
      ) : !result.data ? (
        <p role="status">{b.loading}</p>
      ) : (
        <>
          {!result.data.items.length && <p>{c.empty}</p>}
          <ul>
            {result.data.items.map((v) => (
              <li key={v.id} data-trademark-candidate>
                <p>
                  {row.configuration.brands.find(
                    (brand) => brand.key === v.brand_key,
                  )?.name || c.unknown}{" "}
                  · {v.facts?.mark || c.unavailable} ·{" "}
                  {v.needs_review ? c.needsReview : c.reviewed}
                </p>
                <button onClick={() => setSelected(v.id)}>{c.open}</button>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className={styles.actions}>
        <button
          disabled={anchors.length === 1}
          onClick={() => setAnchors((v) => v.slice(0, -1))}
        >
          {b.back}
        </button>
        <button
          disabled={!result.data?.next_cursor}
          onClick={() =>
            setAnchors((v) => [...v, String(result.data!.next_cursor)])
          }
        >
          {b.next}
        </button>
      </div>
      {selected && (
        <CandidateDetail
          key={`${selected}:${event}`}
          monitor={row.id}
          id={selected}
          event={event}
          canManage={canManage}
        />
      )}
    </section>
  );
}
