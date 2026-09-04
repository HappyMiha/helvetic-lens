"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  Globe2,
  History,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  api,
  errorText,
  host,
  invalidateResources,
  label,
  mutateResource,
  resourceTag,
  useResource,
} from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import type {
  Candidate,
  Discovery,
  Job,
  Law,
  Scan,
  Source,
  SourceCapabilityCatalogue,
} from "@/lib/types";
import { ErrorNote, Loading, Status } from "./common";
import { ConfirmDeleteDialog } from "./confirm-delete-dialog";
import { AddDocumentDialog } from "./document-forms";
import { DurableJobsPanel } from "./durable-jobs-panel";
import { ScanPanel } from "./scan-panel";
import { Shell } from "./shell";
import { useAuth } from "./auth-gate";
import { useI18n } from "@/lib/i18n";

type DocumentForm = {
  mode: "law" | "source";
  url?: string;
  name?: string;
  sourceId?: string;
  source?: Source;
  provider?: string;
};

function OfficialCoverage({ data }: { data?: SourceCapabilityCatalogue | null }) {
  const { t, locale } = useI18n();
  if (!data) return null;
  const groups = new Map<string, SourceCapabilityCatalogue["items"]>();
  for (const item of data.items) {
    groups.set(item.connector, [...(groups.get(item.connector) || []), item]);
  }
  return (
    <section className="official-coverage panel mb-6">
      <div className="panel-header">
        <div>
          <span className="eyebrow">{t("sources.officialCoverageEyebrow")}</span>
          <h2>{t("sources.officialCoverageTitle")}</h2>
        </div>
        <span className="status-badge status-neutral">{data.catalogue_revision}</span>
      </div>
      <div className="panel-body grid gap-3 md:grid-cols-2">
        {[...groups.entries()].map(([connector, items]) => {
          const copy = items[0].localized_copy[locale] || items[0].localized_copy["en-CH"];
          const fullyVerified = items.filter((item) => item.catalogue_state === "available").length;
          return (
            <article className="official-coverage-card rounded-lg border p-4" key={connector}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="m-0">{label(connector)}</h3>
                  <p className="mt-2 mb-1 text-sm">{copy.summary}</p>
                </div>
                <Status value={fullyVerified === items.length ? "available" : "partial"} />
              </div>
              <p className="muted mb-3 text-xs">{copy.boundary}</p>
              <p className="mb-0 text-xs">
                {t("sources.coverageStreams", { count: items.length })} · {t("sources.coverageVerified", { verified: fullyVerified, total: items.length })}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function Workspace({
  view = "overview",
}: {
  view?: "overview" | "sources" | "activity";
}) {
  const router = useRouter();
  const { canManage } = useAuth();
  const { t, dateTime } = useI18n();
  const laws = useResource(resources.laws());
  const sources = useResource(resources.sources());
  const capabilities = useResource(
    view === "sources" ? resources.sourceCapabilities() : null,
  );
  const scans = useResource(resources.scans());
  const jobs = useResource(resources.jobs());
  const [form, setForm] = useState<DocumentForm | null>(null);
  const [query, setQuery] = useState(""),
    [sourceFilter, setSourceFilter] = useState(""),
    [resultFilter, setResultFilter] = useState("");
  const [selected, setSelected] = useState<string[]>([]),
    [busy, setBusy] = useState(""),
    [error, setError] = useState("");
  const [discoverySource, setDiscoverySource] = useState<Source | null>(null);
  const [deletingSource, setDeletingSource] = useState<Source | null>(null);
  const records = laws.data || [],
    connected = sources.data || [];
  const running = scans.data?.find((scan) =>
    ["queued", "running"].includes(scan.status),
  );
  const filtered = records.filter(
    (law) =>
      (law.name + " " + law.url).toLowerCase().includes(query.toLowerCase()) &&
      (!sourceFilter || law.source_id === sourceFilter) &&
      (!resultFilter ||
        (resultFilter === "paused"
          ? !law.active
          : law.last_result === resultFilter)),
  );
  const eligible = filtered.filter((law) => law.active);
  const selectedActive = selected.filter((id) =>
    records.some((law) => law.id === id && law.active),
  );
  function toggle(id: string) {
    setSelected((values) =>
      values.includes(id)
        ? values.filter((value) => value !== id)
        : [...values, id],
    );
  }
  async function scan(ids?: string[]) {
    setBusy("scan");
    setError("");
    try {
      const createdScan = await api<Scan>("/scans", {
        method: "POST",
        body: JSON.stringify({ law_ids: ids || null }),
      });
      const updatedScans = mutateResource<Scan[]>(resources.scans(), (current) =>
        current
          ? [createdScan, ...current.filter((item) => item.id !== createdScan.id)]
          : current,
      );
      if (updatedScans === null) void invalidateResources(resources.scans());
      const createdJob = createdScan.job;
      if (createdJob) {
        const updatedJobs = mutateResource<Job[]>(resources.jobs(), (current) =>
          current
            ? [createdJob, ...current.filter((item) => item.id !== createdJob.id)]
            : current,
        );
        if (updatedJobs === null) void invalidateResources(resources.jobs());
      }
      setSelected([]);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  async function removeSource() {
    if (!deletingSource) return;
    setBusy("delete-source");
    setError("");
    try {
      await api("/sources/" + deletingSource.id, { method: "DELETE" });
      const deletedSourceId = deletingSource.id;
      const updatedSources = mutateResource<Source[]>(resources.sources(), (current) =>
        current?.filter((source) => source.id !== deletedSourceId) ?? current,
      );
      const updatedLaws = mutateResource<Law[]>(resources.laws(), (current) =>
        current?.map((law) =>
          law.source_id === deletedSourceId ? { ...law, source_id: null } : law,
        ) ?? current,
      );
      void invalidateResources(
        ...(updatedSources === null ? [resources.sources()] : []),
        ...(updatedLaws === null ? [resources.laws()] : []),
        resourceTag("law", "organization"),
        resources.organizationStatus(),
      );
      setDeletingSource(null);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  const title =
    view === "sources"
      ? t("monitor.sourcesTitle")
      : view === "activity"
        ? t("monitor.activityTitle")
        : t("monitor.overviewTitle");
  return (
    <Shell
      section={
        view === "overview"
          ? t("nav.overview")
          : view === "sources"
            ? t("nav.sources")
            : t("nav.activity")
      }
    >
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            {view === "overview"
              ? t("monitor.overviewEyebrow")
              : view === "sources"
                ? t("monitor.sourcesEyebrow")
                : t("monitor.activityEyebrow")}
          </span>
          <h1>{title}</h1>
          <p className="muted m-0">
            {view === "overview"
              ? t("monitor.overviewBody")
              : view === "sources"
                ? t("monitor.sourcesBody")
                : t("monitor.activityBody")}
          </p>
        </div>
        {canManage && <div className="heading-actions">
          <Button variant="outline" onClick={() => setForm({ mode: "source" })}>
            <Globe2 />
            {t("monitor.connectWebsite")}
          </Button>
          <Button onClick={() => setForm({ mode: "law" })}>
            <Plus />
            {t("monitor.addLaw")}
          </Button>
        </div>}
      </div>
      <ErrorNote
        message={error || laws.error || sources.error || scans.error}
      />
      {view === "overview" && (
        <>
          <div className="stats-grid">
            <Stat
              value={
                laws.data ? records.filter((law) => law.active).length : null
              }
              title={t("monitor.monitored")}
              note={t("monitor.pausedCount", { count: records.filter((law) => !law.active).length })}
              icon={<BookOpen size={17} />}
            />
            <Stat
              value={sources.data ? connected.length : null}
              title={t("monitor.connected")}
              note={t("monitor.selectedSources")}
              icon={<Globe2 size={17} />}
            />
            <Stat
              value={
                laws.data
                  ? records.filter((law) => law.last_result === "changed")
                      .length
                  : null
              }
              title={t("monitor.liveChanges")}
              note={t("monitor.excludesHistory")}
              warm
              icon={<RefreshCw size={17} />}
            />
            <Stat
              value={
                laws.data
                  ? records.filter((law) => law.last_result === "failed").length
                  : null
              }
              title={t("monitor.attention")}
              note={t("monitor.failedChecks")}
              icon={<AlertCircle size={17} />}
            />
          </div>
          {running && <ScanPanel scan={running} compact />}
          <section className="panel">
            <div className="panel-header">
              <div className="flex items-center gap-3">
                <h2>{t("monitor.watchlist")}</h2>
                <span className="count-pill">{records.length}</span>
              </div>
              {canManage && <div className="flex items-center gap-2">
                {selectedActive.length > 0 && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => scan(selectedActive)}
                    disabled={!!busy || !!running}
                  >
                    {t("monitor.scanSelected", { count: selectedActive.length })}
                  </Button>
                )}
                <Button
                  size="sm"
                  onClick={() => scan()}
                  disabled={
                    !!busy || !!running || !records.some((law) => law.active)
                  }
                >
                  {busy === "scan" || running ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    <RefreshCw />
                  )}
                  {t("monitor.scanAll")}
                </Button>
              </div>}
            </div>
            {laws.loading && !laws.data ? (
              <Loading />
            ) : records.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">
                  <BookOpen size={28} />
                </div>
                <h2>{t("monitor.emptyTitle")}</h2>
                <p className="muted">
                  {t("monitor.emptyBody")}
                </p>
                {canManage && <><Button onClick={() => setForm({ mode: "law" })}>
                  <Plus />
                  {t("monitor.addFirst")}
                </Button>
                <button
                  className="text-link block mx-auto mt-4"
                  onClick={() => setForm({ mode: "source" })}
                >
                  {t("monitor.orConnect")} <ArrowRight size={14} />
                </button></>}
              </div>
            ) : (
              <>
                <div className="filter-bar">
                  <label className="search-field">
                    <Search size={15} />
                    <Input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder={t("monitor.search")}
                      aria-label={t("monitor.search")}
                    />
                  </label>
                  <select
                    aria-label={t("monitor.filterSource")}
                    value={sourceFilter}
                    onChange={(event) => setSourceFilter(event.target.value)}
                  >
                    <option value="">{t("monitor.allSources")}</option>
                    {connected.map((source) => (
                      <option key={source.id} value={source.id}>
                        {source.name}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label={t("monitor.filterResult")}
                    value={resultFilter}
                    onChange={(event) => setResultFilter(event.target.value)}
                  >
                    <option value="">{t("monitor.allResults")}</option>
                    {[
                      "changed",
                      "unchanged",
                      "baseline_created",
                      "failed",
                      "paused",
                    ].map((value) => (
                      <option key={value} value={value}>
                        {label(value)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="table-scroll">
                  <table className="watch-table">
                    <thead>
                      <tr>
                        {canManage && <th className="checkbox-cell">
                          <input
                            type="checkbox"
                            aria-label={t("monitor.selectAll")}
                            checked={
                              eligible.length > 0 &&
                              eligible.every((law) => selected.includes(law.id))
                            }
                            onChange={(event) =>
                              setSelected(
                                event.target.checked
                                  ? [
                                      ...new Set([
                                        ...selected,
                                        ...eligible.map((law) => law.id),
                                      ]),
                                    ]
                                  : selected.filter(
                                      (id) =>
                                        !eligible.some((law) => law.id === id),
                                    ),
                              )
                            }
                          />
                        </th>}
                        <th>{t("monitor.document")}</th>
                        <th>{t("monitor.lastCheck")}</th>
                        <th>{t("monitor.impact")}</th>
                        <th>{t("monitor.lastChecked")}</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((law) => (
                        <tr key={law.id}>
                          {canManage && <td className="checkbox-cell">
                            <input
                              type="checkbox"
                              disabled={!law.active}
                              checked={selected.includes(law.id)}
                              aria-label={t("monitor.select", { name: law.name })}
                              onChange={() => toggle(law.id)}
                            />
                          </td>}
                          <td>
                            <Link
                              className="document-title"
                              href={"/laws/" + law.id}
                            >
                              {law.name}
                            </Link>
                            <div className="document-meta">
                              <span>{host(law.url)}</span>
                              {!law.active && <span>{t("monitor.paused")}</span>}
                              {law.current_version?.synthetic && (
                                <span className="synthetic-label">
                                  {t("monitor.synthetic")}
                                </span>
                              )}
                            </div>
                          </td>
                          <td>
                            <Status value={law.last_result} />
                            {law.comparison_mode === "historical" && (
                              <div className="text-xs muted mt-1">
                                {t("monitor.historicalAvailable")}
                              </div>
                            )}
                            {law.last_error && (
                              <div className="text-xs text-destructive mt-1 max-w-64">
                                {law.last_error}
                              </div>
                            )}
                          </td>
                          <td>
                            {law.analysis?.status === "succeeded" &&
                            !law.analysis.stale &&
                            law.analysis.result ? (
                              <Status value={law.analysis.result.impact} />
                            ) : (
                              <span className="text-xs muted">
                                {law.analysis?.stale
                                  ? t("monitor.profileRerun")
                                  : law.analysis
                                    ? label(law.analysis.status)
                                    : t("monitor.notAnalysed")}
                              </span>
                            )}
                          </td>
                          <td className="text-xs muted whitespace-nowrap">
                            {dateTime(law.last_checked)}
                          </td>
                          <td>
                            <Link
                              className="row-open"
                              aria-label={t("monitor.open", { name: law.name })}
                              href={"/laws/" + law.id}
                            >
                              <ArrowUpRight size={17} />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filtered.length === 0 && (
                    <p className="text-center muted py-8">
                      {t("monitor.noMatch")}
                    </p>
                  )}
                </div>
                <div className="panel-footnote">
                  {t("monitor.resultCount", { shown: filtered.length, total: records.length })}
                </div>
              </>
            )}
          </section>
          {!running && scans.data?.[0] && (
            <div className="mt-6">
              <ScanPanel scan={scans.data[0]} compact />
            </div>
          )}
          <div className="workflow-note">
            <span className="eyebrow">{t("monitor.how")}</span>
            <span>{t("monitor.connect")}</span>
            <ArrowRight size={13} />
            <span>{t("monitor.baseline")}</span>
            <ArrowRight size={13} />
            <span>{t("monitor.compare")}</span>
            <ArrowRight size={13} />
            <span>{t("monitor.review")}</span>
          </div>
        </>
      )}
      {view === "sources" && (
        <>
          <div className="info-note mb-6">
            {t("sources.discoveryNote")}
          </div>
          <ErrorNote message={capabilities.error} />
          {capabilities.loading && !capabilities.data ? (
            <Loading text={t("sources.coverageLoading")} />
          ) : (
            <OfficialCoverage data={capabilities.data} />
          )}
          {sources.loading && !sources.data ? (
            <Loading />
          ) : connected.length === 0 ? (
            <section className="panel">
              <div className="empty-state">
                <div className="empty-icon">
                  <Globe2 size={28} />
                </div>
                <h2>{t("sources.emptyTitle")}</h2>
                <p className="muted">
                  {t("sources.emptyBody")}
                </p>
                {canManage && <Button onClick={() => setForm({ mode: "source" })}>
                  <Plus />
                  {t("sources.connectFirst")}
                </Button>}
              </div>
            </section>
          ) : (
            <div className="sources-grid">
              {connected.map((source) => (
                <section className="panel source-card" key={source.id}>
                  <div className="source-icon">
                    <Globe2 size={22} />
                  </div>
                  <h2>{source.name}</h2>
                  <a
                    className="source-url"
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {host(source.url)}
                    <ArrowUpRight size={13} />
                  </a>
                  <dl className="source-facts">
                    <div>
                      <dt>{t("sources.section")}</dt>
                      <dd>{source.section}</dd>
                    </div>
                    <div>
                      <dt>{t("sources.provider")}</dt>
                      <dd>{source.provider}</dd>
                    </div>
                    <div>
                      <dt>{t("sources.tracked")}</dt>
                      <dd>
                        {
                          records.filter((law) => law.source_id === source.id)
                            .length
                        }
                      </dd>
                    </div>
                    <div>
                      <dt>{t("sources.lastConnection")}</dt>
                      <dd>{dateTime(source.last_checked)}</dd>
                    </div>
                  </dl>
                  <ErrorNote message={source.error} />
                  {canManage && <div className="source-actions">
                    <div className="flex items-center gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setForm({ mode: "source", source })}
                      >
                        <Settings2 />
                        {t("sources.edit")}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="text-destructive"
                        aria-label={t("sources.remove") + " " + source.name}
                        title={t("sources.remove")}
                        onClick={() => {
                          setError("");
                          setDeletingSource(source);
                        }}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => setDiscoverySource(source)}
                    >
                      <Search />
                      {t("sources.discover")}
                    </Button>
                  </div>}
                </section>
              ))}
            </div>
          )}
        </>
      )}
      {view === "activity" && (
        <div className="activity-list">
          {jobs.data?.length ? <DurableJobsPanel jobs={jobs.data} /> : null}
          <ErrorNote message={jobs.error} />
          {scans.loading && !scans.data ? (
            <Loading />
          ) : scans.data?.length ? (
            scans.data.map((scan) => <ScanPanel key={scan.id} scan={scan} />)
          ) : (
            <section className="panel">
              <div className="empty-state">
                <div className="empty-icon">
                  <History size={28} />
                </div>
                <h2>{t("activity.emptyTitle")}</h2>
                <p className="muted">
                  {t("activity.emptyBody")}
                </p>
                <Button asChild variant="outline">
                  <Link href="/">
                    {t("activity.openWatchlist")}
                    <ArrowRight />
                  </Link>
                </Button>
              </div>
            </section>
          )}
        </div>
      )}
      {canManage && form && (
        <AddDocumentDialog
          open
          onOpenChange={(open) => {
            if (!open) setForm(null);
          }}
          mode={form.mode}
          source={form.source}
          sourceId={form.sourceId}
          provider={form.provider}
          initialUrl={form.url}
          initialName={form.name}
          onCreated={(record) => {
            if (form.mode === "law") router.push("/laws/" + record.id);
          }}
        />
      )}
      {canManage && discoverySource && (
        <DiscoveryDialog
          source={discoverySource}
          laws={records}
          onClose={() => setDiscoverySource(null)}
          onSelect={(candidate) => {
            setForm({
              mode: "law",
              url: candidate.url,
              name: candidate.title,
              sourceId: discoverySource.id,
              provider: discoverySource.provider,
            });
            setDiscoverySource(null);
          }}
        />
      )}
      {canManage && <ConfirmDeleteDialog
        open={!!deletingSource}
        onOpenChange={(open) => {
          if (!open) setDeletingSource(null);
        }}
        title={t("sources.removeTitle")}
        description={
          deletingSource
            ? t("sources.removeDescription", { name: deletingSource.name, count: records.filter((law) => law.source_id === deletingSource.id).length })
            : ""
        }
        confirmLabel={t("sources.remove")}
        busy={busy === "delete-source"}
        error={deletingSource ? error : ""}
        onConfirm={() => void removeSource()}
      />}
    </Shell>
  );
}

function Stat({
  value,
  title,
  note,
  icon,
  warm = false,
}: {
  value: number | null;
  title: string;
  note: string;
  icon: React.ReactNode;
  warm?: boolean;
}) {
  return (
    <div className={"stat-card " + (warm ? "stat-warm" : "")}>
      <div className="flex items-center justify-between">
        <span className="eyebrow">{title}</span>
        <span className="muted">{icon}</span>
      </div>
      <strong>{value === null ? "—" : value}</strong>
      <span className="text-xs muted">{note}</span>
    </div>
  );
}

function DiscoveryDialog({
  source,
  laws,
  onClose,
  onSelect,
}: {
  source: Source;
  laws: Law[];
  onClose: () => void;
  onSelect: (candidate: Candidate) => void;
}) {
  const { t, number } = useI18n();
  const [discovery, setDiscovery] = useState<Partial<Discovery>>(
    source.discovery,
  );
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [query, setQuery] = useState("");
  async function discover() {
    setBusy(true);
    setError("");
    try {
      const result = await api<Discovery>(
        "/sources/" + source.id + "/discover",
        {
          method: "POST",
        },
      );
      setDiscovery(result);
      void invalidateResources(resources.sources());
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }
  const candidates = (discovery.candidates || []).filter((candidate) =>
    (
      candidate.title +
      " " +
      candidate.url +
      " " +
      (candidate.preview?.excerpt || "")
    )
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("discover.title")}</DialogTitle>
          <DialogDescription>
            {t("discover.description", { name: source.name, section: source.section })}
          </DialogDescription>
        </DialogHeader>
        <div className="flex gap-3">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("discover.filter")}
            aria-label={t("discover.filterLabel")}
          />
          <Button onClick={discover} disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : <Search />}
            {discovery.candidates ? t("discover.again") : t("discover.website")}
          </Button>
        </div>
        {busy && (
          <p role="status" className="text-sm muted">
            {t("discover.loading")}
          </p>
        )}
        {source.provider === "firecrawl" && (
          <p className="text-xs muted">
            {t("discover.firecrawl")}
          </p>
        )}
        <ErrorNote message={error} />
        {discovery.candidates ? (
          <>
            <div className="text-xs muted">
              {t("discover.summary", {
                inspected: discovery.inspected_count ?? 0,
                verified: discovery.verified_count ?? 0,
                failed: discovery.error_count ?? 0,
                uninspected: discovery.uninspected_count ?? discovery.returned_count ?? 0,
                returned: discovery.returned_count ?? 0,
                candidates: discovery.candidate_count ?? 0,
                limit: discovery.limit ?? 0,
                reached: discovery.limit_reached ? t("discover.limitReached") : "",
              })}{" "}
              {discovery.time_limit_reached ? t("discover.timeReached") : ""}{" "}
              {discovery.note || ""}
            </div>
            <div className="candidate-list">
              {candidates.map((candidate) => {
                const tracked = laws.find((law) => law.url === candidate.url);
                return (
                  <div className="candidate" key={candidate.url}>
                    <div className="min-w-0">
                      <strong>{candidate.title}</strong>
                      <p>{candidate.url}</p>
                      <span className="text-xs muted">
                        {candidate.verified
                          ? t("discover.verified", { type: candidate.content_type || "document" })
                          : t("discover.unverified", { type: candidate.format_hint || "document" })}
                      </span>
                      {candidate.error && (
                        <p className="text-sm text-red-700">
                          {candidate.error}
                        </p>
                      )}
                      {candidate.preview && (
                        <details className="mt-2 text-sm">
                          <summary className="cursor-pointer">
                            {t("discover.preview", { count: number(candidate.preview.characters) })}
                          </summary>
                          <p className="whitespace-pre-wrap max-h-48 overflow-y-auto">
                            {candidate.preview.excerpt}
                          </p>
                        </details>
                      )}
                    </div>
                    {tracked ? (
                      <Button asChild variant="ghost" size="sm">
                        <Link href={"/laws/" + tracked.id} onClick={onClose}>
                          <Check />
                          {t("discover.tracked")}
                        </Link>
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => onSelect(candidate)}
                      >
                        <Plus />
                        {candidate.error ? t("discover.retryPreview") : t("discover.previewAdd")}
                      </Button>
                    )}
                  </div>
                );
              })}
              {candidates.length === 0 && (
                <p className="text-center muted py-6">
                  {t("discover.noMatch")}
                </p>
              )}
            </div>
          </>
        ) : (
          <div className="py-8 text-center muted">
            {t("discover.start")}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
