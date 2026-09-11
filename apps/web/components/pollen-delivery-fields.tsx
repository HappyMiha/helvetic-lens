"use client";

import { useI18n } from "@/lib/i18n";
import { pollenDeliveryCopy } from "@/lib/pollen-delivery-copy";
import { pollenDraftCopy } from "@/lib/pollen-draft-copy";
import type { PollenConfiguration } from "@/lib/pollen-drafts";
import styles from "./pollen-draft-reader.module.css";

type Delivery = PollenConfiguration["delivery"];
export function PollenDeliveryFields({
  delivery,
  timezone,
  onChange,
}: {
  delivery: Delivery;
  timezone: string;
  onChange: (delivery: Delivery) => void;
}) {
  const { locale } = useI18n();
  const copy = pollenDeliveryCopy[locale],
    labels = pollenDraftCopy[locale];
  return (
    <fieldset
      className={styles.deliveryFields}
      data-pollen-delivery
      aria-describedby="pollen-delivery-note pollen-delivery-clock"
    >
      <legend>{copy.title}</legend>
      <p id="pollen-delivery-note">{copy.note}</p>
      <p id="pollen-delivery-clock">
        {copy.clock.replace("{timezone}", timezone)}
      </p>
      <label>
        {labels.delivery}
        <select
          name="pollen-email"
          value={delivery.email}
          aria-describedby="pollen-delivery-mode"
          onChange={(event) => {
            const email = event.target.value as Delivery["email"];
            onChange({
              ...delivery,
              email,
              digest_at: email === "daily_digest" ? "" : null,
            });
          }}
        >
          {Object.entries(labels.email).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <p id="pollen-delivery-mode">{copy.mode}</p>
      {delivery.email === "daily_digest" && (
        <label>
          {copy.digest}
          <input
            name="pollen-digest"
            type="time"
            step={60}
            required
            value={delivery.digest_at ?? ""}
            onChange={(event) =>
              onChange({ ...delivery, digest_at: event.target.value })
            }
          />
        </label>
      )}
      <label className={styles.check}>
        <input
          name="pollen-quiet"
          type="checkbox"
          checked={delivery.quiet_hours !== null}
          onChange={(event) =>
            onChange({
              ...delivery,
              quiet_hours: event.target.checked ? { start: "", end: "" } : null,
            })
          }
        />
        {copy.quiet}
      </label>
      {delivery.quiet_hours && (
        <>
          <label>
            {copy.start}
            <input
              name="pollen-quiet-start"
              type="time"
              step={60}
              required
              value={delivery.quiet_hours.start}
              onChange={(event) =>
                onChange({
                  ...delivery,
                  quiet_hours: {
                    ...delivery.quiet_hours!,
                    start: event.target.value,
                  },
                })
              }
            />
          </label>
          <label>
            {copy.end}
            <input
              name="pollen-quiet-end"
              type="time"
              step={60}
              required
              value={delivery.quiet_hours.end}
              onChange={(event) =>
                onChange({
                  ...delivery,
                  quiet_hours: {
                    ...delivery.quiet_hours!,
                    end: event.target.value,
                  },
                })
              }
            />
          </label>
        </>
      )}
    </fieldset>
  );
}
