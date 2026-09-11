"use client";

import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { pollenStationCopy } from "@/lib/pollen-station-copy";
import { pollenDraftCopy } from "@/lib/pollen-draft-copy";
import {
  orderedPollenStations,
  pollenChannels,
  pollenStations,
  pollenStationSource,
  validPoint,
  type Point,
} from "@/lib/pollen-stations";
import styles from "./pollen-draft-reader.module.css";

export function PollenStationPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (station: string) => void;
}) {
  const { locale } = useI18n(),
    copy = pollenStationCopy[locale];
  const [point, setPoint] = useState<Point | null>(null);
  const [status, setStatus] = useState<
    "locating" | "ordered" | "denied" | "unavailable" | "timeout" | null
  >(null);
  const epoch = useRef(0),
    pending = useRef(false);
  useEffect(
    () => () => {
      epoch.current++;
      pending.current = false;
    },
    [],
  );
  const stations = orderedPollenStations(point, locale);
  const selected = stations.find((station) => station.id === value);
  const distance = (km: number) =>
    new Intl.NumberFormat(locale, {
      style: "unit",
      unit: "kilometer",
      maximumFractionDigits: 1,
    }).format(km);
  function clear() {
    epoch.current++;
    pending.current = false;
    setPoint(null);
    setStatus(null);
  }
  function nearby() {
    if (pending.current) return;
    if (!navigator.geolocation) {
      setStatus("unavailable");
      return;
    }
    const request = ++epoch.current;
    pending.current = true;
    setPoint(null);
    setStatus("locating");
    try {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          if (epoch.current !== request) return;
          pending.current = false;
          const current = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          };
          if (!validPoint(current)) {
            setStatus("unavailable");
            return;
          }
          setPoint(current);
          setStatus("ordered");
        },
        (error) => {
          if (epoch.current !== request) return;
          pending.current = false;
          setStatus(
            error.code === 1
              ? "denied"
              : error.code === 3
                ? "timeout"
                : "unavailable",
          );
        },
        { enableHighAccuracy: false, maximumAge: 60_000, timeout: 10_000 },
      );
    } catch {
      if (epoch.current === request) {
        pending.current = false;
        setStatus("unavailable");
      }
    }
  }
  return (
    <div data-pollen-station-picker>
      <label>
        {pollenDraftCopy[locale].station}
        <select
          name="pollen-station"
          required
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-describedby="pollen-station-limits"
        >
          <option value="">{copy.choose}</option>
          {value && !selected && <option value={value}>{value}</option>}
          {stations.map((station) => (
            <option key={station.id} value={station.id}>
              {station.name} · {station.id}
              {station.distance !== null
                ? ` · ${distance(station.distance)}`
                : ""}
            </option>
          ))}
        </select>
      </label>
      {value && !selected && <p role="status">{copy.unknown}</p>}
      <p id="pollen-station-limits">{copy.limits}</p>
      <details className={styles.history} data-pollen-nearby>
        <summary>{copy.nearby}</summary>
        <p id="pollen-location-privacy">{copy.privacy}</p>
        <button
          type="button"
          className={styles.button}
          data-pollen-locate
          disabled={status === "locating"}
          aria-describedby="pollen-location-privacy"
          onClick={nearby}
        >
          {copy.nearby}
        </button>
        {(point || status === "locating") && (
          <button
            type="button"
            className={styles.button}
            data-pollen-location-clear
            onClick={clear}
          >
            {copy.forget}
          </button>
        )}
        {status && (
          <p
            role={
              status === "denied" ||
              status === "unavailable" ||
              status === "timeout"
                ? "alert"
                : "status"
            }
          >
            {copy[status]}
          </p>
        )}
        {selected?.distance !== null && selected?.distance !== undefined && (
          <p data-pollen-distance>
            {copy.distance}: {distance(selected.distance)}
          </p>
        )}
      </details>
    </div>
  );
}

export function PollenChannelOverview({
  stationId,
  allergens,
}: {
  stationId: string;
  allergens: string[];
}) {
  const { locale } = useI18n(),
    copy = pollenStationCopy[locale],
    labels = pollenDraftCopy[locale];
  const known = pollenStations.some((station) => station.id === stationId);
  return (
    <section data-pollen-channels aria-label={copy.coverage}>
      <p>
        <strong>{copy.coverage}</strong>
      </p>
      {stationId && !known && <p>{copy.unknown}</p>}
      <p>{copy.unverified}</p>
      {!allergens.length ? (
        <p>{copy.chooseAllergens}</p>
      ) : (
        <table className={styles.channelTable}>
          <caption>{copy.coverage}</caption>
          <thead>
            <tr>
              <th scope="col">{copy.allergen}</th>
              <th scope="col">{copy.observation}</th>
              <th scope="col">{copy.forecast}</th>
            </tr>
          </thead>
          <tbody>
            {allergens.map((allergen) => {
              const channels = pollenChannels(allergen);
              return (
                <tr key={allergen}>
                  <th scope="row">
                    {labels.allergens[allergen] || labels.unknown}
                  </th>
                  <td>
                    {channels.observation
                      ? copy.documentedObservation
                      : copy.notEstablished}
                  </td>
                  <td>
                    {channels.forecast
                      ? copy.documentedForecast
                      : copy.notEstablished}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      <p>
        {copy.directory}:{" "}
        {new Intl.DateTimeFormat(locale, {
          dateStyle: "medium",
          timeZone: "UTC",
        }).format(new Date(pollenStationSource.capturedAt))}
        .{" "}
        <a
          href={pollenStationSource.documentation}
          target="_blank"
          rel="noreferrer"
        >
          {copy.source}
        </a>
        {" · "}
        <a href={pollenStationSource.terms} target="_blank" rel="noreferrer">
          {copy.terms}
        </a>
      </p>
    </section>
  );
}
