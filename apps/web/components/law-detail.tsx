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
  errorText,
  invalidateResources,
  label,
  mutateResource,
  primeResource,
  resourceTag,
  useResource,
} from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { translate, useI18n, type Locale } from "@/lib/i18n";
import type {
  Comparison,
  LawDetail as Detail,
  Scan,
  Version,
} from "@/lib/types";
import { ErrorNote, Loading, Status, SuccessNote } from "./common";
import { AIHistory } from "./ai-history";
import { ConfirmDeleteDialog } from "./confirm-delete-dialog";
import { ImportDialog } from "./document-forms";
import { ScanPanel } from "./scan-panel";
import { Shell } from "./shell";
import { useAuth } from "./auth-gate";

export function versionLabel(
  version: Version,
  t: (key: string, values?: Record<string, string | number>) => string,
  locale: Locale,
) {
  return (
    (version.declared_date
      ? t("law.versionStated", { date: version.declared_date })
      : t("law.dateUnknown")) +
    " · " +
    (translate(locale, `status.${version.origin}`) || label(version.origin)) +
    " · " +
    version.id.slice(0, 8) +
    (version.synthetic ? ` · ${t("law.syntheticUpper")}` : "")
  );
}

export function LawDetail({ id }: { id: string }) {
  const router = useRouter();
  const { t, locale, dateTime, number } = useI18n();
  const { canManage } = useAuth();
  const {
    data: law,
    error: loadError,
    loading,
  } = useResource(resources.law(id));
  const scans = useResource(resources.scans());
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
      await invalidateResources(
        resources.law(id),
        resources.laws(),
        resourceTag("registry", "organization"),
      );
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
      const created = await api<Scan>("/scans", {
        method: "POST",
        body: JSON.stringify({
          law_ids: [id],
          baseline_version_id: baseline || null,
        }),
      });
      const scansWereLoaded = scans.data !== null;
      scans.setData((current) => [
        created,
        ...(current || []).filter((item) => item.id !== created.id),
      ]);
      if (!scansWereLoaded) void invalidateResources(resources.scans());
      if (created.job) primeResource(resources.job(created.job.id), created.job);
      void invalidateResources(resources.jobs());
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
      const updatedLaws = mutateResource(resources.laws(), (current) =>
        current?.filter((item) => item.id !== id) || null,
      );
      void invalidateResources(
        ...(updatedLaws === null ? [resources.laws()] : []),
        resources.sources(),
        resources.organizationStatus(),
        resourceTag("registry", "organization"),
        resourceTag("comparison", "organization"),
        resourceTag("ai-history", "organization"),
        resourceTag("impact-inbox", "organization"),
        resourceTag("impact-matrix", "organization"),
      );
      router.push("/");
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  async function removeVersion(version: Version) {
    if (
      !window.confirm(
        t("law.removeVersionConfirm", { version: version.id.slice(0, 8) }),
      )
    )
      return;
    setBusy("delete-version-" + version.id);
    setError("");
    try {
      await api("/versions/" + version.id, { method: "DELETE" });
      if (baseline === version.id) setBaseline("");
      if (oldId === version.id) setOldId("");
      if (newId === version.id) setNewId("");
      setNote(t("law.importRemoved"));
      await invalidateResources(
        resources.law(id),
        resources.version(version.id),
        resourceTag("registry", "organization"),
        resourceTag("comparison", "organization"),
      );
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  return (
    <Shell section={t("law.section")}>
      <Link href="/" className="back-link">
        <ArrowLeft size={14} />
        {t("law.back")}
      </Link>
      <ErrorNote message={loadError || error} />
      {loading && !law ? (
        <Loading />
      ) : (
        law && (
          <>
            <div className="page-heading">
              <div className="min-w-0">
                <span className="eyebrow">{t("law.eyebrow")}</span>
                {editing && canManage ? (
                  <form
                    className="flex items-center gap-2 my-3"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void update({ name });
                    }}
                  >
                    <Input
                      aria-label={t("law.documentName")}
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      required
                      maxLength={300}
                    />
                    <Button size="sm" disabled={!!busy}>
                      {t("common.save")}
                    </Button>
                    <Button
                      size="sm"
                      type="button"
                      variant="ghost"
                      onClick={() => setEditing(false)}
                    >
                      {t("scan.cancel")}
                    </Button>
                  </form>
                ) : (
                  <h1 className="flex items-start gap-3">
                    {law.name}
                    {canManage && <button
                      className="icon-button mt-1 shrink-0"
                      aria-label={t("law.rename")}
                      onClick={() => {
                        setName(law.name);
                        setEditing(true);
                      }}
                    >
                      <Pencil size={15} />
                    </button>}
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
              {canManage && <div className="heading-actions">
                <Button
                  variant="outline"
                  onClick={() => update({ active: !law.active })}
                  disabled={!!busy || !!running}
                >
                  {law.active ? <Pause /> : <Play />}
                  {law.active ? t("law.pause") : t("law.resume")}
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
                  {t("law.delete")}
                </Button>
              </div>}
            </div>
            {!law.active && (
              <div className="info-note mb-5">
                {t("law.pausedNotice")}
              </div>
            )}
            {note && <SuccessNote>{note}</SuccessNote>}
            <div className="detail-overview">
              <div>
                <span className="eyebrow">{t("law.lastResult")}</span>
                <Status value={law.last_result} />
              </div>
              <div>
                <span className="eyebrow">{t("law.lastChecked")}</span>
                <strong>{dateTime(law.last_checked)}</strong>
              </div>
              <div>
                <span className="eyebrow">{t("law.savedVersions")}</span>
                <strong>{number(law.versions.length)}</strong>
              </div>
              <div>
                <span className="eyebrow">{t("law.monitoring")}</span>
                <strong>{law.active ? t("status.active") : t("status.paused")}</strong>
              </div>
            </div>
            <ErrorNote message={law.last_error} />
            <div className="law-grid">
              <section className="panel">
                <div className="panel-header">
                  <h2>{t("law.checkCurrent")}</h2>
                  <RefreshCw size={18} className="muted" />
                </div>
                <div className="panel-body">
                  <p className="muted text-sm mt-0">
                    {t("law.checkBody")}
                  </p>
                  <label className="field-label">
                    {t("law.baseline")}
                    <select
                      value={baseline}
                      onChange={(event) => setBaseline(event.target.value)}
                      disabled={!!running}
                    >
                      <option value="">
                        {t("law.lastLiveBaseline")}
                      </option>
                      {law.versions.map((version) => (
                        <option value={version.id} key={version.id}>
                          {versionLabel(version, t, locale)}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selectedBaseline ? (
                    <div className="historical-note">
                      <strong>{t("law.historicalComparison")}</strong>
                      <p className="m-0 mt-1">
                        {t("law.historicalBody")}
                        {selectedBaseline.synthetic
                          ? ` ${t("law.syntheticBaseline")}`
                          : ""}
                      </p>
                    </div>
                  ) : (
                    <p className="field-help">
                      {t("law.baselineHelp")}
                    </p>
                  )}
                  {canManage && <div className="flex flex-wrap gap-3 mt-5">
                    <Button
                      onClick={scan}
                      disabled={!!busy || !!running || !law.active}
                    >
                      {busy === "scan" || running ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <RefreshCw />
                      )}
                      {baseline ? t("law.fetchCompare") : t("monitor.scanNow")}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setImportOpen(true)}
                      disabled={!!busy}
                    >
                      <FileUp />
                      {t("form.importTitle")}
                    </Button>
                  </div>}
                </div>
              </section>
              <section className="panel">
                <div className="panel-header">
                  <h2>{t("law.compareSaved")}</h2>
                  <GitCompareArrows size={18} className="muted" />
                </div>
                {canManage && <div className="panel-body">
                  <p className="muted text-sm mt-0">
                    {t("law.compareSavedBody")}
                  </p>
                  <div className="saved-selectors">
                    <label className="field-label">
                      {t("law.before")}
                      <select
                        aria-label={t("law.savedBefore")}
                        value={savedOld}
                        onChange={(event) => setOldId(event.target.value)}
                      >
                        {law.versions.map((version) => (
                          <option key={version.id} value={version.id}>
                            {versionLabel(version, t, locale)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <ArrowRight size={15} />
                    <label className="field-label">
                      {t("law.after")}
                      <select
                        aria-label={t("law.savedAfter")}
                        value={savedNew}
                        onChange={(event) => setNewId(event.target.value)}
                      >
                        {law.versions.map((version) => (
                          <option key={version.id} value={version.id}>
                            {versionLabel(version, t, locale)}
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
                    {t("law.openComparison")}
                  </Button>
                </div>}
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
                   <h2>{t("law.versionHistory")}</h2>
                  <span className="count-pill">{law.versions.length}</span>
                </div>
                <span className="text-xs muted">
                  {t("law.versionHistoryBody")}
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
                            {t("law.currentSnapshot")}
                          </span>
                        )}
                        {version.synthetic && (
                          <span className="synthetic-label">
                            {t("law.syntheticDemo")}
                          </span>
                        )}
                        <Status value={version.origin} />
                        {version.identity_json?.canonical_work_id && (
                          <span className="current-label">
                            {version.identity_json.canonical_work_id}
                          </span>
                        )}
                      </div>
                      <p className="text-xs muted mb-0 mt-2">
                        {version.declared_date
                          ? t("law.statedDateUser", { date: version.declared_date })
                          : t("law.versionDateUnknown")}{" "}
                        · {t("law.firstSaved", { date: dateTime(version.created_at) })}
                      </p>
                      <p className="text-xs muted m-0 mt-1">
                        {version.content_type} ·{" "}
                        {t("law.characters", { count: number(version.characters) })} ·{" "}
                        {t("law.passages", { count: number(version.passage_count) })}
                        {version.page_count
                          ? ` · ${t("law.pages", { count: number(version.page_count) })}`
                          : ""}{" "}
                        · {version.id.slice(0, 8)}
                      </p>
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      {canManage && <Button
                        size="sm"
                        variant={
                          baseline === version.id ? "secondary" : "outline"
                        }
                        disabled={!!running}
                        onClick={() => {
                          setBaseline(version.id);
                          setOldId(version.id);
                          setNote(
                            t("law.baselineSelected"),
                          );
                        }}
                      >
                        {t("law.useBaseline")}
                      </Button>}
                      <Button size="icon" variant="ghost" asChild>
                        <Link
                          aria-label={
                            t("law.readVersion", { version: version.id.slice(0, 8) })
                          }
                          href={"/evidence/" + version.id}
                        >
                          <ArrowUpRight />
                        </Link>
                      </Button>
                      {canManage && version.id !== law.current_version_id &&
                        version.origin !== "live" && (
                          <Button
                            size="icon"
                            variant="ghost"
                            aria-label={
                              t("law.removeImport", { version: version.id.slice(0, 8) })
                            }
                            title={t("law.removeMistaken")}
                            disabled={!!busy || !!running}
                            onClick={() => void removeVersion(version)}
                          >
                            {busy === "delete-version-" + version.id ? (
                              <Loader2 className="animate-spin" />
                            ) : (
                              <Trash2 />
                            )}
                          </Button>
                        )}
                    </div>
                  </div>
                ))}
              </div>
              <details className="observations">
                <summary>
                  {t("law.observations")} ({number(law.observations.length)}
                  {law.observations.length === 100 ? "+" : ""})
                </summary>
                <p className="field-help">
                  {t("law.observationsBody")}
                </p>
                <div className="table-scroll">
                  <table className="watch-table">
                    <thead>
                      <tr>
                        <th>{t("common.when")}</th>
                        <th>{t("law.origin")}</th>
                        <th>{t("law.statedDate")}</th>
                        <th>{t("law.version")}</th>
                        <th>{t("law.file")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {law.observations.map((observation) => (
                        <tr key={observation.id}>
                          <td>{dateTime(observation.created_at)}</td>
                          <td>
                            {label(observation.origin)}
                            {observation.synthetic && ` · ${t("law.syntheticLower")}`}
                          </td>
                          <td>
                            {observation.declared_date
                              ? t("law.dateUserSupplied", { date: observation.declared_date })
                              : t("status.unknown")}
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
            <section className="panel mt-6">
              <div className="panel-header">
                <div>
                  <span className="eyebrow">{t("law.legalRecord")}</span>
                  <h2>{t("law.timeline")}</h2>
                </div>
                <div className="flex gap-2">
                  <Status value={law.regulatory_timeline.work.lifecycle} />
                  <Status value={law.regulatory_timeline.monitoring.active ? "active" : "paused"} />
                </div>
              </div>
              <div className="p-5 grid lg:grid-cols-3 gap-4 border-b">
                <div>
                  <span className="eyebrow">{t("law.authorityKind")}</span>
                  <strong className="block mt-2">{law.regulatory_timeline.work.authority}</strong>
                  <span className="muted text-sm">{label(law.regulatory_timeline.work.kind)}</span>
                </div>
                <div>
                  <span className="eyebrow">{t("law.identifiers")}</span>
                  <div className="mt-2 text-sm">
                    {law.regulatory_timeline.identifiers.length
                      ? law.regulatory_timeline.identifiers.map((item) => (
                          <div key={item.scheme + item.value}>
                            <span className="muted">{label(item.scheme)}:</span> {item.value}
                          </div>
                        ))
                      : <span className="muted">{t("law.noIdentifier")}</span>}
                  </div>
                </div>
                <div>
                  <span className="eyebrow">{t("law.expressions")}</span>
                  <div className="mt-2 text-sm">
                    {law.regulatory_timeline.expressions.map((item) => (
                      <span className="status-badge status-neutral mr-1" key={item.id}>{item.language}</span>
                    ))}
                    <div className="muted mt-2">{t("law.immutableVersions", { count: number(law.regulatory_timeline.normalized_versions) })}</div>
                  </div>
                </div>
              </div>
              {law.regulatory_timeline.relations.length > 0 && (
                <div className="p-5 border-b">
                  <span className="eyebrow">{t("law.relations")}</span>
                  <div className="comparison-list mt-3">
                    {law.regulatory_timeline.relations.map((relation) => (
                      <div className="flex items-center justify-between gap-3" key={relation.id}>
                        <span>{translate(locale, `status.${relation.direction}`) || label(relation.direction)} · {translate(locale, `status.${relation.type}`) || label(relation.type)} · {t("law.work", { id: relation.other_work_id.slice(0, 8) })}</span>
                        <span className="flex gap-2"><Status value={relation.state} /><span className="muted text-xs">{label(relation.provenance)}</span></span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className="p-5">
                <div className="flex items-center justify-between mb-4">
                  <span className="eyebrow">{t("law.savedTimeline")}</span>
                  <Link href="/registry" className="text-link text-sm">{t("law.openRegistry")} <ArrowRight size={13} /></Link>
                </div>
                <div className="space-y-3">
                  {law.regulatory_timeline.timeline.map((item) => (
                    <div className="flex items-start gap-3 border-l-2 pl-4 py-1" key={item.id}>
                      <History size={16} className="mt-1 muted shrink-0" />
                      <div className="flex-1">
                        <strong>{item.label}</strong>
                        <div className="text-sm muted">{dateTime(item.at)} · {label(item.detail)}</div>
                      </div>
                      {item.url && item.url.startsWith("/") && (
                        <Button asChild size="sm" variant="ghost"><Link href={item.url}>{t("law.inspect")} <ArrowUpRight size={13} /></Link></Button>
                      )}
                      {item.url && !item.url.startsWith("/") && (
                        <Button asChild size="sm" variant="ghost"><a href={item.url} target="_blank" rel="noreferrer">{t("law.source")} <ArrowUpRight size={13} /></a></Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </section>
            <AIHistory lawId={id} />
            {law.comparisons.length > 0 && (
              <section className="panel mt-6">
                <div className="panel-header">
                  <h2>{t("law.savedComparisons")}</h2>
                  <span className="text-xs muted">{t("law.recentPairs")}</span>
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
                        {t("law.changedPassages")}
                      </span>
                      <ArrowUpRight size={15} />
                    </Link>
                  ))}
                </div>
              </section>
            )}
            {canManage && <ImportDialog
              open={importOpen}
              onOpenChange={setImportOpen}
              law={law}
              onImported={(version, reused) => {
                setBaseline(version.id);
                setOldId(version.id);
                setNote(
                  reused
                    ? t("law.importReused")
                    : t("law.importSaved"),
                );
              }}
            />}
            {canManage && <ConfirmDeleteDialog
              open={deleteOpen}
              onOpenChange={setDeleteOpen}
               title={t("law.deleteTitle")}
               description={t("law.deleteDescription", { name: law.name, count: number(law.versions.length) })}
               confirmLabel={t("law.deleteConfirm")}
              busy={busy === "delete"}
              error={deleteOpen ? error : ""}
              onConfirm={() => void removeDocument()}
            />}
          </>
        )
      )}
    </Shell>
  );
}
