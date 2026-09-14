"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { PollenState, RuntimeAction } from "@/lib/pollen-runtime";
import type { PollenConfiguration } from "@/lib/pollen-drafts";
import { pollenRuntimeCopy } from "@/lib/pollen-runtime-copy";
import { pollenDraftCopy } from "@/lib/pollen-draft-copy";
import { pollenDeliveryCopy } from "@/lib/pollen-delivery-copy";
import { riverEmailCopy } from "@/lib/river-email-copy";
import { monitoringEmailCentreCopy } from "@/lib/monitoring-email-centre-copy";
import { PollenDeliveryFields } from "./pollen-delivery-fields";

export function PollenEmail({
  monitorId,
  canManage,
  changed,
}: {
  monitorId: string;
  canManage: boolean;
  changed: () => void;
}) {
  const { locale } = useI18n(),
    c = pollenRuntimeCopy[locale],
    labels = pollenDraftCopy[locale],
    copy = monitoringEmailCentreCopy[locale];
  const [state, setState] = useState<PollenState | null>(null),
    [delivery, setDelivery] = useState<PollenConfiguration["delivery"] | null>(
      null,
    );
  const [generation, setGeneration] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false),
    [consent, setConsent] = useState(false);
  const lifetime = useRef<AbortController | null>(null),
    pending = useRef(false);
  const base = `/monitoring-subjects/${encodeURIComponent(monitorId)}`;
  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    pending.current = false;
    setState(null);
    setDelivery(null);
    setConsent(false);
    setBusy(false);
    setError("");
    api<PollenState>(base + "/state", { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) {
          setState(value);
          setDelivery(structuredClone(value.configuration.delivery));
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(c.failed);
      });
    const hide = () => {
      controller.abort();
      setState(null);
      setDelivery(null);
      setConsent(false);
    };
    const show = (event: PageTransitionEvent) => {
      if (event.persisted) setGeneration((value) => value + 1);
    };
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    return () => {
      controller.abort();
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
    };
  }, [base, generation, c.failed]);
  async function apply(action?: RuntimeAction) {
    const controller = lifetime.current;
    if (
      !state ||
      !delivery ||
      !canManage ||
      pending.current ||
      !controller ||
      controller.signal.aborted
    )
      return;
    if (!action && !["draft", "paused"].includes(state.status)) return;
    if (
      !action &&
      delivery.quiet_hours &&
      delivery.quiet_hours.start === delivery.quiet_hours.end
    ) {
      setError(pollenDeliveryCopy[locale].invalidQuiet);
      return;
    }
    pending.current = true;
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api(base + (action ? "/commands" : ""), {
        method: action ? "POST" : "PATCH",
        signal: controller.signal,
        body: JSON.stringify(
          action
            ? {
                action,
                expected_revision: state.revision,
                expected_version: state.runtime.version,
                request_key: crypto.randomUUID(),
                email_consent:
                  ["resume", "consent_email"].includes(action) && consent,
              }
            : {
                expected_revision: state.revision,
                configuration: { ...state.configuration, delivery },
              },
        ),
      });
      if (!controller.signal.aborted) {
        setSaved(true);
        setGeneration((value) => value + 1);
        changed();
      }
    } catch (problem) {
      if (!controller.signal.aborted) {
        setState(null);
        setDelivery(null);
        setConsent(false);
        setError(
          problem instanceof ApiError && problem.code.includes("conflict")
            ? c.conflict
            : c.failed,
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        pending.current = false;
        setBusy(false);
      }
    }
  }
  const unsavedSchedule =
    state &&
    delivery &&
    JSON.stringify(delivery) !== JSON.stringify(state.configuration.delivery);
  return (
    <section data-pollen-email className="space-y-4">
      <p>{copy.pollen}</p>
      <p>{c.consentNote}</p>
      {error && <p role="alert">{error}</p>}
      {saved && <p role="status">{copy.saved}</p>}
      <button
        type="button"
        className="min-h-11 underline"
        disabled={busy}
        onClick={() => {
          setSaved(false);
          setGeneration((value) => value + 1);
        }}
      >
        {c.load}
      </button>
      {!state || !delivery ? (
        !error && <p role="status">{labels.loading}</p>
      ) : (
        <>
          <p>
            {labels.email[state.configuration.delivery.email]} ·{" "}
            {state.configuration.timezone} ·{" "}
            {state.runtime.email_consent
              ? riverEmailCopy[locale].active
              : riverEmailCopy[locale].off}
          </p>
          {state.runtime.muted && <p>{c.mute}</p>}
          {!!state.delivery_counts?.uncertain && (
            <p role="status">{c.uncertainDelivery}</p>
          )}
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void apply();
            }}
          >
            <fieldset
              disabled={
                !canManage ||
                busy ||
                !["draft", "paused"].includes(state.status)
              }
            >
              <PollenDeliveryFields
                delivery={delivery}
                timezone={state.configuration.timezone}
                clockNote={`${labels.timezone}: ${state.configuration.timezone}`}
                onChange={(value) => {
                  setDelivery(value);
                  setSaved(false);
                  setConsent(false);
                }}
              />
              <button className="min-h-11 underline" type="submit">
                {copy.save}
              </button>
            </fieldset>
          </form>
          {canManage && state.status !== "draft" && (
            <div className="flex flex-wrap gap-3">
              {state.status === "active" && (
                <button
                  className="min-h-11 underline"
                  disabled={busy}
                  onClick={() => void apply("pause")}
                >
                  {c.pause}
                </button>
              )}
              {state.runtime.email_consent && (
                <button
                  className="min-h-11 underline"
                  disabled={busy}
                  onClick={() => void apply("unsubscribe")}
                >
                  {c.unsubscribe}
                </button>
              )}
              {state.status === "active" && (
                <button
                  className="min-h-11 underline"
                  disabled={busy}
                  onClick={() =>
                    void apply(state.runtime.muted ? "unmute" : "mute")
                  }
                >
                  {state.runtime.muted ? c.unmute : c.mute}
                </button>
              )}
            </div>
          )}
          {canManage && ["active", "paused"].includes(state.status) && (
            <fieldset disabled={busy} className="space-y-3">
              {state.configuration.delivery.email !== "off" && (
                <label className="flex gap-2">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(event) => setConsent(event.target.checked)}
                  />
                  {c.consent}
                </label>
              )}
              {!state.start_available && <p role="status">{labels.blocked}</p>}
              {state.status === "paused" ? (
                <button
                  className="min-h-11 underline"
                  disabled={!state.start_available || Boolean(unsavedSchedule)}
                  onClick={() => void apply("resume")}
                >
                  {c.resume}
                </button>
              ) : (
                state.configuration.delivery.email !== "off" &&
                !state.runtime.email_consent && (
                  <button
                    className="min-h-11 underline"
                    disabled={!consent || !state.start_available}
                    onClick={() => void apply("consent_email")}
                  >
                    {c.consent_email}
                  </button>
                )
              )}
            </fieldset>
          )}
        </>
      )}
    </section>
  );
}
