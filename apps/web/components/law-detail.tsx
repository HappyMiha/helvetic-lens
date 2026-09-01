"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  FileUp,
  GitCompareArrows,
  History,
  Loader2,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  api,
  dateOnly,
  dateTime,
  errorText,
  label,
  refreshWorkspace,
  useResource,
} from "@/lib/api";
import type {
  Comparison,
  LawDetail as Detail,
  Scan,
  Version,
} from "@/lib/types";
import { ErrorNote, Loading, Status, SuccessNote } from "./common";
import { ConfirmDeleteDialog } from "./confirm-delete-dialog";
import { ImportDialog } from "./document-forms";
import { ScanPanel } from "./scan-panel";
import { Shell } from "./shell";

export function versionLabel(version: Version) {
  return (
    (version.declared_date
      ? version.declared_date + " (stated)"
      : "Date unknown") +
    " · " +
    label(version.origin) +
    " · " +
    version.id.slice(0, 8) +
    (version.synthetic ? " · SYNTHETIC" : "")
  );
}

export function LawDetail({ id }: { id: string }) {
  const router = useRouter();
  const {
    data: law,
    error: loadError,
    loading,
  } = useResource<Detail>("/laws/" + id, 4000);
  const scans = useResource<Scan[]>("/scans", 2000);
  const [importOpen, setImportOpen] = useState(false),
    [baseline, setBaseline] = useState("");
  const [oldId, setOldId] = useState(""),
    [newId, setNewId] = useState("");
  const [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [note, setNote] = useState("");
  const [editing, setEditing] = useState(false),
    [name, setName] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const latestScan = scans.data?.find((scan) =>
    scan.items.some((item) => item.law_id === id),
  );
  const running =
    latestScan && ["queued", "running"].includes(latestScan.status);
  const selectedBaseline = law?.versions.find(
    (version) => version.id === baseline,
  );
  const savedOld =
    oldId ||
    law?.versions.find((version) => version.id !== law.current_version_id)
      ?.id ||
    law?.current_version_id ||
    "";
  const savedNew = newId || law?.current_version_id || "";

  async function update(payload: { active?: boolean; name?: string }) {
    setBusy("update");
    setError("");
    try {
      await api("/laws/" + id, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      refreshWorkspace();
      setEditing(false);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  async function scan() {
    setBusy("scan");
    setError("");
    setNote("");
    try {
      await api<Scan>("/scans", {
        method: "POST",
        body: JSON.stringify({
          law_ids: [id],
          baseline_version_id: baseline || null,
        }),
      });
      refreshWorkspace();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  async function compareSaved() {
    setBusy("compare");
    setError("");
    try {
      const comparison = await api<Comparison>("/comparisons", {
        method: "POST",
        body: JSON.stringify({
          old_version_id: savedOld,
          new_version_id: savedNew,
        }),
      });
      router.push("/compare/" + comparison.id);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  async function removeDocument() {
    setBusy("delete");
    setError("");
    try {
      await api("/laws/" + id, { method: "DELETE" });
      setDeleteOpen(false);
      refreshWorkspace();
      router.push("/");
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  return (
    <Shell section="Document & versions">
      <Link href="/" className="back-link">
        <ArrowLeft size={14} />
        Back to watchlist
      </Link>
      <ErrorNote message={loadError || error} />
      {loading && !law ? (
        <Loading />
      ) : (
        law && (
          <>
            <div className="page-heading">
              <div className="min-w-0">
                <span className="eyebrow">MONITORED DOCUMENT</span>
                {editing ? (
                  <form
                    className="flex items-center gap-2 my-3"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void update({ name });
                    }}
                  >
                    <Input
                      aria-label="Document name"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      required
                      maxLength={300}
                    />
                    <Button size="sm" disabled={!!busy}>
                      Save
                    </Button>
                    <Button
                      size="sm"
                      type="button"
                      variant="ghost"
                      onClick={() => setEditing(false)}
                    >
                      Cancel
                    </Button>
                  </form>
                ) : (
                  <h1 className="flex items-start gap-3">
                    {law.name}
                    <button
                      className="icon-button mt-1 shrink-0"
                      aria-label="Rename document"
                      onClick={() => {
                        setName(law.name);
                        setEditing(true);
                      }}
                    >
                      <Pencil size={15} />
                    </button>
                  </h1>
                )}
                <a
                  className="source-url break-all"
                  href={law.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {law.url}
                  <ArrowUpRight size={13} />
                </a>
              </div>
              <div className="heading-actions">
                <Button
                  variant="outline"
                  onClick={() => update({ active: !law.active })}
                  disabled={!!busy || !!running}
                >
                  {law.active ? <Pause /> : <Play />}
                  {law.active ? "Pause monitoring" : "Resume monitoring"}
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => {
                    setError("");
                    setDeleteOpen(true);
                  }}
                  disabled={!!busy || !!running}
                >
                  <Trash2 />
                  Delete document
                </Button>
              </div>
            </div>
            {!law.active && (
              <div className="info-note mb-5">
                Monitoring is paused. Saved versions and comparisons remain
                available. Resume to run a live check.
              </div>
            )}
            {note && <SuccessNote>{note}</SuccessNote>}
            <div className="detail-overview">
              <div>
                <span className="eyebrow">LAST LIVE RESULT</span>
                <Status value={law.last_result} />
              </div>
              <div>
                <span className="eyebrow">LAST CHECKED</span>
                <strong>{dateTime(law.last_checked)}</strong>
              </div>
              <div>
                <span className="eyebrow">SAVED VERSIONS</span>
                <strong>{law.versions.length}</strong>
              </div>
              <div>
                <span className="eyebrow">MONITORING</span>
                <strong>{law.active ? "Active" : "Paused"}</strong>
              </div>
            </div>
            <ErrorNote message={law.last_error} />
            <div className="law-grid">
              <section className="panel">
                <div className="panel-header">
                  <h2>Check the current document</h2>
                  <RefreshCw size={18} className="muted" />
                </div>
                <div className="panel-body">
                  <p className="muted text-sm mt-0">
                    Fetch the URL above and compare its text with the baseline
                    you choose.
                  </p>
                  <label className="field-label">
                    Comparison baseline
                    <select
                      value={baseline}
                      onChange={(event) => setBaseline(event.target.value)}
                      disabled={!!running}
                    >
                      <option value="">
                        Last live version · ordinary monitoring
                      </option>
                      {law.versions.map((version) => (
                        <option value={version.id} key={version.id}>
                          {versionLabel(version)}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selectedBaseline ? (
                    <div className="historical-note">
                      <strong>Historical comparison</strong>
                      <p className="m-0 mt-1">
                        Your selected copy is compared with freshly fetched
                        content. A separate live check still compares against
                        the last live version.
                        {selectedBaseline.synthetic
                          ? " The selected baseline is synthetic."
                          : ""}
                      </p>
                    </div>
                  ) : (
                    <p className="field-help">
                      The last successfully fetched version remains the baseline
                      until a new fetch succeeds.
                    </p>
                  )}
                  <div className="flex flex-wrap gap-3 mt-5">
                    <Button
                      onClick={scan}
                      disabled={!!busy || !!running || !law.active}
                    >
                      {busy === "scan" || running ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <RefreshCw />
                      )}
                      {baseline ? "Fetch & compare with history" : "Scan now"}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setImportOpen(true)}
                      disabled={!!busy}
                    >
                      <FileUp />
                      Import previous version
                    </Button>
                  </div>
                </div>
              </section>
              <section className="panel">
                <div className="panel-header">
                  <h2>Compare saved versions</h2>
                  <GitCompareArrows size={18} className="muted" />
                </div>
                <div className="panel-body">
                  <p className="muted text-sm mt-0">
                    Use existing evidence without contacting the source website.
                    You choose the direction of comparison.
                  </p>
                  <div className="saved-selectors">
                    <label className="field-label">
                      Before
                      <select
                        aria-label="Saved version before"
                        value={savedOld}
                        onChange={(event) => setOldId(event.target.value)}
                      >
                        {law.versions.map((version) => (
                          <option key={version.id} value={version.id}>
                            {versionLabel(version)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <ArrowRight size={15} />
                    <label className="field-label">
                      After
                      <select
                        aria-label="Saved version after"
                        value={savedNew}
                        onChange={(event) => setNewId(event.target.value)}
                      >
                        {law.versions.map((version) => (
                          <option key={version.id} value={version.id}>
                            {versionLabel(version)}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <Button
                    className="mt-5"
                    variant="outline"
                    disabled={!!busy || !savedOld || !savedNew}
                    onClick={compareSaved}
                  >
                    {busy === "compare" ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <GitCompareArrows />
                    )}
                    Open saved comparison
                  </Button>
                </div>
              </section>
            </div>
            {latestScan && (
              <div className="mt-6">
                <ScanPanel scan={latestScan} />
              </div>
            )}
            <section className="panel mt-6">
              <div className="panel-header">
                <div className="flex items-center gap-3">
                  <History size={18} />
                  <h2>Version history</h2>
                  <span className="count-pill">{law.versions.length}</span>
                </div>
                <span className="text-xs muted">
                  Content is saved once. Every observation is retained.
                </span>
              </div>
              <div className="version-list">
                {law.versions.map((version) => (
                  <div className="version-row" key={version.id}>
                    <div className="version-marker">
                      <BookOpen size={17} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Link
                          className="font-semibold hover:underline"
                          href={"/evidence/" + version.id}
                        >
                          {version.title}
                        </Link>
                        {version.id === law.current_version_id && (
                          <span className="current-label">
                            Current live snapshot
                          </span>
                        )}
                        {version.synthetic && (
                          <span className="synthetic-label">
                            Synthetic demo
                          </span>
                        )}
                        <Status value={version.origin} />
                      </div>
                      <p className="text-xs muted mb-0 mt-2">
                        {version.declared_date
                          ? "Stated date: " +
                            dateOnly(version.declared_date) +
                            " · supplied by user"
                          : "Version date unknown"}{" "}
                        · First saved {dateTime(version.created_at)}
                      </p>
                      <p className="text-xs muted m-0 mt-1">
                        {version.content_type} ·{" "}
                        {version.characters.toLocaleString()} characters ·{" "}
                        {version.passage_count} passages
                        {version.page_count
                          ? " · " + version.page_count + " pages"
                          : ""}{" "}
                        · {version.id.slice(0, 8)}
                      </p>
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      <Button
                        size="sm"
                        variant={
                          baseline === version.id ? "secondary" : "outline"
                        }
                        disabled={!!running}
                        onClick={() => {
                          setBaseline(version.id);
                          setOldId(version.id);
                          setNote(
                            "Baseline selected. Fetch the current document to run this historical comparison.",
                          );
                        }}
                      >
                        Use as baseline
                      </Button>
                      <Button size="icon" variant="ghost" asChild>
                        <Link
                          aria-label={
                            "Read saved version " + version.id.slice(0, 8)
                          }
                          href={"/evidence/" + version.id}
                        >
                          <ArrowUpRight />
                        </Link>
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
              <details className="observations">
                <summary>
                  Fetch & import observations ({law.observations.length}
                  {law.observations.length === 100 ? "+" : ""})
                </summary>
                <p className="field-help">
                  An unchanged check or duplicate import reuses the saved
                  content and adds an observation. Each import retains its
                  supplied date here; it does not rewrite the snapshot's first
                  provenance. Importing does not prove official historical
                  status.
                </p>
                <div className="table-scroll">
                  <table className="watch-table">
                    <thead>
                      <tr>
                        <th>WHEN</th>
                        <th>ORIGIN</th>
                        <th>STATED DATE</th>
                        <th>VERSION</th>
                        <th>FILE</th>
                      </tr>
                    </thead>
                    <tbody>
                      {law.observations.map((observation) => (
                        <tr key={observation.id}>
                          <td>{dateTime(observation.created_at)}</td>
                          <td>
                            {label(observation.origin)}
                            {observation.synthetic && " · synthetic"}
                          </td>
                          <td>
                            {observation.declared_date
                              ? observation.declared_date + " · user supplied"
                              : "Unknown"}
                          </td>
                          <td>
                            <Link
                              className="text-primary"
                              href={"/evidence/" + observation.version_id}
                            >
                              {observation.version_id.slice(0, 8)}
                            </Link>
                          </td>
                          <td>
                            {observation.source_url ? (
                              <a
                                href={observation.source_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-link"
                              >
                                {observation.filename}
                                <ArrowUpRight size={11} />
                              </a>
                            ) : (
                              observation.filename
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </section>
            {law.comparisons.length > 0 && (
              <section className="panel mt-6">
                <div className="panel-header">
                  <h2>Saved comparisons</h2>
                  <span className="text-xs muted">Most recent 50 pairs</span>
                </div>
                <div className="comparison-list">
                  {law.comparisons.map((comparison) => (
                    <Link
                      href={"/compare/" + comparison.id}
                      key={comparison.id}
                    >
                      <div className="flex items-center gap-3">
                        <GitCompareArrows size={16} />
                        <Status value={comparison.mode} />
                        <span className="text-xs muted">
                          {comparison.old_version_id.slice(0, 8)} →{" "}
                          {comparison.new_version_id.slice(0, 8)}
                        </span>
                      </div>
                      <span className="text-xs">
                        {comparison.counts.added +
                          comparison.counts.removed +
                          comparison.counts.modified}{" "}
                        changed passages
                      </span>
                      <ArrowUpRight size={15} />
                    </Link>
                  ))}
                </div>
              </section>
            )}
            <ImportDialog
              open={importOpen}
              onOpenChange={setImportOpen}
              law={law}
              onImported={(version, reused) => {
                setBaseline(version.id);
                setOldId(version.id);
                setNote(
                  reused
                    ? "Existing content reused and selected. The new import date and provenance are recorded under Fetch & import observations."
                    : "Previous version saved and selected. Run Fetch & compare with history to compare it with the live source.",
                );
              }}
            />
            <ConfirmDeleteDialog
              open={deleteOpen}
              onOpenChange={setDeleteOpen}
              title="Delete this monitored document?"
              description={`This permanently deletes ${law.name}, all ${law.versions.length} saved version(s), observations, comparisons, analyses, and its scan entries. This cannot be undone.`}
              confirmLabel="Delete document and history"
              busy={busy === "delete"}
              error={deleteOpen ? error : ""}
              onConfirm={() => void removeDocument()}
            />
          </>
        )
      )}
    </Shell>
  );
}
