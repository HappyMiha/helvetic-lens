"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { pollenDraftCopy } from "@/lib/pollen-draft-copy";
import { pollenDeliveryCopy } from "@/lib/pollen-delivery-copy";
import { commuteCopy } from "@/lib/commute-copy";
import { commuteEmailCopy } from "@/lib/commute-email-copy";
import styles from "./commute-watch.module.css";

type Config = {
  timezone: string;
  delivery: {
    email: "off" | "immediate" | "daily_digest";
    digest_at: string | null;
    quiet_hours: { start: string; end: string } | null;
  };
};
type Saved = {
  revision: number;
  monitor_version: number;
  configuration: Config;
  consent_active: boolean;
  email_verified: boolean;
  uncertain_deliveries: number;
  delivery_service_available?: boolean;
  recipient_email: string;
};
type Preview = {
  status: string;
  quiet_hours: boolean;
  more_available: boolean;
  items: {
    event_id: string;
    sequence: number;
    service_day: string;
    href: string;
  }[];
};

export function CommuteEmail({
  monitorId,
  canManage,
  archived,
  changed,
}: {
  monitorId: string;
  canManage: boolean;
  archived: boolean;
  changed: () => void;
}) {
  const { locale } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <details
      className={styles.card}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>{pollenDeliveryCopy[locale].title}</summary>
      {open && (
        <EmailForm
          key={`${monitorId}:${locale}`}
          monitorId={monitorId}
          canManage={canManage}
          archived={archived}
          changed={changed}
        />
      )}
    </details>
  );
}

function EmailForm({
  monitorId,
  canManage,
  archived,
  changed,
}: {
  monitorId: string;
  canManage: boolean;
  archived: boolean;
  changed: () => void;
}) {
  const { locale } = useI18n(),
    c = commuteCopy[locale],
    e = commuteEmailCopy[locale],
    d = pollenDeliveryCopy[locale],
    labels = pollenDraftCopy[locale];
  const [revision, setRevision] = useState(0),
    [saved, setSaved] = useState<Saved | null>(null),
    [config, setConfig] = useState<Config | null>(null);
  const [confirmed, setConfirmed] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [preview, setPreview] = useState<Preview | null>(null);
  const path = `/commute-watch/monitors/${monitorId}`;
  const lifetime = useRef<AbortController | null>(null);
  const inFlight = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    inFlight.current = false;
    setBusy(false);
    setSaved(null);
    setConfig(null);
    setPreview(null);
    setConfirmed(false);
    setError("");
    api<Saved>(path + "/email", { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) {
          setSaved(value);
          setConfig(structuredClone(value.configuration));
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(c.failed);
      });
    const clearPreview = () => setPreview(null);
    const hide = () => {
      controller.abort();
      setSaved(null);
      setConfig(null);
      setPreview(null);
      setConfirmed(false);
    };
    const show = (event: PageTransitionEvent) => {
      if (event.persisted) setRevision((value) => value + 1);
    };
    window.addEventListener("focus", clearPreview);
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    return () => {
      controller.abort();
      window.removeEventListener("focus", clearPreview);
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
    };
  }, [path, revision, c.failed]);
  function update(delivery: Partial<Config["delivery"]>) {
    setError("");
    setConfig(
      (previous) =>
        previous && {
          ...previous,
          delivery: { ...previous.delivery, ...delivery },
        },
    );
    setConfirmed(false);
    setPreview(null);
  }
  async function save() {
    const controller = lifetime.current;
    if (
      !saved ||
      !config ||
      !canManage ||
      inFlight.current ||
      !controller ||
      controller.signal.aborted
    )
      return;
    if (
      config.delivery.email !== "off" &&
      (!confirmed || !saved.email_verified || archived)
    )
      return;
    if (
      config.delivery.quiet_hours?.start === config.delivery.quiet_hours?.end &&
      config.delivery.quiet_hours
    ) {
      setError(d.invalidQuiet);
      return;
    }
    inFlight.current = true;
    setBusy(true);
    setError("");
    setPreview(null);
    try {
      await api(path + "/email", {
        method: "PUT",
        signal: controller.signal,
        body: JSON.stringify({
          expected_version: saved.monitor_version,
          configuration: config,
          consent: config.delivery.email !== "off" && confirmed,
        }),
      });
      if (!controller.signal.aborted) {
        setRevision((v) => v + 1);
        changed();
      }
    } catch (failure) {
      if (controller.signal.aborted) return;
      setSaved(null);
      setConfig(null);
      setConfirmed(false);
      setError(
        failure instanceof ApiError && failure.code.includes("conflict")
          ? c.conflict
          : failure instanceof ApiError &&
              (failure.code === "invalid_input" ||
                failure.code.includes("invalid"))
            ? c.invalid
            : c.failed,
      );
    } finally {
      if (!controller.signal.aborted) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  }
  async function loadPreview() {
    const controller = lifetime.current;
    if (inFlight.current || !controller || controller.signal.aborted) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    setPreview(null);
    try {
      const value = await api<Preview>(path + "/email-preview", {
        signal: controller.signal,
      });
      if (!controller.signal.aborted) setPreview(value);
    } catch {
      if (controller.signal.aborted) return;
      setSaved(null);
      setConfig(null);
      setConfirmed(false);
      setError(c.failed);
    } finally {
      if (!controller.signal.aborted) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  }
  return (
    <section data-commute-email>
      <p>{e.note}</p>
      <p>{e.window}</p>
      {error && <p role="alert">{error}</p>}
      <button disabled={busy} onClick={() => setRevision((v) => v + 1)}>
        {c.refresh}
      </button>
      {!saved || !config ? (
        !error && <p role="status">{c.loading}</p>
      ) : (
        <>
          <p>
            {saved.recipient_email} · {saved.consent_active ? e.active : e.off}
          </p>
          {!saved.email_verified && <p>{e.verify}</p>}
          {saved.delivery_service_available === false && (
            <p role="status">{e.serviceOff}</p>
          )}
          {saved.uncertain_deliveries > 0 && <p role="status">{e.uncertain}</p>}
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            <fieldset disabled={!canManage || busy}>
              <legend>{d.title}</legend>
              <label>
                {labels.delivery}
                <select
                  value={config.delivery.email}
                  onChange={(event) =>
                    update({
                      email: event.target.value as Config["delivery"]["email"],
                      digest_at:
                        event.target.value === "daily_digest" ? "08:00" : null,
                    })
                  }
                >
                  {Object.entries(labels.email).map(([value, name]) => (
                    <option
                      value={value}
                      key={value}
                      disabled={
                        value !== "off" && (archived || !saved.email_verified)
                      }
                    >
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              {config.delivery.email === "daily_digest" && (
                <label>
                  {d.digest}
                  <input
                    type="time"
                    required
                    value={config.delivery.digest_at || ""}
                    onChange={(event) =>
                      update({ digest_at: event.target.value })
                    }
                  />
                </label>
              )}
              <label>
                {labels.timezone}
                <input
                  required
                  maxLength={64}
                  value={config.timezone}
                  onChange={(event) => {
                    setConfig({ ...config, timezone: event.target.value });
                    setConfirmed(false);
                    setPreview(null);
                  }}
                />
              </label>
              <label className={styles.check}>
                <input
                  type="checkbox"
                  checked={!!config.delivery.quiet_hours}
                  onChange={(event) =>
                    update({
                      quiet_hours: event.target.checked
                        ? { start: "22:00", end: "07:00" }
                        : null,
                    })
                  }
                />
                {d.quiet}
              </label>
              {config.delivery.quiet_hours && (
                <div className={styles.grid}>
                  <label>
                    {d.start}
                    <input
                      type="time"
                      required
                      value={config.delivery.quiet_hours.start}
                      onChange={(event) =>
                        update({
                          quiet_hours: {
                            ...config.delivery.quiet_hours!,
                            start: event.target.value,
                          },
                        })
                      }
                    />
                  </label>
                  <label>
                    {d.end}
                    <input
                      type="time"
                      required
                      value={config.delivery.quiet_hours.end}
                      onChange={(event) =>
                        update({
                          quiet_hours: {
                            ...config.delivery.quiet_hours!,
                            end: event.target.value,
                          },
                        })
                      }
                    />
                  </label>
                </div>
              )}
              {config.delivery.email !== "off" && (
                <label className={styles.check}>
                  <input
                    type="checkbox"
                    required
                    checked={confirmed}
                    onChange={(event) => setConfirmed(event.target.checked)}
                  />
                  {e.consent}
                </label>
              )}
              {canManage && (
                <button
                  type="submit"
                  disabled={
                    config.delivery.email !== "off" &&
                    (!confirmed || !saved.email_verified || archived)
                  }
                >
                  {e.save}
                </button>
              )}
            </fieldset>
          </form>
          <p>{e.previewNote}</p>
          <button disabled={busy} onClick={() => void loadPreview()}>
            {e.preview}
          </button>
          {preview && (
            <section aria-live="polite">
              <h3>{e.preview}</h3>
              {preview.status === "daily_already_attempted" ? (
                <p>{e.daily}</p>
              ) : (
                preview.status !== "ready" && <p>{e.unavailable}</p>
              )}
              {preview.quiet_hours && <p>{e.quiet}</p>}
              {!preview.items.length && !preview.more_available && (
                <p>{e.none}</p>
              )}
              <ul>
                {preview.items.map((item) => (
                  <li key={`${item.event_id}:${item.sequence}`}>
                    <a href={item.href}>
                      {c.savedUpdate} · {item.service_day} · {item.sequence}
                    </a>
                  </li>
                ))}
              </ul>
              {preview.more_available && <p>{e.more}</p>}
            </section>
          )}
        </>
      )}
    </section>
  );
}
