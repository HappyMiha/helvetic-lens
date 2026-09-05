"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  Archive,
  Edit3,
  Eye,
  Pause,
  Play,
  Plus,
  Radar,
  RotateCcw,
  Save,
  Sparkles,
} from "lucide-react";
import {
  api,
  dateTime,
  errorText,
  invalidateResources,
  resources,
  useResource,
} from "@/lib/api";
import { localeNames, type Locale, useI18n } from "@/lib/i18n";
import type {
  MonitoringTopic,
  MonitoringTopicDraft,
  MonitoringTopicPlan,
  MonitoringTopicPreview,
} from "@/lib/types";
import {
  topicDraftKey,
  readTopicDraft,
  writeTopicDraft,
  removeTopicDraft,
  type TopicForm as FormPlan,
  type TopicTabDraft,
  type TopicEditIdentity,
  type TopicAiIdentity,
} from "@/lib/topic-tab-draft";
import { useAuth } from "./auth-gate";
import { ErrorNote, Loading, Status, SuccessNote } from "./common";
import { Shell } from "./shell";
import { TopicHistoryStatus } from "./topic-history-status";
import { TopicPreviewCoverage } from "./topic-preview-coverage";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";

const DOCUMENT_KINDS = [
  "act",
  "ordinance",
  "parliamentary_business",
  "initiative",
  "bill",
  "court_decision",
  "official_notice",
  "consultation",
  "unclassified_document",
];
const EVENT_KINDS = [
  "created",
  "new_version",
  "amended",
  "repealed",
  "replaced",
  "status_changed",
  "decided",
  "notice_published",
];
const LANGUAGES = ["de", "fr", "it", "rm", "en"];

const initialPlan: FormPlan = {
  name: "",
  goal: "",
  concepts: "",
  synonyms: "",
  exclusions: "",
  jurisdictions: "CH",
  languages: ["de", "fr", "it", "rm", "en"],
  source_pack_ids: [],
  document_kinds: [
    "act",
    "ordinance",
    "parliamentary_business",
    "initiative",
    "bill",
    "court_decision",
    "official_notice",
    "consultation",
  ],
  event_kinds: [
    "created",
    "new_version",
    "amended",
    "repealed",
    "replaced",
    "status_changed",
    "decided",
    "notice_published",
  ],
  importance_floor: "low",
};

function split(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toPayload(form: FormPlan): MonitoringTopicPlan {
  return {
    ...form,
    concepts: split(form.concepts),
    synonyms: split(form.synonyms),
    exclusions: split(form.exclusions),
    jurisdictions: split(form.jurisdictions),
  };
}

function fromPlan(plan: MonitoringTopicPlan): FormPlan {
  return {
    ...plan,
    concepts: plan.concepts.join(", "),
    synonyms: plan.synonyms.join(", "),
    exclusions: plan.exclusions.join(", "),
    jurisdictions: plan.jurisdictions.join(", "),
  };
}

const kindLabels: Record<string, string> = {
  act: "topics.kind.act",
  ordinance: "topics.kind.ordinance",
  parliamentary_business: "topics.kind.parliamentary_business",
  initiative: "topics.kind.initiative",
  bill: "topics.kind.bill",
  court_decision: "topics.kind.court_decision",
  official_notice: "topics.kind.official_notice",
  consultation: "topics.kind.consultation",
  unclassified_document: "topics.kind.unclassified_document",
  created: "topics.kind.created",
  new_version: "topics.kind.new_version",
  amended: "topics.kind.amended",
  repealed: "topics.kind.repealed",
  replaced: "topics.kind.replaced",
  status_changed: "topics.kind.status_changed",
  decided: "topics.kind.decided",
  notice_published: "topics.kind.notice_published",
};

function Choices({
  values,
  selected,
  onChange,
  labels,
}: {
  values: string[];
  selected: string[];
  onChange: (values: string[]) => void;
  labels: Record<string, string>;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {values.map((value) => (
        <label
          className="inline-flex min-h-11 items-center gap-2 rounded-md border px-3 py-2 text-sm"
          key={value}
        >
          <input
            checked={selected.includes(value)}
            value={value}
            onChange={() =>
              onChange(
                selected.includes(value)
                  ? selected.filter((item) => item !== value)
                  : [...selected, value],
              )
            }
            type="checkbox"
          />
          {labels[value]}
        </label>
      ))}
    </div>
  );
}

export function MonitoringTopicsPage() {
  const { session } = useAuth();
  const principal = session?.authenticated
    ? session.user?.id
    : session?.anonymous_development
      ? "anonymous-development"
      : undefined;
  const scope = topicDraftKey(principal, session?.organization?.id);
  return <TopicEditor key={scope || "unavailable"} draftScope={scope} />;
}

function TopicEditor({ draftScope }: { draftScope: string | null }) {
  const { t, locale } = useI18n();
  const { canManage } = useAuth();
  const topics = useResource(resources.monitoringTopics(true));
  const packs = useResource(resources.sourcePacks());
  const [form, setForm] = useState<FormPlan>(initialPlan);
  const [savedForm, setSavedForm] = useState<FormPlan>(initialPlan);
  const dirty =
    JSON.stringify(toPayload(form)) !== JSON.stringify(toPayload(savedForm));
  const [editing, setEditing] = useState<TopicEditIdentity | null>(null);
  const [preview, setPreview] = useState<MonitoringTopicPreview | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [aiDraft, setAiDraft] = useState<TopicAiIdentity | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const editorRef = useRef<HTMLFormElement>(null);
  const scopeRef = useRef<HTMLDetailsElement>(null);
  const initializedPacks = useRef(false);
  const [draftLoaded, setDraftLoaded] = useState(false);
  const [recovery, setRecovery] = useState<TopicTabDraft | null>(null);
  const [storageFailed, setStorageFailed] = useState(false);

  useEffect(() => {
    if (!draftScope || !canManage) return;
    try {
      const loaded = readTopicDraft(window.sessionStorage, draftScope);
      setRecovery(loaded.draft);
      setStorageFailed(loaded.failed);
    } catch {
      setStorageFailed(true);
    }
    setDraftLoaded(true);
  }, [draftScope, canManage]);

  useEffect(() => {
    if (!draftLoaded || !draftScope || !canManage || recovery) return;
    try {
      const ok = dirty
        ? writeTopicDraft(window.sessionStorage, {
            version: 1,
            scope: draftScope,
            savedAt: Date.now(),
            form,
            baseline: savedForm,
            editing,
            aiDraft,
            idempotencyKey,
          })
        : removeTopicDraft(window.sessionStorage, draftScope);
      setStorageFailed(!ok);
    } catch {
      setStorageFailed(true);
    }
  }, [
    draftLoaded,
    draftScope,
    canManage,
    recovery,
    dirty,
    form,
    savedForm,
    editing,
    aiDraft,
    idempotencyKey,
  ]);

  function restoreDraft() {
    if (!recovery) return;
    initializedPacks.current = true;
    setForm(recovery.form);
    setSavedForm(recovery.baseline);
    setEditing(recovery.editing);
    setAiDraft(recovery.aiDraft);
    setIdempotencyKey(recovery.idempotencyKey);
    setPreview(null);
    setRecovery(null);
    setMessage(t("topics.tabDraftRestored"));
    focusEditor();
  }

  function discardRecoveredDraft() {
    if (draftScope) {
      try {
        setStorageFailed(!removeTopicDraft(window.sessionStorage, draftScope));
      } catch {
        setStorageFailed(true);
      }
    }
    setRecovery(null);
    focusEditor();
  }

  const packIds = useMemo(
    () => packs.data?.items.map((item) => item.id) || [],
    [packs.data],
  );
  const defaultPackIds = useMemo(
    () =>
      packs.data?.items
        .filter((item) => item.subscription.enabled)
        .map((item) => item.id) || [],
    [packs.data],
  );
  const packLabels = Object.fromEntries(
    (packs.data?.items || []).map((item) => [
      item.id,
      item.name[locale] ||
        item.name[locale.split("-")[0]] ||
        item.name["en-CH"] ||
        item.name.en ||
        t("topics.unknownPack"),
    ]),
  );
  const labels = Object.fromEntries(
    Object.entries(kindLabels).map(([key, message]) => [key, t(message)]),
  );
  const languageLabels = Object.fromEntries(
    LANGUAGES.map((language) => [
      language,
      localeNames[`${language}-CH` as Locale],
    ]),
  );

  useEffect(() => {
    // Polling must never reselect options the user deliberately cleared.
    if (initializedPacks.current || !packs.data || editing) return;
    initializedPacks.current = true;
    setForm((current) => ({ ...current, source_pack_ids: defaultPackIds }));
    setSavedForm((current) => ({
      ...current,
      source_pack_ids: defaultPackIds,
    }));
  }, [packs.data, defaultPackIds, editing]);

  useEffect(() => {
    if (!dirty) return;
    function beforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  function confirmDiscard() {
    if (!dirty || window.confirm(t("topics.discardConfirm"))) return true;
    focusEditor();
    return false;
  }

  function discard() {
    if (!confirmDiscard()) return;
    reset();
    focusEditor();
  }

  function focusEditor() {
    requestAnimationFrame(() => {
      const editor = editorRef.current;
      if (!editor) return;
      const header = editor.closest("main")?.querySelector(".topbar");
      editor.style.scrollMarginTop = `${(header?.getBoundingClientRect().height || 0) + 16}px`;
      editor.scrollIntoView({ block: "start" });
      editorRef.current
        ?.querySelector<HTMLInputElement>('[name="topic-name"]')
        ?.focus({ preventScroll: true });
    });
  }

  function changed(next: FormPlan) {
    setForm(next);
    setPreview(null);
    if (!editing) setIdempotencyKey("");
  }

  function reset() {
    setEditing(null);
    const next = { ...initialPlan, source_pack_ids: defaultPackIds };
    setForm(next);
    setSavedForm(next);
    setPreview(null);
    setIdempotencyKey("");
    setAiDraft(null);
    setError("");
    setMessage("");
  }

  async function draftWithAi() {
    setBusy("draft");
    setError("");
    setMessage("");
    try {
      const result = await api<MonitoringTopicDraft>(
        "/monitoring-topics/draft",
        {
          method: "POST",
          body: JSON.stringify({ goal: form.goal, locale }),
        },
      );
      setForm(fromPlan(result.plan));
      setAiDraft(result);
      setPreview(null);
      setIdempotencyKey("");
      setMessage(t("topics.aiDraftReady"));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  async function previewPlan(event: FormEvent) {
    event.preventDefault();
    const missingScope =
      !form.source_pack_ids.length ||
      !form.languages.length ||
      !form.document_kinds.length ||
      !form.event_kinds.length ||
      !split(form.jurisdictions).length;
    if (missingScope) {
      setError(t("topics.scopeRequired"));
      if (scopeRef.current) scopeRef.current.open = true;
      scopeRef.current?.querySelector<HTMLElement>("summary")?.focus();
      scopeRef.current?.scrollIntoView({ block: "nearest" });
      return;
    }
    setBusy("preview");
    setError("");
    setMessage("");
    try {
      const result = await api<MonitoringTopicPreview>(
        "/monitoring-topics/preview",
        {
          method: "POST",
          body: JSON.stringify(toPayload(form)),
        },
      );
      setPreview(result);
      if (!editing && !idempotencyKey) setIdempotencyKey(crypto.randomUUID());
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  async function save() {
    setBusy("save");
    setError("");
    try {
      const payload = toPayload(form);
      if (editing) {
        await api(`/monitoring-topics/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify({
            ...payload,
            expected_revision: editing.current_revision,
            ai_draft_id: aiDraft?.id,
          }),
        });
      } else {
        await api("/monitoring-topics", {
          method: "POST",
          body: JSON.stringify({
            ...payload,
            idempotency_key: idempotencyKey || crypto.randomUUID(),
            ai_draft_id: aiDraft?.id,
          }),
        });
      }
      const savedMessage = t(editing ? "topics.updated" : "topics.created");
      await invalidateResources(resources.monitoringTopics(true));
      reset();
      setMessage(savedMessage);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  async function status(
    topic: MonitoringTopic,
    next: "active" | "paused" | "archived",
  ) {
    setBusy(topic.id);
    setError("");
    try {
      await api(`/monitoring-topics/${topic.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({
          status: next,
          expected_revision: topic.current_revision,
        }),
      });
      await invalidateResources(resources.monitoringTopics(true));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  function edit(topic: MonitoringTopic) {
    if (!confirmDiscard()) return;
    setEditing(topic);
    const next = fromPlan(topic.plan);
    setForm(next);
    setSavedForm(next);
    setIdempotencyKey("");
    setMessage("");
    setPreview(null);
    setAiDraft(null);
    setError("");
    focusEditor();
  }

  async function resumeHistory(topic: MonitoringTopic) {
    setBusy(topic.id);
    setError("");
    try {
      await api(`/monitoring-topics/${topic.id}/history-scan`, {
        method: "POST",
      });
      await invalidateResources(resources.monitoringTopics(true));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  return (
    <Shell section={t("nav.topics")} wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("topics.eyebrow")}</span>
          <h1>{t("topics.title")}</h1>
          <p className="muted m-0">{t("topics.body")}</p>
        </div>
        {editing && (
          <Button
            data-topic-new
            disabled={!!busy || !!recovery}
            variant="outline"
            onClick={discard}
          >
            <Plus /> {t("topics.new")}
          </Button>
        )}
      </div>
      <ErrorNote
        message={topics.error || packs.error || (!canManage ? error : "")}
      />
      {message && <SuccessNote>{message}</SuccessNote>}
      {canManage ? (
        <form
          ref={editorRef}
          className="monitoring-topic-builder card p-5 mb-6 scroll-mt-4"
          onSubmit={previewPlan}
          aria-busy={!!busy}
        >
          {recovery && (
            <section
              data-topic-recovery
              className="mb-5 rounded-lg border p-4"
              aria-label={t("topics.tabDraftTitle")}
            >
              <h2 className="font-semibold">{t("topics.tabDraftTitle")}</h2>
              <p className="text-sm muted">
                {t("topics.tabDraftFound", {
                  date: dateTime(new Date(recovery.savedAt).toISOString()),
                })}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button type="button" data-topic-restore onClick={restoreDraft}>
                  {t("topics.tabDraftRestore")}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  data-topic-discard-recovery
                  onClick={discardRecoveredDraft}
                >
                  {t("topics.tabDraftDiscard")}
                </Button>
              </div>
            </section>
          )}
          {storageFailed && (
            <p
              role="status"
              data-topic-storage-error
              className="text-sm muted mb-3"
            >
              {t("topics.tabDraftUnavailable")}
            </p>
          )}
          <fieldset disabled={!!busy || !!recovery} className="min-w-0">
            <ErrorNote message={error} />
            {dirty && (
              <p
                className="text-sm text-muted-foreground"
                role="status"
                data-topic-unsaved
              >
                {t("topics.unsavedNote")}
                {draftLoaded && draftScope && !storageFailed && (
                  <span data-topic-tab-saved className="block">
                    {t("topics.tabDraftSaved")}
                  </span>
                )}
              </p>
            )}
            <div className="flex items-start justify-between gap-4 mb-5">
              <div>
                <span className="eyebrow">
                  {editing ? t("topics.editing") : t("topics.builder")}
                </span>
                <h2 className="m-0">{t("topics.planTitle")}</h2>
              </div>
              {editing && (
                <span className="text-sm muted">
                  {t("topics.revision", { revision: editing.current_revision })}
                </span>
              )}
            </div>
            <p className="muted mt-0">{t("topics.startHelp")}</p>
            <div className="grid gap-4 lg:grid-cols-2">
              <label className="text-sm font-medium lg:col-span-2">
                {t("topics.goal")}
                <Textarea
                  name="topic-goal"
                  required
                  maxLength={3000}
                  className="mt-1 text-base"
                  value={form.goal}
                  onChange={(event) =>
                    changed({ ...form, goal: event.target.value })
                  }
                  placeholder={t("topics.goalPlaceholder")}
                />
              </label>
              <label className="text-sm font-medium">
                {t("topics.name")}
                <Input
                  name="topic-name"
                  required
                  maxLength={240}
                  className="mt-1 text-base"
                  value={form.name}
                  onChange={(event) =>
                    changed({ ...form, name: event.target.value })
                  }
                  placeholder={t("topics.namePlaceholder")}
                />
              </label>
              <label className="text-sm font-medium">
                {t("topics.concepts")}
                <Input
                  name="topic-concepts"
                  required
                  className="mt-1 text-base"
                  value={form.concepts}
                  onChange={(event) =>
                    changed({ ...form, concepts: event.target.value })
                  }
                  placeholder={t("topics.commaHint")}
                />
                <span className="mt-1 block text-sm muted">
                  {t("topics.conceptsHelp")}
                </span>
              </label>
            </div>
            <div
              className="rounded-lg border bg-muted p-3 my-4"
              data-topic-scope
            >
              <p className="m-0 text-sm font-semibold">
                {t("topics.scopeSummary", {
                  packs: form.source_pack_ids.length,
                  languages: form.languages.length,
                })}
              </p>
              <p className="my-1 text-sm">
                {form.source_pack_ids
                  .map((id) => packLabels[id] || t("topics.unknownPack"))
                  .join(" · ") || t("topics.noPacksSelected")}
              </p>
              <p className="m-0 text-sm muted">{t("topics.previewHelp")}</p>
            </div>
            <details
              ref={scopeRef}
              className="mb-4 rounded-lg border p-3"
              data-topic-scope-options
            >
              <summary className="cursor-pointer min-h-11 content-center font-semibold">
                {t("topics.adjustScope")}
              </summary>
              <div className="mt-3 space-y-4">
                <fieldset>
                  <legend className="text-sm font-semibold mb-2">
                    {t("topics.sourcePacks")}
                  </legend>
                  <Choices
                    values={packIds}
                    labels={packLabels}
                    selected={form.source_pack_ids}
                    onChange={(values) =>
                      changed({ ...form, source_pack_ids: values })
                    }
                  />
                  <p className="text-sm muted">
                    {t("topics.packScopeHelp")}{" "}
                    <a className="underline" href="/sources">
                      {t("nav.sources")}
                    </a>
                  </p>
                </fieldset>
                <label className="block text-sm font-medium">
                  {t("topics.jurisdictions")}
                  <Input
                    name="topic-jurisdictions"
                    className="mt-1"
                    value={form.jurisdictions}
                    onChange={(event) =>
                      changed({ ...form, jurisdictions: event.target.value })
                    }
                    placeholder={t("topics.jurisdictionPlaceholder")}
                  />
                </label>
                <fieldset>
                  <legend className="text-sm font-semibold mb-2">
                    {t("topics.languages")}
                  </legend>
                  <Choices
                    values={LANGUAGES}
                    labels={languageLabels}
                    selected={form.languages}
                    onChange={(values) =>
                      changed({ ...form, languages: values })
                    }
                  />
                </fieldset>
                <fieldset>
                  <legend className="text-sm font-semibold mb-2">
                    {t("topics.documentKinds")}
                  </legend>
                  <Choices
                    values={DOCUMENT_KINDS}
                    labels={labels}
                    selected={form.document_kinds}
                    onChange={(values) =>
                      changed({ ...form, document_kinds: values })
                    }
                  />
                </fieldset>
                <fieldset>
                  <legend className="text-sm font-semibold mb-2">
                    {t("topics.eventKinds")}
                  </legend>
                  <Choices
                    values={EVENT_KINDS}
                    labels={labels}
                    selected={form.event_kinds}
                    onChange={(values) =>
                      changed({ ...form, event_kinds: values })
                    }
                  />
                </fieldset>
                <label className="block text-sm font-semibold max-w-xs">
                  {t("topics.importance")}
                  <select
                    className="input mt-1 w-full"
                    value={form.importance_floor}
                    onChange={(event) =>
                      changed({
                        ...form,
                        importance_floor: event.target
                          .value as FormPlan["importance_floor"],
                      })
                    }
                  >
                    <option value="high">{t("status.high")}</option>
                    <option value="medium">{t("status.medium")}</option>
                    <option value="low">{t("status.low")}</option>
                    <option value="none">{t("topics.anyImportance")}</option>
                  </select>
                </label>
              </div>
            </details>
            <details
              className="mb-4 rounded-lg border p-3"
              data-topic-matching-options
            >
              <summary className="cursor-pointer min-h-11 content-center font-semibold">
                {t("topics.refineMatching")}
              </summary>
              <div className="grid gap-4 mt-3 lg:grid-cols-2">
                <label className="text-sm font-medium">
                  {t("topics.synonyms")}
                  <Input
                    className="mt-1"
                    value={form.synonyms}
                    onChange={(event) =>
                      changed({ ...form, synonyms: event.target.value })
                    }
                    placeholder={t("topics.commaHint")}
                  />
                </label>
                <label className="text-sm font-medium">
                  {t("topics.exclusions")}
                  <Input
                    className="mt-1"
                    value={form.exclusions}
                    onChange={(event) =>
                      changed({ ...form, exclusions: event.target.value })
                    }
                    placeholder={t("topics.exclusionsHint")}
                  />
                </label>
              </div>
            </details>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                disabled={busy !== "" || form.goal.trim().length < 3}
                onClick={() => void draftWithAi()}
                type="button"
                variant="outline"
              >
                <Sparkles />{" "}
                {busy === "draft"
                  ? t("topics.drafting")
                  : t("topics.draftWithAi")}
              </Button>
              <span className="text-sm muted">{t("topics.aiOptional")}</span>
            </div>
            {aiDraft && (
              <div className="info-note mt-3">
                {t("topics.aiDraftProvenance", {
                  provider: aiDraft.provider,
                  model: aiDraft.model,
                })}
              </div>
            )}
            <div className="mt-5 flex flex-wrap gap-2">
              <Button disabled={busy !== ""} type="submit">
                <Eye /> {t("topics.preview")}
              </Button>
              {preview && (
                <Button
                  disabled={busy !== ""}
                  data-topic-save
                  onClick={() => void save()}
                  type="button"
                  variant="outline"
                >
                  <Save />{" "}
                  {editing ? t("topics.saveRevision") : t("topics.activate")}
                </Button>
              )}
              {editing && (
                <Button type="button" variant="ghost" onClick={discard}>
                  <RotateCcw /> {t("topics.cancel")}
                </Button>
              )}
            </div>
          </fieldset>
        </form>
      ) : (
        <div className="info-note mb-6">{t("topics.viewerHelp")}</div>
      )}

      {preview && (
        <section
          className="card p-5 mb-6"
          aria-live="polite"
          data-topic-preview
        >
          <span className="eyebrow">{t("topics.previewEyebrow")}</span>
          <h2>
            {t("topics.previewCount", { count: preview.candidate_count })}
          </h2>
          <TopicPreviewCoverage
            preview={preview}
            capturedAtLabel={
              preview.sample_captured_at
                ? dateTime(preview.sample_captured_at)
                : undefined
            }
          />
          {preview.items.length === 0 ? (
            <p>{t("topics.noCandidates")}</p>
          ) : (
            <div className="space-y-3">
              {preview.items.map((item) => (
                <article className="rounded-lg border p-4" key={item.event_id}>
                  <div className="flex flex-wrap items-center gap-2">
                    <Status value={item.event_type} />
                    <Status value={item.importance} />
                  </div>
                  <h3 className="mt-3 mb-1">{item.title}</h3>
                  <p className="muted text-sm">
                    {item.authority} · {dateTime(item.detected_at)}
                  </p>
                  <p className="text-sm">
                    {t("topics.matchReason", {
                      reasons: item.reason_signals
                        .filter((signal) => signal.type !== "source_pack")
                        .flatMap(
                          (signal) =>
                            signal.values ||
                            (signal.value ? [signal.value] : []),
                        )
                        .join(", "),
                    })}
                  </p>
                  <p className="text-xs muted">
                    {t("topics.notLegalRelation")}
                  </p>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      <section>
        <div className="flex items-end justify-between mb-4">
          <div>
            <span className="eyebrow">{t("topics.savedEyebrow")}</span>
            <h2 className="m-0">{t("topics.saved")}</h2>
          </div>
          <span className="muted text-sm">{topics.data?.length || 0}</span>
        </div>
        {topics.loading && !topics.data && (
          <Loading text={t("topics.loading")} />
        )}
        {!topics.loading && topics.data?.length === 0 && (
          <div className="empty-state card">
            <Radar />
            <h3>{t("topics.empty")}</h3>
            <p className="muted">{t("topics.emptyBody")}</p>
          </div>
        )}
        <div className="grid gap-4 xl:grid-cols-2">
          {topics.data?.map((topic) => (
            <article className="card p-5" key={topic.id}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex flex-wrap gap-2 mb-2">
                    <Status value={topic.status} />
                    <span className="status-badge status-neutral">
                      {t("topics.revision", {
                        revision: topic.current_revision,
                      })}
                    </span>
                  </div>
                  <h3 className="m-0">{topic.plan.name}</h3>
                  <p className="muted mt-2">{topic.plan.goal}</p>
                </div>
              </div>
              <dl className="source-facts mt-4">
                <div>
                  <dt>{t("topics.concepts")}</dt>
                  <dd>{topic.plan.concepts.join(", ")}</dd>
                </div>
                <div>
                  <dt>{t("topics.sourcePacks")}</dt>
                  <dd>
                    {topic.plan.source_pack_ids
                      .map((id) => packLabels[id] || t("topics.unknownPack"))
                      .join(", ")}
                  </dd>
                </div>
                <div>
                  <dt>{t("topics.updatedAt")}</dt>
                  <dd>{dateTime(topic.updated_at)}</dd>
                </div>
              </dl>
              <TopicHistoryStatus
                topic={topic}
                capturedAtLabel={
                  topic.history_scan?.captured_at
                    ? dateTime(topic.history_scan.captured_at)
                    : undefined
                }
                renderResume={
                  canManage
                    ? () => (
                        <Button
                          variant="outline"
                          disabled={Boolean(busy)}
                          onClick={() => resumeHistory(topic)}
                        >
                          <RotateCcw /> {t("topicHistory.resume")}
                        </Button>
                      )
                    : undefined
                }
              />
              <details className="mt-4">
                <summary className="cursor-pointer font-semibold">
                  {t("topics.history")}
                </summary>
                <ol className="mt-2 space-y-2 text-sm">
                  {topic.revisions?.map((revision) => (
                    <li key={revision.id}>
                      {t("topics.historyItem", {
                        revision: revision.revision || 0,
                        status: t(`status.${revision.status || "active"}`),
                        date: dateTime(revision.created_at),
                      })}
                    </li>
                  )) || <li>{t("topics.openToLoad")}</li>}
                </ol>
              </details>
              {canManage && topic.status !== "archived" && (
                <div className="flex flex-wrap gap-2 mt-5">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!!busy || !!recovery}
                    data-topic-edit={topic.id}
                    onClick={() => edit(topic)}
                  >
                    <Edit3 /> {t("topics.edit")}
                  </Button>
                  {topic.status === "active" ? (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!!busy || !!recovery}
                      onClick={() => void status(topic, "paused")}
                    >
                      <Pause /> {t("topics.pause")}
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!!busy || !!recovery}
                      onClick={() => void status(topic, "active")}
                    >
                      <Play /> {t("topics.resume")}
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={!!busy || !!recovery}
                    onClick={() => void status(topic, "archived")}
                  >
                    <Archive /> {t("topics.archive")}
                  </Button>
                </div>
              )}
            </article>
          ))}
        </div>
      </section>
    </Shell>
  );
}
