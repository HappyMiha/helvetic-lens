"use client";

import type { TopicSourceCoverage } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { Status } from "./common";

function attentionCount(pack: TopicSourceCoverage["items"][number]) {
  return pack.unknown_stream_count + pack.streams.filter(stream =>
    !stream.configured || !stream.enabled || !stream.last_success_at || stream.next_attempt_past_due ||
    ["unknown", "degraded", "error"].includes(stream.last_reported_health) ||
    ["partial", "failed"].includes(stream.last_run_status || "")
  ).length;
}

export function TopicSourceReadiness({ coverage }: { coverage: TopicSourceCoverage }) {
  const { t, locale, dateTime, number } = useI18n();
  const timestamp = (value: string) => dateTime(value, { dateStyle: "medium", timeStyle: "short" });
  return (
    <section className="mt-5 scroll-mt-24 rounded-lg border p-4 text-sm" data-topic-source-readiness aria-live="polite">
      <h3>{t("topicSources.title")}</h3>
      <p>{t("topicSources.boundary")}</p>
      <p>{t("topicSources.enabled", { enabled: coverage.enabled_pack_count, total: coverage.items.length })}</p>
      {coverage.enabled_pack_count === 0 && <p className="font-medium" data-topic-sources-inactive>{t("topicSources.none")}</p>}
      <p>{t("topicSources.asOf")} <time dateTime={coverage.captured_at}>{timestamp(coverage.captured_at)}</time></p>
      <a className="underline inline-flex min-h-11 items-center" href="/sources">{t("topicSources.manage")}</a>
      <div className="space-y-3">
        {coverage.items.map(pack => (
          <details className="rounded-lg border p-3" key={pack.id} data-topic-source-pack>
            <summary className="cursor-pointer min-h-11 break-words">
              {pack.name[locale] || pack.name["en-CH"] || pack.id}
              <span className="ml-2"><Status value={pack.subscription_state} /></span>
              {attentionCount(pack) > 0 && <span className="block mt-2" data-topic-source-attention>{t("topicSources.attention", { count: attentionCount(pack) })}</span>}
            </summary>
            {!pack.subscription_enabled && <p>{t("topicSources.inactive")}</p>}
            {pack.unknown_stream_count > 0 && <p>{t("topicSources.unknown")}</p>}
            <div className="grid gap-3 mt-3 lg:grid-cols-2">
              {pack.streams.map(stream => (
                <article className="rounded border p-3 break-words" key={`${stream.connector}:${stream.stream}`} data-topic-source-stream>
                  <h4>{stream.publisher} · {stream.stream}</h4>
                  <p>{stream.localized_copy[locale]?.summary || stream.localized_copy["en-CH"]?.summary}</p>
                  <p className="font-medium">{t(!stream.configured ? "topicSources.unscheduled" : !stream.enabled ? "topicSources.paused" : "topicSources.scheduled")}</p>
                  {stream.configured && <p>{t("topicSources.interval", { minutes: number((stream.interval_seconds || 0) / 60), jitter: number((stream.jitter_seconds || 0) / 60) })}</p>}
                  {stream.window_start && stream.window_end && <p>{t("topicSources.window", { start: stream.window_start, end: stream.window_end })}</p>}
                  {stream.enabled && stream.next_run_at && <p>{t("topicSources.next")} <time data-topic-source-next dateTime={stream.next_run_at}>{timestamp(stream.next_run_at)}</time></p>}
                  {stream.next_attempt_past_due && <p>{t("topicSources.overdue")}</p>}
                  <p>{t("topicSources.lastSuccess")} {stream.last_success_at ? timestamp(stream.last_success_at) : t("topicSources.never")}</p>
                  <p>{t("topicSources.health")} <Status value={stream.last_reported_health} /></p>
                  {stream.last_run_status && <p>{t("topicSources.lastRun")} <Status value={stream.last_run_status} /></p>}
                  {stream.catalogue_state !== "available" && <p>{t("topicSources.partial")}</p>}
                  <p className="muted">{stream.localized_copy[locale]?.boundary || stream.localized_copy["en-CH"]?.boundary}</p>
                </article>
              ))}
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}
