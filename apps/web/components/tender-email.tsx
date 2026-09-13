"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { pollenDraftCopy } from "@/lib/pollen-draft-copy";
import { pollenDeliveryCopy } from "@/lib/pollen-delivery-copy";
import { tenderCopy } from "@/lib/tender-copy";
import { tenderEmailCopy } from "@/lib/tender-email-copy";
import styles from "./tender-watch.module.css";

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
    dossier_id: string;
    evidence_version_id: string;
    kind: string;
    href: string;
  }[];
};

export function TenderEmail({
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
    c = tenderCopy[locale],
    e = tenderEmailCopy[locale],
    d = pollenDeliveryCopy[locale],
    labels = pollenDraftCopy[locale];
  const [revision, setRevision] = useState(0),
    [saved, setSaved] = useState<Saved | null>(null),
    [config, setConfig] = useState<Config | null>(null);
  const [confirmed, setConfirmed] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [preview, setPreview] = useState<Preview | null>(null);
  const path = `/tender-watch/monitors/${monitorId}`;
  useEffect(() => {
    const controller = new AbortController();
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
    return () => controller.abort();
  }, [path, revision, c.failed]);
  function update(delivery: Partial<Config["delivery"]>) {
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
    if (!saved || !config) return;
    if (
      config.delivery.quiet_hours?.start === config.delivery.quiet_hours?.end &&
      config.delivery.quiet_hours
    ) {
      setError(d.invalidQuiet);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(path + "/email", {
        method: "PATCH",
        body: JSON.stringify({
          expected_version: saved.monitor_version,
          configuration: config,
          consent: config.delivery.email !== "off" && confirmed,
        }),
      });
      setRevision((v) => v + 1);
      changed();
    } catch (failure) {
      setError(
        failure instanceof ApiError && failure.code.includes("conflict")
          ? c.conflict
          : c.failed,
      );
    } finally {
      setBusy(false);
    }
  }
  async function loadPreview() {
    setBusy(true);
    setError("");
    try {
      setPreview(await api<Preview>(path + "/email-preview"));
    } catch {
      setError(c.failed);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section data-tender-email>
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
            <fieldset disabled={!canManage || busy || !!error}>
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
                  {c.saveEdit}
                </button>
              )}
            </fieldset>
          </form>
          <button disabled={busy} onClick={() => void loadPreview()}>
            {e.preview}
          </button>
          {preview && (
            <section aria-live="polite">
              <h3>{e.preview}</h3>
              {preview.status !== "ready" && <p>{e.unavailable}</p>}
              {preview.quiet_hours && <p>{e.quiet}</p>}
              {!preview.items.length && !preview.more_available && (
                <p>{e.none}</p>
              )}
              <ul>
                {preview.items.map((item) => (
                  <li key={item.evidence_version_id}>
                    <a href={item.href}>
                      {item.kind === "new_opportunity"
                        ? c.new_opportunity
                        : c.material_update}
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
