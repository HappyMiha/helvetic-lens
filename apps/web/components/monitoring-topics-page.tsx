"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Archive, Edit3, Eye, Pause, Play, Plus, Radar, RotateCcw, Save, Sparkles } from "lucide-react";
import { api, dateTime, errorText, invalidateResources, resources, useResource } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { MonitoringTopic, MonitoringTopicDraft, MonitoringTopicPlan, MonitoringTopicPreview } from "@/lib/types";
import { useAuth } from "./auth-gate";
import { ErrorNote, Loading, Status, SuccessNote } from "./common";
import { Shell } from "./shell";
import { TopicHistoryStatus } from "./topic-history-status";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";

const DOCUMENT_KINDS = ["act", "ordinance", "parliamentary_business", "initiative", "bill", "court_decision", "official_notice", "consultation"];
const EVENT_KINDS = ["created", "new_version", "amended", "repealed", "replaced", "status_changed", "decided", "notice_published"];
const LANGUAGES = ["de", "fr", "it", "rm", "en"];

type FormPlan = Omit<MonitoringTopicPlan, "concepts" | "synonyms" | "exclusions" | "jurisdictions"> & {
  concepts: string;
  synonyms: string;
  exclusions: string;
  jurisdictions: string;
};

const initialPlan: FormPlan = {
  name: "",
  goal: "",
  concepts: "",
  synonyms: "",
  exclusions: "",
  jurisdictions: "CH",
  languages: ["de", "fr", "it", "rm", "en"],
  source_pack_ids: [],
  document_kinds: ["act", "ordinance", "parliamentary_business", "initiative", "bill", "court_decision", "official_notice", "consultation"],
  event_kinds: ["created", "new_version", "amended", "repealed", "replaced", "status_changed", "decided", "notice_published"],
  importance_floor: "low",
};

function split(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
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

function Choices({ values, selected, onChange }: { values: string[]; selected: string[]; onChange: (values: string[]) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {values.map((value) => (
        <label className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm" key={value}>
          <input
            checked={selected.includes(value)}
            onChange={() => onChange(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value])}
            type="checkbox"
          />
          {value.replaceAll("_", " ")}
        </label>
      ))}
    </div>
  );
}

export function MonitoringTopicsPage() {
  const { t, locale } = useI18n();
  const { canManage } = useAuth();
  const topics = useResource(resources.monitoringTopics(true));
  const packs = useResource(resources.sourcePacks());
  const [form, setForm] = useState<FormPlan>(initialPlan);
  const [editing, setEditing] = useState<MonitoringTopic | null>(null);
  const [preview, setPreview] = useState<MonitoringTopicPreview | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [aiDraft, setAiDraft] = useState<MonitoringTopicDraft | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const packIds = useMemo(() => packs.data?.items.map((item) => item.id) || [], [packs.data]);

  useEffect(() => {
    if (!editing && packIds.length && form.source_pack_ids.length === 0) {
      setForm((current) => ({ ...current, source_pack_ids: packIds }));
    }
  }, [editing, form.source_pack_ids.length, packIds]);

  function changed(next: FormPlan) {
    setForm(next);
    setPreview(null);
    if (!editing) setIdempotencyKey("");
  }

  function reset() {
    setEditing(null);
    setForm({ ...initialPlan, source_pack_ids: packIds });
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
      const result = await api<MonitoringTopicDraft>("/monitoring-topics/draft", {
        method: "POST",
        body: JSON.stringify({ goal: form.goal, locale }),
      });
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
    setBusy("preview");
    setError("");
    setMessage("");
    try {
      const result = await api<MonitoringTopicPreview>("/monitoring-topics/preview", {
        method: "POST",
        body: JSON.stringify(toPayload(form)),
      });
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
          body: JSON.stringify({ ...payload, expected_revision: editing.current_revision, ai_draft_id: aiDraft?.id }),
        });
      } else {
        await api("/monitoring-topics", {
          method: "POST",
          body: JSON.stringify({ ...payload, idempotency_key: idempotencyKey || crypto.randomUUID(), ai_draft_id: aiDraft?.id }),
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

  async function status(topic: MonitoringTopic, next: "active" | "paused" | "archived") {
    setBusy(topic.id);
    setError("");
    try {
      await api(`/monitoring-topics/${topic.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: next, expected_revision: topic.current_revision }),
      });
      await invalidateResources(resources.monitoringTopics(true));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  function edit(topic: MonitoringTopic) {
    setEditing(topic);
    setForm(fromPlan(topic.plan));
    setPreview(null);
    setAiDraft(null);
    setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function resumeHistory(topic: MonitoringTopic) {
    setBusy(topic.id);
    setError("");
    try {
      await api(`/monitoring-topics/${topic.id}/history-scan`, { method: "POST" });
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
        {editing && <Button variant="outline" onClick={reset}><Plus /> {t("topics.new")}</Button>}
      </div>
      <ErrorNote message={error || topics.error || packs.error} />
      {message && <SuccessNote>{message}</SuccessNote>}
      {canManage ? (
        <form className="monitoring-topic-builder card p-5 mb-6" onSubmit={previewPlan}>
          <div className="flex items-start justify-between gap-4 mb-5">
            <div><span className="eyebrow">{editing ? t("topics.editing") : t("topics.builder")}</span><h2 className="m-0">{t("topics.planTitle")}</h2></div>
            {editing && <span className="text-sm muted">{t("topics.revision", { revision: editing.current_revision })}</span>}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <label className="text-sm font-medium">{t("topics.name")}<Input className="mt-1" value={form.name} onChange={(event) => changed({ ...form, name: event.target.value })} placeholder={t("topics.namePlaceholder")} /></label>
            <label className="text-sm font-medium">{t("topics.jurisdictions")}<Input className="mt-1" value={form.jurisdictions} onChange={(event) => changed({ ...form, jurisdictions: event.target.value })} placeholder={t("topics.jurisdictionPlaceholder")} /></label>
            <label className="text-sm font-medium lg:col-span-2">{t("topics.goal")}<Textarea className="mt-1" value={form.goal} onChange={(event) => changed({ ...form, goal: event.target.value })} placeholder={t("topics.goalPlaceholder")} /></label>
            <div className="lg:col-span-2 flex flex-wrap items-center gap-3">
              <Button disabled={busy !== "" || form.goal.trim().length < 3} onClick={() => void draftWithAi()} type="button" variant="outline"><Sparkles /> {busy === "draft" ? t("topics.drafting") : t("topics.draftWithAi")}</Button>
              <span className="text-sm muted">{t("topics.aiOptional")}</span>
            </div>
            {aiDraft && <div className="info-note lg:col-span-2">{t("topics.aiDraftProvenance", { provider: aiDraft.provider, model: aiDraft.model })}</div>}
            <label className="text-sm font-medium">{t("topics.concepts")}<Input className="mt-1" value={form.concepts} onChange={(event) => changed({ ...form, concepts: event.target.value })} placeholder={t("topics.commaHint")} /></label>
            <label className="text-sm font-medium">{t("topics.synonyms")}<Input className="mt-1" value={form.synonyms} onChange={(event) => changed({ ...form, synonyms: event.target.value })} placeholder={t("topics.commaHint")} /></label>
            <label className="text-sm font-medium lg:col-span-2">{t("topics.exclusions")}<Input className="mt-1" value={form.exclusions} onChange={(event) => changed({ ...form, exclusions: event.target.value })} placeholder={t("topics.exclusionsHint")} /></label>
          </div>
          <div className="mt-5 space-y-4">
            <fieldset><legend className="text-sm font-semibold mb-2">{t("topics.sourcePacks")}</legend><Choices values={packIds} selected={form.source_pack_ids} onChange={(values) => changed({ ...form, source_pack_ids: values })} /></fieldset>
            <fieldset><legend className="text-sm font-semibold mb-2">{t("topics.languages")}</legend><Choices values={LANGUAGES} selected={form.languages} onChange={(values) => changed({ ...form, languages: values })} /></fieldset>
            <fieldset><legend className="text-sm font-semibold mb-2">{t("topics.documentKinds")}</legend><Choices values={DOCUMENT_KINDS} selected={form.document_kinds} onChange={(values) => changed({ ...form, document_kinds: values })} /></fieldset>
            <fieldset><legend className="text-sm font-semibold mb-2">{t("topics.eventKinds")}</legend><Choices values={EVENT_KINDS} selected={form.event_kinds} onChange={(values) => changed({ ...form, event_kinds: values })} /></fieldset>
            <label className="block text-sm font-semibold max-w-xs">{t("topics.importance")}<select className="input mt-1 w-full" value={form.importance_floor} onChange={(event) => changed({ ...form, importance_floor: event.target.value as FormPlan["importance_floor"] })}><option value="high">{t("status.high")}</option><option value="medium">{t("status.medium")}</option><option value="low">{t("status.low")}</option><option value="none">{t("topics.anyImportance")}</option></select></label>
          </div>
          <div className="mt-5 flex flex-wrap gap-2"><Button disabled={busy !== ""} type="submit"><Eye /> {t("topics.preview")}</Button>{preview && <Button disabled={busy !== ""} onClick={() => void save()} type="button" variant="outline"><Save /> {editing ? t("topics.saveRevision") : t("topics.activate")}</Button>}{editing && <Button type="button" variant="ghost" onClick={reset}><RotateCcw /> {t("topics.cancel")}</Button>}</div>
        </form>
      ) : <div className="info-note mb-6">{t("topics.viewerHelp")}</div>}

      {preview && (
        <section className="card p-5 mb-6" aria-live="polite">
          <span className="eyebrow">{t("topics.previewEyebrow")}</span>
          <h2>{t("topics.previewCount", { count: preview.candidate_count })}</h2>
          <p className="muted">{t("topics.previewBoundary", { limit: preview.scanned_event_limit })}</p>
          {preview.items.length === 0 ? <p>{t("topics.noCandidates")}</p> : <div className="space-y-3">{preview.items.map((item) => <article className="rounded-lg border p-4" key={item.event_id}><div className="flex flex-wrap items-center gap-2"><Status value={item.event_type} /><Status value={item.importance} /></div><h3 className="mt-3 mb-1">{item.title}</h3><p className="muted text-sm">{item.authority} · {dateTime(item.detected_at)}</p><p className="text-sm">{t("topics.matchReason", { reasons: item.reason_signals.filter((signal) => signal.type !== "source_pack").map((signal) => signal.value).join(", ") })}</p><p className="text-xs muted">{t("topics.notLegalRelation")}</p></article>)}</div>}
        </section>
      )}

      <section>
        <div className="flex items-end justify-between mb-4"><div><span className="eyebrow">{t("topics.savedEyebrow")}</span><h2 className="m-0">{t("topics.saved")}</h2></div><span className="muted text-sm">{topics.data?.length || 0}</span></div>
        {topics.loading && !topics.data && <Loading text={t("topics.loading")} />}
        {!topics.loading && topics.data?.length === 0 && <div className="empty-state card"><Radar /><h3>{t("topics.empty")}</h3><p className="muted">{t("topics.emptyBody")}</p></div>}
        <div className="grid gap-4 xl:grid-cols-2">{topics.data?.map((topic) => <article className="card p-5" key={topic.id}><div className="flex items-start justify-between gap-4"><div><div className="flex flex-wrap gap-2 mb-2"><Status value={topic.status} /><span className="status-badge status-neutral">{t("topics.revision", { revision: topic.current_revision })}</span></div><h3 className="m-0">{topic.plan.name}</h3><p className="muted mt-2">{topic.plan.goal}</p></div></div><dl className="source-facts mt-4"><div><dt>{t("topics.concepts")}</dt><dd>{topic.plan.concepts.join(", ")}</dd></div><div><dt>{t("topics.sourcePacks")}</dt><dd>{topic.plan.source_pack_ids.join(", ")}</dd></div><div><dt>{t("topics.updatedAt")}</dt><dd>{dateTime(topic.updated_at)}</dd></div></dl><TopicHistoryStatus topic={topic} capturedAtLabel={topic.history_scan?.captured_at ? dateTime(topic.history_scan.captured_at) : undefined} renderResume={canManage ? () => <Button variant="outline" disabled={Boolean(busy)} onClick={() => resumeHistory(topic)}><RotateCcw /> {t("topicHistory.resume")}</Button> : undefined} /><details className="mt-4"><summary className="cursor-pointer font-semibold">{t("topics.history")}</summary><ol className="mt-2 space-y-2 text-sm">{topic.revisions?.map((revision) => <li key={revision.id}>{t("topics.historyItem", { revision: revision.revision || 0, status: revision.status || "active", date: dateTime(revision.created_at) })}</li>) || <li>{t("topics.openToLoad")}</li>}</ol></details>{canManage && topic.status !== "archived" && <div className="flex flex-wrap gap-2 mt-5"><Button size="sm" variant="outline" onClick={() => edit(topic)}><Edit3 /> {t("topics.edit")}</Button>{topic.status === "active" ? <Button size="sm" variant="outline" disabled={busy === topic.id} onClick={() => void status(topic, "paused")}><Pause /> {t("topics.pause")}</Button> : <Button size="sm" variant="outline" disabled={busy === topic.id} onClick={() => void status(topic, "active")}><Play /> {t("topics.resume")}</Button>}<Button size="sm" variant="ghost" disabled={busy === topic.id} onClick={() => void status(topic, "archived")}><Archive /> {t("topics.archive")}</Button></div>}</article>)}</div>
      </section>
    </Shell>
  );
}
