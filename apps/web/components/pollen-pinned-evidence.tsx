"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { pollenEvidenceCopy } from "@/lib/pollen-evidence-copy";
import { pollenRuntimeCopy } from "@/lib/pollen-runtime-copy";
import { pollenDraftCopy } from "@/lib/pollen-draft-copy";
import type { PollenActivity, PollenSample } from "@/lib/pollen-runtime";
import styles from "./pollen-draft-reader.module.css";
import { MonitoringEvidenceAsk } from "./monitoring-evidence-ask";

type Props = {
  id: string;
  canManage: boolean;
  onChanged: () => void;
  onDenied: (error: unknown) => void;
};
type Exact = {
  entry: PollenActivity & { source_withheld?: boolean };
  current_configuration: boolean;
  newer_available: boolean;
};

export function PollenPinnedEvidence(props: Props) {
  const params = useSearchParams();
  const entry = params.get("entry");
  if (!entry) return null;
  return <Pinned key={`${props.id}:${entry}`} {...props} entryId={entry} />;
}

function Pinned({
  id,
  entryId,
  canManage,
  onChanged,
  onDenied,
}: Props & { entryId: string }) {
  const { locale, dateTime, number } = useI18n();
  const copy = pollenEvidenceCopy[locale],
    runtime = pollenRuntimeCopy[locale],
    labels = pollenDraftCopy[locale];
  const [value, setValue] = useState<Exact | null>(null);
  const [busy, setBusy] = useState(true),
    [failed, setFailed] = useState(false),
    [generation, setGeneration] = useState(0);
  const denial = useRef(onDenied),
    mutation = useRef<AbortController | null>(null);
  useEffect(() => {
    denial.current = onDenied;
  }, [onDenied]);
  useEffect(() => () => mutation.current?.abort(), []);
  const path = `/monitoring-subjects/${encodeURIComponent(id)}/activity/${encodeURIComponent(entryId)}`;
  useEffect(() => {
    const request = new AbortController();
    setValue(null);
    setBusy(true);
    setFailed(false);
    void api<Exact>(path, { signal: request.signal })
      .then((result) => {
        if (!request.signal.aborted) setValue(result);
      })
      .catch((error) => {
        if (!request.signal.aborted) {
          setValue(null);
          setFailed(true);
          if (
            error instanceof ApiError &&
            [
              "authentication_required",
              "membership_required",
              "subject_role_denied",
            ].includes(error.code)
          )
            denial.current(error);
        }
      })
      .finally(() => {
        if (!request.signal.aborted) setBusy(false);
      });
    return () => request.abort();
  }, [path, generation]);
  const label = (key: string) =>
    runtime[key as keyof typeof runtime] || runtime.unverified;
  function sample(point: PollenSample) {
    return (
      <div className="space-y-1">
        <p>
          {labels.allergens[point.series.allergen] || labels.unknown} ·{" "}
          {point.series.station_id}
        </p>
        <p className="font-semibold">
          {point.value === null
            ? runtime.missing
            : `${number(Number(point.value), { maximumFractionDigits: 6 })} ${point.series.unit}`}
        </p>
        <p>
          {point.series.forecast ? runtime.forecast : runtime.measured} ·{" "}
          {labels.periods[point.series.period] || labels.unknown}
        </p>
        <p>
          {copy.quality}: {label(point.quality)}
        </p>
        {point.series.forecast && (
          <p>
            {runtime.issuedAt}:{" "}
            {dateTime(point.series.forecast.issue_at, {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </p>
        )}
        <p>
          {point.series.forecast ? runtime.validAt : runtime.observedAt}:{" "}
          {dateTime(point.valid_at, {
            dateStyle: "medium",
            timeStyle: "short",
          })}
        </p>
      </div>
    );
  }
  async function review(
    decision: NonNullable<PollenActivity["review"]>["decision"],
  ) {
    if (!value || busy) return;
    const controller = new AbortController();
    mutation.current = controller;
    setBusy(true);
    setFailed(false);
    try {
      await api(`${path}/review`, {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          decision,
          expected_version: value.entry.review?.version || 0,
        }),
      });
      if (!controller.signal.aborted) onChanged();
    } catch (error) {
      if (controller.signal.aborted) return;
      setValue(null);
      setFailed(true);
      if (
        error instanceof ApiError &&
        [
          "authentication_required",
          "membership_required",
          "subject_role_denied",
        ].includes(error.code)
      )
        onDenied(error);
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  const entry = value?.entry;
  return (
    <section
      className={styles.runtime}
      data-pollen-pinned
      aria-busy={busy}
      aria-labelledby="pollen-pinned-heading"
    >
      <h2 id="pollen-pinned-heading">{copy.title}</h2>
      <p>{copy.retained}</p>
      <button
        className={styles.button}
        type="button"
        disabled={busy}
        onClick={() => setGeneration((v) => v + 1)}
      >
        {copy.reload}
      </button>
      {busy && <p role="status">{labels.loading}</p>}
      {failed && <p role="alert">{copy.failed}</p>}
      {value && entry && (
        <>
          {value.newer_available && <p>{copy.newer}</p>}
          {!value.current_configuration && <p>{copy.oldSettings}</p>}
          <MonitoringEvidenceAsk
            domain="pollen"
            monitorId={id}
            itemId={entryId}
            contextVersion={entry.configuration_revision}
          />
          <p>
            {labels.revision}: {entry.configuration_revision} ·{" "}
            {dateTime(entry.created_at, {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </p>
          {entry.source_withheld ? (
            <p role="status">{copy.withheld}</p>
          ) : (
            <>
              <h3>{runtime.current}</h3>
              {sample(entry.current)}
              {entry.previous && (
                <>
                  <h3>{runtime.previous}</h3>
                  {sample(entry.previous)}
                </>
              )}
              {entry.baseline && (
                <>
                  <h3>{labels.rapid}</h3>
                  {sample(entry.baseline)}
                </>
              )}
              {!!entry.reasons.length && (
                <>
                  <h3>{runtime.why}</h3>
                  <ul>
                    {entry.reasons.map((reason) => (
                      <li key={reason}>{label(reason)}</li>
                    ))}
                  </ul>
                </>
              )}
              <p>
                {runtime.retrieved}:{" "}
                {dateTime(entry.current.fetched_at, {
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </p>
              <p>
                <a
                  href="https://opendatadocs.meteoswiss.ch/general/terms-of-use"
                  target="_blank"
                  rel="noreferrer"
                >
                  {runtime.attribution}
                </a>
              </p>
              {entry.raw_export_available ? (
                <ul>
                  {entry.current.artifact_hashes.map((hash) => (
                    <li key={hash} className="break-all">
                      <a
                        href={`/api${path}/artifacts/${encodeURIComponent(hash)}`}
                        download
                      >
                        {runtime.artifactHash}: {hash}
                      </a>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>{copy.rawUnavailable}</p>
              )}
            </>
          )}
          <h3>{runtime.reviews}</h3>
          <p>{entry.review ? label(entry.review.decision) : runtime.new}</p>
          {canManage && entry.material_id && !entry.source_withheld && (
            <div className="flex flex-wrap gap-2">
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
                  key={decision}
                  className={styles.button}
                  disabled={busy}
                  aria-pressed={entry.review?.decision === decision}
                  onClick={() => void review(decision)}
                >
                  {runtime[decision]}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
