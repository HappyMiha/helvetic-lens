"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { centreCopy, type TemplateId } from "@/lib/monitoring-centre-copy";
import { sourceOperationsCopy } from "@/lib/source-operations-copy";
import { sourceHistoryCopy } from "@/lib/source-history-copy";

const channels = [
  "pollen",
  "river",
  "air",
  "warnings",
  "commute:trip_updates",
  "commute:service_alerts",
  "traffic",
  "tenders",
  "auctions",
  "ip",
];
type Metric =
  "latest_acquisition_age" | "oldest_acquisition_age" | "publication_age";
type Point = {
  at: string;
  samples: number;
  expected_samples: number;
  missing_samples: number;
  states: Record<string, number>;
  access_states: Record<string, number>;
  collector_states: Record<string, number>;
  disabled_samples: number;
  binding_changed: boolean;
  metrics: Record<
    Metric,
    {
      min_seconds: number | null;
      max_seconds: number | null;
      known_samples: number;
    }
  >;
  last_state: {
    state: string;
    access: string;
    collector: string;
    section_enabled: boolean;
  } | null;
};
type History = {
  channel: string;
  days: number;
  checked_at: string;
  first_sample_at: string | null;
  last_sample_at: string | null;
  points: Point[];
};

export function MonitoringSourceHistory({ denied }: { denied: () => void }) {
  const { locale, dateTime } = useI18n(),
    c = sourceHistoryCopy[locale],
    s = sourceOperationsCopy[locale];
  const [channel, setChannel] = useState("pollen"),
    [days, setDays] = useState(1),
    [metric, setMetric] = useState<Metric>("latest_acquisition_age");
  const [data, setData] = useState<History | null>(null),
    [error, setError] = useState(false),
    [page, setPage] = useState(0),
    [revision, setRevision] = useState(0),
    [visible, setVisible] = useState(true);
  const active = useRef<AbortController | null>(null),
    onDenied = useRef(denied);
  onDenied.current = denied;
  useEffect(() => {
    const hide = () => {
      active.current?.abort();
      setData(null);
      setVisible(false);
    };
    const visibility = () => {
      if (document.hidden) hide();
      else {
        setVisible(true);
        setRevision((v) => v + 1);
      }
    };
    const show = () => {
      setVisible(true);
      setRevision((v) => v + 1);
    };
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    document.addEventListener("visibilitychange", visibility);
    const timer = window.setInterval(() => {
      if (!document.hidden && !active.current) setRevision((v) => v + 1);
    }, 300000);
    return () => {
      active.current?.abort();
      clearInterval(timer);
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  useEffect(() => {
    setData(null);
    setError(false);
    setPage(0);
    if (!visible) return;
    const controller = new AbortController();
    active.current = controller;
    void api<History>(
      `/admin/monitoring-sources/history?channel=${encodeURIComponent(channel)}&days=${days}`,
      { signal: controller.signal },
    )
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((problem) => {
        if (!controller.signal.aborted) {
          setError(true);
          if (
            problem instanceof ApiError &&
            [
              "authentication_required",
              "platform_admin_required",
              "membership_required",
            ].includes(problem.code)
          )
            onDenied.current();
        }
      })
      .finally(() => {
        if (active.current === controller) active.current = null;
      });
    return () => controller.abort();
  }, [channel, days, revision, visible]);
  const label = (key: string) =>
    s[(key === "errors" ? "errors_state" : key) as keyof typeof s] || s.unknown;
  const number = (value: number | null) =>
    value === null ? s.unknown : new Intl.NumberFormat(locale).format(value);
  const hour = (value: string) =>
    new Intl.DateTimeFormat(locale, {
      dateStyle: "short",
      timeStyle: "short",
      timeZone: "Europe/Zurich",
    }).format(new Date(value));
  const metrics: [Metric, string][] = [
    ["latest_acquisition_age", c.latest],
    ["oldest_acquisition_age", c.oldest],
    ["publication_age", c.publication],
  ];
  const points = data?.points || [],
    maximum = Math.max(
      1,
      ...points.map((p) => p.metrics[metric].max_seconds ?? 0),
    );
  const pageCount = Math.max(1, Math.ceil(points.length / 24));
  return (
    <section data-source-history className="card p-5 my-6 min-w-0">
      <h2>{c.title}</h2>
      <p className="my-3">{c.body}</p>
      <div className="flex flex-wrap gap-4 items-end my-4">
        <label>
          {c.source}
          <select
            className="block max-w-full min-h-11"
            data-history-channel
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
          >
            {channels.map((key) => {
              const [domain, feed] = key.split(":");
              return (
                <option key={key} value={key}>
                  {centreCopy[locale].templates[domain as TemplateId][0]}
                  {feed ? ` · ${label(feed)}` : ""}
                </option>
              );
            })}
          </select>
        </label>
        <label>
          {c.period}
          <select
            className="block min-h-11"
            data-history-period
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={1}>{c.day}</option>
            <option value={7}>{c.week}</option>
            <option value={30}>{c.month}</option>
          </select>
        </label>
        <label>
          {c.metric}
          <select
            className="block max-w-full min-h-11"
            data-history-metric
            value={metric}
            onChange={(e) => setMetric(e.target.value as Metric)}
          >
            {metrics.map(([key, name]) => (
              <option key={key} value={key}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <button
          className="button min-h-11"
          onClick={() => setRevision((v) => v + 1)}
        >
          {s.refresh}
        </button>
      </div>
      {error ? (
        <p role="alert">{c.failed}</p>
      ) : !data ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          <p>
            {s.checked}: {dateTime(data.checked_at)} · {c.samples}:{" "}
            {points.reduce((n, p) => n + p.samples, 0)} /{" "}
            {points.reduce((n, p) => n + p.expected_samples, 0)}
          </p>
          {!data.first_sample_at && (
            <p role="status" className="my-3">
              {c.empty}
            </p>
          )}
          <p className="my-3">{c.boundary}</p>
          <p>
            {c.maximum}:{" "}
            {number(
              maximum === 1 &&
                !points.some((p) => p.metrics[metric].known_samples)
                ? null
                : Math.max(
                    ...points.map((p) => p.metrics[metric].max_seconds ?? 0),
                  ),
            )}
          </p>
          <svg
            className="block w-full h-40 my-3 text-[#174ea6]"
            viewBox="0 0 720 150"
            preserveAspectRatio="none"
            role="img"
            aria-label={`${c.chart}: ${metrics.find(([key]) => key === metric)?.[1]}`}
          >
            {points.map((p, i) => {
              const value = p.metrics[metric].max_seconds,
                width = 720 / points.length,
                height =
                  value === null ? 0 : Math.max(2, (value / maximum) * 120);
              return (
                <g key={p.at}>
                  <title>
                    {hour(p.at)} · {c.maximum}: {number(value)} · {c.gap}:{" "}
                    {p.missing_samples}
                  </title>
                  {value !== null && (
                    <rect
                      x={i * width}
                      y={125 - height}
                      width={Math.max(0.5, width - 0.5)}
                      height={height}
                      fill="currentColor"
                    />
                  )}
                  {p.missing_samples > 0 && (
                    <rect
                      x={i * width}
                      y={135}
                      width={Math.max(0.5, width - 0.5)}
                      height={8}
                      fill="#795000"
                    />
                  )}
                </g>
              );
            })}
          </svg>
          <div className="flex justify-between gap-3 text-sm">
            <span>{points[0] ? hour(points[0].at) : s.unknown}</span>
            <span>
              {points.length ? hour(points[points.length - 1].at) : s.unknown}
            </span>
          </div>
          <p className="my-3">
            <span
              aria-hidden="true"
              className="inline-block w-3 h-3 mr-2 bg-[#795000]"
            />
            {c.gap}
          </p>
          <details>
            <summary className="cursor-pointer min-h-11 py-2">
              {c.hours}
            </summary>
            <div
              className="overflow-x-auto"
              role="region"
              aria-label={c.hours}
              tabIndex={0}
            >
              <table className="w-full text-sm">
                <caption className="text-left my-3">
                  {c.hours} ·{" "}
                  {
                    new Intl.DateTimeFormat(locale, {
                      timeZone: "Europe/Zurich",
                    }).resolvedOptions().timeZone
                  }
                </caption>
                <thead>
                  <tr>
                    {[
                      c.hour,
                      c.samples,
                      c.minimum,
                      c.maximum,
                      c.known,
                      c.state,
                      s.access,
                      s.collector,
                    ].map((name) => (
                      <th className="text-left p-2" scope="col" key={name}>
                        {name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...points]
                    .reverse()
                    .slice(page * 24, (page + 1) * 24)
                    .map((p) => (
                      <tr key={p.at} data-history-hour>
                        <th scope="row" className="text-left p-2">
                          {hour(p.at)}
                          {p.binding_changed && <p>{c.changed}</p>}
                        </th>
                        <td className="p-2">
                          {p.samples} / {p.expected_samples}
                          <p>
                            {c.gap}: {p.missing_samples}
                          </p>
                        </td>
                        <td className="p-2">
                          {number(p.metrics[metric].min_seconds)}
                        </td>
                        <td className="p-2">
                          {number(p.metrics[metric].max_seconds)}
                        </td>
                        <td className="p-2">
                          {p.metrics[metric].known_samples}
                        </td>
                        <td className="p-2">
                          {Object.entries(p.states).map(([key, count]) => (
                            <p key={key}>
                              {label(key)}: {count}
                            </p>
                          ))}
                          {!p.samples && s.unknown}
                        </td>
                        <td className="p-2">
                          {Object.entries(p.access_states).map(
                            ([key, count]) => (
                              <p key={key}>
                                {label(key)}: {count}
                              </p>
                            ),
                          )}
                          {!p.samples && s.unknown}
                        </td>
                        <td className="p-2">
                          {Object.entries(p.collector_states).map(
                            ([key, count]) => (
                              <p key={key}>
                                {label(key)}: {count}
                              </p>
                            ),
                          )}
                          {!p.samples && s.unknown}
                          {p.disabled_samples > 0 && (
                            <p>
                              {s.section} · {s.disabled}: {p.disabled_samples}
                            </p>
                          )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap gap-3 items-center my-3">
              <button
                className="button min-h-11"
                disabled={page === 0}
                onClick={() => setPage((v) => v - 1)}
              >
                {c.previous}
              </button>
              <span>
                {c.page} {page + 1} / {pageCount}
              </span>
              <button
                className="button min-h-11"
                disabled={page + 1 >= pageCount}
                onClick={() => setPage((v) => v + 1)}
              >
                {c.next}
              </button>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
