"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
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
  dateTime,
  errorText,
  host,
  label,
  refreshWorkspace,
  useResource,
} from "@/lib/api";
import type { Candidate, Discovery, Law, Scan, Source } from "@/lib/types";
import { ErrorNote, Loading, Status } from "./common";
import { AddDocumentDialog } from "./document-forms";
import { ScanPanel } from "./scan-panel";
import { Shell } from "./shell";

type DocumentForm = {
  mode: "law" | "source";
  url?: string;
  name?: string;
  sourceId?: string;
  source?: Source;
  provider?: string;
};

export function Workspace({
  view = "overview",
}: {
  view?: "overview" | "sources" | "activity";
}) {
  const router = useRouter();
  const laws = useResource<Law[]>("/laws", 5000);
  const sources = useResource<Source[]>("/sources", 8000);
  const scans = useResource<Scan[]>("/scans", 2000);
  const [form, setForm] = useState<DocumentForm | null>(null);
  const [query, setQuery] = useState(""),
    [sourceFilter, setSourceFilter] = useState(""),
    [resultFilter, setResultFilter] = useState("");
  const [selected, setSelected] = useState<string[]>([]),
    [busy, setBusy] = useState(""),
    [error, setError] = useState("");
  const [discoverySource, setDiscoverySource] = useState<Source | null>(null);
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
      await api<Scan>("/scans", {
        method: "POST",
        body: JSON.stringify({ law_ids: ids || null }),
      });
      refreshWorkspace();
      setSelected([]);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  const title =
    view === "sources"
      ? "Start with trusted sources."
      : view === "activity"
        ? "Every check, accounted for."
        : "Keep up with what changes.";
  return (
    <Shell
      section={
        view === "overview"
          ? "Overview"
          : view === "sources"
            ? "Sources"
            : "Scan activity"
      }
    >
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            {view === "overview"
              ? "REGULATORY INTELLIGENCE"
              : view === "sources"
                ? "YOUR CONNECTIONS"
                : "MONITORING HISTORY"}
          </span>
          <h1>{title}</h1>
          <p className="muted m-0">
            {view === "overview"
              ? "Know what changed. Know what it means. Know what to do."
              : view === "sources"
                ? "Connect a website, discover documents, and choose what matters."
                : "Real processing stages, saved comparisons, and clear outcomes."}
          </p>
        </div>
        <div className="heading-actions">
          <Button variant="outline" onClick={() => setForm({ mode: "source" })}>
            <Globe2 />
            Connect website
          </Button>
          <Button onClick={() => setForm({ mode: "law" })}>
            <Plus />
            Add a law
          </Button>
        </div>
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
              title="MONITORED DOCUMENTS"
              note={records.filter((law) => !law.active).length + " paused"}
              icon={<BookOpen size={17} />}
            />
            <Stat
              value={sources.data ? connected.length : null}
              title="CONNECTED WEBSITES"
              note="Sources you selected"
              icon={<Globe2 size={17} />}
            />
            <Stat
              value={
                laws.data
                  ? records.filter((law) => law.last_result === "changed")
                      .length
                  : null
              }
              title="LATEST LIVE CHANGES"
              note="Excludes historical comparisons"
              warm
              icon={<RefreshCw size={17} />}
            />
            <Stat
              value={
                laws.data
                  ? records.filter((law) => law.last_result === "failed").length
                  : null
              }
              title="NEED ATTENTION"
              note="Failed document checks"
              icon={<History size={17} />}
            />
          </div>
          {running && <ScanPanel scan={running} compact />}
          <section className="panel">
            <div className="panel-header">
              <div className="flex items-center gap-3">
                <h2>Your watchlist</h2>
                <span className="count-pill">{records.length}</span>
              </div>
              <div className="flex items-center gap-2">
                {selectedActive.length > 0 && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => scan(selectedActive)}
                    disabled={!!busy || !!running}
                  >
                    Scan selected ({selectedActive.length})
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
                  Scan all active
                </Button>
              </div>
            </div>
            {laws.loading && !laws.data ? (
              <Loading />
            ) : records.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">
                  <BookOpen size={28} />
                </div>
                <h2>Your first source is the starting point.</h2>
                <p className="muted">
                  Add a current law or public document. Then import an earlier
                  copy and see exactly what changed, without waiting for the
                  website to update.
                </p>
                <Button onClick={() => setForm({ mode: "law" })}>
                  <Plus />
                  Add your first document
                </Button>
                <button
                  className="text-link block mx-auto mt-4"
                  onClick={() => setForm({ mode: "source" })}
                >
                  Or connect a regulatory website <ArrowRight size={14} />
                </button>
              </div>
            ) : (
              <>
                <div className="filter-bar">
                  <label className="search-field">
                    <Search size={15} />
                    <Input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Search documents…"
                      aria-label="Search documents"
                    />
                  </label>
                  <select
                    aria-label="Filter by source"
                    value={sourceFilter}
                    onChange={(event) => setSourceFilter(event.target.value)}
                  >
                    <option value="">All sources</option>
                    {connected.map((source) => (
                      <option key={source.id} value={source.id}>
                        {source.name}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Filter by result"
                    value={resultFilter}
                    onChange={(event) => setResultFilter(event.target.value)}
                  >
                    <option value="">All results</option>
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
                        <th className="checkbox-cell">
                          <input
                            type="checkbox"
                            aria-label="Select all visible active documents"
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
                        </th>
                        <th>DOCUMENT</th>
                        <th>LAST LIVE CHECK</th>
                        <th>APERTUS IMPACT</th>
                        <th>LAST CHECKED</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((law) => (
                        <tr key={law.id}>
                          <td className="checkbox-cell">
                            <input
                              type="checkbox"
                              disabled={!law.active}
                              checked={selected.includes(law.id)}
                              aria-label={"Select " + law.name}
                              onChange={() => toggle(law.id)}
                            />
                          </td>
                          <td>
                            <Link
                              className="document-title"
                              href={"/laws/" + law.id}
                            >
                              {law.name}
                            </Link>
                            <div className="document-meta">
                              <span>{host(law.url)}</span>
                              {!law.active && <span>Paused</span>}
                              {law.current_version?.synthetic && (
                                <span className="synthetic-label">
                                  Synthetic
                                </span>
                              )}
                            </div>
                          </td>
                          <td>
                            <Status value={law.last_result} />
                            {law.comparison_mode === "historical" && (
                              <div className="text-xs muted mt-1">
                                Historical comparison available
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
                                  ? "Profile changed · rerun"
                                  : law.analysis
                                    ? label(law.analysis.status)
                                    : "Not analysed"}
                              </span>
                            )}
                          </td>
                          <td className="text-xs muted whitespace-nowrap">
                            {dateTime(law.last_checked)}
                          </td>
                          <td>
                            <Link
                              className="row-open"
                              aria-label={"Open " + law.name}
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
                      No documents match these filters.
                    </p>
                  )}
                </div>
                <div className="panel-footnote">
                  {filtered.length} of {records.length} documents · Imported
                  history never replaces the live baseline.
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
            <span className="eyebrow">HOW IT WORKS</span>
            <span>Connect a source</span>
            <ArrowRight size={13} />
            <span>Save a baseline</span>
            <ArrowRight size={13} />
            <span>Scan & compare</span>
            <ArrowRight size={13} />
            <span>Review the evidence</span>
          </div>
        </>
      )}
      {view === "sources" && (
        <>
          <div className="info-note mb-6">
            Discovery reads one listing page and inspects up to 50 direct
            documents within your selected website section. Review real
            extraction previews and individual errors before choosing what to
            monitor. Discovery does not imply a legal amendment.
          </div>
          {sources.loading && !sources.data ? (
            <Loading />
          ) : connected.length === 0 ? (
            <section className="panel">
              <div className="empty-state">
                <div className="empty-icon">
                  <Globe2 size={28} />
                </div>
                <h2>Choose the websites you rely on.</h2>
                <p className="muted">
                  Connect a regulator’s document listing or a public legal
                  portal. You stay in control of which documents enter the
                  watchlist.
                </p>
                <Button onClick={() => setForm({ mode: "source" })}>
                  <Plus />
                  Connect your first website
                </Button>
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
                      <dt>Section</dt>
                      <dd>{source.section}</dd>
                    </div>
                    <div>
                      <dt>Provider</dt>
                      <dd>{source.provider}</dd>
                    </div>
                    <div>
                      <dt>Tracked documents</dt>
                      <dd>
                        {
                          records.filter((law) => law.source_id === source.id)
                            .length
                        }
                      </dd>
                    </div>
                    <div>
                      <dt>Last connection check</dt>
                      <dd>{dateTime(source.last_checked)}</dd>
                    </div>
                  </dl>
                  <ErrorNote message={source.error} />
                  <div className="source-actions">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setForm({ mode: "source", source })}
                    >
                      <Settings2 />
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => setDiscoverySource(source)}
                    >
                      <Search />
                      Discover documents
                    </Button>
                  </div>
                </section>
              ))}
            </div>
          )}
        </>
      )}
      {view === "activity" && (
        <div className="activity-list">
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
                <h2>No scans yet.</h2>
                <p className="muted">
                  After adding a document, choose Scan now. Every real check and
                  its outcome will appear here.
                </p>
                <Button asChild variant="outline">
                  <Link href="/">
                    Open watchlist
                    <ArrowRight />
                  </Link>
                </Button>
              </div>
            </section>
          )}
        </div>
      )}
      {form && (
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
      {discoverySource && (
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
      setDiscovery(
        await api<Discovery>("/sources/" + source.id + "/discover", {
          method: "POST",
        }),
      );
      refreshWorkspace();
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
          <DialogTitle>Discover documents</DialogTitle>
          <DialogDescription>
            {source.name} · {source.section}. Inspect at most 50 linked
            documents, then choose which ones to monitor.
          </DialogDescription>
        </DialogHeader>
        <div className="flex gap-3">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter titles, URLs, or preview text…"
            aria-label="Filter discovered links"
          />
          <Button onClick={discover} disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : <Search />}
            {discovery.candidates ? "Search again" : "Search website"}
          </Button>
        </div>
        {busy && (
          <p role="status" className="text-sm muted">
            Fetching the listing and inspecting linked documents. Up to three
            requests run at once; results return within the two-minute
            inspection limit. No monitoring versions are created during
            discovery.
          </p>
        )}
        {source.provider === "firecrawl" && (
          <p className="text-xs muted">
            This source uses Firecrawl. A search can make one listing request
            and up to 50 document requests against your configured account.
          </p>
        )}
        <ErrorNote message={error} />
        {discovery.candidates ? (
          <>
            <div className="text-xs muted">
              {discovery.inspected_count ?? 0} inspected ·{" "}
              {discovery.verified_count ?? 0} verified ·{" "}
              {discovery.error_count ?? 0} failed ·{" "}
              {discovery.uninspected_count ?? discovery.returned_count} not
              inspected. {discovery.returned_count} of{" "}
              {discovery.candidate_count} links selected · limit{" "}
              {discovery.limit}
              {discovery.limit_reached ? " reached" : ""}.
              {discovery.time_limit_reached
                ? " Inspection time limit reached."
                : ""}{" "}
              {discovery.note}
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
                          ? candidate.content_type + " · extraction verified"
                          : candidate.format_hint +
                            " hint · extraction not verified"}
                      </span>
                      {candidate.error && (
                        <p className="text-sm text-red-700">
                          {candidate.error}
                        </p>
                      )}
                      {candidate.preview && (
                        <details className="mt-2 text-sm">
                          <summary className="cursor-pointer">
                            Extracted preview ·{" "}
                            {candidate.preview.characters.toLocaleString()}{" "}
                            characters
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
                          Tracked · Open
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
                        {candidate.error ? "Retry preview" : "Preview & add"}
                      </Button>
                    )}
                  </div>
                );
              })}
              {candidates.length === 0 && (
                <p className="text-center muted py-6">
                  No matching direct links. Try a different listing URL or
                  section.
                </p>
              )}
            </div>
          </>
        ) : (
          <div className="py-8 text-center muted">
            Start a bounded discovery request. Only direct links from this
            listing are inspected; links found inside those documents are not
            followed. Search and previews do not add laws automatically.
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
