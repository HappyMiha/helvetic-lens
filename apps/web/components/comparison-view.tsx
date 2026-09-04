"use client";

import { useEffect, useRef, useState } from "react";
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
  History as HistoryIcon,
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
  errorText,
  invalidateResources,
  label,
  mutateResource,
  mutateResourceForLocale,
  primeResourceForLocale,
  useResource,
} from "@/lib/api";
import { resources } from "@/lib/resource-keys";
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
  Citation,
  Impact,
  Job,
  Version,
} from "@/lib/types";
import { ErrorNote, Loading, Status } from "./common";
import { AIHistory } from "./ai-history";
import { Shell } from "./shell";
import { useAuth } from "./auth-gate";
import { storedLocale, translate, type Locale, useI18n } from "@/lib/i18n";

const PAGE_SIZE = 40;
const JOB_TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);
type ComparisonLocale = "de" | "fr" | "it" | "rm" | "en";
type CompanionTab = "summary" | "actions" | "ask" | "history";
const comparisonCopy = {
  en: {
    overview: "Deterministic change overview",
    material: "Material",
    reviewFirst: "Review first",
    addedRemoved: "Added / removed",
    newDeleted: "New or deleted units",
    movedRenumbered: "Moved / renumbered",
    structural: "Structural, kept out of AI",
    formatting: "Formatting only",
    hidden: "Hidden by default",
    needsReview: "Needs review",
    uncertain: "Uncertain match",
  },
  de: {
    overview: "Deterministische Änderungsübersicht",
    material: "Wesentlich",
    reviewFirst: "Zuerst prüfen",
    addedRemoved: "Hinzugefügt / entfernt",
    newDeleted: "Neue oder gelöschte Einheiten",
    movedRenumbered: "Verschoben / neu nummeriert",
    structural: "Strukturell, nicht an KI gesendet",
    formatting: "Nur Formatierung",
    hidden: "Standardmässig ausgeblendet",
    needsReview: "Prüfung nötig",
    uncertain: "Unsichere Zuordnung",
  },
  fr: {
    overview: "Aperçu déterministe des changements",
    material: "Essentiel",
    reviewFirst: "À examiner d’abord",
    addedRemoved: "Ajouté / supprimé",
    newDeleted: "Unités nouvelles ou supprimées",
    movedRenumbered: "Déplacé / renuméroté",
    structural: "Structurel, exclu de l’IA",
    formatting: "Mise en forme seulement",
    hidden: "Masqué par défaut",
    needsReview: "À vérifier",
    uncertain: "Correspondance incertaine",
  },
  it: {
    overview: "Panoramica deterministica delle modifiche",
    material: "Sostanziale",
    reviewFirst: "Da esaminare prima",
    addedRemoved: "Aggiunto / rimosso",
    newDeleted: "Unità nuove o eliminate",
    movedRenumbered: "Spostato / rinumerato",
    structural: "Strutturale, escluso dall’IA",
    formatting: "Solo formattazione",
    hidden: "Nascosto per impostazione predefinita",
    needsReview: "Da verificare",
    uncertain: "Corrispondenza incerta",
  },
  rm: {
    overview: "Survista deterministica da las midadas",
    material: "Essenzial",
    reviewFirst: "Examinar l’emprim",
    addedRemoved: "Agiuntà / eliminà",
    newDeleted: "Unitads novas u eliminadas",
    movedRenumbered: "Spustà / renumerà",
    structural: "Structural, exclus da l’IA",
    formatting: "Mo furmataziun",
    hidden: "Zuppentà tenor standard",
    needsReview: "Da verifitgar",
    uncertain: "Attribuziun intscherta",
  },
} satisfies Record<ComparisonLocale, Record<string, string>>;

const localizedValues: Record<ComparisonLocale, Record<string, string>> = {
  en: {
    confirmed: "Confirmed",
    supported: "Supported",
    possible: "Possible",
    needs_review: "Needs review",
    accepted: "Accepted",
    assigned: "Assigned",
    scheduled: "Scheduled",
    dismissed: "Dismissed",
    not_applicable: "Not applicable",
    ready: "Ready",
    limited: "Limited",
    failed: "Failed",
    cancelled: "Cancelled",
  },
  de: {
    confirmed: "Bestätigt",
    supported: "Belegt",
    possible: "Möglich",
    needs_review: "Prüfung nötig",
    accepted: "Angenommen",
    assigned: "Zugewiesen",
    scheduled: "Terminiert",
    dismissed: "Verworfen",
    not_applicable: "Nicht anwendbar",
    ready: "Bereit",
    limited: "Begrenzt",
    failed: "Fehlgeschlagen",
    cancelled: "Abgebrochen",
  },
  fr: {
    confirmed: "Confirmé",
    supported: "Étayé",
    possible: "Possible",
    needs_review: "À vérifier",
    accepted: "Accepté",
    assigned: "Attribué",
    scheduled: "Planifié",
    dismissed: "Écarté",
    not_applicable: "Non applicable",
    ready: "Prêt",
    limited: "Limité",
    failed: "Échec",
    cancelled: "Annulé",
  },
  it: {
    confirmed: "Confermato",
    supported: "Supportato",
    possible: "Possibile",
    needs_review: "Da verificare",
    accepted: "Accettato",
    assigned: "Assegnato",
    scheduled: "Pianificato",
    dismissed: "Scartato",
    not_applicable: "Non applicabile",
    ready: "Pronto",
    limited: "Limitato",
    failed: "Non riuscito",
    cancelled: "Annullato",
  },
  rm: {
    confirmed: "Confermà",
    supported: "Cumprovà",
    possible: "Pussaivel",
    needs_review: "Da verifitgar",
    accepted: "Acceptà",
    assigned: "Attribuì",
    scheduled: "Planisà",
    dismissed: "Refusà",
    not_applicable: "Betg applitgabel",
    ready: "Pront",
    limited: "Limità",
    failed: "Betg reussì",
    cancelled: "Interrut",
  },
};

function localLabel(value: string, locale: ComparisonLocale) {
  return localizedValues[locale][value] || label(value);
}

function completedAnalysis(job: Job): Analysis | null {
  const result = job.result?.data;
  if (
    job.state !== "succeeded" ||
    job.result?.type !== "analysis" ||
    !result ||
    typeof result !== "object"
  )
    return null;
  return result as Analysis;
}

export function ComparisonView({ id }: { id: string }) {
  const { canManage } = useAuth();
  const { locale, t, dateTime, number } = useI18n();
  const uiLocale = locale.slice(0, 2) as ComparisonLocale;
  const ui = comparisonCopy[uiLocale];
  const { data, error: loadError } = useResource<Comparison>(
    resources.comparison(id),
  );
  const { data: health } = useResource(resources.health());
  const [filter, setFilter] = useState("substantive"),
    [context, setContext] = useState(false),
    [page, setPage] = useState(0);
  const [jumpTarget, setJumpTarget] = useState(""),
    [jumpRevision, setJumpRevision] = useState(0),
    [analysisJobs, setAnalysisJobs] = useState<Partial<Record<Locale, Job>>>(
      {},
    ),
    [analysisNotice, setAnalysisNotice] = useState(""),
    [confirmingIdentity, setConfirmingIdentity] = useState(""),
    [error, setError] = useState("");
  const [companionTab, setCompanionTab] = useState<CompanionTab>("summary");
  const [mobileSurface, setMobileSurface] = useState<"evidence" | "companion">(
    "evidence",
  );
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
  const analysisJob = analysisJobs[locale] || null;
  const effectiveAnalysisJob = analysisJob || data?.analysis_job || null;
  const effectiveAnalysisJobLocale = locale;
  const analysisJobActive =
    !!effectiveAnalysisJob &&
    !JOB_TERMINAL_STATES.has(effectiveAnalysisJob.state);
  const polledAnalysisJob = useResource<Job>(
    analysisJobActive && effectiveAnalysisJob
      ? resources.job(effectiveAnalysisJob.id)
      : null,
  );
  useEffect(() => {
    setAnalysisJobs((current) => {
      const saved = data?.analysis_job || null;
      const local = current[locale] || null;
      if (!saved || saved === local) return current;
      if (
        local &&
        new Date(local.updated_at).getTime() >=
          new Date(saved.updated_at).getTime()
      )
        return current;
      return { ...current, [locale]: saved };
    });
  }, [data?.analysis_job, locale]);
  useEffect(() => {
    if (polledAnalysisJob.error) setError(polledAnalysisJob.error);
  }, [polledAnalysisJob.error]);
  useEffect(() => {
    const next = polledAnalysisJob.data;
    if (!next || next.id !== effectiveAnalysisJob?.id) return;
    setAnalysisJobs((current) => ({
      ...current,
      [effectiveAnalysisJobLocale]: next,
    }));
    if (!JOB_TERMINAL_STATES.has(next.state)) return;
    const completed = completedAnalysis(next);
    mutateResourceForLocale<Comparison>(
      resources.comparison(id),
      effectiveAnalysisJobLocale,
      (current) =>
        current
          ? {
              ...current,
              analysis_job: next,
              analysis: completed || current.analysis,
            }
          : current,
    );
    void invalidateResources(resources.comparisonHistory(id));
    if (
      next.state === "succeeded" &&
      storedLocale() === effectiveAnalysisJobLocale
    ) {
      setAnalysisNotice(t("compare.reportReady"));
      if (
        document.hidden &&
        "Notification" in window &&
        Notification.permission === "granted"
      )
        new Notification("Helvetic Lens", {
          body: t("compare.reportReadyShort"),
        });
    } else if (storedLocale() === effectiveAnalysisJobLocale) {
      setAnalysisNotice(
        t("compare.analysisEnded", {
          state: localLabel(next.state, uiLocale),
        }),
      );
    }
  }, [
    effectiveAnalysisJob?.id,
    effectiveAnalysisJobLocale,
    id,
    polledAnalysisJob.data,
    t,
    uiLocale,
  ]);
  useEffect(() => {
    if (!jumpTarget) return;
    const target = document.getElementById(jumpTarget);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
    target?.focus({ preventScroll: true });
  }, [jumpRevision, jumpTarget, page]);
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
    const requestLocale = locale;
    setError("");
    try {
      const queued = await api<Job>("/comparisons/" + id + "/analyse-jobs", {
        method: "POST",
        body: JSON.stringify({ output_locale: requestLocale }),
      });
      primeResourceForLocale(resources.job(queued.id), requestLocale, queued);
      setAnalysisJobs((current) => ({ ...current, [requestLocale]: queued }));
      mutateResourceForLocale<Comparison>(
        resources.comparison(id),
        requestLocale,
        (current) => (current ? { ...current, analysis_job: queued } : current),
      );
      if (storedLocale() === requestLocale) {
        setAnalysisNotice(
          JOB_TERMINAL_STATES.has(queued.state)
            ? t("compare.reportFinished")
            : t("compare.analysisSubmitted"),
        );
        if (queued.state === "failed")
          setError(queued.error?.detail || t("compare.analysisFailed"));
      }
      if (JOB_TERMINAL_STATES.has(queued.state)) {
        const completed = completedAnalysis(queued);
        mutateResourceForLocale<Comparison>(
          resources.comparison(id),
          requestLocale,
          (current) =>
            current
              ? {
                  ...current,
                  analysis_job: queued,
                  analysis: completed || current.analysis,
                }
              : current,
        );
        void invalidateResources(resources.comparisonHistory(id));
      }
    } catch (cause) {
      if (storedLocale() === requestLocale) setError(errorText(cause));
    }
  }
  async function cancelAnalysis() {
    if (!effectiveAnalysisJob) return;
    try {
      const cancelled = await api<Job>(
        `/jobs/${effectiveAnalysisJob.id}/cancel`,
        {
          method: "POST",
        },
      );
      primeResourceForLocale(
        resources.job(cancelled.id),
        effectiveAnalysisJobLocale,
        cancelled,
      );
      setAnalysisJobs((current) => ({
        ...current,
        [effectiveAnalysisJobLocale]: cancelled,
      }));
      if (storedLocale() === effectiveAnalysisJobLocale)
        setAnalysisNotice(t("compare.analysisCancelled"));
      mutateResourceForLocale<Comparison>(
        resources.comparison(id),
        effectiveAnalysisJobLocale,
        (current) =>
          current ? { ...current, analysis_job: cancelled } : current,
      );
      void invalidateResources(resources.comparisonHistory(id));
    } catch (cause) {
      if (storedLocale() === effectiveAnalysisJobLocale)
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
          note: t("compare.identityConfirmedNote"),
        }),
      });
      await invalidateResources(resources.comparison(id));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setConfirmingIdentity("");
    }
  }
  async function removeMistakenImport(versionId: string) {
    if (!window.confirm(t("compare.removeImportConfirm"))) return;
    setConfirmingIdentity(versionId);
    setError("");
    try {
      await api("/versions/" + versionId, { method: "DELETE" });
      window.location.href = "/laws/" + data?.law_id;
    } catch (cause) {
      setError(errorText(cause));
      setConfirmingIdentity("");
    }
  }
  function jump(value: string) {
    const target = data?.diff.items.find((item) => item.id === value);
    const includeContext = target?.kind === "unchanged";
    const targetItems =
      data?.diff.items.filter(
        (item) => includeContext || item.kind !== "unchanged",
      ) || [];
    setFilter("all");
    setContext(includeContext);
    setPage(
      Math.max(
        0,
        Math.floor(
          targetItems.findIndex((item) => item.id === value) / PAGE_SIZE,
        ),
      ),
    );
    setMobileSurface("evidence");
    setJumpTarget(value);
    setJumpRevision((current) => current + 1);
  }
  function openCompanion(tab: CompanionTab) {
    setCompanionTab(tab);
    setMobileSurface("companion");
  }
  return (
    <Shell section={t("compare.section")} wide>
      <Link className="back-link" href={data ? "/laws/" + data.law_id : "/"}>
        <ArrowLeft size={14} />
        {t("evidence.back")}
      </Link>
      <ErrorNote message={loadError} />
      {!data ? (
        !loadError && <Loading text={t("compare.loading")} />
      ) : (
        <>
          <div className="page-heading">
            <div>
              <span className="eyebrow">{t("compare.eyebrow")}</span>
              <h1>{data.law.name}</h1>
              <div className="flex flex-wrap gap-3 items-center text-xs muted">
                <Status value={data.mode} />
                <span>
                  {t("compare.savedAt", { date: dateTime(data.created_at) })}
                </span>
                {(data.old_version.synthetic || data.new_version.synthetic) && (
                  <span className="synthetic-label">
                    {t("compare.synthetic")}
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
                ? t("compare.historicalNotice")
                : t("compare.savedNotice")}
            </div>
          )}
          {identityBlocked && data.identity && (
            <div
              className="identity-warning identity-mismatch mb-6"
              role="alert"
            >
              <strong>
                {data.identity.effective_status === "mismatch"
                  ? t("compare.identityMismatch")
                  : t("compare.identityUnknown")}
              </strong>
              <p>
                {data.identity.effective_status === "verified"
                  ? t("identity.reason.comparison_verified")
                  : data.identity.effective_status === "probable"
                    ? t("identity.reason.comparison_probable")
                    : data.identity.effective_status === "mismatch"
                      ? t("identity.reason.comparison_mismatch")
                      : t("identity.reason.comparison_unknown")}
              </p>
              <p>
                {t("compare.tracked")}: <b>{data.law.name}</b>
                <br />
                {t("compare.detectedBefore")}:{" "}
                <b>
                  {data.identity.old.detected_identifier ||
                    data.identity.old.detected_title ||
                    t("compare.notIdentified")}
                </b>
                <br />
                {t("compare.detectedAfter")}:{" "}
                <b>
                  {data.identity.new.detected_identifier ||
                    data.identity.new.detected_title ||
                    t("compare.notIdentified")}
                </b>
              </p>
              <span>{t("compare.identityGateBody")}</span>
              <div className="flex flex-wrap gap-2 mt-3">
                <Button asChild variant="outline" size="sm">
                  <a href={data.old_version.artifact_url} target="_blank">
                    {t("compare.inspectBefore")} <ArrowUpRight />
                  </a>
                </Button>
                <Button asChild variant="outline" size="sm">
                  <a href={data.new_version.artifact_url} target="_blank">
                    {t("compare.inspectAfter")} <ArrowUpRight />
                  </a>
                </Button>
                <Button asChild variant="outline" size="sm">
                  <Link href={"/laws/" + data.law_id}>
                    {t("compare.attachAnother")}
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
                        {t("compare.removeImport", {
                          version: version.id.slice(0, 8),
                        })}
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
                        {t(
                          index === 0
                            ? "compare.confirmThis"
                            : "compare.confirmOther",
                        )}
                      </Button>
                    ))}
                </div>
              )}
            </div>
          )}
          <ComparisonWorkspaceTabs
            active={companionTab}
            evidenceActive={mobileSurface === "evidence"}
            includeEvidence
            canAsk={canManage}
            onEvidence={() => setMobileSurface("evidence")}
            onSelect={openCompanion}
          />
          <div
            className="comparison-layout"
            data-mobile-surface={mobileSurface}
          >
            <div
              className="comparison-evidence-pane min-w-0"
              id="comparison-evidence"
            >
              <section className="panel diff-panel">
                <div className="panel-header">
                  <h2>{t("compare.meaningful")}</h2>
                  <div className="diff-counts">
                    <span className="count-added">
                      + {number(data.diff.counts.added)} {t("status.added")}
                    </span>
                    <span className="count-removed">
                      − {number(data.diff.counts.removed)} {t("status.removed")}
                    </span>
                    <span>
                      {number(data.diff.counts.modified)} {t("status.modified")}
                    </span>
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
                  <VersionCard
                    version={data.old_version}
                    side={t("compare.beforeUpper")}
                  />
                  <VersionCard
                    version={data.new_version}
                    side={t("compare.afterUpper")}
                  />
                </div>
                <div className="diff-toolbar">
                  <div
                    className="segmented"
                    role="group"
                    aria-label={t("compare.filters")}
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
                            ? t("compare.materialFirst")
                            : value === "all"
                              ? t("compare.allChanges")
                              : translate(locale, `status.${value}`) ||
                                label(value)}
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
                    {t("compare.showContext")}
                  </label>
                </div>
                {changes.length > 0 && (
                  <div className="change-navigation">
                    <label htmlFor="jump-change">{t("compare.jump")}</label>
                    <select
                      id="jump-change"
                      value=""
                      onChange={(event) => jump(event.target.value)}
                    >
                      <option value="" disabled>
                        {t("compare.selectPassage")}
                      </option>
                      {changes.map((item, index) => (
                        <option key={item.id} value={item.id}>
                          {number(index + 1)}.{" "}
                          {translate(locale, `status.${item.kind}`) ||
                            label(item.kind)}{" "}
                          —{" "}
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
                    <del>{t("compare.removedWording")}</del>
                  </span>
                  <span>
                    <ins>{t("compare.addedWording")}</ins>
                  </span>
                  <span className="muted">{t("compare.neutralWording")}</span>
                </div>
                {!data.diff.changed && (
                  <div className="unchanged-state">
                    <Check size={24} />
                    <h2>{t("compare.noChanges")}</h2>
                    <p>{t("compare.sameText")}</p>
                  </div>
                )}
                {data.diff.changed && items.length === 0 && (
                  <div className="unchanged-state">
                    <Check size={24} />
                    <h2>
                      {filter === "substantive" && !classificationAvailable
                        ? t("compare.classificationUnavailable")
                        : filter === "substantive"
                          ? t("compare.noMaterial")
                          : t("compare.noFilterMatch")}
                    </h2>
                    <p>
                      {filter === "substantive" && !classificationAvailable
                        ? t("compare.classificationHelp")
                        : filter === "substantive"
                          ? t("compare.hiddenDifferences", {
                              count: number(hiddenExactChangeCount),
                            })
                          : t("compare.chooseFilter")}
                    </p>
                  </div>
                )}
                {filter === "substantive" &&
                data.diff.change_clusters?.length ? (
                  <div className="semantic-clusters">
                    {data.diff.change_clusters.map((cluster, index) => {
                      const clusterItems = cluster.change_ids
                        .map((changeId) =>
                          changes.find((item) => item.id === changeId),
                        )
                        .filter((item): item is Change => !!item);
                      const first = clusterItems[0];
                      return (
                        <article key={cluster.id}>
                          <div className="semantic-cluster-heading">
                            <span>
                              {t("compare.changeGroup", {
                                number: number(index + 1),
                              })}
                            </span>
                            <strong>
                              {t("compare.exactChangeCount", {
                                count: number(cluster.change_ids.length),
                              })}
                            </strong>
                          </div>
                          <p>
                            {cluster.classifications.map(label).join(" · ")}
                          </p>
                          <p className="semantic-cluster-units">
                            {t("compare.before")}:{" "}
                            {cluster.old_unit_ids[0] ||
                              t("compare.noEarlierUnit")}{" "}
                            · {t("compare.after")}:{" "}
                            {cluster.new_unit_ids[0] ||
                              t("compare.noCurrentUnit")}
                          </p>
                          <p>
                            {(
                              first?.new?.text ||
                              first?.old?.text ||
                              t("compare.savedUnitChange")
                            ).slice(0, 260)}
                          </p>
                          {cluster.ambiguous && (
                            <span className="needs-review-label">
                              {t("compare.needsReview")}
                            </span>
                          )}
                          {first && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => jump(first.id)}
                            >
                              <FileText size={13} /> {t("compare.viewEvidence")}
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
                        tabIndex={-1}
                        className={
                          "diff-row diff-" +
                          item.kind +
                          (jumpTarget === item.id ? " diff-focused" : "")
                        }
                        key={item.id}
                      >
                        <DiffSide
                          item={item}
                          side="old"
                          version={data.old_version}
                        />
                        <DiffSide
                          item={item}
                          side="new"
                          version={data.new_version}
                        />
                      </div>
                    ))}
                  </div>
                )}
                {filter !== "substantive" && items.length > 0 && (
                  <div className="pagination">
                    <span>
                      {t("evidence.range", {
                        start: number(page * PAGE_SIZE + 1),
                        end: number(
                          Math.min((page + 1) * PAGE_SIZE, items.length),
                        ),
                        total: number(items.length),
                      })}
                    </span>
                    <div className="flex gap-2 items-center">
                      <Button
                        variant="outline"
                        size="icon-sm"
                        aria-label={t("compare.previous")}
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
                        aria-label={t("compare.next")}
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
            {mobileSurface === "companion" && (
              <button
                type="button"
                className="comparison-drawer-backdrop"
                aria-label={t("common.close")}
                onClick={() => setMobileSurface("evidence")}
              />
            )}
            <aside
              className="analysis-column"
              aria-label={t("compare.currentReport")}
            >
              <div className="companion-nav-wrap">
                <ComparisonWorkspaceTabs
                  active={companionTab}
                  canAsk={canManage}
                  onSelect={openCompanion}
                />
                <button
                  type="button"
                  className="companion-close"
                  aria-label={t("common.close")}
                  onClick={() => setMobileSurface("evidence")}
                >
                  <XCircle size={18} />
                </button>
              </div>
              <section
                id="companion-summary"
                role="tabpanel"
                aria-label={t("compare.whatChanged")}
                hidden={companionTab !== "summary"}
                className="panel impact-panel companion-tab-panel"
              >
                <div className="panel-header">
                  <div className="flex items-center gap-2">
                    <Sparkles size={18} className="text-primary" />
                    <h2>{t("compare.currentReport")}</h2>
                  </div>
                  {analysis?.result && (
                    <Status value={analysis.result.impact} />
                  )}
                </div>
                <div className="panel-body">
                  <span className="eyebrow">{t("compare.reportFlow")}</span>
                  {analysisNotice && (
                    <div
                      className="analysis-notice"
                      role="status"
                      aria-live="polite"
                    >
                      <Bell size={15} /> {analysisNotice}
                    </div>
                  )}
                  {!health?.apertus.configured && (
                    <div className="model-unavailable">
                      <Sparkles size={25} />
                      <h3>{t("compare.connectApertus")}</h3>
                      <p>{t("compare.connectApertusBody")}</p>
                      <span>{t("compare.noAiResponse")}</span>
                      <Button
                        asChild
                        variant="outline"
                        size="sm"
                        className="mt-3"
                      >
                        <Link href="/settings">
                          {t("compare.configureApertus")}
                        </Link>
                      </Button>
                    </div>
                  )}
                  {identityBlocked && (
                    <div className="historical-note">
                      {t("compare.analysisBlocked")}
                    </div>
                  )}
                  {analysis?.stale && (
                    <div className="historical-note">
                      {t("compare.staleReport")}
                    </div>
                  )}
                  {analysis?.latest_attempt?.status === "failed" && (
                    <div className="historical-note">
                      {t("compare.rerunFailed")}
                    </div>
                  )}
                  {analysisJobActive && effectiveAnalysisJob && (
                    <AnalysisJobProgress
                      job={effectiveAnalysisJob}
                      onCancel={cancelAnalysis}
                    />
                  )}
                  {!analysisJobActive && effectiveAnalysisJob && (
                    <AnalysisJobOutcome job={effectiveAnalysisJob} />
                  )}
                  {analysis?.status === "succeeded" && analysis.result ? (
                    <>
                      <div className="impact-report-heading">
                        <span className="eyebrow">
                          {t("compare.whatChanged")}
                        </span>
                        <h3>
                          {analysis.result.headline || analysis.result.summary}
                        </h3>
                      </div>
                      <p className="impact-summary">
                        {analysis.result.summary}
                      </p>
                      <p className="text-sm muted">
                        {analysis.result.reason}{" "}
                        <ComparisonCitations
                          values={analysis.result.citations}
                          items={data.diff.items}
                          onEvidence={jump}
                        />
                      </p>
                      {analysis.result.evidence_grade && (
                        <div className="impact-grade-line">
                          <span>
                            {t("compare.potentialSeverity")}:{" "}
                            {localLabel(
                              analysis.result.materiality ||
                                analysis.result.impact,
                              uiLocale,
                            )}
                          </span>
                          <span>
                            {t("compare.evidence")}:{" "}
                            {localLabel(
                              analysis.result.evidence_grade,
                              uiLocale,
                            )}
                          </span>
                        </div>
                      )}
                      <div className="area-tags">
                        {analysis.result.business_areas.map((area) => (
                          <span key={area}>{area}</span>
                        ))}
                      </div>
                      {!!analysis.result.material_changes?.length && (
                        <details className="impact-details">
                          <summary>
                            <FileText size={14} />
                            {t("compare.materialCards")} ·{" "}
                            {number(analysis.result.material_changes.length)}
                          </summary>
                          <div className="impact-report-section">
                            <div className="impact-change-list">
                              {analysis.result.material_changes.map(
                                (change) => (
                                  <article key={change.change_id}>
                                    <div className="impact-change-title">
                                      <strong>{change.title}</strong>
                                      <span>
                                        {localLabel(
                                          change.evidence_grade,
                                          uiLocale,
                                        )}
                                      </span>
                                    </div>
                                    <p>
                                      {change.old_unit?.label ||
                                        t("compare.noEarlierUnit")}{" "}
                                      →{" "}
                                      {change.new_unit?.label ||
                                        t("compare.noCurrentUnit")}
                                    </p>
                                    <p>{change.explanation}</p>
                                    <p className="material-card-meta">
                                      {t("compare.organizationRelevance")}:{" "}
                                      {localLabel(
                                        analysis.result!
                                          .organization_applicability?.status ||
                                          "unknown",
                                        uiLocale,
                                      )}
                                      {analysis.result!.important_dates?.length
                                        ? ` · ${t("compare.dateFindingCount", { count: number(analysis.result!.important_dates.length) })}`
                                        : ` · ${t("compare.noDateFinding")}`}
                                    </p>
                                    <p className="material-card-meta">
                                      {t("compare.datesObligations")}:{" "}
                                      {analysis.result!.important_dates?.length
                                        ? analysis
                                            .result!.important_dates.map(
                                              (item) =>
                                                `${item.label}: ${item.date || translate(locale, `status.${item.status}`) || label(item.status)}`,
                                            )
                                            .join("; ")
                                        : t("compare.noneSupported")}
                                    </p>
                                    <p className="material-card-meta">
                                      {t("compare.assumptions")}:{" "}
                                      {analysis.result!.uncertainties?.length
                                        ? analysis.result!.uncertainties.join(
                                            "; ",
                                          )
                                        : t("compare.noneRecorded")}
                                    </p>
                                    <ComparisonCitations
                                      values={change.citations}
                                      items={data.diff.items}
                                      onEvidence={jump}
                                    />
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      className="mt-2"
                                      onClick={() => jump(change.change_id)}
                                    >
                                      <FileText size={13} />{" "}
                                      {t("compare.viewEvidence")}
                                    </Button>
                                  </article>
                                ),
                              )}
                            </div>
                          </div>
                        </details>
                      )}
                      {analysis.result.organization_applicability && (
                        <div className="impact-report-section">
                          <span className="eyebrow">
                            {t("compare.whyMatter")}
                          </span>
                          <div className="impact-applicability">
                            <strong>
                              {localLabel(
                                analysis.result.organization_applicability
                                  .status,
                                uiLocale,
                              )}
                            </strong>
                            <span>
                              {t("compare.evidence")}:{" "}
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
                              <ComparisonCitations
                                values={
                                  analysis.result.organization_applicability
                                    .citations
                                }
                                items={data.diff.items}
                                onEvidence={jump}
                              />
                            </p>
                          </div>
                        </div>
                      )}
                      {!!analysis.result.important_dates?.length && (
                        <div className="impact-report-section">
                          <span className="eyebrow">
                            {t("compare.datesDeadlines")}
                          </span>
                          <div className="impact-date-list">
                            {analysis.result.important_dates.map((item) => (
                              <div key={item.kind + item.label}>
                                <strong>{item.label}</strong>
                                <span>
                                  {item.date ||
                                    translate(
                                      locale,
                                      `status.${item.status}`,
                                    ) ||
                                    label(item.status)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {!!analysis.result.uncertainties?.length && (
                        <details className="impact-uncertainties">
                          <summary>{t("compare.assumptionsUnknowns")}</summary>
                          <ul>
                            {analysis.result.uncertainties.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </details>
                      )}
                      <ActionPreview
                        actions={analysis.result.actions}
                        onOpen={() => openCompanion("actions")}
                      />
                      <details className="impact-details provenance-disclosure">
                        <summary>
                          <ListChecks size={14} /> {t("compare.provenance")}
                        </summary>
                        <ReportProvenance
                          analysis={analysis}
                          comparison={data}
                          onHistory={() => openCompanion("history")}
                        />
                      </details>
                    </>
                  ) : (
                    !analysisJobActive &&
                    health?.apertus.configured && (
                      <p className="text-sm muted">
                        {!data.diff.changed
                          ? t("compare.noChangesAssess")
                          : !classificationAvailable
                            ? t("compare.freshComparison")
                            : hasMeaningfulChanges
                              ? t("compare.readyToAnalyse")
                              : t("compare.noAiNeeded")}
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
                        (analysis?.status === "succeeded" &&
                          !analysis.stale &&
                          effectiveAnalysisJob?.state === "succeeded") ||
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
                      {analysis?.stale ||
                      analysis?.status === "failed" ||
                      effectiveAnalysisJob?.state === "failed"
                        ? t("compare.retryAnalysis")
                        : analysis?.status === "succeeded"
                          ? t("compare.currentSaved")
                          : t("compare.analyse")}
                    </Button>
                  )}
                  <p className="review-note">{t("compare.reviewDisclaimer")}</p>
                </div>
              </section>
              <ActionsPanel
                id="companion-actions"
                hidden={companionTab !== "actions"}
                analysis={analysis}
                comparisonId={id}
                canManage={canManage}
                identityBlocked={identityBlocked}
                items={data.diff.items}
                onEvidence={jump}
                onSummary={() => openCompanion("summary")}
              />
              {identityBlocked ? (
                <section
                  id="companion-ask"
                  role="tabpanel"
                  aria-label={t("compare.ask")}
                  hidden={companionTab !== "ask"}
                  className="panel ask-panel companion-tab-panel"
                >
                  <div className="panel-header">
                    <h2 className="flex items-center gap-2">
                      <MessageSquare size={17} />
                      {t("compare.ask")}
                    </h2>
                  </div>
                  <div className="panel-body">
                    <div className="historical-note" role="status">
                      {t("compare.questionsBlocked")}
                    </div>
                  </div>
                </section>
              ) : (
                canManage && (
                  <AskPanel
                    comparisonId={id}
                    configured={!!health?.apertus.configured}
                    hidden={companionTab !== "ask"}
                    evidenceItems={data.diff.items}
                    onEvidence={jump}
                  />
                )
              )}
              <AIHistory
                comparisonId={id}
                compact
                hidden={companionTab !== "history"}
                evidenceItems={data.diff.items}
                onEvidence={jump}
              />
            </aside>
          </div>
        </>
      )}
    </Shell>
  );
}

function ComparisonWorkspaceTabs({
  active,
  evidenceActive = false,
  includeEvidence = false,
  canAsk,
  onEvidence,
  onSelect,
}: {
  active: CompanionTab;
  evidenceActive?: boolean;
  includeEvidence?: boolean;
  canAsk: boolean;
  onEvidence?: () => void;
  onSelect: (tab: CompanionTab) => void;
}) {
  const { t } = useI18n();
  const tabs: {
    id: "evidence" | CompanionTab;
    label: string;
    shortLabel: string;
    icon: React.ReactNode;
    disabled?: boolean;
  }[] = [
    ...(includeEvidence
      ? [
          {
            id: "evidence" as const,
            label: t("compare.meaningful"),
            shortLabel: t("compare.mobileTab.diff"),
            icon: <FileText size={15} />,
          },
        ]
      : []),
    {
      id: "summary",
      label: t("compare.whatChanged"),
      shortLabel: t("compare.mobileTab.summary"),
      icon: <Sparkles size={15} />,
    },
    {
      id: "actions",
      label: t("compare.suggestedActions"),
      shortLabel: t("compare.mobileTab.actions"),
      icon: <ListChecks size={15} />,
    },
    {
      id: "ask",
      label: t("compare.ask"),
      shortLabel: t("compare.mobileTab.ask"),
      icon: <MessageSquare size={15} />,
      disabled: !canAsk,
    },
    {
      id: "history",
      label: t("history.title"),
      shortLabel: t("compare.mobileTab.history"),
      icon: <HistoryIcon size={15} />,
    },
  ];
  function moveFocus(event: React.KeyboardEvent<HTMLButtonElement>) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const buttons = Array.from(
      event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>(
        '[role="tab"]:not(:disabled)',
      ) || [],
    );
    const current = buttons.indexOf(event.currentTarget);
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? buttons.length - 1
          : (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) %
            buttons.length;
    buttons[next]?.focus();
    buttons[next]?.click();
  }
  return (
    <div
      className={includeEvidence ? "comparison-task-tabs" : "companion-tabs"}
      role="tablist"
      aria-label={t("compare.section")}
    >
      {tabs.map((tab) => {
        const selected =
          tab.id === "evidence"
            ? evidenceActive
            : !evidenceActive && tab.id === active;
        return (
          <button
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={
              tab.id === "evidence"
                ? "comparison-evidence"
                : `companion-${tab.id}`
            }
            tabIndex={selected ? 0 : -1}
            disabled={tab.disabled}
            onKeyDown={moveFocus}
            onClick={() =>
              tab.id === "evidence" ? onEvidence?.() : onSelect(tab.id)
            }
            key={tab.id}
            aria-label={tab.label}
          >
            {tab.icon}
            <span className="comparison-tab-label-full">{tab.label}</span>
            <span className="comparison-tab-label-short" aria-hidden="true">
              {tab.shortLabel}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function ActionPreview({
  actions,
  onOpen,
}: {
  actions: Impact["actions"];
  onOpen: () => void;
}) {
  const { t } = useI18n();
  if (!actions.length)
    return (
      <div className="action-empty">
        <span className="eyebrow">{t("compare.knowWhatToDo")}</span>
        <strong>{t("compare.noAction")}</strong>
        <p>{t("compare.noActionBody")}</p>
      </div>
    );
  return (
    <div className="action-preview">
      <div className="action-preview-heading">
        <div>
          <span className="eyebrow">{t("compare.reviewPlan")}</span>
          <h3>{t("compare.suggestedActions")}</h3>
        </div>
        <Button type="button" size="sm" variant="outline" onClick={onOpen}>
          {t("compare.suggestedActions")} <ArrowRight size={13} />
        </Button>
      </div>
      <ol>
        {actions.slice(0, 3).map((action, index) => (
          <li key={action.action_key || index}>
            <span>{index + 1}</span>
            <strong>{action.title || action.text}</strong>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ActionsPanel({
  id,
  hidden,
  analysis,
  comparisonId,
  canManage,
  identityBlocked,
  items,
  onEvidence,
  onSummary,
}: {
  id: string;
  hidden: boolean;
  analysis: Analysis | null | undefined;
  comparisonId: string;
  canManage: boolean;
  identityBlocked: boolean;
  items: Change[];
  onEvidence: (changeId: string) => void;
  onSummary: () => void;
}) {
  const { locale, t } = useI18n();
  return (
    <section
      id={id}
      role="tabpanel"
      aria-label={t("compare.suggestedActions")}
      hidden={hidden}
      className="panel companion-tab-panel actions-panel"
    >
      <div className="panel-header">
        <h2 className="flex items-center gap-2">
          <ListChecks size={18} /> {t("compare.suggestedActions")}
        </h2>
        {analysis?.result && <Status value={analysis.result.impact} />}
      </div>
      <div className="panel-body">
        {identityBlocked ? (
          <div className="historical-note">{t("compare.analysisBlocked")}</div>
        ) : analysis?.status === "succeeded" && analysis.result ? (
          analysis.result.actions.length ? (
            <ol className="action-list">
              {analysis.result.actions.map((action, index) => (
                <li key={action.action_key || index}>
                  <span>{index + 1}</span>
                  <div>
                    <strong>{action.title || action.text}</strong>
                    {action.rationale && <p>{action.rationale}</p>}
                    {action.owner_role && (
                      <p className="action-meta">
                        {t("compare.owner")}: {action.owner_role} ·{" "}
                        {t("compare.area")}: {action.affected_area} ·{" "}
                        {t("compare.priority")}:{" "}
                        {action.priority
                          ? translate(locale, `status.${action.priority}`) ||
                            label(action.priority)
                          : t("compare.notRecorded")}{" "}
                        · {t("compare.due")}:{" "}
                        {action.due_date || action.due_basis}
                      </p>
                    )}
                    {action.applicability_condition && (
                      <p className="action-condition">
                        {t("compare.applyWhen")}:{" "}
                        {action.applicability_condition}
                      </p>
                    )}
                    <ComparisonCitations
                      values={action.citations}
                      items={items}
                      onEvidence={onEvidence}
                    />
                    {action.action_key && (
                      <ReviewActionControls
                        comparisonId={comparisonId}
                        analysisId={analysis.id}
                        action={action}
                        current={
                          analysis.action_decisions?.current?.[
                            action.action_key
                          ]
                        }
                        history={
                          analysis.action_decisions?.history?.filter(
                            (item) => item.action_key === action.action_key,
                          ) || []
                        }
                        canManage={canManage}
                      />
                    )}
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <div className="action-empty">
              <span className="eyebrow">{t("compare.knowWhatToDo")}</span>
              <strong>{t("compare.noAction")}</strong>
              <p>{t("compare.noActionBody")}</p>
            </div>
          )
        ) : (
          <div className="action-empty">
            <span className="eyebrow">{t("compare.reviewPlan")}</span>
            <strong>{t("compare.readyToAnalyse")}</strong>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={onSummary}
            >
              <Sparkles size={14} /> {t("compare.currentReport")}
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}

function ComparisonCitations({
  values,
  items,
  onEvidence,
}: {
  values: Citation[];
  items: Change[];
  onEvidence: (changeId: string) => void;
}) {
  const { t } = useI18n();
  if (!values?.length) return null;
  return (
    <span className="citations comparison-citations">
      {values.map((citation, index) => {
        const change = items.find(
          (item) =>
            item.old?.id === citation.passage_id ||
            item.new?.id === citation.passage_id,
        );
        const accessibleLabel = t("common.citation", {
          number: index + 1,
          quote: citation.quote.slice(0, 80),
        });
        return change ? (
          <button
            type="button"
            onClick={() => onEvidence(change.id)}
            aria-label={accessibleLabel}
            title={citation.quote}
            key={`${citation.version_id}-${citation.passage_id}-${index}`}
          >
            [{index + 1}] <FileText size={10} />
          </button>
        ) : (
          <Link
            href={citation.url}
            target="_blank"
            rel="noreferrer"
            aria-label={accessibleLabel}
            title={citation.quote}
            key={`${citation.version_id}-${citation.passage_id}-${index}`}
          >
            [{index + 1}] <ArrowUpRight size={10} />
          </Link>
        );
      })}
    </span>
  );
}

function VersionCard({ version, side }: { version: Version; side: string }) {
  const { locale, t, dateTime } = useI18n();
  return (
    <div className="version-card">
      <div className="flex justify-between gap-2">
        <span className="eyebrow">{side}</span>
        <span className="text-xs muted">{version.id.slice(0, 8)}</span>
      </div>
      <strong>{version.declared_date || t("law.versionDateUnknown")}</strong>
      <p>
        {translate(locale, `status.${version.origin}`) || label(version.origin)}{" "}
        ·{" "}
        {version.declared_date
          ? t("compare.dateSupplied")
          : t("compare.noPublicationDate")}
        {version.synthetic ? ` · ${t("law.syntheticDemo")}` : ""}
      </p>
      <p>{t("law.firstSaved", { date: dateTime(version.created_at) })}</p>
      <Link href={"/evidence/" + version.id} className="text-link">
        <FileText size={12} />
        {t("compare.readEvidence")}
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
  const { locale, t } = useI18n();
  const passage = side === "old" ? item.old : item.new;
  const parts = side === "old" ? item.old_parts : item.new_parts;
  return (
    <div
      className={"diff-side diff-side-" + side}
      lang={version.identity_json?.language || undefined}
    >
      <div className="passage-meta">
        <span>
          {side === "old" ? t("compare.beforeUpper") : t("compare.afterUpper")}{" "}
          ·{" "}
          {translate(
            locale,
            `status.${item.classification || item.change_type || item.kind}`,
          ) || label(item.classification || item.change_type || item.kind)}
        </span>
        {passage && (
          <Link
            href={"/evidence/" + version.id + "?passage=" + passage.id}
            target="_blank"
          >
            {passage.page
              ? `${t("compare.page", { page: passage.page })} · `
              : ""}
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
        <p className="no-passage">{t("compare.noPassage")}</p>
      )}
    </div>
  );
}

function AnalysisJobProgress({
  job,
  onCancel,
}: {
  job: Job;
  onCancel: () => void;
}) {
  const { locale: productLocale, t } = useI18n();
  const locale = productLocale.slice(0, 2) as ComparisonLocale;
  const activeStep =
    job.steps.find((step) => step.state === "running") ||
    job.steps.find((step) => step.state === "pending");
  const state = (() => {
    if (
      ["queued", "dispatched", "retrying", "waiting_for_model"].includes(
        job.state,
      )
    )
      return job.queue_position
        ? t("compare.queuePosition", { position: job.queue_position })
        : t("compare.queueWaiting");
    if (activeStep?.position === 1) return t("compare.preparingChanges");
    if (activeStep?.position === 2)
      return t("compare.analysingGroups", {
        current: activeStep.progress.current,
        total: activeStep.progress.total,
      });
    if (activeStep?.position === 3) return t("compare.validatingEvidence");
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
          <span>
            {t("compare.backgroundAttempt", {
              attempt: job.attempts,
              total: job.max_attempts,
            })}
          </span>
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
      <p>{t("compare.backgroundBody")}</p>
      <Button type="button" size="sm" variant="outline" onClick={onCancel}>
        <XCircle size={14} /> {t("compare.cancelAnalysis")}
      </Button>
    </div>
  );
}

function AnalysisJobOutcome({ job }: { job: Job }) {
  const { locale: productLocale, t, dateTime } = useI18n();
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
        {job.error?.detail
          ? ` · ${job.error.detail}`
          : ` · ${t("compare.savedBackground")}`}
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
  const { locale: productLocale, t, dateTime, number } = useI18n();
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
      assigned_to =
        window
          .prompt(t("compare.assignPrompt"), action.owner_role || "")
          ?.trim() || null;
      if (!assigned_to) return;
    }
    if (decision === "scheduled") {
      const date = window
        .prompt(t("compare.schedulePrompt"), action.due_date || "")
        ?.trim();
      if (!date) return;
      const localDate = new Date(`${date}T09:00:00`);
      if (Number.isNaN(localDate.getTime())) {
        setError(t("compare.invalidDate"));
        return;
      }
      scheduled_for = localDate.toISOString();
    }
    if (["dismissed", "not_applicable"].includes(decision)) {
      rationale = window.prompt(t("compare.reasonPrompt"))?.trim() || null;
      if (!rationale) return;
    }
    setBusy(decision);
    setError("");
    try {
      const page = await api<{
        current: Record<string, ActionDecision>;
        history: ActionDecision[];
      }>(
        `/comparisons/${comparisonId}/analyses/${analysisId}/actions/${encodeURIComponent(action.action_key || "")}/decisions`,
        {
          method: "POST",
          body: JSON.stringify({
            decision,
            assigned_to,
            scheduled_for,
            rationale,
          }),
        },
      );
      setSaved(page.current[action.action_key || ""]);
      setEvents(
        page.history.filter((item) => item.action_key === action.action_key),
      );
      mutateResource<Comparison>(
        resources.comparison(comparisonId),
        (currentComparison) => {
          if (
            !currentComparison?.analysis ||
            currentComparison.analysis.id !== analysisId
          )
            return currentComparison;
          return {
            ...currentComparison,
            analysis: {
              ...currentComparison.analysis,
              action_decisions: page,
            },
          };
        },
      );
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
        <div
          className="action-decision-buttons"
          aria-label={t("compare.actionDecision")}
        >
          <Button
            size="sm"
            variant="outline"
            disabled={!!busy}
            onClick={() => decide("accepted")}
          >
            <Check size={13} /> {t("compare.accept")}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!!busy}
            onClick={() => decide("assigned")}
          >
            <UserRound size={13} /> {t("compare.assign")}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!!busy}
            onClick={() => decide("scheduled")}
          >
            <CalendarClock size={13} /> {t("compare.schedule")}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={!!busy}
            onClick={() => decide("dismissed")}
          >
            {t("compare.dismiss")}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={!!busy}
            onClick={() => decide("not_applicable")}
          >
            {t("compare.notApplicable")}
          </Button>
        </div>
      )}
      {error && <ErrorNote message={error} />}
      {events.length > 1 && (
        <details className="action-decision-history">
          <summary>
            {t("compare.recordedDecisions", { count: number(events.length) })}
          </summary>
          <ol>
            {events.map((item) => (
              <li key={item.id}>
                {localLabel(item.decision, locale)} · {item.actor_label} ·{" "}
                {dateTime(item.created_at)}
                {item.rationale ? ` — ${item.rationale}` : ""}
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}

function ReportProvenance({
  analysis,
  comparison,
  onHistory,
}: {
  analysis: Analysis;
  comparison: Comparison;
  onHistory: () => void;
}) {
  const { t, dateTime } = useI18n();
  const provenance = analysis.provenance || {};
  const execution = analysis.analysis_plan?.execution;
  const outputLocale =
    analysis.result?.output_locale || t("compare.notRecorded");
  return (
    <div className="report-provenance">
      <div className="report-provenance-title">
        <ListChecks size={15} />
        <strong>{t("compare.provenance")}</strong>
        <button type="button" onClick={onHistory}>
          {t("compare.priorReports")}
        </button>
      </div>
      <dl>
        <div>
          <dt>{t("compare.generated")}</dt>
          <dd>{dateTime(analysis.created_at)}</dd>
        </div>
        <div>
          <dt>{t("compare.versions")}</dt>
          <dd>
            {comparison.old_version.id.slice(0, 8)} →{" "}
            {comparison.new_version.id.slice(0, 8)}
          </dd>
        </div>
        <div>
          <dt>{t("compare.profile")}</dt>
          <dd>
            {t("compare.revision", {
              revision: execution?.profile_revision ?? t("compare.notRecorded"),
            })}
          </dd>
        </div>
        <div>
          <dt>{t("compare.modelRuntime")}</dt>
          <dd>
            {analysis.model} ·{" "}
            {String(
              provenance.runtime_version ||
                provenance.backend ||
                t("compare.notRecorded"),
            )}
          </dd>
        </div>
        <div>
          <dt>{t("compare.promptLocale")}</dt>
          <dd>
            {t("compare.revision", { revision: analysis.prompt_revision })} ·{" "}
            {outputLocale}
          </dd>
        </div>
      </dl>
      <CoverageNote coverage={analysis.coverage} />
      <PlanNote plan={analysis.analysis_plan} />
    </div>
  );
}

function CoverageNote({ coverage }: { coverage?: Partial<Coverage> }) {
  const { t, number } = useI18n();
  if (!coverage) return null;
  if (coverage.material_items !== undefined) {
    return (
      <div
        className={coverage.limited ? "coverage-note limited" : "coverage-note"}
      >
        {coverage.limited ? t("compare.limitedReview") : t("compare.aiReview")}{" "}
        {t("compare.materialCoverage", {
          included: number(coverage.reviewed_material_items ?? 0),
          total: number(coverage.material_items),
        })}
        {coverage.suppressed_non_material_items
          ? ` · ${t("compare.suppressed", { count: number(coverage.suppressed_non_material_items) })}`
          : ""}
        {coverage.provider_calls !== undefined
          ? ` · ${t("compare.modelCalls", { count: number(coverage.provider_calls) })}`
          : ""}
        .{" "}
        {t("compare.coverageMaterialScope", {
          included: number(coverage.reviewed_material_items ?? 0),
          suppressed: number(coverage.suppressed_non_material_items ?? 0),
        })}
      </div>
    );
  }
  if (!coverage.available_passages) return null;
  return (
    <div
      className={coverage.limited ? "coverage-note limited" : "coverage-note"}
    >
      {coverage.limited
        ? t("compare.limitedContext")
        : t("compare.evidenceReviewed")}{" "}
      {t("compare.passageCoverage", {
        included: number(coverage.included_passages ?? 0),
        total: number(coverage.available_passages),
        characters: number(coverage.included_characters ?? 0),
      })}
      {coverage.provider_calls !== undefined
        ? ` · ${t("compare.modelCalls", { count: number(coverage.provider_calls) })}`
        : ""}
      .{" "}
      {coverage.included_passages === 0
        ? t("compare.coverageNoMatch")
        : coverage.limited
          ? t("compare.coverageSelectedScope")
          : t("compare.coverageCompleteScope")}
    </div>
  );
}

function PlanNote({ plan }: { plan?: AnalysisPlan }) {
  const { t, number } = useI18n();
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
      {t("compare.fixedPlan", {
        expected: number(plan.estimates.planned_generation_calls),
        actual: number(plan.actual?.provider_calls ?? 0),
        limit: number(plan.limits.provider_call_budget),
        groups: number(plan.execution.batch_count),
        coverage: plan.coverage.limited
          ? t("status.limited")
          : t("status.complete"),
      })}
      {actual
        ? ` · ${t("compare.timings", { queue: number(Math.round(actual.queue_wait_ms)), inference: number(Math.round(actual.inference_duration_ms)) })}`
        : ""}
      {tokenTotal
        ? ` · ${t("compare.recordedTokens", { count: number(tokenTotal) })}`
        : ""}
      {actual
        ? ` · ${t("compare.validationRepairs", { count: number(repairs) })}`
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
  hidden,
  evidenceItems,
  onEvidence,
}: {
  comparisonId: string;
  configured: boolean;
  blockedReason?: string;
  hidden: boolean;
  evidenceItems: Change[];
  onEvidence: (changeId: string) => void;
}) {
  const { locale, t } = useI18n();
  const [question, setQuestion] = useState(""),
    [submitting, setSubmitting] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const knownJobStates = useRef(new Map<string, string>());
  const handledTerminalJobs = useRef(new Set<string>());
  const promptLocale = askPrompts[locale.slice(0, 2)]
    ? locale.slice(0, 2)
    : "en";
  const savedHistory = useResource<AIHistoryPage>(
    resources.comparisonHistory(comparisonId),
  );
  const askJobs = useResource<Job[]>(resources.comparisonAskJobs(comparisonId));
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
  const jobs = askJobs.data || [];
  const activeJob = jobs.find((job) => !JOB_TERMINAL_STATES.has(job.state));
  const historyRecordIds = new Set(history.map((item) => item.id));
  const visibleJobs = jobs
    .filter(
      (job) =>
        !job.result?.id ||
        !historyRecordIds.has(job.result.id) ||
        !JOB_TERMINAL_STATES.has(job.state),
    )
    .slice(0, 3);

  useEffect(() => {
    for (const job of jobs) {
      const previous = knownJobStates.current.get(job.id);
      knownJobStates.current.set(job.id, job.state);
      if (!JOB_TERMINAL_STATES.has(job.state)) continue;
      if (!handledTerminalJobs.current.has(job.id)) {
        handledTerminalJobs.current.add(job.id);
        void invalidateResources(resources.comparisonHistory(comparisonId));
      }
      if (!previous || JOB_TERMINAL_STATES.has(previous)) continue;
      const result = job.result?.data as Answer | undefined;
      const completed = job.state === "succeeded";
      setNotice(
        completed
          ? result?.cached
            ? t("compare.answerCached")
            : t("compare.answerReady")
          : t("compare.askEnded", {
              state: localLabel(job.state, promptLocale as ComparisonLocale),
            }),
      );
      if (
        completed &&
        document.hidden &&
        "Notification" in window &&
        Notification.permission === "granted"
      ) {
        new Notification("Helvetic Lens", {
          body: t("compare.answerReadyShort"),
        });
      }
    }
  }, [comparisonId, jobs, promptLocale, t]);

  function updateJob(next: Job) {
    primeResourceForLocale(resources.job(next.id), locale, next);
    askJobs.setData((current) => [
      next,
      ...(current || []).filter((item) => item.id !== next.id),
    ]);
  }

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setSubmitting(true);
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
      updateJob(queued);
      setQuestion("");
      setNotice(
        JOB_TERMINAL_STATES.has(queued.state)
          ? (queued.result?.data as Answer | undefined)?.cached
            ? t("compare.answerCached")
            : t("compare.answerReady")
          : t("compare.askSubmitted"),
      );
      if (JOB_TERMINAL_STATES.has(queued.state))
        void invalidateResources(resources.comparisonHistory(comparisonId));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setSubmitting(false);
    }
  }

  async function cancel(job: Job) {
    setError("");
    try {
      updateJob(await api<Job>(`/jobs/${job.id}/cancel`, { method: "POST" }));
      setNotice(t("compare.askCancelled"));
    } catch (cause) {
      setError(errorText(cause));
    }
  }

  async function retry(job: Job) {
    setError("");
    setNotice("");
    try {
      const retried = await api<Job>(`/jobs/${job.id}/retry`, {
        method: "POST",
      });
      handledTerminalJobs.current.delete(job.id);
      updateJob(retried);
      setNotice(t("compare.askResubmitted"));
    } catch (cause) {
      setError(errorText(cause));
      setQuestion(job.request?.question || question);
    }
  }
  return (
    <section
      id="companion-ask"
      role="tabpanel"
      aria-label={t("compare.ask")}
      hidden={hidden}
      className="panel ask-panel companion-tab-panel"
    >
      <div className="panel-header">
        <h2 className="flex items-center gap-2">
          <MessageSquare size={17} />
          {t("compare.ask")}
        </h2>
        <span className="text-xs muted">{t("compare.thisComparison")}</span>
      </div>
      <div className="panel-body">
        <p className="text-xs muted mt-0">{t("compare.askBody")}</p>
        <div className="chat-history" aria-live="polite">
          {history.map((item) => (
            <SavedQuestionTurn
              item={item}
              key={item.id}
              onSuggestion={setQuestion}
              evidenceItems={evidenceItems}
              onEvidence={onEvidence}
            />
          ))}
          {visibleJobs.map((job) => (
            <AskJobCard
              key={job.id}
              job={job}
              onCancel={() => cancel(job)}
              onRetry={() => retry(job)}
              onRevise={() => setQuestion(job.request?.question || "")}
            />
          ))}
        </div>
        {savedHistory.loading && !savedHistory.data && (
          <Loading text={t("compare.loadingQuestions")} />
        )}
        <ErrorNote message={savedHistory.error} />
        <ErrorNote message={askJobs.error} />
        {blockedReason && <ErrorNote message={blockedReason} />}
        <div
          className="ask-intents"
          role="group"
          aria-label={t("compare.suggestedQuestions")}
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
            {t("compare.questionLabel")}
          </label>
          <Textarea
            id="apertus-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={
              ready
                ? t("compare.askPlaceholder")
                : blockedReason || t("compare.connectToAsk")
            }
            disabled={!ready || submitting || !!activeJob}
            maxLength={2000}
            rows={3}
          />
          <ErrorNote message={error} />
          {notice && <p className="saved-answer-note">{notice}</p>}
          <Button
            type="submit"
            className="mt-3 w-full"
            disabled={!ready || submitting || !!activeJob || !question.trim()}
          >
            {submitting ? <Loader2 className="animate-spin" /> : <Send />}
            {submitting
              ? t("compare.submittingQuestion")
              : activeJob
                ? t("compare.questionInProgress")
                : t("compare.askCitations")}
          </Button>
        </form>
      </div>
    </section>
  );
}

function AskJobCard({
  job,
  onCancel,
  onRetry,
  onRevise,
}: {
  job: Job;
  onCancel: () => void;
  onRetry: () => void;
  onRevise: () => void;
}) {
  const { t } = useI18n();
  const result = job.result?.data as Answer | undefined;
  const active = !JOB_TERMINAL_STATES.has(job.state);
  const limited =
    job.state === "succeeded" &&
    (!result?.supported || result?.coverage?.limited);
  const runningStep = job.steps.find((step) => step.state === "running");
  const stage =
    job.state === "waiting_for_model"
      ? "startingModel"
      : ["queued", "dispatched", "retrying"].includes(job.state)
        ? "queued"
        : job.state === "succeeded"
          ? limited
            ? "limited"
            : "completed"
          : job.state === "failed"
            ? "failed"
            : job.state === "cancelled"
              ? "cancelled"
              : runningStep?.position === 1
                ? "selectingEvidence"
                : runningStep?.position === 3
                  ? "validating"
                  : "generating";
  const percent = JOB_TERMINAL_STATES.has(job.state)
    ? 100
    : Math.max(
        4,
        Math.round(
          (job.progress.current / Math.max(1, job.progress.total)) * 100,
        ),
      );
  const code = job.error?.code || "";
  const recovery =
    job.state === "waiting_for_model" || code.includes("model")
      ? t("compare.askRecoveryModel")
      : code.includes("context")
        ? t("compare.askRecoveryContext")
        : code.includes("valid") ||
            code.includes("citation") ||
            code.includes("structured")
          ? t("compare.askRecoveryValidation")
          : !result?.supported && job.state === "succeeded"
            ? t("compare.askRecoveryEvidence")
            : job.state === "failed"
              ? t("compare.askRecoveryRetry")
              : ["queued", "dispatched", "retrying"].includes(job.state)
                ? job.state === "retrying"
                  ? t("compare.askRecoveryQueue")
                  : t("compare.queueTimeout")
                : "";
  const stageLabel = (() => {
    switch (stage) {
      case "queued":
        return t("compare.askStage.queued");
      case "startingModel":
        return t("compare.askStage.startingModel");
      case "selectingEvidence":
        return t("compare.askStage.selectingEvidence");
      case "generating":
        return t("compare.askStage.generating");
      case "validating":
        return t("compare.askStage.validating");
      case "completed":
        return t("compare.askStage.completed");
      case "limited":
        return t("compare.askStage.limited");
      case "failed":
        return t("compare.askStage.failed");
      default:
        return t("compare.askStage.cancelled");
    }
  })();
  return (
    <article
      className={`ask-job-card ${job.state} ${limited ? "limited" : ""}`}
      aria-live={active ? "polite" : "assertive"}
      aria-atomic="true"
    >
      <p className="question-bubble">
        {job.request?.question || t("compare.savedQuestion")}
      </p>
      <div className="ask-job-heading">
        {active ? (
          <Loader2 className="animate-spin" size={15} />
        ) : job.state === "succeeded" ? (
          <Check size={15} />
        ) : (
          <XCircle size={15} />
        )}
        <div>
          <strong>{stageLabel}</strong>
          <span>
            {job.queue_position
              ? t("compare.queuePosition", { position: job.queue_position })
              : t("compare.backgroundAttempt", {
                  attempt: Math.max(1, job.attempts),
                  total: job.max_attempts,
                })}
          </span>
        </div>
      </div>
      <div className="analysis-job-track" aria-hidden="true">
        <span style={{ width: `${percent}%` }} />
      </div>
      {job.state === "failed" && (
        <ErrorNote message={job.error?.detail || t("compare.answerFailed")} />
      )}
      {active && runningStep?.position === 1 && (
        <p className="ask-job-recovery">{t("compare.reviewingEvidence")}</p>
      )}
      {recovery && <p className="ask-job-recovery">{recovery}</p>}
      {job.state === "succeeded" && (
        <p className="ask-job-result-kind">
          {!result
            ? t("compare.answerMissing")
            : result.cached
              ? t("compare.answerFromCache")
              : `${t("compare.answerFromInference")} · ${t("compare.answerSaved")}`}
        </p>
      )}
      <div className="ask-job-actions">
        {active && (
          <Button type="button" size="sm" variant="outline" onClick={onCancel}>
            <XCircle size={14} /> {t("compare.cancelQuestion")}
          </Button>
        )}
        {job.state === "waiting_for_model" && (
          <Button asChild size="sm" variant="outline">
            <Link href="/models">{t("compare.openModels")}</Link>
          </Button>
        )}
        {["failed", "cancelled"].includes(job.state) && (
          <Button type="button" size="sm" variant="outline" onClick={onRetry}>
            {t("compare.retryQuestion")}
          </Button>
        )}
        {(job.state === "failed" || limited) && (
          <Button type="button" size="sm" variant="ghost" onClick={onRevise}>
            {t("compare.reviseQuestion")}
          </Button>
        )}
      </div>
    </article>
  );
}

function SavedQuestionTurn({
  item,
  onSuggestion,
  evidenceItems,
  onEvidence,
}: {
  item: AIHistoryItem;
  onSuggestion: (value: string) => void;
  evidenceItems: Change[];
  onEvidence: (changeId: string) => void;
}) {
  const { t, locale, dateTime, number } = useI18n();
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
          <ErrorNote message={item.error || t("compare.savedRequestFailed")} />
        ) : answer ? (
          <>
            {!answer.supported && (
              <strong className="block mb-2">
                {t("compare.notSupported")}
              </strong>
            )}
            <p>{answer.answer}</p>
            <ComparisonCitations
              values={answer.citations}
              items={evidenceItems}
              onEvidence={onEvidence}
            />
            {answer.intent && answer.context_mode && (
              <p className="ask-answer-route">
                {translate(locale, `status.${answer.intent}`) ||
                  label(answer.intent)}{" "}
                ·{" "}
                {answer.context_mode === "impact_report"
                  ? t("compare.reusedReport")
                  : translate(locale, `status.${answer.context_mode}`) ||
                    label(answer.context_mode)}
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
                ? ` · ${t("compare.reusedTimes", { count: number(item.use_count - 1) })}`
                : ""}
            </p>
          </>
        ) : (
          <Loading text={t("compare.answering")} />
        )}
      </div>
    </div>
  );
}
