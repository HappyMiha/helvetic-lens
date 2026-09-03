"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Bell,
  CalendarClock,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  GitCompareArrows,
  Loader2,
  ListChecks,
  MessageSquare,
  Send,
  Sparkles,
  UserRound,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  api,
  dateTime,
  errorText,
  label,
  refreshWorkspace,
  useResource,
} from "@/lib/api";
import type {
  ActionDecision,
  AIHistoryItem,
  AIHistoryPage,
  Analysis,
  AnalysisPlan,
  Answer,
  Change,
  Comparison,
  Coverage,
  Health,
  Impact,
  Job,
  Version,
} from "@/lib/types";
import { Citations, ErrorNote, Loading, Status } from "./common";
import { AIHistory } from "./ai-history";
import { Shell } from "./shell";
import { useAuth } from "./auth-gate";
import { useI18n } from "@/lib/i18n";

const PAGE_SIZE = 40;
const JOB_TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);
type ComparisonLocale = "de" | "fr" | "it" | "rm" | "en";
const comparisonCopy = {
  en: { overview: "Deterministic change overview", material: "Material", reviewFirst: "Review first", addedRemoved: "Added / removed", newDeleted: "New or deleted units", movedRenumbered: "Moved / renumbered", structural: "Structural, kept out of AI", formatting: "Formatting only", hidden: "Hidden by default", needsReview: "Needs review", uncertain: "Uncertain match" },
  de: { overview: "Deterministische Änderungsübersicht", material: "Wesentlich", reviewFirst: "Zuerst prüfen", addedRemoved: "Hinzugefügt / entfernt", newDeleted: "Neue oder gelöschte Einheiten", movedRenumbered: "Verschoben / neu nummeriert", structural: "Strukturell, nicht an KI gesendet", formatting: "Nur Formatierung", hidden: "Standardmässig ausgeblendet", needsReview: "Prüfung nötig", uncertain: "Unsichere Zuordnung" },
  fr: { overview: "Aperçu déterministe des changements", material: "Essentiel", reviewFirst: "À examiner d’abord", addedRemoved: "Ajouté / supprimé", newDeleted: "Unités nouvelles ou supprimées", movedRenumbered: "Déplacé / renuméroté", structural: "Structurel, exclu de l’IA", formatting: "Mise en forme seulement", hidden: "Masqué par défaut", needsReview: "À vérifier", uncertain: "Correspondance incertaine" },
  it: { overview: "Panoramica deterministica delle modifiche", material: "Sostanziale", reviewFirst: "Da esaminare prima", addedRemoved: "Aggiunto / rimosso", newDeleted: "Unità nuove o eliminate", movedRenumbered: "Spostato / rinumerato", structural: "Strutturale, escluso dall’IA", formatting: "Solo formattazione", hidden: "Nascosto per impostazione predefinita", needsReview: "Da verificare", uncertain: "Corrispondenza incerta" },
  rm: { overview: "Survista deterministica da las midadas", material: "Essenzial", reviewFirst: "Examinar l’emprim", addedRemoved: "Agiuntà / eliminà", newDeleted: "Unitads novas u eliminadas", movedRenumbered: "Spustà / renumerà", structural: "Structural, exclus da l’IA", formatting: "Mo furmataziun", hidden: "Zuppentà tenor standard", needsReview: "Da verifitgar", uncertain: "Attribuziun intscherta" },
} satisfies Record<ComparisonLocale, Record<string, string>>;

const localizedValues: Record<ComparisonLocale, Record<string, string>> = {
  en: { confirmed: "Confirmed", supported: "Supported", possible: "Possible", needs_review: "Needs review", accepted: "Accepted", assigned: "Assigned", scheduled: "Scheduled", dismissed: "Dismissed", not_applicable: "Not applicable", ready: "Ready", limited: "Limited", failed: "Failed", cancelled: "Cancelled" },
  de: { confirmed: "Bestätigt", supported: "Belegt", possible: "Möglich", needs_review: "Prüfung nötig", accepted: "Angenommen", assigned: "Zugewiesen", scheduled: "Terminiert", dismissed: "Verworfen", not_applicable: "Nicht anwendbar", ready: "Bereit", limited: "Begrenzt", failed: "Fehlgeschlagen", cancelled: "Abgebrochen" },
  fr: { confirmed: "Confirmé", supported: "Étayé", possible: "Possible", needs_review: "À vérifier", accepted: "Accepté", assigned: "Attribué", scheduled: "Planifié", dismissed: "Écarté", not_applicable: "Non applicable", ready: "Prêt", limited: "Limité", failed: "Échec", cancelled: "Annulé" },
  it: { confirmed: "Confermato", supported: "Supportato", possible: "Possibile", needs_review: "Da verificare", accepted: "Accettato", assigned: "Assegnato", scheduled: "Pianificato", dismissed: "Scartato", not_applicable: "Non applicabile", ready: "Pronto", limited: "Limitato", failed: "Non riuscito", cancelled: "Annullato" },
  rm: { confirmed: "Confermà", supported: "Cumprovà", possible: "Pussaivel", needs_review: "Da verifitgar", accepted: "Acceptà", assigned: "Attribuì", scheduled: "Planisà", dismissed: "Refusà", not_applicable: "Betg applitgabel", ready: "Pront", limited: "Limità", failed: "Betg reussì", cancelled: "Interrut" },
};

function localLabel(value: string, locale: ComparisonLocale) {
  return localizedValues[locale][value] || label(value);
}

async function waitForJob(initial: Job): Promise<Job> {
  let current = initial;
  const deadline = Date.now() + 10 * 60 * 1000;
  while (!JOB_TERMINAL_STATES.has(current.state)) {
    if (Date.now() >= deadline)
      throw new Error(
        "The work is still queued. You can leave this page and follow it in Scan activity.",
      );
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    current = await api<Job>("/jobs/" + current.id);
  }
  return current;
}

export function ComparisonView({ id }: { id: string }) {
  const { canManage } = useAuth();
  const { locale } = useI18n();
  const uiLocale = locale.slice(0, 2) as ComparisonLocale;
  const ui = comparisonCopy[uiLocale];
  const [polling, setPolling] = useState(true);
  const { data, error: loadError } = useResource<Comparison>(
    "/comparisons/" + id,
    polling ? 2000 : 0,
  );
  const { data: health } = useResource<Health>("/health", 15000);
  const [filter, setFilter] = useState("substantive"),
    [context, setContext] = useState(false),
    [page, setPage] = useState(0);
  const [jumpTarget, setJumpTarget] = useState(""),
    [analysing, setAnalysing] = useState(false),
    [analysisJob, setAnalysisJob] = useState<Job | null>(null),
    [analysisNotice, setAnalysisNotice] = useState(""),
    [confirmingIdentity, setConfirmingIdentity] = useState(""),
    [error, setError] = useState("");
  const identityBlocked = ["mismatch", "unknown"].includes(
    data?.identity?.effective_status || data?.identity?.status || "",
  );
  const analysis = identityBlocked ? null : data?.analysis;
  const classificationAvailable = !!data?.diff.classification_counts;
  const meaningfulChangeCount =
    data?.diff.material_count ??
    data?.diff.items.filter(
      (item) =>
        item.significance === "substantive" ||
        item.significance === "uncertain",
    ).length ??
    0;
  const hasMeaningfulChanges =
    data?.diff.material_changed ?? meaningfulChangeCount > 0;
  const canAnalyseMeaningfulChanges =
    classificationAvailable && hasMeaningfulChanges;
  const hiddenExactChangeCount = data?.diff.classification_counts
    ? data.diff.classification_counts.structural +
      data.diff.classification_counts.formatting
    : 0;
  const effectiveAnalysisJob = analysisJob || data?.analysis_job || null;
  const analysisJobActive =
    !!effectiveAnalysisJob &&
    !JOB_TERMINAL_STATES.has(effectiveAnalysisJob.state);
  useEffect(() => {
    setPolling(analysisJobActive || analysing || analysis?.status === "pending");
  }, [analysisJobActive, analysing, analysis?.status]);
  useEffect(() => {
    if (!data?.analysis_job) return;
    setAnalysisJob((current) =>
      !current || current.id === data.analysis_job?.id ? data.analysis_job! : current,
    );
  }, [data?.analysis_job]);
  useEffect(() => {
    if (!analysisJobActive || !effectiveAnalysisJob) return;
    const jobId = effectiveAnalysisJob.id;
    const timer = window.setInterval(async () => {
      try {
        const next = await api<Job>("/jobs/" + jobId);
        setAnalysisJob(next);
        if (JOB_TERMINAL_STATES.has(next.state)) {
          window.clearInterval(timer);
          setAnalysing(false);
          if (next.state === "succeeded") {
            setAnalysisNotice("Impact report ready. The saved result is open below.");
            if (document.hidden && "Notification" in window && Notification.permission === "granted")
              new Notification("Helvetic Lens", { body: "Impact report ready." });
          } else {
            setAnalysisNotice(`Impact analysis ${next.state}. The exact comparison remains available.`);
          }
          refreshWorkspace();
        }
      } catch (cause) {
        setError(errorText(cause));
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [analysisJobActive, effectiveAnalysisJob?.id]);
  useEffect(() => {
    if (jumpTarget)
      document
        .getElementById(jumpTarget)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [jumpTarget, page]);
  const items =
    data?.diff.items.filter(
      (item) =>
        (context || item.kind !== "unchanged") &&
        (filter === "all" ||
          (filter === "substantive"
            ? item.significance === "substantive" ||
              item.significance === "uncertain"
            : item.kind === filter)),
    ) || [];
  const pages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const visible = items.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const changes =
    data?.diff.items.filter((item) => item.kind !== "unchanged") || [];
  async function analyse() {
    setAnalysing(true);
    setError("");
    try {
      const queued = await api<Job>("/comparisons/" + id + "/analyse-jobs", {
        method: "POST",
        body: JSON.stringify({ output_locale: locale }),
      });
      setAnalysisJob(queued);
      setAnalysisNotice(
        JOB_TERMINAL_STATES.has(queued.state)
          ? "Impact report finished. Opening the saved result."
          : "Impact analysis was submitted. You can keep reviewing the exact changes or leave this page.",
      );
      if (queued.state === "failed")
        setError(queued.error?.detail || "Apertus could not analyse this change dossier.");
      refreshWorkspace();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      if (!analysisJobActive) setAnalysing(false);
    }
  }
  async function cancelAnalysis() {
    if (!effectiveAnalysisJob) return;
    try {
      const cancelled = await api<Job>(`/jobs/${effectiveAnalysisJob.id}/cancel`, {
        method: "POST",
      });
      setAnalysisJob(cancelled);
      setAnalysing(false);
      setAnalysisNotice("Impact analysis cancelled. The exact comparison remains available.");
      refreshWorkspace();
    } catch (cause) {
      setError(errorText(cause));
    }
  }
  async function confirmIdentity(versionId: string) {
    setConfirmingIdentity(versionId);
    setError("");
    try {
      await api("/versions/" + versionId + "/identity-decision", {
        method: "POST",
        body: JSON.stringify({
          note: "Confirmed from the saved comparison identity review",
        }),
      });
      refreshWorkspace();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setConfirmingIdentity("");
    }
  }
  async function removeMistakenImport(versionId: string) {
    if (
      !window.confirm(
        "Remove this saved import and every comparison that uses it?",
      )
    )
      return;
    setConfirmingIdentity(versionId);
    setError("");
    try {
      await api("/versions/" + versionId, { method: "DELETE" });
      refreshWorkspace();
      window.location.href = "/laws/" + data?.law_id;
    } catch (cause) {
      setError(errorText(cause));
      setConfirmingIdentity("");
    }
  }
  function jump(value: string) {
    setFilter("all");
    setContext(false);
    setPage(
      Math.floor(changes.findIndex((item) => item.id === value) / PAGE_SIZE),
    );
    setJumpTarget(value);
  }
  return (
    <Shell section="Document comparison" wide>
      <Link className="back-link" href={data ? "/laws/" + data.law_id : "/"}>
        <ArrowLeft size={14} />
        Back to document
      </Link>
      <ErrorNote message={loadError} />
      {!data ? (
        !loadError && <Loading text="Loading saved comparison…" />
      ) : (
        <>
          <div className="page-heading">
            <div>
              <span className="eyebrow">KNOW WHAT CHANGED</span>
              <h1>{data.law.name}</h1>
              <div className="flex flex-wrap gap-3 items-center text-xs muted">
                <Status value={data.mode} />
                <span>Comparison saved {dateTime(data.created_at)}</span>
                {(data.old_version.synthetic || data.new_version.synthetic) && (
                  <span className="synthetic-label">
                    Contains synthetic demo content
                  </span>
                )}
              </div>
            </div>
            <span className="comparison-mark">
              <GitCompareArrows size={22} />
            </span>
          </div>
          {data.mode !== "monitoring" && (
            <div className="info-note mb-6">
              {data.mode === "historical"
                ? "An imported or selected baseline was compared with freshly fetched content. This historical difference is not reported as a new live amendment."
                : "These are two saved versions. No source website was contacted and the live monitoring state was not changed."}
            </div>
          )}
          {identityBlocked && data.identity && (
            <div
              className="identity-warning identity-mismatch mb-6"
              role="alert"
            >
              <strong>
                {data.identity.effective_status === "mismatch"
                  ? "Comparison paused: these files identify different legal works"
                  : "Comparison paused: confirm the unknown document assignment"}
              </strong>
              <p>{data.identity.reason}</p>
              <p>
                Tracked: <b>{data.law.name}</b>
                <br />
                Detected before:{" "}
                <b>
                  {data.identity.old.detected_identifier ||
                    data.identity.old.detected_title ||
                    "Not identified"}
                </b>
                <br />
                Detected after:{" "}
                <b>
                  {data.identity.new.detected_identifier ||
                    data.identity.new.detected_title ||
                    "Not identified"}
                </b>
              </p>
              <span>
                No new comparison or AI request can start while this gate is
                unresolved. Existing exact evidence remains available for
                inspection.
              </span>
              <div className="flex flex-wrap gap-2 mt-3">
                <Button asChild variant="outline" size="sm">
                  <a href={data.old_version.artifact_url} target="_blank">
                    Inspect before original <ArrowUpRight />
                  </a>
                </Button>
                <Button asChild variant="outline" size="sm">
                  <a href={data.new_version.artifact_url} target="_blank">
                    Inspect after original <ArrowUpRight />
                  </a>
                </Button>
                <Button asChild variant="outline" size="sm">
                  <Link href={"/laws/" + data.law_id}>
                    Select or attach another version
                  </Link>
                </Button>
                {canManage &&
                  [data.old_version, data.new_version]
                    .filter(
                      (version) =>
                        version.id !== data.law.current_version_id &&
                        version.origin !== "live",
                    )
                    .map((version) => (
                      <Button
                        key={"remove-" + version.id}
                        variant="destructive"
                        size="sm"
                        disabled={!!confirmingIdentity}
                        onClick={() => removeMistakenImport(version.id)}
                      >
                        Remove mistaken import {version.id.slice(0, 8)}
                      </Button>
                    ))}
              </div>
              {canManage && data.identity.status === "unknown" && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {[
                    { side: data.identity.old, version: data.old_version },
                    { side: data.identity.new, version: data.new_version },
                  ]
                    .filter(
                      ({ side }) =>
                        side.status === "unknown" && !side.user_confirmed,
                    )
                    .map(({ version }, index) => (
                      <Button
                        key={version.id}
                        variant="outline"
                        size="sm"
                        disabled={!!confirmingIdentity}
                        onClick={() => confirmIdentity(version.id)}
                      >
                        {confirmingIdentity === version.id && (
                          <Loader2 className="animate-spin" />
                        )}
                        Confirm {index === 0 ? "this" : "other"} unknown
                        assignment
                      </Button>
                    ))}
                </div>
              )}
            </div>
          )}
          <div className="comparison-layout">
            <div className="min-w-0">
              <section className="panel diff-panel">
                <div className="panel-header">
                  <h2>Meaningful changes</h2>
                  <div className="diff-counts">
                    <span className="count-added">
                      + {data.diff.counts.added} added
                    </span>
                    <span className="count-removed">
                      − {data.diff.counts.removed} removed
                    </span>
                    <span>{data.diff.counts.modified} modified</span>
                  </div>
                </div>
                {data.diff.classification_counts && (
                  <div className="triage-summary" aria-label={ui.overview}>
                    <div>
                      <span>{ui.material}</span>
                      <strong>
                        {data.diff.classification_counts.substantive}
                      </strong>
                      <small>{ui.reviewFirst}</small>
                    </div>
                    <div>
                      <span>{ui.addedRemoved}</span>
                      <strong>
                        {(data.diff.semantic_counts?.added || 0) +
                          (data.diff.semantic_counts?.removed || 0)}
                      </strong>
                      <small>{ui.newDeleted}</small>
                    </div>
                    <div>
                      <span>{ui.movedRenumbered}</span>
                      <strong>
                        {(data.diff.semantic_counts?.moved || 0) +
                          (data.diff.semantic_counts?.renumbered || 0)}
                      </strong>
                      <small>{ui.structural}</small>
                    </div>
                    <div>
                      <span>{ui.formatting}</span>
                      <strong>
                        {data.diff.classification_counts.formatting}
                      </strong>
                      <small>{ui.hidden}</small>
                    </div>
                    <div>
                      <span>{ui.needsReview}</span>
                      <strong>
                        {data.diff.classification_counts.uncertain}
                      </strong>
                      <small>{ui.uncertain}</small>
                    </div>
                  </div>
                )}
                <div className="version-pair">
                  <VersionCard version={data.old_version} side="BEFORE" />
                  <VersionCard version={data.new_version} side="AFTER" />
                </div>
                <div className="diff-toolbar">
                  <div
                    className="segmented"
                    role="group"
                    aria-label="Change filters"
                  >
                    {["substantive", "all", "added", "removed", "modified"].map(
                      (value) => (
                        <button
                          key={value}
                          type="button"
                          aria-pressed={filter === value}
                          onClick={() => {
                            setFilter(value);
                            setPage(0);
                          }}
                          className={filter === value ? "selected" : ""}
                        >
                          {value === "substantive"
                            ? "Material first"
                            : value === "all"
                              ? "All exact changes"
                              : label(value)}
                        </button>
                      ),
                    )}
                  </div>
                  <label className="checkbox-label !text-xs">
                    <input
                      type="checkbox"
                      checked={context}
                      onChange={(event) => {
                        setContext(event.target.checked);
                        setPage(0);
                      }}
                    />
                    Show unchanged context
                  </label>
                </div>
                {changes.length > 0 && (
                  <div className="change-navigation">
                    <label htmlFor="jump-change">Jump to a change</label>
                    <select
                      id="jump-change"
                      value=""
                      onChange={(event) => jump(event.target.value)}
                    >
                      <option value="" disabled>
                        Select passage…
                      </option>
                      {changes.map((item, index) => (
                        <option key={item.id} value={item.id}>
                          {index + 1}. {label(item.kind)} —{" "}
                          {(item.new?.text || item.old?.text || "").slice(
                            0,
                            100,
                          )}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="diff-legend">
                  <span>
                    <del>Removed wording</del>
                  </span>
                  <span>
                    <ins>Added wording</ins>
                  </span>
                  <span className="muted">
                    Unchanged wording stays neutral.
                  </span>
                </div>
                {!data.diff.changed && (
                  <div className="unchanged-state">
                    <Check size={24} />
                    <h2>No text changes.</h2>
                    <p>
                      These versions contain the same normalised text. Enable
                      unchanged context to read it.
                    </p>
                  </div>
                )}
                {data.diff.changed && items.length === 0 && (
                  <div className="unchanged-state">
                    <Check size={24} />
                    <h2>
                      {filter === "substantive" && !classificationAvailable
                        ? "Meaningful-change classification unavailable"
                        : filter === "substantive"
                          ? "No substantive wording change detected"
                          : "No passages match this filter"}
                    </h2>
                    <p>
                      {filter === "substantive" && !classificationAvailable
                        ? "This older saved comparison has not been classified. Review All exact changes or create a fresh comparison before using AI."
                        : filter === "substantive"
                          ? `${hiddenExactChangeCount} formatting or renumbering ${hiddenExactChangeCount === 1 ? "difference remains" : "differences remain"} available under All exact changes. No model request is needed.`
                          : "Choose another filter to continue reviewing the exact comparison."}
                    </p>
                  </div>
                )}
                {filter === "substantive" && data.diff.change_clusters?.length ? (
                  <div className="semantic-clusters">
                    {data.diff.change_clusters.map((cluster, index) => {
                      const clusterItems = cluster.change_ids
                        .map((changeId) => changes.find((item) => item.id === changeId))
                        .filter((item): item is Change => !!item);
                      const first = clusterItems[0];
                      return (
                        <article key={cluster.id}>
                          <div className="semantic-cluster-heading">
                            <span>Change group {index + 1}</span>
                            <strong>{cluster.change_ids.length} exact change{cluster.change_ids.length === 1 ? "" : "s"}</strong>
                          </div>
                          <p>{cluster.classifications.map(label).join(" · ")}</p>
                          <p className="semantic-cluster-units">
                            Before: {cluster.old_unit_ids[0] || "no earlier unit"} · After: {cluster.new_unit_ids[0] || "no current unit"}
                          </p>
                          <p>{(first?.new?.text || first?.old?.text || "Saved legal-unit change").slice(0, 260)}</p>
                          {cluster.ambiguous && <span className="needs-review-label">Needs review · uncertain match</span>}
                          {first && (
                            <Button size="sm" variant="outline" onClick={() => jump(first.id)}>
                              <FileText size={13} /> View exact evidence
                            </Button>
                          )}
                        </article>
                      );
                    })}
                  </div>
                ) : (
                  <div className="diff-rows">
                    {visible.map((item) => (
                      <div
                        id={item.id}
                        className={
                          "diff-row diff-" +
                          item.kind +
                          (jumpTarget === item.id ? " diff-focused" : "")
                        }
                        key={item.id}
                      >
                        <DiffSide item={item} side="old" version={data.old_version} />
                        <DiffSide item={item} side="new" version={data.new_version} />
                      </div>
                    ))}
                  </div>
                )}
                {filter !== "substantive" && items.length > 0 && (
                  <div className="pagination">
                    <span>
                      {page * PAGE_SIZE + 1}–
                      {Math.min((page + 1) * PAGE_SIZE, items.length)} of{" "}
                      {items.length} passages
                    </span>
                    <div className="flex gap-2 items-center">
                      <Button
                        variant="outline"
                        size="icon-sm"
                        aria-label="Previous passages"
                        onClick={() =>
                          setPage((value) => Math.max(0, value - 1))
                        }
                        disabled={page === 0}
                      >
                        <ChevronLeft />
                      </Button>
                      <span>
                        {page + 1} / {pages}
                      </span>
                      <Button
                        variant="outline"
                        size="icon-sm"
                        aria-label="Next passages"
                        onClick={() =>
                          setPage((value) => Math.min(pages - 1, value + 1))
                        }
                        disabled={page >= pages - 1}
                      >
                        <ChevronRight />
                      </Button>
                    </div>
                  </div>
                )}
              </section>
            </div>
            <aside className="analysis-column">
              <section className="panel impact-panel">
                <div className="panel-header">
                  <div className="flex items-center gap-2">
                    <Sparkles size={18} className="text-primary" />
                    <h2>Current impact report</h2>
                  </div>
                  {analysis?.result && (
                    <Status value={analysis.result.impact} />
                  )}
                </div>
                <div className="panel-body">
                  <span className="eyebrow">WHAT CHANGED · WHY IT MAY MATTER · REVIEW PLAN</span>
                  {analysisNotice && (
                    <div className="analysis-notice" role="status" aria-live="polite">
                      <Bell size={15} /> {analysisNotice}
                    </div>
                  )}
                  {!health?.apertus.configured && (
                    <div className="model-unavailable">
                      <Sparkles size={25} />
                      <h3>Connect Apertus to explain this change.</h3>
                      <p>
                        The source text and visual diff already work. Open
                        Settings to connect your model endpoint and generate an
                        actual assessment.
                      </p>
                      <span>No AI response has been generated.</span>
                      <Button
                        asChild
                        variant="outline"
                        size="sm"
                        className="mt-3"
                      >
                        <Link href="/settings">Configure Apertus</Link>
                      </Button>
                    </div>
                  )}
                  {identityBlocked && (
                    <div className="historical-note">
                      Impact analysis is unavailable until the document mismatch
                      above is resolved.
                    </div>
                  )}
                  {analysis?.stale && (
                    <div className="historical-note">
                      This assessment used earlier profile or model settings.
                      Rerun it before relying on its impact rating.
                    </div>
                  )}
                  {analysis?.latest_attempt?.status === "failed" && (
                    <div className="historical-note">
                      The latest rerun failed, so this last valid report remains
                      visible. Open AI history for the failed attempt.
                    </div>
                  )}
                  {analysisJobActive && effectiveAnalysisJob && (
                    <AnalysisJobProgress job={effectiveAnalysisJob} onCancel={cancelAnalysis} />
                  )}
                  {!analysisJobActive && effectiveAnalysisJob && (
                    <AnalysisJobOutcome job={effectiveAnalysisJob} />
                  )}
                  {analysis?.status === "succeeded" && analysis.result ? (
                    <>
                      <div className="impact-report-heading">
                        <span className="eyebrow">WHAT CHANGED</span>
                        <h3>{analysis.result.headline || analysis.result.summary}</h3>
                      </div>
                      <p className="impact-summary">
                        {analysis.result.summary}
                      </p>
                      <p className="text-sm muted">
                        {analysis.result.reason}{" "}
                        <Citations values={analysis.result.citations} />
                      </p>
                      {analysis.result.evidence_grade && (
                        <div className="impact-grade-line">
                          <span>
                            Potential severity:{" "}
                            {localLabel(
                              analysis.result.materiality || analysis.result.impact,
                              uiLocale,
                            )}
                          </span>
                          <span>
                            Evidence: {localLabel(analysis.result.evidence_grade, uiLocale)}
                          </span>
                        </div>
                      )}
                      <div className="area-tags">
                        {analysis.result.business_areas.map((area) => (
                          <span key={area}>{area}</span>
                        ))}
                      </div>
                      {!!analysis.result.material_changes?.length && (
                        <div className="impact-report-section">
                          <span className="eyebrow">MATERIAL CHANGE CARDS</span>
                          <div className="impact-change-list">
                            {analysis.result.material_changes.map((change) => (
                              <article key={change.change_id}>
                                <div className="impact-change-title">
                                  <strong>{change.title}</strong>
                                  <span>{localLabel(change.evidence_grade, uiLocale)}</span>
                                </div>
                                <p>
                                  {change.old_unit?.label || "No earlier unit"}{" "}
                                  →{" "}
                                  {change.new_unit?.label || "No current unit"}
                                </p>
                                <p>{change.explanation}</p>
                                <p className="material-card-meta">
                                  Organization relevance: {localLabel(
                                    analysis.result!.organization_applicability?.status || "unknown",
                                    uiLocale,
                                  )}
                                  {analysis.result!.important_dates?.length
                                    ? ` · ${analysis.result!.important_dates.length} date or obligation finding${analysis.result!.important_dates.length === 1 ? "" : "s"}`
                                    : " · No supported date or obligation found"}
                                </p>
                                <p className="material-card-meta">
                                  Dates / obligations: {analysis.result!.important_dates?.length
                                    ? analysis.result!.important_dates
                                        .map((item) => `${item.label}: ${item.date || label(item.status)}`)
                                        .join("; ")
                                    : "None supported by the saved evidence"}
                                </p>
                                <p className="material-card-meta">
                                  Assumptions: {analysis.result!.uncertainties?.length
                                    ? analysis.result!.uncertainties.join("; ")
                                    : "None recorded"}
                                </p>
                                <Citations values={change.citations} />
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  className="mt-2"
                                  onClick={() => jump(change.change_id)}
                                >
                                  <FileText size={13} /> View exact evidence
                                </Button>
                              </article>
                            ))}
                          </div>
                        </div>
                      )}
                      {analysis.result.organization_applicability && (
                        <div className="impact-report-section">
                          <span className="eyebrow">WHY IT MAY MATTER</span>
                          <div className="impact-applicability">
                            <strong>
                              {localLabel(
                                analysis.result.organization_applicability
                                  .status,
                                uiLocale,
                              )}
                            </strong>
                            <span>
                              Evidence:{" "}
                              {localLabel(
                                analysis.result.organization_applicability
                                  .evidence_grade,
                                uiLocale,
                              )}
                            </span>
                            <p>
                              {
                                analysis.result.organization_applicability
                                  .explanation
                              }{" "}
                              <Citations
                                values={
                                  analysis.result.organization_applicability
                                    .citations
                                }
                              />
                            </p>
                          </div>
                        </div>
                      )}
                      {!!analysis.result.important_dates?.length && (
                        <div className="impact-report-section">
                          <span className="eyebrow">DATES & DEADLINES</span>
                          <div className="impact-date-list">
                            {analysis.result.important_dates.map((item) => (
                              <div key={item.kind + item.label}>
                                <strong>{item.label}</strong>
                                <span>{item.date || label(item.status)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {!!analysis.result.uncertainties?.length && (
                        <details className="impact-uncertainties">
                          <summary>Assumptions and unknowns</summary>
                          <ul>
                            {analysis.result.uncertainties.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </details>
                      )}
                      {analysis.result.actions.length > 0 ? (
                        <>
                          <div className="action-heading">
                            <span className="eyebrow">REVIEW PLAN</span>
                            <h3>Suggested review actions</h3>
                          </div>
                          <ol className="action-list">
                            {analysis.result.actions.map((action, index) => (
                              <li key={action.action_key || index}>
                                <span>{index + 1}</span>
                                <div>
                                  <strong>{action.title || action.text}</strong>
                                  {action.rationale && (
                                    <p>{action.rationale}</p>
                                  )}
                                  {action.owner_role && (
                                    <p className="action-meta">
                                      Owner: {action.owner_role} · Area:{" "}
                                      {action.affected_area} · Priority:{" "}
                                      {action.priority} · Due:{" "}
                                      {action.due_date || action.due_basis}
                                    </p>
                                  )}
                                  {action.applicability_condition && (
                                    <p className="action-condition">
                                      Apply when:{" "}
                                      {action.applicability_condition}
                                    </p>
                                  )}
                                  <Citations values={action.citations} />
                                  {action.action_key && (
                                    <ReviewActionControls
                                      comparisonId={id}
                                      analysisId={analysis.id}
                                      action={action}
                                      current={analysis.action_decisions?.current?.[action.action_key]}
                                      history={analysis.action_decisions?.history?.filter(
                                        (item) => item.action_key === action.action_key,
                                      ) || []}
                                      canManage={canManage}
                                    />
                                  )}
                                </div>
                              </li>
                            ))}
                          </ol>
                        </>
                      ) : (
                        <div className="action-empty">
                          <span className="eyebrow">KNOW WHAT TO DO</span>
                          <strong>No concrete action established</strong>
                          <p>
                            The evidence did not support a specific task. Refine
                            the company profile or ask about applicability
                            before changing a process.
                          </p>
                        </div>
                      )}
                      <ReportProvenance analysis={analysis} comparison={data} />
                    </>
                  ) : (
                    !analysisJobActive && health?.apertus.configured && (
                      <p className="text-sm muted">
                        {!data.diff.changed
                          ? "There are no changes to assess. You can still ask questions about this document."
                          : !classificationAvailable
                            ? "Create a fresh comparison to classify the exact changes before asking AI for impact."
                            : hasMeaningfulChanges
                              ? "Analyse the bounded dossier of substantive and uncertain changes against your company profile."
                              : "The exact differences are formatting or renumbering only. No AI analysis is needed."}
                      </p>
                    )
                  )}
                  <ErrorNote message={error || analysis?.error} />
                  {canManage && (
                    <Button
                      className="w-full mt-3"
                      variant="outline"
                      disabled={
                        analysisJobActive ||
                        (analysis?.status === "succeeded" && !analysis.stale && effectiveAnalysisJob?.state === "succeeded") ||
                        !health?.apertus.configured ||
                        identityBlocked ||
                        !canAnalyseMeaningfulChanges
                      }
                      onClick={analyse}
                    >
                      {analysisJobActive ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <Sparkles />
                      )}
                      {analysis?.stale || analysis?.status === "failed" || effectiveAnalysisJob?.state === "failed"
                        ? "Retry impact analysis"
                        : analysis?.status === "succeeded"
                          ? "Current report saved"
                          : "Analyse with Apertus"}
                    </Button>
                  )}
                  <p className="review-note">
                    Indicative impact and actions support your review. Check the
                    evidence before making a legal or business decision.
                  </p>
                </div>
              </section>
              {identityBlocked ? (
                <section className="panel ask-panel">
                  <div className="panel-header">
                    <h2 className="flex items-center gap-2">
                      <MessageSquare size={17} />
                      Ask Apertus
                    </h2>
                  </div>
                  <div className="panel-body">
                    <div className="historical-note" role="status">
                      Questions and saved AI history are hidden until the
                      document mismatch is resolved.
                    </div>
                  </div>
                </section>
              ) : (
                <>
                  {canManage && (
                    <AskPanel
                      comparisonId={id}
                      configured={!!health?.apertus.configured}
                    />
                  )}
                  <AIHistory comparisonId={id} compact />
                </>
              )}
            </aside>
          </div>
        </>
      )}
    </Shell>
  );
}

function VersionCard({ version, side }: { version: Version; side: string }) {
  return (
    <div className="version-card">
      <div className="flex justify-between gap-2">
        <span className="eyebrow">{side}</span>
        <span className="text-xs muted">{version.id.slice(0, 8)}</span>
      </div>
      <strong>{version.declared_date || "Version date unknown"}</strong>
      <p>
        {label(version.origin)} ·{" "}
        {version.declared_date
          ? "date supplied by user"
          : "no verified publication date"}
        {version.synthetic ? " · synthetic demo" : ""}
      </p>
      <p>First saved {dateTime(version.created_at)}</p>
      <Link href={"/evidence/" + version.id} className="text-link">
        <FileText size={12} />
        Read saved evidence
        <ArrowUpRight size={12} />
      </Link>
    </div>
  );
}

function DiffSide({
  item,
  side,
  version,
}: {
  item: Change;
  side: "old" | "new";
  version: Version;
}) {
  const passage = side === "old" ? item.old : item.new;
  const parts = side === "old" ? item.old_parts : item.new_parts;
  return (
    <div
      className={"diff-side diff-side-" + side}
      lang={version.identity_json?.language || undefined}
    >
      <div className="passage-meta">
        <span>
          {side === "old" ? "BEFORE" : "AFTER"} ·{" "}
          {label(item.classification || item.change_type || item.kind)}
        </span>
        {passage && (
          <Link
            href={"/evidence/" + version.id + "?passage=" + passage.id}
            target="_blank"
          >
            {passage.page ? "Page " + passage.page + " · " : ""}
            {passage.id}
            <ArrowUpRight size={10} />
          </Link>
        )}
      </div>
      {passage ? (
        <p>
          {parts.map((part, index) =>
            part.kind === "removed" ? (
              <del key={index}>{part.text}</del>
            ) : part.kind === "added" ? (
              <ins key={index}>{part.text}</ins>
            ) : (
              <span key={index}>{part.text}</span>
            ),
          )}
        </p>
      ) : (
        <p className="no-passage">No passage on this side</p>
      )}
    </div>
  );
}

function AnalysisJobProgress({ job, onCancel }: { job: Job; onCancel: () => void }) {
  const { locale: productLocale } = useI18n();
  const locale = productLocale.slice(0, 2) as ComparisonLocale;
  const activeStep = job.steps.find((step) => step.state === "running") ||
    job.steps.find((step) => step.state === "pending");
  const state = (() => {
    if (["queued", "dispatched", "retrying", "waiting_for_model"].includes(job.state))
      return job.queue_position
        ? `Queued · position ${job.queue_position}; start estimate is not yet available`
        : "Queued · waiting for an available local AI slot";
    if (activeStep?.position === 1) return "Preparing changes";
    if (activeStep?.position === 2)
      return `Analysing ${activeStep.progress.current}/${activeStep.progress.total} evidence groups`;
    if (activeStep?.position === 3) return "Validating evidence";
    return localLabel(job.state, locale);
  })();
  const percent = Math.round(
    (Math.max(0, job.progress.current) / Math.max(1, job.progress.total)) * 100,
  );
  return (
    <div className="analysis-job" role="status" aria-live="polite">
      <div className="analysis-job-title">
        <Loader2 className="animate-spin" size={17} />
        <div>
          <strong>{state}</strong>
          <span>Saved background job · attempt {job.attempts}/{job.max_attempts}</span>
        </div>
      </div>
      <div
        className="analysis-job-track"
        role="progressbar"
        aria-label={state}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      <p>
        The deterministic overview and exact evidence remain usable. Refreshing or leaving
        this page will not cancel the job.
      </p>
      <Button type="button" size="sm" variant="outline" onClick={onCancel}>
        <XCircle size={14} /> Cancel analysis
      </Button>
    </div>
  );
}

function AnalysisJobOutcome({ job }: { job: Job }) {
  const { locale: productLocale } = useI18n();
  const locale = productLocale.slice(0, 2) as ComparisonLocale;
  const result = job.result?.data as Analysis | undefined;
  const state =
    job.state === "succeeded"
      ? result?.coverage?.limited
        ? "limited"
        : "ready"
      : job.state;
  return (
    <div className={`analysis-job-outcome ${state}`} role="status">
      <strong>{localLabel(state, locale)}</strong>
      <span>
        {job.finished_at ? dateTime(job.finished_at) : dateTime(job.updated_at)}
        {job.error?.detail ? ` · ${job.error.detail}` : " · saved background job"}
      </span>
    </div>
  );
}

function ReviewActionControls({
  comparisonId,
  analysisId,
  action,
  current,
  history,
  canManage,
}: {
  comparisonId: string;
  analysisId: string;
  action: Impact["actions"][number];
  current?: ActionDecision;
  history: ActionDecision[];
  canManage: boolean;
}) {
  const { locale: productLocale } = useI18n();
  const locale = productLocale.slice(0, 2) as ComparisonLocale;
  const [saved, setSaved] = useState<ActionDecision | undefined>(current);
  const [events, setEvents] = useState(history);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    setSaved(current);
    setEvents(history);
  }, [current, history]);
  async function decide(decision: ActionDecision["decision"]) {
    let assigned_to: string | null = null;
    let scheduled_for: string | null = null;
    let rationale: string | null = null;
    if (decision === "assigned") {
      assigned_to = window.prompt("Assign this review action to", action.owner_role || "")?.trim() || null;
      if (!assigned_to) return;
    }
    if (decision === "scheduled") {
      const date = window.prompt("Schedule review for (YYYY-MM-DD)", action.due_date || "")?.trim();
      if (!date) return;
      const localDate = new Date(`${date}T09:00:00`);
      if (Number.isNaN(localDate.getTime())) {
        setError("Use a valid date in YYYY-MM-DD format.");
        return;
      }
      scheduled_for = localDate.toISOString();
    }
    if (["dismissed", "not_applicable"].includes(decision)) {
      rationale = window.prompt("Record the reason for your organization")?.trim() || null;
      if (!rationale) return;
    }
    setBusy(decision);
    setError("");
    try {
      const page = await api<{ current: Record<string, ActionDecision>; history: ActionDecision[] }>(
        `/comparisons/${comparisonId}/analyses/${analysisId}/actions/${encodeURIComponent(action.action_key || "")}/decisions`,
        {
          method: "POST",
          body: JSON.stringify({ decision, assigned_to, scheduled_for, rationale }),
        },
      );
      setSaved(page.current[action.action_key || ""]);
      setEvents(page.history.filter((item) => item.action_key === action.action_key));
      refreshWorkspace();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  return (
    <div className="review-action-controls">
      {saved && (
        <div className="action-decision-current" role="status">
          <strong>{localLabel(saved.decision, locale)}</strong>
          <span>
            {saved.assigned_to ? ` · ${saved.assigned_to}` : ""}
            {saved.scheduled_for ? ` · ${dateTime(saved.scheduled_for)}` : ""}
            {` · ${saved.actor_label}, ${dateTime(saved.created_at)}`}
          </span>
          {saved.rationale && <p>{saved.rationale}</p>}
        </div>
      )}
      {canManage && (
        <div className="action-decision-buttons" aria-label="Review action decision">
          <Button size="sm" variant="outline" disabled={!!busy} onClick={() => decide("accepted")}>
            <Check size={13} /> Accept
          </Button>
          <Button size="sm" variant="outline" disabled={!!busy} onClick={() => decide("assigned")}>
            <UserRound size={13} /> Assign
          </Button>
          <Button size="sm" variant="outline" disabled={!!busy} onClick={() => decide("scheduled")}>
            <CalendarClock size={13} /> Schedule
          </Button>
          <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => decide("dismissed")}>
            Dismiss
          </Button>
          <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => decide("not_applicable")}>
            Not applicable
          </Button>
        </div>
      )}
      {error && <ErrorNote message={error} />}
      {events.length > 1 && (
        <details className="action-decision-history">
          <summary>{events.length} recorded decisions</summary>
          <ol>
            {events.map((item) => (
              <li key={item.id}>
                {localLabel(item.decision, locale)} · {item.actor_label} · {dateTime(item.created_at)}
                {item.rationale ? ` — ${item.rationale}` : ""}
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}

function ReportProvenance({ analysis, comparison }: { analysis: Analysis; comparison: Comparison }) {
  const provenance = analysis.provenance || {};
  const execution = analysis.analysis_plan?.execution;
  const outputLocale = analysis.result?.output_locale || "not recorded";
  return (
    <div className="report-provenance">
      <div className="report-provenance-title">
        <ListChecks size={15} />
        <strong>Report provenance</strong>
        <a href="#ai-history">Prior reports</a>
      </div>
      <dl>
        <div><dt>Generated</dt><dd>{dateTime(analysis.created_at)}</dd></div>
        <div><dt>Versions</dt><dd>{comparison.old_version.id.slice(0, 8)} → {comparison.new_version.id.slice(0, 8)}</dd></div>
        <div><dt>Profile</dt><dd>revision {execution?.profile_revision ?? "not recorded"}</dd></div>
        <div><dt>Model/runtime</dt><dd>{analysis.model} · {String(provenance.runtime_version || provenance.backend || "not recorded")}</dd></div>
        <div><dt>Prompt / locale</dt><dd>revision {analysis.prompt_revision} · {outputLocale}</dd></div>
      </dl>
      <CoverageNote coverage={analysis.coverage} />
      <PlanNote plan={analysis.analysis_plan} />
    </div>
  );
}

function CoverageNote({ coverage }: { coverage?: Partial<Coverage> }) {
  if (!coverage) return null;
  if (coverage.material_items !== undefined) {
    return (
      <div
        className={coverage.limited ? "coverage-note limited" : "coverage-note"}
      >
        {coverage.limited ? "Limited AI review: " : "AI review: "}
        {coverage.reviewed_material_items ?? 0} of {coverage.material_items}{" "}
        meaningful change units
        {coverage.suppressed_non_material_items
          ? ` · ${coverage.suppressed_non_material_items} formatting or structural differences kept out of model context`
          : ""}
        {coverage.provider_calls !== undefined
          ? ` · ${coverage.provider_calls} model ${coverage.provider_calls === 1 ? "call" : "calls"}`
          : ""}
        . {coverage.scope}
      </div>
    );
  }
  if (!coverage.available_passages) return null;
  return (
    <div
      className={coverage.limited ? "coverage-note limited" : "coverage-note"}
    >
      {coverage.limited ? "Limited context: " : "Evidence reviewed: "}
      {coverage.included_passages ?? 0} of {coverage.available_passages}{" "}
      passages · {(coverage.included_characters ?? 0).toLocaleString()}{" "}
      characters
      {coverage.provider_calls !== undefined
        ? ` · ${coverage.provider_calls} model ${coverage.provider_calls === 1 ? "call" : "calls"}`
        : ""}
      . {coverage.scope}
    </div>
  );
}

function PlanNote({ plan }: { plan?: AnalysisPlan }) {
  if (!plan?.limits) return null;
  const actual = plan.actual;
  const usage = actual?.token_counts || {};
  const tokenTotal = Object.values(usage).reduce(
    (sum, value) => sum + value,
    0,
  );
  const repairs = Number(actual?.validation?.repair_count || 0);
  return (
    <p className="coverage-note mb-0">
      Fixed plan: {plan.estimates.planned_generation_calls} expected ·{" "}
      {plan.actual?.provider_calls ?? 0} actual model calls · hard limit{" "}
      {plan.limits.provider_call_budget}. {plan.execution.batch_count} evidence{" "}
      {plan.execution.batch_count === 1 ? "group" : "groups"};{" "}
      {plan.coverage.limited ? "limited" : "complete"} planned coverage
      {actual
        ? ` · queue ${Math.round(actual.queue_wait_ms)} ms · inference ${Math.round(actual.inference_duration_ms)} ms`
        : ""}
      {tokenTotal ? ` · ${tokenTotal.toLocaleString()} recorded tokens` : ""}
      {actual
        ? ` · ${repairs} validation ${repairs === 1 ? "repair" : "repairs"}`
        : ""}
      .
    </p>
  );
}

const askPrompts: Record<string, string[]> = {
  en: [
    "Explain the material changes simply",
    "Does this affect our organization?",
    "Show new obligations or deadlines",
    "Create a review checklist",
  ],
  de: [
    "Erkläre die wesentlichen Änderungen einfach",
    "Betrifft das unsere Organisation?",
    "Zeige neue Pflichten oder Fristen",
    "Erstelle eine Prüfliste",
  ],
  fr: [
    "Explique simplement les changements essentiels",
    "Cela concerne-t-il notre organisation ?",
    "Montre les nouvelles obligations ou échéances",
    "Crée une liste de vérification",
  ],
  it: [
    "Spiega semplicemente le modifiche essenziali",
    "Questo riguarda la nostra organizzazione?",
    "Mostra nuovi obblighi o scadenze",
    "Crea una lista di controllo",
  ],
  rm: [
    "Declera simplamain las midadas essenzialas",
    "Ha quai in effect sin nossa organisaziun?",
    "Mussa novas obligaziuns u termins",
    "Crea ina glista da controlla",
  ],
};

function AskPanel({
  comparisonId,
  configured,
  blockedReason,
}: {
  comparisonId: string;
  configured: boolean;
  blockedReason?: string;
}) {
  const { locale } = useI18n();
  const [question, setQuestion] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const promptLocale = askPrompts[locale.slice(0, 2)] ? locale.slice(0, 2) : "en";
  const savedHistory = useResource<AIHistoryPage>(
    `/comparisons/${comparisonId}/ai-history`,
    5000,
  );
  const history = (savedHistory.data?.items || [])
    .filter((item) => item.type === "question")
    .sort(
      (left, right) =>
        new Date(right.last_used_at || right.created_at).getTime() -
        new Date(left.last_used_at || left.created_at).getTime(),
    )
    .slice(0, 20)
    .reverse();
  const ready = configured && !blockedReason;
  const quickQuestions = askPrompts[promptLocale];
  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const submittedQuestion = question.trim();
      const queued = await api<Job>(
        "/comparisons/" + comparisonId + "/ask-jobs",
        {
          method: "POST",
          body: JSON.stringify({
            question: submittedQuestion,
            output_locale: locale,
            history: history
              .filter((item) => item.status === "succeeded")
              .slice(-4)
              .map((item) => {
                const prior = item.result as Answer | null;
                return {
                  question: item.question,
                  answer: prior?.answer,
                  citations: prior?.citations || [],
                };
              }),
          }),
        },
      );
      const job = await waitForJob(queued);
      if (job.state !== "succeeded")
        throw new Error(
          job.error?.detail || "Apertus could not answer this question.",
        );
      const answer = job.result?.data as Answer | undefined;
      if (!answer) throw new Error("The saved job did not include an answer.");
      setQuestion("");
      setNotice(
        answer.cached
          ? "Loaded the saved answer. No new provider request was made."
          : "Answer saved to this comparison's AI history.",
      );
      savedHistory.reload();
      refreshWorkspace();
    } catch (cause) {
      setError(errorText(cause));
      savedHistory.reload();
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel ask-panel">
      <div className="panel-header">
        <h2 className="flex items-center gap-2">
          <MessageSquare size={17} />
          Ask Apertus
        </h2>
        <span className="text-xs muted">This comparison</span>
      </div>
      <div className="panel-body">
        <p className="text-xs muted mt-0">
          Ask about the current wording, the earlier version, or what changed.
          Answers link to the exact saved evidence.
        </p>
        <div className="chat-history" aria-live="polite">
          {history.map((item) => (
            <SavedQuestionTurn
              item={item}
              key={item.id}
              onSuggestion={setQuestion}
            />
          ))}
        </div>
        {savedHistory.loading && !savedHistory.data && (
          <Loading text="Loading saved questions…" />
        )}
        <ErrorNote message={savedHistory.error} />
        {blockedReason && <ErrorNote message={blockedReason} />}
        <div
          className="ask-intents"
          role="group"
          aria-label="Suggested questions"
        >
          {quickQuestions.map((value) => (
            <button
              type="button"
              disabled={!ready}
              className="suggested-question"
              onClick={() => setQuestion(value)}
              key={value}
            >
              {value}
              <ArrowRight size={13} />
            </button>
          ))}
        </div>
        <form onSubmit={ask}>
          <label className="sr-only" htmlFor="apertus-question">
            Question for Apertus
          </label>
          <Textarea
            id="apertus-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={
              ready
                ? "Ask about these versions…"
                : blockedReason || "Connect Apertus to ask a question"
            }
            disabled={!ready || busy}
            maxLength={2000}
            rows={3}
          />
          <ErrorNote message={error} />
          {notice && <p className="saved-answer-note">{notice}</p>}
          <Button
            type="submit"
            className="mt-3 w-full"
            disabled={!ready || busy || !question.trim()}
          >
            {busy ? <Loader2 className="animate-spin" /> : <Send />}
            {busy ? "Reviewing targeted evidence…" : "Ask with citations"}
          </Button>
        </form>
      </div>
    </section>
  );
}

function SavedQuestionTurn({
  item,
  onSuggestion,
}: {
  item: AIHistoryItem;
  onSuggestion: (value: string) => void;
}) {
  const answer = item.result as Pick<
    Answer,
    | "supported"
    | "answer"
    | "citations"
    | "suggestions"
    | "intent"
    | "context_mode"
    | "reused_impact_report_id"
  > | null;
  return (
    <div className="chat-turn">
      <p className="question-bubble">{item.question}</p>
      <div className="answer-bubble">
        {item.status === "failed" ? (
          <ErrorNote message={item.error || "This saved request failed."} />
        ) : answer ? (
          <>
            {!answer.supported && (
              <strong className="block mb-2">
                Not supported by the supplied evidence
              </strong>
            )}
            <p>{answer.answer}</p>
            <Citations values={answer.citations} />
            {answer.intent && answer.context_mode && (
              <p className="ask-answer-route">
                {answer.intent.replaceAll("_", " ")} ·{" "}
                {answer.context_mode === "impact_report"
                  ? "reused validated report · no model call"
                  : answer.context_mode.replaceAll("_", " ")}
              </p>
            )}
            {!!answer.suggestions?.length && (
              <div className="answer-suggestions">
                {answer.suggestions.map((suggestion) => (
                  <button
                    type="button"
                    key={suggestion}
                    onClick={() => onSuggestion(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
            <CoverageNote coverage={item.coverage} />
            <PlanNote plan={item.analysis_plan} />
            <p className="saved-answer-meta">
              {dateTime(item.created_at)} · {item.model}
              {item.use_count > 1
                ? ` · reused ${item.use_count - 1} ${item.use_count === 2 ? "time" : "times"}`
                : ""}
            </p>
          </>
        ) : (
          <Loading text="Apertus is answering…" />
        )}
      </div>
    </div>
  );
}
