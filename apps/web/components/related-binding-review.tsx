"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { relatedCopy } from "@/lib/related-copy";
import type { Reference } from "@/lib/related-developments";
import styles from "./related-developments.module.css";

type Inspection = {
  fact: {
    source_revision: string;
    source_feature: { namespace: string; identifier: string };
    availability: string;
  };
  source_feature_hash: string;
  bindings: { id: string; place_id: string; valid_until: string }[];
};
type Area = {
  state: string;
  version: string;
  sha256: string;
  municipality_code: string;
  municipality_name: string;
  expires_on: string;
};
const ROOT = "/related-developments/bindings";

export function RelatedBindingReview({
  reference,
  onChanged,
  onClose,
}: {
  reference: Reference;
  onChanged: () => void;
  onClose: () => void;
}) {
  const { locale } = useI18n(),
    c = relatedCopy[locale];
  const [inspection, setInspection] = useState<Inspection | null>(null),
    [area, setArea] = useState<Area | null>(null);
  const [code, setCode] = useState(""),
    [evidence, setEvidence] = useState(""),
    [until, setUntil] = useState("");
  const [attested, setAttested] = useState(false),
    [busy, setBusy] = useState(false),
    [failed, setFailed] = useState(false);
  const request = useRef<AbortController | null>(null),
    retry = useRef<{ signature: string; id: string } | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  async function run<T>(
    path: string,
    body: object | null,
    accept: (data: T) => void,
  ) {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setFailed(false);
    try {
      const data = await api<T>(ROOT + path, {
        method: body ? "POST" : "GET",
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
      if (!controller.signal.aborted) accept(data);
    } catch {
      if (!controller.signal.aborted) {
        setFailed(true);
        setInspection(null);
        setAttested(false);
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
      request.current = null;
    }
  }
  function publish() {
    if (!area || !inspection) return;
    const body = {
      reference,
      municipality_code: code,
      boundary_version: area.version,
      boundary_hash: area.sha256,
      evidence_hash: evidence,
      source_revision: inspection.fact.source_revision,
      source_feature_hash: inspection.source_feature_hash,
      valid_until: until + ":00Z",
      reviewed: true,
    };
    const signature = JSON.stringify(body);
    if (retry.current?.signature !== signature)
      retry.current = { signature, id: crypto.randomUUID() };
    void run("", { ...body, id: retry.current.id }, () => {
      onChanged();
      onClose();
    });
  }
  return (
    <section className={styles.card} aria-label={c.bindingReview}>
      <h2>{c.bindingReview}</h2>
      <p>{c.reviewIntro}</p>
      {failed && <p role="alert">{c.failed}</p>}
      <button
        disabled={busy}
        onClick={() =>
          void run<Inspection>("/inspect", { reference }, (data) => {
            setInspection(data);
            setAttested(false);
          })
        }
      >
        {c.inspect}
      </button>
      {inspection && (
        <>
          <details>
            <summary>{c.sourceFeature}</summary>
            <pre>{JSON.stringify(inspection.fact, null, 2)}</pre>
          </details>
          <h3>{c.existingBindings}</h3>
          {!inspection.bindings.length && <p>{c.noBindings}</p>}
          {inspection.bindings.map((binding) => (
            <p key={binding.id}>
              {binding.place_id} · {binding.valid_until}{" "}
              <button
                disabled={busy}
                onClick={() =>
                  void run(`/${binding.id}/revoke`, {}, () => {
                    setInspection(null);
                    setAttested(false);
                    onChanged();
                  })
                }
              >
                {c.revoke}
              </button>
            </p>
          ))}
          <fieldset disabled={busy}>
            <legend>{c.geography}</legend>
            <label className={styles.field}>
              {c.areaCode}
              <input
                inputMode="numeric"
                pattern="[0-9]{1,4}"
                maxLength={4}
                value={code}
                onChange={(event) => {
                  setCode(event.target.value);
                  setArea(null);
                  setAttested(false);
                }}
              />
            </label>
            <button
              disabled={!/^[0-9]{1,4}$/.test(code)}
              onClick={() =>
                void run<Area>(`/municipalities/${code}`, null, setArea)
              }
            >
              {c.checkArea}
            </button>
            {area && (
              <p role="status">
                {area.state === "verified"
                  ? `${area.municipality_name} · ${area.municipality_code} · ${area.version}`
                  : c.unavailable}
              </p>
            )}
            <label className={styles.field}>
              {c.evidenceHash}
              <input
                value={evidence}
                maxLength={64}
                onChange={(event) => {
                  setEvidence(event.target.value);
                  setAttested(false);
                }}
              />
            </label>
            <label className={styles.field}>
              {c.validUntil}
              <input
                type="datetime-local"
                value={until}
                onChange={(event) => {
                  setUntil(event.target.value);
                  setAttested(false);
                }}
              />
            </label>
            <label>
              <input
                type="checkbox"
                checked={attested}
                onChange={(event) => setAttested(event.target.checked)}
              />
              {c.attest}
            </label>
            <button
              disabled={
                !attested ||
                !/^[a-f0-9]{64}$/.test(evidence) ||
                !until ||
                area?.state !== "verified" ||
                inspection.fact.availability !== "available"
              }
              onClick={publish}
            >
              {c.publish}
            </button>
          </fieldset>
        </>
      )}
      <button disabled={busy} onClick={onClose}>
        {c.cancel}
      </button>
    </section>
  );
}
