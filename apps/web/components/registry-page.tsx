"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  Clock3,
  Eye,
  FileSearch,
  Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, dateTime, errorText, label, useResource } from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { registryDateRange, registryPeriods } from "@/lib/registry-filters";
import { ErrorNote, Loading, Status } from "./common";
import { Shell } from "./shell";
import { useAuth } from "./auth-gate";
import { useI18n } from "@/lib/i18n";

type OfficialDate = {
  value: string;
  precision: string;
  provenance: string;
  source_url?: string;
};
type RegistryRow = {
  id: string;
  record_type: "event" | "monitored";
  event_id?: string;
  event_type: string;
  detected_at: string;
  title: string;
  authority: string;
  connector: string;
  connector_health: string;
  kind: string;
  languages: string[];
  lifecycle: string;
  impact: string;
  analysis_state: string;
  read: boolean;
  watched: boolean;
  why: string;
  linked_laws: { law_id: string; name: string; timeline_url: string }[];
  official_dates: Record<string, OfficialDate[]>;
  source_url?: string;
  evidence_url?: string;
  timeline_url?: string;
  comparison_url?: string;
};
type RegistryResponse = {
  view: "monitored" | "events";
  groups: { name: string; items: RegistryRow[] }[];
  next_cursor?: string;
  count: number;
};

const FILTERS = [
  [
    "authority",
    "filter.authority",
    ["", "fedlex", "parliament", "federal_supreme_court", "native"],
  ],
  [
    "connector",
    "filter.connector",
    ["", "fedlex", "parliament", "federal_supreme_court", "test-feed"],
  ],
  [
    "kind",
    "filter.kind",
    [
      "",
      "act",
      "ordinance",
      "parliamentary_business",
      "initiative",
      "bill",
      "court_decision",
      "official_notice",
      "unclassified_document",
    ],
  ],
  ["language", "filter.language", ["", "de", "fr", "it", "rm", "en", "und"]],
  [
    "lifecycle",
    "filter.lifecycle",
    ["", "in_force", "planned", "repealed", "unknown"],
  ],
  ["impact", "filter.impact", ["", "high", "medium", "low", "none", "unknown"]],
  ["watched", "filter.monitoring", ["", "watched", "unwatched"]],
  ["read", "filter.readState", ["", "unread", "read"]],
  ["health", "filter.health", ["", "healthy", "degraded", "error", "unknown"]],
] as const;
const ALL_FILTER_KEYS: Record<string, string> = {
  authority: "filter.allAuthorities",
  connector: "filter.allConnectors",
  kind: "filter.allKinds",
  language: "filter.allLanguages",
  lifecycle: "filter.allLifecycle",
  impact: "filter.allImpacts",
  watched: "filter.allMonitoring",
  read: "filter.allRead",
  health: "filter.allHealth",
};
const PRIMARY_FILTERS = new Set(["impact", "read", "watched"]);
const LANGUAGES: Record<string, string> = {
  de: "Deutsch",
  fr: "Français",
  it: "Italiano",
  rm: "Rumantsch",
  en: "English",
};
const VALUE_LABELS: Record<string, string> = {
  parliament: "registryFilters.value.parliament",
  federal_supreme_court: "registryFilters.value.federal_supreme_court",
  native: "registryFilters.value.native",
  "test-feed": "registryFilters.value.test-feed",
  in_force: "registryFilters.value.in_force",
  repealed: "registryFilters.value.repealed",
  watched: "registryFilters.value.watched",
  unwatched: "registryFilters.value.unwatched",
  und: "registryFilters.value.und",
};
const PERIOD_LABELS: Record<string, string> = {
  all: "registryFilters.period.all",
  today: "registryFilters.period.today",
  yesterday: "registryFilters.period.yesterday",
  week: "registryFilters.period.week",
  month: "registryFilters.period.month",
};
function filterValue(key: string, value: string, t: (key: string) => string) {
  if (!value) return t(ALL_FILTER_KEYS[key]);
  if (
    !FILTERS.find(([name]) => name === key)?.[2].some(
      (option) => option === value,
    )
  )
    return t("registryFilters.unavailable");
  if (key === "language" && LANGUAGES[value]) return LANGUAGES[value];
  if (key === "kind") return t(`topics.kind.${value}`);
  if (
    ["impact", "read", "health"].includes(key) ||
    ["unknown", "planned"].includes(value)
  )
    return t(`status.${value}`);
  if (value === "fedlex") return "Fedlex";
  return t(VALUE_LABELS[value] || "registryFilters.unavailable");
}

const GROUP_LABELS: Record<string, string> = {
  Today: "registryFilters.period.today",
  Yesterday: "registryFilters.period.yesterday",
  "Last 7 days": "registryFilters.period.week",
  "Last 30 days": "registryFilters.period.month",
  Older: "registryFilters.older",
  "Custom range": "registryFilters.custom",
};

function officialDates(
  row: RegistryRow,
  t: (key: string, values?: Record<string, string | number>) => string,
) {
  const order = [
    "published_at",
    "version_date",
    "decision_date",
    "effective_from",
    "effective_to",
  ];
  const dates = order.flatMap((kind) =>
    (row.official_dates[kind] || []).map((item) => ({ kind, ...item })),
  );
  if (!dates.length)
    return <span className="muted">{t("registry.officialDatesUnknown")}</span>;
  return (
    <span className="flex flex-wrap gap-x-3 gap-y-1 muted">
      {dates.map((item, index) => (
        <span key={item.kind + item.value + index}>
          {label(item.kind)}: <strong>{item.value}</strong> ({item.precision})
        </span>
      ))}
    </span>
  );
}

export function RegistryPage({
  defaultView = "monitored",
}: {
  defaultView?: "monitored" | "events";
}) {
  const params = useSearchParams();
  const router = useRouter();
  const { canManage } = useAuth();
  const { t } = useI18n();
  const requestedView = params.get("view");
  const legacyView =
    requestedView === "events" || requestedView === "monitored"
      ? requestedView
      : null;
  const view = legacyView || defaultView;
  const canonicalPath = view === "events" ? "/discover" : "/registry";
  const [query, setQuery] = useState(params.get("q") || "");
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const advancedSignature = FILTERS.filter(([key]) => !PRIMARY_FILTERS.has(key))
    .map(([key]) => params.get(key) || "")
    .join("|");
  useEffect(() => {
    if (advancedSignature.replaceAll("|", "")) setAdvancedOpen(true);
  }, [advancedSignature]);
  const activeFilters = FILTERS.filter(([key]) => !!params.get(key));
  const advancedCount = activeFilters.filter(
    ([key]) => !PRIMARY_FILTERS.has(key),
  ).length;
  const hasDateRange = !!(params.get("start") || params.get("end"));
  const activeCount =
    activeFilters.length + Number(!!params.get("q")) + Number(hasDateRange);
  const endpointParameters = new URLSearchParams(params.toString());
  endpointParameters.set("view", view);
  const endpoint = "/registry?" + endpointParameters.toString();
  const resource = useResource(resources.registry<RegistryResponse>(endpoint));

  useEffect(() => setQuery(params.get("q") || ""), [params]);

  useEffect(() => {
    if (requestedView === null) return;
    const next = new URLSearchParams(params.toString());
    next.delete("view");
    const search = next.toString();
    router.replace(canonicalPath + (search ? `?${search}` : ""), {
      scroll: false,
    });
  }, [canonicalPath, params, requestedView, router]);

  function routeFor(targetView: "monitored" | "events") {
    const next = new URLSearchParams(params.toString());
    next.delete("view");
    next.delete("cursor");
    const search = next.toString();
    const path = targetView === "events" ? "/discover" : "/registry";
    return path + (search ? `?${search}` : "");
  }

  function update(values: Record<string, string>, resetCursor = true) {
    const next = new URLSearchParams(params.toString());
    next.delete("view");
    for (const [key, value] of Object.entries(values)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (resetCursor) next.delete("cursor");
    const search = next.toString();
    router.push(canonicalPath + (search ? `?${search}` : ""));
  }
  function clearFilters() {
    setQuery("");
    update(
      Object.fromEntries(
        [...FILTERS.map(([key]) => key), "q", "start", "end"].map((key) => [
          key,
          "",
        ]),
      ),
    );
  }
  function renderFilters(primary: boolean) {
    return FILTERS.filter(([key]) => PRIMARY_FILTERS.has(key) === primary).map(
      ([key, title, values]) => (
        <label className="text-sm muted" key={key}>
          {t(title)}
          <select
            name={key}
            className="input mt-1 w-full min-h-11"
            value={params.get(key) || ""}
            onChange={(event) => update({ [key]: event.target.value })}
          >
            {!values.some((value) => value === params.get(key)) &&
              params.get(key) && (
                <option value={params.get(key)!}>
                  {t("registryFilters.unavailable")}
                </option>
              )}
            {values.map((value) => (
              <option value={value} key={value}>
                {filterValue(key, value, t)}
              </option>
            ))}
          </select>
        </label>
      ),
    );
  }
  function search(event: FormEvent) {
    event.preventDefault();
    update({ q: query });
  }
  async function markRead(row: RegistryRow) {
    if (!row.event_id) return;
    setBusy(row.event_id);
    setActionError("");
    try {
      await api(`/registry/events/${row.event_id}/read`, {
        method: "PATCH",
        body: JSON.stringify({ read: !row.read }),
      });
      resource.reload();
    } catch (cause) {
      setActionError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  return (
    <Shell
      section={t(view === "events" ? "nav.discover" : "nav.monitoring")}
      wide
    >
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("registry.eyebrow")}</span>
          <h1>{t("registry.title")}</h1>
          <p className="muted m-0">{t("registry.body")}</p>
        </div>
      </div>

      <div
        className="flex flex-wrap gap-2 mb-5"
        role="tablist"
        aria-label={t("registry.views")}
      >
        <Button asChild variant={view === "monitored" ? "default" : "outline"}>
          <Link
            aria-controls="registry-results"
            aria-selected={view === "monitored"}
            href={routeFor("monitored")}
            id="registry-monitored-tab"
            role="tab"
          >
            <BookOpen size={16} /> {t("registry.monitored")}
          </Link>
        </Button>
        <Button asChild variant={view === "events" ? "default" : "outline"}>
          <Link
            aria-controls="registry-results"
            aria-selected={view === "events"}
            href={routeFor("events")}
            id="registry-events-tab"
            role="tab"
          >
            <Clock3 size={16} /> {t("registry.events")}
          </Link>
        </Button>
      </div>

      <div
        aria-labelledby={
          view === "events" ? "registry-events-tab" : "registry-monitored-tab"
        }
        id="registry-results"
        role="tabpanel"
        tabIndex={0}
      >
        <section
          className="card p-5 mb-5"
          aria-label={t("registryFilters.title")}
          data-registry-filters
        >
          <form className="flex flex-wrap gap-2 mb-4" onSubmit={search}>
            <label className="relative flex-1 min-w-40">
              <span className="sr-only">{t("registry.searchPlaceholder")}</span>
              <Search
                size={16}
                className="absolute left-3 top-3 muted"
                aria-hidden="true"
              />
              <Input
                name="q"
                className="pl-9 min-h-11"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("registry.searchPlaceholder")}
              />
            </label>
            <Button type="submit" variant="outline" className="min-h-11">
              {t("common.search")}
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="min-h-11"
              onClick={clearFilters}
              data-registry-clear
            >
              {t("common.clear")}
            </Button>
          </form>
          <fieldset className="mb-4">
            <legend className="text-sm font-semibold mb-2">
              {t("registryFilters.period")}
            </legend>
            <div className="flex flex-wrap gap-2">
              {registryPeriods.map((period) => {
                const range = registryDateRange(period);
                const selected =
                  range.start === (params.get("start") || "") &&
                  range.end === (params.get("end") || "");
                return (
                  <Button
                    key={period}
                    variant={selected ? "default" : "outline"}
                    className="min-h-11"
                    aria-pressed={selected}
                    data-registry-period={period}
                    onClick={() => update(range)}
                  >
                    {t(PERIOD_LABELS[period])}
                  </Button>
                );
              })}
            </div>
            <p className="text-xs muted mb-0">
              {t("registryFilters.periodHelp")}
            </p>
          </fieldset>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {renderFilters(true)}
          </div>
          <details
            className="mt-4"
            open={advancedOpen}
            onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
            data-registry-advanced
          >
            <summary className="cursor-pointer min-h-11 py-3 font-medium text-sm">
              {t("registryFilters.advanced", { count: advancedCount })}
            </summary>
            <p className="text-sm muted mt-0">
              {t("registryFilters.advancedHelp")}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {renderFilters(false)}
              <label className="text-sm muted">
                {t("registry.from")}
                <Input
                  type="date"
                  name="start"
                  className="mt-1 min-h-11"
                  value={params.get("start") || ""}
                  onChange={(event) => update({ start: event.target.value })}
                />
              </label>
              <label className="text-sm muted">
                {t("registry.to")}
                <Input
                  type="date"
                  name="end"
                  className="mt-1 min-h-11"
                  value={params.get("end") || ""}
                  onChange={(event) => update({ end: event.target.value })}
                />
              </label>
            </div>
          </details>
          {activeCount > 0 && (
            <div className="mt-4" data-registry-active>
              <p className="text-sm font-semibold mb-2">
                {t("registryFilters.active", { count: activeCount })}
              </p>
              <div className="flex flex-wrap gap-2">
                {params.get("q") && (
                  <Button
                    variant="outline"
                    className="min-h-11 h-auto whitespace-normal text-left break-words max-w-full"
                    onClick={() => {
                      setQuery("");
                      update({ q: "" });
                    }}
                    data-remove-filter="q"
                  >
                    {t("registryFilters.remove", {
                      name: t("common.search"),
                      value: params.get("q")!,
                    })}
                  </Button>
                )}
                {activeFilters.map(([key, title]) => (
                  <Button
                    key={key}
                    variant="outline"
                    className="min-h-11 h-auto whitespace-normal text-left break-words max-w-full"
                    onClick={() => update({ [key]: "" })}
                    data-remove-filter={key}
                  >
                    {t("registryFilters.remove", {
                      name: t(title),
                      value: filterValue(key, params.get(key)!, t),
                    })}
                  </Button>
                ))}
                {hasDateRange && (
                  <Button
                    variant="outline"
                    className="min-h-11 h-auto whitespace-normal text-left break-words max-w-full"
                    onClick={() => update({ start: "", end: "" })}
                    data-remove-filter="dates"
                  >
                    {t("registryFilters.remove", {
                      name: t("registryFilters.period"),
                      value: `${params.get("start") || t("registryFilters.anyDate")} – ${params.get("end") || t("registryFilters.anyDate")}`,
                    })}
                  </Button>
                )}
              </div>
            </div>
          )}
        </section>

        <ErrorNote message={actionError || resource.error} />
        {resource.loading && !resource.data && (
          <Loading text={t("registry.loading")} />
        )}
        {!resource.loading && resource.data?.count === 0 && (
          <section className="empty-state card">
            <FileSearch size={28} />
            <h2>{t("registry.empty")}</h2>
            <p className="muted">{t("registry.emptyBody")}</p>
            {activeCount > 0 && (
              <Button
                variant="outline"
                onClick={clearFilters}
                data-registry-empty-clear
                className="min-h-11"
              >
                {t("registryFilters.clearEmpty")}
              </Button>
            )}
          </section>
        )}
        <div className="space-y-6">
          {resource.data?.groups.map((group) => (
            <section key={group.name}>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xl m-0">
                  {t(GROUP_LABELS[group.name] || "registryFilters.custom")}
                </h2>
                <span className="muted text-sm">
                  {t("registry.onPage", { count: group.items.length })}
                </span>
              </div>
              <div className="space-y-3">
                {group.items.map((row) => (
                  <article className="card p-5" key={row.id}>
                    <div className="flex flex-col sm:flex-row items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap gap-2 mb-2">
                          <Status value={row.event_type} />
                          <Status value={row.impact} />
                          <Status value={row.analysis_state} />
                          {row.read && (
                            <span className="status-badge status-green">
                              <CheckCircle2 size={12} /> {t("status.read")}
                            </span>
                          )}
                        </div>
                        <h3 className="text-lg m-0 mb-1">{row.title}</h3>
                        <p className="muted m-0 text-sm">
                          {row.authority} · {label(row.kind)} ·{" "}
                          {row.languages.join(", ")} · {label(row.lifecycle)}
                        </p>
                        {row.kind === "official_notice" && (
                          <p className="muted m-0 mt-2 text-xs">
                            {t("registry.officialNotice")}
                          </p>
                        )}
                      </div>
                      <div className="text-sm sm:text-right sm:shrink-0">
                        <strong>
                          {t("registry.detected", {
                            date: dateTime(row.detected_at),
                          })}
                        </strong>
                        <div className="muted">
                          {row.connector} · {label(row.connector_health)}
                        </div>
                      </div>
                    </div>
                    <p className="my-3">{row.why}</p>
                    <div className="text-sm mb-3">{officialDates(row, t)}</div>
                    <div className="text-sm muted mb-4">
                      {row.linked_laws.length
                        ? t("registry.linked", {
                            laws: row.linked_laws
                              .map((item) => item.name)
                              .join(", "),
                          })
                        : t("registry.notLinked")}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {row.timeline_url && (
                        <Button asChild size="sm">
                          <Link href={row.timeline_url}>
                            {t("common.timeline")} <ArrowRight size={14} />
                          </Link>
                        </Button>
                      )}
                      {row.comparison_url && (
                        <Button asChild size="sm" variant="outline">
                          <Link href={row.comparison_url}>
                            {t("common.comparison")}
                          </Link>
                        </Button>
                      )}
                      {row.evidence_url && (
                        <Button asChild size="sm" variant="outline">
                          <Link href={row.evidence_url}>
                            {t("common.evidence")}
                          </Link>
                        </Button>
                      )}
                      {row.source_url && (
                        <Button asChild size="sm" variant="ghost">
                          <a
                            href={row.source_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {t("common.officialSource")}{" "}
                            <ArrowUpRight size={13} />
                          </a>
                        </Button>
                      )}
                      {canManage && row.event_id && (
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={busy === row.event_id}
                          onClick={() => markRead(row)}
                        >
                          <Eye size={14} />{" "}
                          {t("registry.markRead", {
                            state: t(`status.${row.read ? "unread" : "read"}`),
                          })}
                        </Button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
        {resource.data?.next_cursor && (
          <div className="flex justify-end mt-5">
            <Button
              variant="outline"
              onClick={() =>
                update({ cursor: resource.data?.next_cursor || "" }, false)
              }
            >
              {t("registry.next")} <ArrowRight size={15} />
            </Button>
          </div>
        )}
      </div>
    </Shell>
  );
}
