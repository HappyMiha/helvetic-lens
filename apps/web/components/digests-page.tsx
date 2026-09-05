"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CalendarClock, ExternalLink, Mail, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, errorText, useResource } from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { useI18n } from "@/lib/i18n";
import type { DigestOverview } from "@/lib/types";
import { ErrorNote, Loading, SuccessNote } from "./common";
import { Shell } from "./shell";
import { DigestCoverageNotice } from "./digest-coverage-notice";

const severities = ["high", "medium", "low", "none", "unknown"];

export function DigestsPage() {
  const { t, dateTime } = useI18n();
  const resource = useResource(resources.digests());
  const [enabled, setEnabled] = useState(false);
  const [frequency, setFrequency] = useState<"daily" | "weekly">("weekly");
  const [selectedSeverities, setSelectedSeverities] = useState<string[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!resource.data) return;
    setEnabled(resource.data.preference.enabled);
    setFrequency(resource.data.preference.frequency);
    setSelectedSeverities(resource.data.preference.severities);
    setSelectedSources(resource.data.preference.sources);
  }, [resource.data]);

  function toggle(
    values: string[],
    value: string,
    change: (next: string[]) => void,
  ) {
    change(
      values.includes(value)
        ? values.filter((item) => item !== value)
        : [...values, value],
    );
  }

  async function save() {
    setBusy("save");
    setError("");
    setNotice("");
    try {
      const result = await api<DigestOverview>("/digests/preferences", {
        method: "PUT",
        body: JSON.stringify({
          enabled,
          frequency,
          severities: selectedSeverities,
          sources: selectedSources,
        }),
      });
      resource.setData(result);
      setNotice(t("digests.saved"));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  async function sendNow() {
    setBusy("send");
    setError("");
    setNotice("");
    try {
      await api("/digests/send", { method: "POST" });
      setNotice(t("digests.queued"));
      resource.reload();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  return (
    <Shell section={t("nav.digests")}>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("digests.eyebrow")}</span>
          <h1>{t("digests.title")}</h1>
          <p className="muted m-0">{t("digests.body")}</p>
        </div>
        <Mail className="muted" size={28} />
      </div>
      <ErrorNote message={resource.error || error} />
      {notice && <SuccessNote>{notice}</SuccessNote>}
      {!resource.data ? (
        <div className="panel p-6">
          <Loading />
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)] items-start">
          <section className="panel p-6 grid gap-5">
            <div>
              <h2 className="mb-2">{t("digests.delivery")}</h2>
              <p className="text-sm muted m-0">{t("digests.deliveryBody")}</p>
            </div>
            <label className="flex gap-3 items-start">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(event) => setEnabled(event.target.checked)}
              />
              <span>
                <strong>{t("digests.enable")}</strong>
                <small className="block muted">{t("digests.enableHelp")}</small>
              </span>
            </label>
            <label className="grid gap-2 text-sm font-semibold">
              {t("digests.frequency")}
              <select
                className="input"
                value={frequency}
                onChange={(event) =>
                  setFrequency(event.target.value as "daily" | "weekly")
                }
              >
                <option value="daily">{t("digests.daily")}</option>
                <option value="weekly">{t("digests.weekly")}</option>
              </select>
            </label>
            <fieldset className="grid gap-2">
              <legend className="text-sm font-semibold mb-2">
                {t("digests.severity")}
              </legend>
              <p className="text-xs muted mt-0">{t("digests.allEmpty")}</p>
              <div className="flex flex-wrap gap-2">
                {severities.map((severity) => (
                  <label key={severity} className="chip cursor-pointer">
                    <input
                      className="mr-2"
                      type="checkbox"
                      checked={selectedSeverities.includes(severity)}
                      onChange={() =>
                        toggle(
                          selectedSeverities,
                          severity,
                          setSelectedSeverities,
                        )
                      }
                    />
                    {t(`status.${severity}`)}
                  </label>
                ))}
              </div>
            </fieldset>
            {resource.data.source_options.length > 0 && (
              <fieldset className="grid gap-2">
                <legend className="text-sm font-semibold mb-2">
                  {t("digests.sources")}
                </legend>
                <p className="text-xs muted mt-0">{t("digests.allEmpty")}</p>
                {resource.data.source_options.map((source) => (
                  <label key={source} className="flex gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={selectedSources.includes(source)}
                      onChange={() =>
                        toggle(selectedSources, source, setSelectedSources)
                      }
                    />
                    {source}
                  </label>
                ))}
              </fieldset>
            )}
            {resource.data.delivery_mode === "disabled" && (
              <div className="note">{t("digests.emailDisabled")}</div>
            )}
            <div className="flex flex-wrap gap-2">
              <Button onClick={save} disabled={!!busy}>
                {t("common.save")}
              </Button>
              <Button
                variant="outline"
                onClick={sendNow}
                disabled={!!busy || !resource.data.preference.enabled}
              >
                <Send size={15} />
                {t("digests.sendNow")}
              </Button>
            </div>
            <p className="text-xs muted m-0">
              <CalendarClock size={13} className="inline mr-1" />
              {resource.data.preference.next_delivery_at
                ? t("digests.next", {
                    date: dateTime(resource.data.preference.next_delivery_at),
                  })
                : t("digests.off")}
            </p>
          </section>
          <div className="grid gap-6">
            <section className="panel p-6">
              <h2 className="mb-2">{t("digests.preview")}</h2>
              <p className="text-sm muted">{t("digests.previewBody")}</p>
              <DigestCoverageNotice summary={resource.data.preview} />
              {resource.data.preview.events.length === 0 ? (
                <p className="muted">{t("digests.empty")}</p>
              ) : (
                <div className="grid gap-4">
                  {resource.data.preview.events.map((event) => (
                    <article
                      key={event.event_id}
                      className="rounded-xl border border-border p-4"
                    >
                      <div className="flex justify-between gap-3">
                        <div>
                          <span className="eyebrow">
                            {event.source} · {t(`status.${event.severity}`)}
                          </span>
                          <h3 className="mt-2">{event.title}</h3>
                        </div>
                        {event.source_url && (
                          <a
                            href={event.source_url}
                            target="_blank"
                            rel="noreferrer"
                            aria-label={t("common.officialSource")}
                          >
                            <ExternalLink size={16} />
                          </a>
                        )}
                      </div>
                      {event.impacts.map((impact) => (
                        <div
                          key={impact.law_id}
                          className="mt-3 pt-3 border-t border-border"
                        >
                          <strong>{impact.law_title}</strong>
                          <p className="text-sm muted mb-2">
                            {impact.potential_effect}
                          </p>
                          <p className="text-sm">
                            <b>{t("impact.next")}:</b> {impact.next_step}
                          </p>
                          {impact.comparison && (
                            <Link className="text-sm" href={impact.comparison}>
                              {t("common.comparison")}
                            </Link>
                          )}
                        </div>
                      ))}
                      {event.impacts_truncated &&
                        typeof event.impact_count === "number" && (
                          <p className="text-sm font-medium mt-3 mb-0">
                            {t("digests.moreLaws", {
                              shown: event.impacts.length,
                              total: event.impact_count,
                            })}
                          </p>
                        )}
                    </article>
                  ))}
                </div>
              )}
            </section>
            <section className="panel p-6">
              <h2>{t("digests.history")}</h2>
              {resource.data.deliveries.length === 0 ? (
                <p className="muted">{t("digests.noHistory")}</p>
              ) : (
                resource.data.deliveries.map((delivery) => (
                  <div
                    key={delivery.id}
                    className="py-3 border-b border-border text-sm"
                  >
                    <div className="flex flex-wrap justify-between gap-2">
                      <span>
                        {dateTime(delivery.created_at)} ·{" "}
                        {t(`status.${delivery.status}`)}
                      </span>
                      <span>
                        {t("digests.items", { count: delivery.item_count })}
                      </span>
                    </div>
                    <DigestCoverageNotice summary={delivery.summary} />
                  </div>
                ))
              )}
            </section>
          </div>
        </div>
      )}
    </Shell>
  );
}
