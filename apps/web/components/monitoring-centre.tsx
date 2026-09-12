"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import {
  centreCopy,
  centreSources,
  centreTimezone,
  type TemplateId,
} from "@/lib/monitoring-centre-copy";
import { riverCopy, riverAttribution } from "@/lib/river-copy";
import { airCopy } from "@/lib/air-copy";
import { pollenDraftCopy } from "@/lib/pollen-draft-copy";
import { pollenStations } from "@/lib/pollen-stations";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import styles from "./monitoring-centre.module.css";

type Domain = "air" | "pollen" | "river";
type Monitor = {
  id: string;
  domain: Domain;
  name: string | null;
  station_id: string;
  status: string;
  health: string;
  href: string | null;
  metrics: string[];
  last_observation_at: string | null;
  last_check_at: string | null;
  next_check_at: string | null;
};
type Page = {
  items: Monitor[];
  next_cursor: string | null;
  templates: {
    id: TemplateId;
    group: "personal" | "business";
    availability: "available" | "blocked" | "disabled" | "preview_only";
    href: string | null;
  }[];
};

export function MonitoringCentre() {
  const { session } = useAuth();
  const scope = session?.authenticated
    ? `${session.user?.id}:${session.organization?.id}:${session.role}`
    : "unavailable";
  return (
    <Centre
      key={scope}
      allowed={scope !== "unavailable"}
      canManage={session?.role === "organization_admin"}
    />
  );
}

function Centre({
  allowed,
  canManage,
}: {
  allowed: boolean;
  canManage: boolean;
}) {
  const { locale } = useI18n();
  const c = centreCopy[locale],
    r = riverCopy[locale];
  const [domain, setDomain] = useState("");
  const [status, setStatus] = useState("");
  const filterKey = `${domain}:${status}`;
  const [result, setResult] = useState<{ key: string; page: Page } | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const request = useRef<AbortController | null>(null);
  const data = result?.key === filterKey ? result.page : null;

  const load = useCallback(
    async (cursor: string | null = null) => {
      if (!allowed) return;
      request.current?.abort();
      const controller = new AbortController();
      request.current = controller;
      setBusy(true);
      setFailed(false);
      const query = new URLSearchParams({ limit: "30" });
      if (domain) query.set("domain", domain);
      if (status) query.set("status", status);
      if (cursor) query.set("cursor", cursor);
      try {
        const page = await api<Page>(`/monitoring-centre?${query}`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setResult((old) => ({
          key: filterKey,
          page: {
            ...page,
            items:
              cursor && old?.key === filterKey
                ? [
                    ...old.page.items,
                    ...page.items.filter(
                      (item) =>
                        !old.page.items.some(
                          (saved) =>
                            saved.id === item.id &&
                            saved.domain === item.domain,
                        ),
                    ),
                  ]
                : page.items,
          },
        }));
      } catch {
        if (!controller.signal.aborted) {
          setResult(null);
          setFailed(true);
        }
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    },
    [allowed, domain, status, filterKey],
  );

  useEffect(() => {
    void load();
    // Recheck access and freshness on return. Periodic reads do not collect sources.
    const refresh = () => {
      if (document.visibilityState === "visible") void load();
    };
    window.addEventListener("focus", refresh);
    const timer = window.setInterval(refresh, 60_000);
    return () => {
      request.current?.abort();
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
    };
  }, [load]);

  function label(key: string) {
    return (
      (c as unknown as Record<string, string>)[key] ||
      (r as unknown as Record<string, string>)[key] ||
      c.unknown
    );
  }
  function metric(row: Monitor, key: string) {
    const labels =
      row.domain === "pollen"
        ? pollenDraftCopy[locale].allergens
        : row.domain === "air"
          ? airCopy[locale]
          : r;
    return (labels as unknown as Record<string, string>)[key] || c.unknown;
  }
  function clock(value: string | null) {
    return value ? (
      <time dateTime={value}>
        {new Intl.DateTimeFormat(locale === "rm-CH" ? "de-CH" : locale, {
          dateStyle: "medium",
          timeStyle: "short",
          timeZone: "Europe/Zurich",
        }).format(new Date(value))}
      </time>
    ) : (
      c.none
    );
  }
  return (
    <Shell section={c.title}>
      <div className={styles.root} data-monitoring-centre>
        <header>
          <h1>{c.title}</h1>
          <p>{c.intro}</p>
          <a href="#choose-monitor">{c.choose}</a>
        </header>
        {!canManage && <p>{r.readonly}</p>}
        {!allowed && <p role="alert">{r.access_unavailable}</p>}
        {failed && <p role="alert">{r.failed}</p>}
        <button
          className={styles.button}
          disabled={!allowed || busy}
          onClick={() => void load()}
        >
          {r.refresh}
        </button>
        {busy && <p role="status">{r.loading}</p>}
        <section aria-labelledby="saved-monitors">
          <h2 id="saved-monitors">{c.saved}</h2>
          <div className={styles.filters}>
            <label>
              {c.domain}
              <select
                value={domain}
                onChange={(event) => setDomain(event.target.value)}
              >
                <option value="">{c.all}</option>
                {(["pollen", "river", "air"] as const).map((id) => (
                  <option key={id} value={id}>
                    {c.templates[id][0]}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {c.lifecycle}
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
              >
                <option value="">{c.all}</option>
                {["draft", "active", "paused", "archived"].map((id) => (
                  <option key={id} value={id}>
                    {label(id)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className={styles.note}>
            {c.scheduleHelp} {centreTimezone}
          </p>
          {data && data.items.length === 0 && <p role="status">{c.empty}</p>}
          <div className={styles.grid}>
            {data?.items.map((row) => (
              <article
                className={styles.card}
                key={`${row.domain}:${row.id}`}
                data-monitor={row.id}
              >
                <h3>
                  {row.name ||
                    `${c.templates[row.domain][0]} · ${pollenStations.find((station) => station.id === row.station_id)?.name || row.station_id}`}
                </h3>
                <p>
                  {c.templates[row.domain][0]} · {row.station_id}
                </p>
                <div className={styles.badges}>
                  <span className={styles.badge}>{label(row.status)}</span>
                  <span className={styles.badge}>{label(row.health)}</span>
                </div>
                <p>{row.metrics.map((key) => metric(row, key)).join(" · ")}</p>
                <p>
                  {c.source}:{" "}
                  {row.domain === "river"
                    ? riverAttribution[locale]
                    : row.domain === "pollen"
                      ? centreSources.pollen
                      : centreSources.air}
                </p>
                <dl>
                  {(
                    [
                      [c.observation, row.last_observation_at],
                      [c.lastCheck, row.last_check_at],
                      [c.nextCheck, row.next_check_at],
                    ] as const
                  ).map(([title, value]) => (
                    <div key={title}>
                      <dt>{title}</dt>
                      <dd>{clock(value)}</dd>
                    </div>
                  ))}
                </dl>
                {row.href ? (
                  <Link href={row.href}>
                    {c.open}
                    <span className="sr-only">
                      {" "}
                      · {row.name || c.templates[row.domain][0]}
                    </span>
                  </Link>
                ) : (
                  <p>{c.disabledHelp}</p>
                )}
              </article>
            ))}
          </div>
          {data?.next_cursor && (
            <button
              className={styles.button}
              disabled={busy}
              onClick={() => void load(data.next_cursor)}
            >
              {r.more}
            </button>
          )}
        </section>
        {data && (
          <section aria-labelledby="choose-monitor">
            <h2 id="choose-monitor" tabIndex={-1}>
              {c.choose}
            </h2>
            {(["personal", "business"] as const).map((group) => (
              <section key={group} aria-labelledby={`group-${group}`}>
                <h3 id={`group-${group}`}>{c[group]}</h3>
                <div className={styles.grid}>
                  {data.templates
                    .filter((item) => item.group === group)
                    .map((item) => (
                      <article
                        className={styles.card}
                        key={item.id}
                        data-template={item.id}
                      >
                        <h4>{c.templates[item.id][0]}</h4>
                        <span className={styles.badge}>
                          {c[item.availability]}
                        </span>
                        <p>{c.templates[item.id][1]}</p>
                        {item.availability === "disabled" && (
                          <p>{c.disabledHelp}</p>
                        )}
                        {item.availability === "preview_only" && (
                          <p>{c.previewHelp}</p>
                        )}
                        {item.href && (
                          <Link href={item.href}>
                            {canManage ? c.configure : c.open}
                            <span className="sr-only">
                              {" "}
                              · {c.templates[item.id][0]}
                            </span>
                          </Link>
                        )}
                      </article>
                    ))}
                </div>
              </section>
            ))}
          </section>
        )}
        <section aria-labelledby="legacy-monitoring">
          <h2 id="legacy-monitoring">{c.legacy}</h2>
          <p>{c.legacyHelp}</p>
          <div className={styles.filters}>
            <Link href="/topics">{c.topics}</Link>
            <Link href="/registry">{c.documents}</Link>
          </div>
        </section>
      </div>
    </Shell>
  );
}
