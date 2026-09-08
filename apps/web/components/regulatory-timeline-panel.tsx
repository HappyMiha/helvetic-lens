"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { invalidateResources, label, useResource } from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { translate, useI18n } from "@/lib/i18n";
import { regulatoryTimelineCopy } from "@/lib/regulatory-timeline-copy";
import type {
  RegulatoryTimeline,
  RegulatoryTimelineKind,
  RegulatoryTimelinePage,
} from "@/lib/types";
import { Status } from "./common";
import { Button } from "./ui/button";
import { DocumentHistoryNavigation } from "./document-history-navigation";

const kinds: RegulatoryTimelineKind[] = [
  "timeline",
  "relations",
  "identifiers",
  "expressions",
  "source_provenance",
];
function SourceLink({
  href,
  children,
}: {
  href?: string | null;
  children: React.ReactNode;
}) {
  if (!href) return null;
  if (/^\/(laws|evidence|compare)\/[^/]/.test(href))
    return (
      <Link className="text-link" href={href}>
        {children}
        <ArrowUpRight size={14} />
      </Link>
    );
  if (/^https?:\/\//i.test(href))
    return (
      <a className="text-link" href={href} target="_blank" rel="noreferrer">
        {children}
        <ArrowUpRight size={14} />
      </a>
    );
  return null;
}

export function RegulatoryTimelinePanel({
  lawId,
  record,
}: {
  lawId: string;
  record: RegulatoryTimeline;
}) {
  const { t, locale, number } = useI18n();
  const copy = regulatoryTimelineCopy[locale];
  const [selected, setSelected] = useState<RegulatoryTimelineKind>("timeline");
  const titles = {
    timeline: t("law.savedTimeline"),
    relations: t("law.relations"),
    identifiers: t("law.identifiers"),
    expressions: t("law.expressions"),
    source_provenance: copy.sources,
  };
  return (
    <section
      className="panel mt-6 regulatory-timeline"
      data-regulatory-timeline
    >
      <header className="panel-header">
        <div>
          <span className="eyebrow">{t("law.legalRecord")}</span>
          <h2>{t("law.timeline")}</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <Status value={record.work.lifecycle} />
          <Status value={record.monitoring.active ? "active" : "paused"} />
          <Button asChild variant="outline">
            <Link href="/registry">{t("law.openRegistry")}</Link>
          </Button>
        </div>
      </header>
      <div className="p-5 border-b">
        <p>{copy.help}</p>
        <p className="mt-3">
          {t("law.authorityKind")}: <strong>{record.work.authority}</strong> ·{" "}
          {translate(locale, `topics.kind.${record.work.kind}`) ||
            label(record.work.kind)}
        </p>
        <p>
          {t("law.immutableVersions", {
            count: number(record.normalized_versions),
          })}
        </p>
        <nav
          className="flex flex-wrap gap-2 mt-4"
          aria-label={t("law.timeline")}
        >
          {kinds.map((kind) => (
            <Button
              key={kind}
              variant={selected === kind ? "default" : "outline"}
              aria-pressed={selected === kind}
              data-timeline-kind={kind}
              onClick={() => setSelected(kind)}
            >
              {titles[kind]}
              {record.pages && ` (${number(record.pages[kind].total)})`}
            </Button>
          ))}
        </nav>
      </div>
      {kinds.map((kind) => (
        <TimelineRows
          key={`${lawId}:${record.work.id}:${kind}:${locale}`}
          lawId={lawId}
          record={record}
          kind={kind}
          title={titles[kind]}
          active={selected === kind}
        />
      ))}
    </section>
  );
}

function TimelineRows({
  lawId,
  record,
  kind,
  title,
  active,
}: {
  lawId: string;
  record: RegulatoryTimeline;
  kind: RegulatoryTimelineKind;
  title: string;
  active: boolean;
}) {
  const { t, locale, dateTime } = useI18n();
  const copy = regulatoryTimelineCopy[locale];
  const [cursors, setCursors] = useState<string[]>([]);
  const cursor = cursors.at(-1);
  const focus = useRef(false);
  const request = useResource(
    cursor && active ? resources.regulatoryTimeline(lawId, kind, cursor) : null,
  );
  const initial = record.pages?.[kind];
  const candidate = cursor
    ? request.data
    : initial
      ? { ...initial, items: record[kind] }
      : null;
  const retained = useRef<{
    data: RegulatoryTimelinePage<RegulatoryTimelineKind>;
    page: number;
  } | null>(null);
  if (candidate && !request.error)
    retained.current = { data: candidate, page: Math.max(1, cursors.length) };
  const data = candidate || retained.current?.data;
  const items = data?.items || record[kind];
  const headingId = `history-regulatory-${kind}`;
  useEffect(() => {
    if (
      active &&
      focus.current &&
      !request.loading &&
      (candidate || request.error)
    ) {
      document.getElementById(headingId)?.focus();
      focus.current = false;
    }
  }, [active, candidate, request.loading, request.error, headingId]);
  const history = {
    kind: `regulatory-${kind}`,
    data,
    items,
    loading: !!cursor && request.loading,
    error: cursor ? request.error : "",
    page: retained.current?.page || 1,
    canPrevious: cursors.length > 1,
    emptyMessage: kind === "identifiers" ? t("law.noIdentifier") : undefined,
    next: () => {
      if (data?.next_cursor) {
        focus.current = true;
        setCursors((v) => [
          ...(v.length ? v : [data.first_cursor]),
          data.next_cursor!,
        ]);
      }
    },
    previous: () => {
      focus.current = true;
      setCursors((v) => v.slice(0, -1));
    },
    retry: () => request.reload(),
    restart: () => {
      focus.current = true;
      retained.current = null;
      setCursors([]);
      void invalidateResources(resources.law(lawId));
    },
  };
  const provenance = (value: string) =>
    translate(locale, `feedProvenance.${value.replaceAll(" ", "_")}`) ||
    translate(locale, `status.${value}`) ||
    label(value);
  return (
    <section
      hidden={!active}
      aria-labelledby={headingId}
      data-timeline-section={kind}
    >
      <h3 className="p-4 font-semibold" id={headingId} tabIndex={-1}>
        {title}
      </h3>
      <DocumentHistoryNavigation history={history} />
      <ul className="p-5 space-y-3" data-timeline-rows={kind}>
        {kind === "timeline" &&
          (items as RegulatoryTimeline["timeline"]).map((item) => (
            <li key={item.id}>
              <strong>
                {item.type === "version"
                  ? copy.version
                  : item.type === "comparison"
                    ? copy.comparison
                    : translate(
                        locale,
                        `topics.kind.${item.event_type || item.label.toLowerCase().replaceAll(" ", "_")}`,
                      ) || copy.event}
              </strong>
              <p>
                <time dateTime={item.at}>
                  {dateTime(item.at, {
                    dateStyle: "medium",
                    timeStyle: "long",
                  })}
                </time>{" "}
                · {provenance(item.detail)}
              </p>
              <SourceLink href={item.url}>
                {item.type === "event" ? t("law.source") : t("law.inspect")}
              </SourceLink>
            </li>
          ))}
        {kind === "identifiers" &&
          (items as RegulatoryTimeline["identifiers"]).map((item) => (
            <li key={item.scheme + item.value}>
              <strong>
                {label(item.scheme)}: {item.value}
              </strong>
              <SourceLink href={item.source_url}>{t("law.source")}</SourceLink>
            </li>
          ))}
        {kind === "expressions" &&
          (items as RegulatoryTimeline["expressions"]).map((item) => (
            <li key={item.id}>
              <strong>
                {item.language} · {item.title}
              </strong>
              <SourceLink href={item.url}>{t("law.source")}</SourceLink>
            </li>
          ))}
        {kind === "relations" &&
          (items as RegulatoryTimeline["relations"]).map((item) => (
            <li key={item.id}>
              <strong>
                {item.other_title ||
                  t("law.work", { id: item.other_work_id.slice(0, 8) })}
              </strong>
              <p>
                {translate(locale, `status.${item.direction}`) ||
                  label(item.direction)}{" "}
                · {translate(locale, `status.${item.type}`) || label(item.type)}{" "}
                · {provenance(item.provenance)}
              </p>
              <Status value={item.state} />
              <SourceLink href={item.other_timeline_url}>
                {t("law.inspect")}
              </SourceLink>
            </li>
          ))}
        {kind === "source_provenance" &&
          (items as RegulatoryTimeline["source_provenance"]).map(
            (item, index) => (
              <li key={item.observed_at + index}>
                <strong>{provenance(item.origin)}</strong>
                <p>
                  <time dateTime={item.observed_at}>
                    {dateTime(item.observed_at, {
                      dateStyle: "medium",
                      timeStyle: "long",
                    })}
                  </time>
                </p>
                <SourceLink href={item.source_url}>
                  {t("law.source")}
                </SourceLink>
              </li>
            ),
          )}
      </ul>
    </section>
  );
}
