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

function officialDates(row: RegistryRow) {
  const order = ["published_at", "version_date", "decision_date", "effective_from", "effective_to"];
  const dates = order.flatMap((kind) =>
    (row.official_dates[kind] || []).map((item) => ({ kind, ...item })),
  );
  if (!dates.length) return <span className="muted">Official dates: unknown</span>;
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
    <Shell section="Registry" wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">SAVED REGULATORY ACTIVITY</span>
          <h1>Know what happened, and when.</h1>
          <p className="muted m-0">
            Detection time and official legal dates stay separate. This page renders saved evidence without waiting for AI or a source.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-5" role="tablist" aria-label="Registry view">
        <Button type="button" variant={view === "monitored" ? "default" : "outline"} onClick={() => update({ view: "monitored" })}>
          <BookOpen size={16} /> My monitored documents
        </Button>
        <Button type="button" variant={view === "events" ? "default" : "outline"} onClick={() => update({ view: "events" })}>
          <Clock3 size={16} /> All discovered events
        </Button>
      </div>

      <section className="card p-5 mb-5">
        <form className="flex gap-2 mb-4" onSubmit={search}>
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-3 muted" />
            <Input className="pl-9" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title, authority, event, or language…" />
          </div>
          <Button type="submit" variant="outline">Search</Button>
          <Button type="button" variant="ghost" onClick={() => { setQuery(""); router.push(pathname + `?view=${view}`); }}>Clear</Button>
        </form>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {FILTERS.map(([key, title, values]) => (
            <label className="text-xs muted" key={key}>
              {title}
              <select className="input mt-1 w-full" value={params.get(key) || ""} onChange={(event) => update({ [key]: event.target.value })}>
                {values.map(([value, text]) => <option value={value} key={value}>{text}</option>)}
              </select>
            </label>
          ))}
          <label className="text-xs muted">Custom range from<Input type="date" className="mt-1" value={params.get("start") || ""} onChange={(event) => update({ start: event.target.value })} /></label>
          <label className="text-xs muted">Custom range to<Input type="date" className="mt-1" value={params.get("end") || ""} onChange={(event) => update({ end: event.target.value })} /></label>
        </div>
      </section>

      <ErrorNote message={actionError || resource.error} />
      {resource.loading && !resource.data && <Loading text="Reading the saved registry…" />}
      {!resource.loading && resource.data?.count === 0 && (
        <section className="empty-state card">
          <FileSearch size={28} />
          <h2>No saved records match these filters.</h2>
          <p className="muted">Adjust the date or metadata filters. A source failure never becomes a false legal event.</p>
        </section>
      )}
      <div className="space-y-6">
        {resource.data?.groups.map((group) => (
          <section key={group.name}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xl m-0">{group.name}</h2>
              <span className="muted text-sm">{group.items.length} on this page</span>
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
                        {row.read && <span className="status-badge status-green"><CheckCircle2 size={12} /> read</span>}
                      </div>
                      <h3 className="text-lg m-0 mb-1">{row.title}</h3>
                      <p className="muted m-0 text-sm">{row.authority} · {label(row.kind)} · {row.languages.join(", ")} · {label(row.lifecycle)}</p>
                      {row.kind === "official_notice" && (
                        <p className="muted m-0 mt-2 text-xs">
                          Context from the publishing authority. This is not a statute, enacted amendment, or court holding.
                        </p>
                      )}
                    </div>
                    <div className="text-right text-sm shrink-0">
                      <strong>Detected {dateTime(row.detected_at)}</strong>
                      <div className="muted">{row.connector} · {label(row.connector_health)}</div>
                    </div>
                  </div>
                  <p className="my-3">{row.why}</p>
                  <div className="text-sm mb-3">{officialDates(row)}</div>
                  <div className="text-sm muted mb-4">
                    {row.linked_laws.length ? <>Linked monitored laws: {row.linked_laws.map((item) => item.name).join(", ")}</> : "No monitored law is linked yet."}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {row.timeline_url && <Button asChild size="sm"><Link href={row.timeline_url}>Timeline <ArrowRight size={14} /></Link></Button>}
                    {row.comparison_url && <Button asChild size="sm" variant="outline"><Link href={row.comparison_url}>Comparison</Link></Button>}
                    {row.evidence_url && <Button asChild size="sm" variant="outline"><Link href={row.evidence_url}>Evidence</Link></Button>}
                    {row.source_url && <Button asChild size="sm" variant="ghost"><a href={row.source_url} target="_blank" rel="noreferrer">Official source <ArrowUpRight size={13} /></a></Button>}
                    {canManage && row.event_id && <Button size="sm" variant="ghost" disabled={busy === row.event_id} onClick={() => markRead(row)}><Eye size={14} /> Mark {row.read ? "unread" : "read"}</Button>}
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
      {resource.data?.next_cursor && (
        <div className="flex justify-end mt-5">
          <Button variant="outline" onClick={() => update({ cursor: resource.data?.next_cursor || "" }, false)}>Next page <ArrowRight size={15} /></Button>
        </div>
      )}
    </Shell>
  );
}
