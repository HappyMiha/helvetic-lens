"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
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
  ["authority", "Authority", [["", "All authorities"], ["fedlex", "Fedlex"], ["parliament", "Parliament"], ["federal_supreme_court", "Federal Supreme Court"], ["native", "Direct URL"]]],
  ["connector", "Connector", [["", "All connectors"], ["fedlex", "Fedlex"], ["parliament", "Parliament"], ["federal_supreme_court", "Federal Supreme Court"], ["test-feed", "Test feed"]]],
  ["kind", "Document kind", [["", "All kinds"], ["act", "Act"], ["ordinance", "Ordinance"], ["parliamentary_business", "Parliamentary business"], ["initiative", "Initiative"], ["bill", "Bill"], ["court_decision", "Court decision"], ["official_notice", "Official notice"], ["unclassified_document", "Direct document"]]],
  ["language", "Language", [["", "All languages"], ["de", "German"], ["fr", "French"], ["it", "Italian"], ["rm", "Romansh"], ["en", "English"], ["und", "Not stated"]]],
  ["lifecycle", "Lifecycle", [["", "All lifecycle states"], ["in_force", "In force"], ["planned", "Planned"], ["repealed", "Repealed"], ["unknown", "Unknown"]]],
  ["impact", "Impact", [["", "All impacts"], ["high", "High"], ["medium", "Medium"], ["low", "Low"], ["none", "None"], ["unknown", "Unknown"]]],
  ["watched", "Monitoring", [["", "Watched and unwatched"], ["watched", "Watched"], ["unwatched", "Unwatched"]]],
  ["read", "Read state", [["", "Read and unread"], ["unread", "Unread"], ["read", "Read"]]],
  ["health", "Connector health", [["", "Any connector health"], ["healthy", "Healthy"], ["degraded", "Degraded"], ["error", "Error"], ["unknown", "Unknown"]]],
] as const;
const ALL_FILTER_KEYS: Record<string, string> = {
  authority: "filter.allAuthorities", connector: "filter.allConnectors", kind: "filter.allKinds",
  language: "filter.allLanguages", lifecycle: "filter.allLifecycle", impact: "filter.allImpacts",
  watched: "filter.allMonitoring", read: "filter.allRead", health: "filter.allHealth",
};

function officialDates(row: RegistryRow, t: (key: string, values?: Record<string, string | number>) => string) {
  const order = ["published_at", "version_date", "decision_date", "effective_from", "effective_to"];
  const dates = order.flatMap((kind) =>
    (row.official_dates[kind] || []).map((item) => ({ kind, ...item })),
  );
  if (!dates.length) return <span className="muted">{t("registry.officialDatesUnknown")}</span>;
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

export function RegistryPage() {
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const { canManage } = useAuth();
  const { t } = useI18n();
  const view = params.get("view") === "events" ? "events" : "monitored";
  const [query, setQuery] = useState(params.get("q") || "");
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");
  const endpoint = "/registry?" + new URLSearchParams(params.toString()).toString();
  const resource = useResource<RegistryResponse>(endpoint, 15000);

  useEffect(() => setQuery(params.get("q") || ""), [params]);

  function update(values: Record<string, string>, resetCursor = true) {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(values)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (resetCursor) next.delete("cursor");
    router.push(pathname + "?" + next.toString());
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
    <Shell section={t("nav.registry")} wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("registry.eyebrow")}</span>
          <h1>{t("registry.title")}</h1>
          <p className="muted m-0">
            {t("registry.body")}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-5" role="tablist" aria-label={t("registry.views")}>
        <Button type="button" variant={view === "monitored" ? "default" : "outline"} onClick={() => update({ view: "monitored" })}>
          <BookOpen size={16} /> {t("registry.monitored")}
        </Button>
        <Button type="button" variant={view === "events" ? "default" : "outline"} onClick={() => update({ view: "events" })}>
          <Clock3 size={16} /> {t("registry.events")}
        </Button>
      </div>

      <section className="card p-5 mb-5">
        <form className="flex gap-2 mb-4" onSubmit={search}>
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-3 muted" />
            <Input className="pl-9" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("registry.searchPlaceholder")} />
          </div>
          <Button type="submit" variant="outline">{t("common.search")}</Button>
          <Button type="button" variant="ghost" onClick={() => { setQuery(""); router.push(pathname + `?view=${view}`); }}>{t("common.clear")}</Button>
        </form>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {FILTERS.map(([key, title, values]) => (
            <label className="text-xs muted" key={key}>
              {key === "authority" ? t("filter.authority") : key === "connector" ? t("filter.connector") : key === "kind" ? t("filter.kind") : key === "language" ? t("filter.language") : key === "lifecycle" ? t("filter.lifecycle") : key === "impact" ? t("filter.impact") : key === "watched" ? t("filter.monitoring") : key === "read" ? t("filter.readState") : key === "health" ? t("filter.health") : title}
              <select className="input mt-1 w-full" value={params.get(key) || ""} onChange={(event) => update({ [key]: event.target.value })}>
                {values.map(([value, text]) => <option value={value} key={value}>{value ? text : t(ALL_FILTER_KEYS[key] || "common.clear")}</option>)}
              </select>
            </label>
          ))}
          <label className="text-xs muted">{t("registry.from")}<Input type="date" className="mt-1" value={params.get("start") || ""} onChange={(event) => update({ start: event.target.value })} /></label>
          <label className="text-xs muted">{t("registry.to")}<Input type="date" className="mt-1" value={params.get("end") || ""} onChange={(event) => update({ end: event.target.value })} /></label>
        </div>
      </section>

      <ErrorNote message={actionError || resource.error} />
      {resource.loading && !resource.data && <Loading text={t("registry.loading")} />}
      {!resource.loading && resource.data?.count === 0 && (
        <section className="empty-state card">
          <FileSearch size={28} />
          <h2>{t("registry.empty")}</h2>
          <p className="muted">{t("registry.emptyBody")}</p>
        </section>
      )}
      <div className="space-y-6">
        {resource.data?.groups.map((group) => (
          <section key={group.name}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xl m-0">{group.name}</h2>
              <span className="muted text-sm">{t("registry.onPage", { count: group.items.length })}</span>
            </div>
            <div className="space-y-3">
              {group.items.map((row) => (
                <article className="card p-5" key={row.id}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap gap-2 mb-2">
                        <Status value={row.event_type} />
                        <Status value={row.impact} />
                        <Status value={row.analysis_state} />
                        {row.read && <span className="status-badge status-green"><CheckCircle2 size={12} /> {t("status.read")}</span>}
                      </div>
                      <h3 className="text-lg m-0 mb-1">{row.title}</h3>
                      <p className="muted m-0 text-sm">{row.authority} · {label(row.kind)} · {row.languages.join(", ")} · {label(row.lifecycle)}</p>
                      {row.kind === "official_notice" && (
                        <p className="muted m-0 mt-2 text-xs">
                          {t("registry.officialNotice")}
                        </p>
                      )}
                    </div>
                    <div className="text-right text-sm shrink-0">
                      <strong>{t("registry.detected", { date: dateTime(row.detected_at) })}</strong>
                      <div className="muted">{row.connector} · {label(row.connector_health)}</div>
                    </div>
                  </div>
                  <p className="my-3">{row.why}</p>
                  <div className="text-sm mb-3">{officialDates(row, t)}</div>
                  <div className="text-sm muted mb-4">
                    {row.linked_laws.length ? t("registry.linked", { laws: row.linked_laws.map((item) => item.name).join(", ") }) : t("registry.notLinked")}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {row.timeline_url && <Button asChild size="sm"><Link href={row.timeline_url}>{t("common.timeline")} <ArrowRight size={14} /></Link></Button>}
                    {row.comparison_url && <Button asChild size="sm" variant="outline"><Link href={row.comparison_url}>{t("common.comparison")}</Link></Button>}
                    {row.evidence_url && <Button asChild size="sm" variant="outline"><Link href={row.evidence_url}>{t("common.evidence")}</Link></Button>}
                    {row.source_url && <Button asChild size="sm" variant="ghost"><a href={row.source_url} target="_blank" rel="noreferrer">{t("common.officialSource")} <ArrowUpRight size={13} /></a></Button>}
                    {canManage && row.event_id && <Button size="sm" variant="ghost" disabled={busy === row.event_id} onClick={() => markRead(row)}><Eye size={14} /> {t("registry.markRead", { state: t(`status.${row.read ? "unread" : "read"}`) })}</Button>}
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
      {resource.data?.next_cursor && (
        <div className="flex justify-end mt-5">
          <Button variant="outline" onClick={() => update({ cursor: resource.data?.next_cursor || "" }, false)}>{t("registry.next")} <ArrowRight size={15} /></Button>
        </div>
      )}
    </Shell>
  );
}
