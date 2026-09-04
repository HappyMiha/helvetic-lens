"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowUpRight,
  BellOff,
  Bot,
  ChevronRight,
  Eye,
  Loader2,
  MessageCircle,
  Send,
  Settings2,
  Sparkles,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, useResource } from "@/lib/api";
import { ASSISTANT_QUESTION_EVENT } from "@/lib/assistant-events";
import { translate, useI18n } from "@/lib/i18n";
import { jobResultHref } from "@/lib/job-links";
import { resources } from "@/lib/resource-keys";
import type { Job } from "@/lib/types";

type Tone = "neutral" | "dry" | "very_dry";

type CompanionPreferences = {
  enabled: boolean;
  spontaneous: boolean;
  tone: Tone;
};

type RouteContext = {
  actionHref: string;
  actionKey: string;
  descriptionKey: string;
  quipKey: string;
  titleKey: string;
};

const STORAGE_KEY = "helvetic_lens_companion_v1";
const SESSION_KEY = "helvetic_lens_companion_seen_v1";
const DRAFT_KEY_PREFIX = "helvetic_lens_companion_draft_v1:";
const TERMINAL_JOB_STATES = new Set(["succeeded", "failed", "cancelled"]);
const ASSISTANT_JOB_TYPES = new Set([
  "ask",
  "impact_analysis",
  "relation_impact_analysis",
]);
const DEFAULT_PREFERENCES: CompanionPreferences = {
  enabled: true,
  spontaneous: true,
  tone: "very_dry",
};

type AssistantContextResponse = {
  context: { entity: { kind: string; id: string; label?: string } | null };
  persona: { quip_allowed: boolean };
};

type AssistantEntityRef = {
  kind: "law" | "comparison";
  id: string;
};

type AssistantRuntime = {
  display_name: string;
  ready: boolean;
  state: "ready" | "degraded" | "starting" | "stopped" | "needs_download";
  selected_model: { display_name: string };
  policy: { cloud_fallback: boolean; single_runtime: boolean };
};

type AssistantRemarkResponse = {
  key: string;
  provenance: {
    local: true;
    cloud_fallback: false;
    persona_version: string;
  };
};

type AssistantConversationResponse = {
  id: string;
  draft: string;
  handoffs: Array<{ id: string; question: string; created_at: string }>;
  visibility: "personal";
};

const GENERATED_REMARK_KEYS = new Set([
  "companion.generated.bureaucracy",
  "companion.generated.evidence",
  "companion.generated.queue",
  "companion.generated.progress",
]);

function runtimeStatusKey(
  runtime: AssistantRuntime | null,
  fallbackReady: boolean,
) {
  if (!runtime)
    return fallbackReady
      ? "companion.localReady"
      : "companion.localUnavailable";
  if (runtime.state === "ready") return "companion.localReady";
  if (runtime.state === "degraded") return "companion.localLimited";
  if (runtime.state === "starting") return "companion.localStarting";
  if (runtime.state === "stopped") return "companion.localStopped";
  return "companion.localNeedsDownload";
}

function contractRoute(pathname: string) {
  if (pathname.startsWith("/compare/")) return "/compare";
  if (pathname.startsWith("/laws/")) return "/laws";
  const allowed = new Set([
    "/",
    "/registry",
    "/topics",
    "/impact",
    "/discover",
    "/sources",
    "/activity",
    "/matrix",
    "/digests",
    "/organization",
  ]);
  return allowed.has(pathname) ? pathname : "/";
}

function routeEntity(pathname: string): AssistantEntityRef | null {
  const match = pathname.match(
    /^\/(compare|laws)\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i,
  );
  if (!match) return null;
  return {
    kind: match[1] === "compare" ? "comparison" : "law",
    id: match[2],
  };
}

function routeContext(pathname: string): RouteContext {
  if (pathname.startsWith("/compare/")) {
    return {
      actionHref: `${pathname}?task=impact`,
      actionKey: "companion.action.reviewCitedImpact",
      descriptionKey: "companion.context.compare",
      quipKey: "companion.quip.compare",
      titleKey: "companion.route.compare",
    };
  }
  if (pathname.startsWith("/laws/")) {
    return {
      actionHref: pathname,
      actionKey: "companion.action.reviewLaw",
      descriptionKey: "companion.context.law",
      quipKey: "companion.quip.law",
      titleKey: "companion.route.law",
    };
  }
  if (pathname === "/registry" || pathname === "/discover") {
    return {
      actionHref: "/topics",
      actionKey: "companion.action.createTopic",
      descriptionKey: "companion.context.registry",
      quipKey: "companion.quip.registry",
      titleKey: "companion.route.registry",
    };
  }
  if (pathname === "/topics") {
    return {
      actionHref: "/topics",
      actionKey: "companion.action.createTopic",
      descriptionKey: "companion.context.topics",
      quipKey: "companion.quip.topics",
      titleKey: "companion.route.topics",
    };
  }
  if (pathname === "/impact") {
    return {
      actionHref: "/impact",
      actionKey: "companion.action.reviewImpact",
      descriptionKey: "companion.context.impact",
      quipKey: "companion.quip.impact",
      titleKey: "companion.route.impact",
    };
  }
  if (pathname === "/sources") {
    return {
      actionHref: "/sources",
      actionKey: "companion.action.reviewSources",
      descriptionKey: "companion.context.sources",
      quipKey: "companion.quip.sources",
      titleKey: "companion.route.sources",
    };
  }
  if (
    pathname === "/settings" ||
    pathname === "/prompts" ||
    pathname === "/models" ||
    pathname === "/connectors" ||
    pathname === "/admin"
  ) {
    return {
      actionHref: pathname,
      actionKey: "companion.action.reviewSettings",
      descriptionKey: "companion.context.settings",
      quipKey: "companion.quip.settings",
      titleKey: "companion.route.settings",
    };
  }
  return {
    actionHref: "/registry",
    actionKey: "companion.action.openRegistry",
    descriptionKey: "companion.context.today",
    quipKey: "companion.quip.today",
    titleKey: "companion.route.today",
  };
}

function humanize(value: string) {
  return value.replaceAll("_", " ").replace(/^./, (character) => character.toUpperCase());
}

function readPreferences(): CompanionPreferences {
  try {
    const saved = JSON.parse(
      window.localStorage.getItem(STORAGE_KEY) || "null",
    ) as Partial<CompanionPreferences> | null;
    return {
      enabled: saved?.enabled ?? DEFAULT_PREFERENCES.enabled,
      spontaneous: saved?.spontaneous ?? DEFAULT_PREFERENCES.spontaneous,
      tone:
        saved?.tone === "neutral" ||
        saved?.tone === "dry" ||
        saved?.tone === "very_dry"
          ? saved.tone
          : DEFAULT_PREFERENCES.tone,
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function rememberRoute(pathname: string) {
  try {
    const seen = JSON.parse(
      window.sessionStorage.getItem(SESSION_KEY) || "{}",
    ) as Record<string, number>;
    seen[pathname] = Date.now();
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(seen));
  } catch {
    // The companion remains useful when storage is unavailable.
  }
}

function seenRecently(pathname: string): boolean {
  try {
    const seen = JSON.parse(
      window.sessionStorage.getItem(SESSION_KEY) || "{}",
    ) as Record<string, number>;
    return Date.now() - (seen[pathname] || 0) < 15 * 60 * 1000;
  } catch {
    return false;
  }
}

function RobotPortrait({ compact = false }: { compact?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`marvin-robot ${compact ? "marvin-robot-compact" : ""}`}
    >
      <span className="marvin-antenna" />
      <span className="marvin-head">
        <span className="marvin-eye marvin-eye-left" />
        <span className="marvin-eye marvin-eye-right" />
        <span className="marvin-mouth" />
      </span>
      <span className="marvin-body">HL</span>
    </span>
  );
}

export function MarvinCompanion({
  localAiReady,
  onOpenChange,
  open,
}: {
  localAiReady: boolean;
  onOpenChange: (open: boolean) => void;
  open: boolean;
}) {
  const pathname = usePathname();
  const { locale, t } = useI18n();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [preferences, setPreferences] =
    useState<CompanionPreferences>(DEFAULT_PREFERENCES);
  const [hydrated, setHydrated] = useState(false);
  const [bubbleVisible, setBubbleVisible] = useState(false);
  const [bubbleKey, setBubbleKey] = useState<string | null>(null);
  const [questionDraft, setQuestionDraft] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversationLoaded, setConversationLoaded] = useState(false);
  const [recentQuestions, setRecentQuestions] = useState<
    AssistantConversationResponse["handoffs"]
  >([]);
  const [handoffPending, setHandoffPending] = useState(false);
  const [contextAttached, setContextAttached] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [serverQuipAllowed, setServerQuipAllowed] = useState(false);
  const [contextLabel, setContextLabel] = useState<string | null>(null);
  const [runtime, setRuntime] = useState<AssistantRuntime | null>(null);
  const interactionCount = useRef(0);
  const deepScrollSeen = useRef(false);
  const remarkRequestId = useRef(0);
  const knownAiJobStates = useRef<Map<string, string> | null>(null);
  const context = useMemo(() => routeContext(pathname), [pathname]);
  const entity = useMemo(() => routeEntity(pathname), [pathname]);
  const comparisonId = pathname.startsWith("/compare/")
    ? pathname.slice("/compare/".length)
    : "";
  const jobsResource = useResource<Job[]>(resources.assistantJobs(), {
    pollMs: open ? 2_000 : 10_000,
    staleMs: open ? 1_000 : 5_000,
    priority: "interactive",
  });
  const aiJobs = useMemo(
    () =>
      (jobsResource.data || []).filter((job) =>
        ASSISTANT_JOB_TYPES.has(job.type),
      ),
    [jobsResource.data],
  );
  const activeAiJobs = useMemo(
    () => aiJobs.filter((job) => !TERMINAL_JOB_STATES.has(job.state)),
    [aiJobs],
  );
  const visibleAiJobs = useMemo(
    () => (activeAiJobs.length ? activeAiJobs.slice(0, 3) : aiJobs.slice(0, 1)),
    [activeAiJobs, aiJobs],
  );

  useEffect(() => {
    setPreferences(readPreferences());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    let active = true;
    setServerQuipAllowed(false);
    setContextLabel(null);
    setConversationId(null);
    setConversationLoaded(false);
    setRecentQuestions([]);
    const contextPayload = {
      schema_version: "assistant-context.v1",
      intent: "explain_screen",
      route: contractRoute(pathname),
      ...(entity ? { entity } : {}),
      locale,
    };
    Promise.allSettled([
      contextAttached
        ? api<AssistantContextResponse>("/assistant/context", {
            method: "POST",
            body: JSON.stringify(contextPayload),
          })
        : Promise.resolve(null),
      api<AssistantRuntime>("/assistant/runtime"),
      contextAttached && comparisonId
        ? api<AssistantConversationResponse>("/assistant/conversations", {
            method: "POST",
            body: JSON.stringify(contextPayload),
          })
        : Promise.resolve(null),
    ]).then(([contextResult, runtimeResult, conversationResult]) => {
      if (!active) return;
      setServerQuipAllowed(
        contextResult.status === "fulfilled" &&
          Boolean(contextResult.value?.persona.quip_allowed),
      );
      setContextLabel(
        contextResult.status === "fulfilled"
          ? contextResult.value?.context.entity?.label || null
          : null,
      );
      setRuntime(
        runtimeResult.status === "fulfilled" ? runtimeResult.value : null,
      );
      if (
        conversationResult.status === "fulfilled" &&
        conversationResult.value
      ) {
        setConversationId(conversationResult.value.id);
        setRecentQuestions(conversationResult.value.handoffs);
        setQuestionDraft(
          conversationResult.value.draft ||
            window.sessionStorage.getItem(DRAFT_KEY_PREFIX + comparisonId) ||
            "",
        );
        setConversationLoaded(true);
      } else if (comparisonId) {
        setQuestionDraft(
          window.sessionStorage.getItem(DRAFT_KEY_PREFIX + comparisonId) || "",
        );
      }
    });
    return () => {
      active = false;
    };
  }, [comparisonId, contextAttached, entity, hydrated, locale, pathname]);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
    } catch {
      // Private browsing may deny storage; keep the in-memory preference.
    }
  }, [hydrated, preferences]);

  const presentRemark = useCallback(
    async (
      trigger: "arrival" | "activity" | "deep_scroll",
      fallbackKey: string,
    ) => {
      const requestId = ++remarkRequestId.current;
      let selectedKey = fallbackKey;
      if (
        contextAttached &&
        runtime?.ready &&
        preferences.tone !== "neutral"
      ) {
        try {
          const response = await api<AssistantRemarkResponse>(
            "/assistant/remark",
            {
              method: "POST",
              body: JSON.stringify({
                schema_version: "assistant-context.v1",
                intent: "explain_screen",
                route: contractRoute(pathname),
                ...(entity ? { entity } : {}),
                locale,
                trigger,
                tone: preferences.tone,
              }),
            },
          );
          if (
            response.provenance.local &&
            response.provenance.cloud_fallback === false &&
            GENERATED_REMARK_KEYS.has(response.key)
          ) {
            selectedKey = response.key;
          }
        } catch {
          // The translated deterministic remark is the honest offline fallback.
        }
      }
      if (requestId !== remarkRequestId.current) return;
      setBubbleKey(selectedKey);
      setBubbleVisible(true);
    },
    [contextAttached, entity, locale, pathname, preferences.tone, runtime?.ready],
  );

  useEffect(() => {
    if (!conversationId || !conversationLoaded || !comparisonId) return;
    const timer = window.setTimeout(() => {
      void api<AssistantConversationResponse>(
        `/assistant/conversations/${conversationId}`,
        {
          method: "PATCH",
          body: JSON.stringify({ draft: questionDraft }),
        },
      ).catch(() => undefined);
    }, 500);
    return () => window.clearTimeout(timer);
  }, [comparisonId, conversationId, conversationLoaded, questionDraft]);

  useEffect(() => {
    setContextAttached(true);
  }, [pathname]);

  useEffect(() => {
    const current = new Map(aiJobs.map((job) => [job.id, job.state]));
    const previous = knownAiJobStates.current;
    knownAiJobStates.current = current;
    if (!previous || open) return;
    const completed = aiJobs.find(
      (job) =>
        TERMINAL_JOB_STATES.has(job.state) &&
        previous.has(job.id) &&
        !TERMINAL_JOB_STATES.has(previous.get(job.id) || ""),
    );
    if (!completed) return;
    setBubbleKey(
      completed.state === "succeeded"
        ? "companion.jobComplete"
        : "companion.jobEnded",
    );
    setBubbleVisible(true);
  }, [aiJobs, open]);

  useEffect(() => {
    setBubbleVisible(false);
    remarkRequestId.current += 1;
    setBubbleKey(null);
    setSettingsOpen(false);
    interactionCount.current = 0;
    deepScrollSeen.current = false;
    if (
      !hydrated ||
      !preferences.enabled ||
      !preferences.spontaneous ||
      preferences.tone === "neutral" ||
      !contextAttached ||
      !serverQuipAllowed ||
      seenRecently(pathname)
    ) {
      return;
    }
    const delay = 6500 + (pathname.length % 4) * 1200;
    const timer = window.setTimeout(() => {
      if (document.visibilityState !== "visible" || open) return;
      rememberRoute(pathname);
      void presentRemark("arrival", context.quipKey);
    }, delay);
    return () => window.clearTimeout(timer);
  }, [
    hydrated,
    open,
    pathname,
    preferences.enabled,
    preferences.spontaneous,
    preferences.tone,
    serverQuipAllowed,
    context.quipKey,
    contextAttached,
    presentRemark,
  ]);

  useEffect(() => {
    if (
      !hydrated ||
      !preferences.enabled ||
      !preferences.spontaneous ||
      preferences.tone === "neutral" ||
      !contextAttached ||
      !serverQuipAllowed ||
      open
    ) {
      return;
    }

    function showActivityRemark(key: string) {
      if (seenRecently(`${pathname}:activity`)) return;
      rememberRoute(`${pathname}:activity`);
      void presentRemark("activity", key);
    }

    function observeAllowlistedAction(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest(".marvin-companion")) return;
      const control = target.closest("button, a[href], summary");
      if (!control || control.closest("form")) return;
      interactionCount.current += 1;
      if (interactionCount.current === 4) {
        window.setTimeout(
          () => showActivityRemark("companion.quip.busy"),
          1200,
        );
      }
    }

    function observeScroll(event: Event) {
      if (deepScrollSeen.current) return;
      const target = event.currentTarget;
      if (!(target instanceof HTMLElement)) return;
      const remaining =
        target.scrollHeight - target.scrollTop - target.clientHeight;
      if (target.scrollHeight <= target.clientHeight || remaining > 160) return;
      deepScrollSeen.current = true;
      if (seenRecently(`${pathname}:activity`)) return;
      rememberRoute(`${pathname}:activity`);
      void presentRemark("deep_scroll", "companion.quip.deepScroll");
    }

    const main = document.querySelector<HTMLElement>("main.main");
    document.addEventListener("pointerup", observeAllowlistedAction, true);
    main?.addEventListener("scroll", observeScroll, { passive: true });
    return () => {
      document.removeEventListener("pointerup", observeAllowlistedAction, true);
      main?.removeEventListener("scroll", observeScroll);
    };
  }, [
    hydrated,
    open,
    pathname,
    preferences.enabled,
    preferences.spontaneous,
    preferences.tone,
    presentRemark,
    serverQuipAllowed,
    contextAttached,
  ]);

  useEffect(() => {
    if (!open) return;
    setBubbleVisible(false);
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      onOpenChange(false);
      triggerRef.current?.focus();
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onOpenChange, open]);

  function updatePreferences(next: Partial<CompanionPreferences>) {
    setPreferences((current) => ({ ...current, ...next }));
  }

  function updateQuestionDraft(value: string) {
    setQuestionDraft(value);
    if (!comparisonId) return;
    if (value) window.sessionStorage.setItem(DRAFT_KEY_PREFIX + comparisonId, value);
    else window.sessionStorage.removeItem(DRAFT_KEY_PREFIX + comparisonId);
  }

  async function handQuestionToCitedAsk(event: React.FormEvent) {
    event.preventDefault();
    const question = questionDraft.trim();
    if (!comparisonId || !question) return;
    setHandoffPending(true);
    if (conversationId) {
      try {
        const saved = await api<AssistantConversationResponse>(
          `/assistant/conversations/${conversationId}/handoffs`,
          {
            method: "POST",
            body: JSON.stringify({ question }),
          },
        );
        setRecentQuestions(saved.handoffs);
      } catch {
        // The cited Ask workflow remains available if personal history is offline.
      }
    }
    window.sessionStorage.removeItem(DRAFT_KEY_PREFIX + comparisonId);
    setQuestionDraft("");
    window.dispatchEvent(
      new CustomEvent(ASSISTANT_QUESTION_EVENT, {
        detail: { comparisonId, question },
      }),
    );
    onOpenChange(false);
    setHandoffPending(false);
  }

  if (!hydrated || !preferences.enabled) return null;

  const showQuip = preferences.tone !== "neutral";
  const runtimeReady = runtime?.ready ?? localAiReady;

  return (
    <aside
      aria-label={t("companion.panelLabel")}
      className="marvin-companion"
      data-open={open}
    >
      {open && (
        <section className="marvin-drawer">
          <header className="marvin-drawer-header">
            <div className="marvin-identity">
              <RobotPortrait compact />
              <span>
                <strong>{t("companion.name")}</strong>
                <small>{t("companion.role")}</small>
              </span>
            </div>
            <button
              aria-label={t("companion.close")}
              className="marvin-icon-button"
              onClick={() => {
                onOpenChange(false);
                triggerRef.current?.focus();
              }}
              type="button"
            >
              <X size={18} />
            </button>
          </header>

          <div className="marvin-drawer-body">
            <div className="marvin-status-row">
              <button
                aria-label={
                  contextAttached
                    ? t("companion.detachContext")
                    : t("companion.attachContext")
                }
                className={`marvin-context-chip ${
                  contextAttached ? "" : "is-detached"
                }`}
                onClick={() => setContextAttached((value) => !value)}
                type="button"
              >
                <Eye size={13} />
                {contextAttached
                  ? contextLabel || t(context.titleKey)
                  : t("companion.attachContext")}
                {contextAttached && <X size={12} />}
              </button>
              <span
                className={`marvin-model-status ${
                  runtimeReady ? "is-ready" : ""
                }`}
              >
                <span className="status-dot" />
                {t(runtimeStatusKey(runtime, localAiReady))}
              </span>
            </div>

            {runtime && (
              <p className="marvin-runtime-detail">
                {t("companion.runtimeProfile", {
                  profile: runtime.display_name,
                  model: runtime.selected_model.display_name,
                })}
              </p>
            )}

            {contextAttached ? (
              <div className="marvin-message">
                <span className="eyebrow">{t("companion.observation")}</span>
                <p>{t(context.descriptionKey)}</p>
              </div>
            ) : (
              <div className="marvin-message">
                <span className="eyebrow">{t("companion.observation")}</span>
                <p>{t("companion.noContext")}</p>
              </div>
            )}

            {showQuip && contextAttached && (
              <blockquote className="marvin-quip">
                “{t(context.quipKey)}”
              </blockquote>
            )}

            {contextAttached && (
              <Link
                className="marvin-primary-action"
                href={context.actionHref}
                onClick={() => onOpenChange(false)}
              >
                <span>
                  <Sparkles size={16} />
                  {t(context.actionKey)}
                </span>
                <ChevronRight size={16} />
              </Link>
            )}

            {comparisonId && contextAttached && (
              <form className="marvin-ask-form" onSubmit={handQuestionToCitedAsk}>
                <label htmlFor="marvin-question">{t("companion.askLabel")}</label>
                <textarea
                  id="marvin-question"
                  maxLength={2000}
                  onChange={(event) => updateQuestionDraft(event.target.value)}
                  placeholder={t("companion.askPlaceholder")}
                  rows={3}
                  value={questionDraft}
                />
                <small>{t("companion.draftPrivacy")}</small>
                <button
                  disabled={!questionDraft.trim() || handoffPending}
                  type="submit"
                >
                  {handoffPending ? (
                    <Loader2 className="animate-spin" size={15} />
                  ) : (
                    <Send size={15} />
                  )}
                  {t("companion.openCitedAsk")}
                </button>
                {recentQuestions.length > 0 && (
                  <div className="marvin-recent-questions">
                    <strong>{t("companion.recentQuestions")}</strong>
                    {recentQuestions
                      .slice(-3)
                      .reverse()
                      .map((item) => (
                        <button
                          key={item.id}
                          onClick={() => updateQuestionDraft(item.question)}
                          title={item.question}
                          type="button"
                        >
                          {item.question}
                        </button>
                      ))}
                  </div>
                )}
              </form>
            )}

            {visibleAiJobs.length > 0 && (
              <section className="marvin-jobs" aria-live="polite">
                <div className="marvin-jobs-heading">
                  <span>
                    <Loader2
                      className={activeAiJobs.length ? "animate-spin" : ""}
                      size={15}
                    />
                    <strong>{t("companion.aiWork")}</strong>
                  </span>
                  <small>
                    {activeAiJobs.length
                      ? t("companion.activeJobs", {
                          count: activeAiJobs.length,
                        })
                      : t("companion.latestJob")}
                  </small>
                </div>
                {visibleAiJobs.map((job) => {
                  const active = !TERMINAL_JOB_STATES.has(job.state);
                  const activeStep =
                    job.steps.find((step) => step.state === "running") ||
                    job.steps.find((step) => step.state === "pending");
                  const percent = Math.round(
                    (Math.max(0, job.progress.current) /
                      Math.max(1, job.progress.total)) *
                      100,
                  );
                  return (
                    <article className="marvin-job" key={job.id}>
                      <div>
                        <strong>
                          {translate(locale, `status.${job.type}`) ||
                            humanize(job.type)}
                        </strong>
                        <span className={`marvin-job-state ${job.state}`}>
                          {translate(locale, `status.${job.state}`) ||
                            humanize(job.state)}
                        </span>
                      </div>
                      <p>
                        {activeStep
                          ? translate(locale, `status.${activeStep.name}`) ||
                            activeStep.name
                          : t("companion.jobSaved")}
                        {job.queue_position
                          ? ` · ${t("companion.queuePosition", {
                              position: job.queue_position,
                            })}`
                          : ""}
                      </p>
                      <div
                        aria-label={t("companion.jobProgress", { percent })}
                        aria-valuemax={100}
                        aria-valuemin={0}
                        aria-valuenow={percent}
                        className="marvin-job-track"
                        role="progressbar"
                      >
                        <span style={{ width: `${percent}%` }} />
                      </div>
                      <Link
                        href={jobResultHref(job)}
                        onClick={() => onOpenChange(false)}
                      >
                        {active
                          ? t("companion.openJob")
                          : t("companion.openJobResult")}
                        <ArrowUpRight size={13} />
                      </Link>
                    </article>
                  );
                })}
              </section>
            )}

            <div className="marvin-boundary-note">
              <Bot size={16} />
              <p>{t("companion.contextBoundary")}</p>
            </div>

            <button
              aria-expanded={settingsOpen}
              className="marvin-settings-toggle"
              onClick={() => setSettingsOpen((value) => !value)}
              type="button"
            >
              <span>
                <Settings2 size={15} />
                {t("companion.behaviour")}
              </span>
              <ChevronRight
                className={settingsOpen ? "rotate-90" : ""}
                size={15}
              />
            </button>

            {settingsOpen && (
              <div className="marvin-settings">
                <label>
                  <span>{t("companion.tone")}</span>
                  <select
                    value={preferences.tone}
                    onChange={(event) =>
                      updatePreferences({ tone: event.target.value as Tone })
                    }
                  >
                    <option value="neutral">
                      {t("companion.toneNeutral")}
                    </option>
                    <option value="dry">{t("companion.toneDry")}</option>
                    <option value="very_dry">
                      {t("companion.toneVeryDry")}
                    </option>
                  </select>
                </label>
                <label className="marvin-check-row">
                  <input
                    checked={preferences.spontaneous}
                    onChange={(event) =>
                      updatePreferences({ spontaneous: event.target.checked })
                    }
                    type="checkbox"
                  />
                  <span>
                    <strong>{t("companion.spontaneous")}</strong>
                    <small>{t("companion.spontaneousHelp")}</small>
                  </span>
                </label>
                <button
                  className="marvin-disable"
                  onClick={() => {
                    updatePreferences({ spontaneous: false });
                    setBubbleVisible(false);
                  }}
                  type="button"
                >
                  <BellOff size={15} />
                  {t("companion.disable")}
                </button>
              </div>
            )}
          </div>
        </section>
      )}

      {!open && bubbleVisible && (
        <div className="marvin-bubble">
          <button
            aria-label={t("companion.dismissRemark")}
            className="marvin-bubble-close"
            onClick={() => setBubbleVisible(false)}
            type="button"
          >
            <X size={13} />
          </button>
          <button
            className="marvin-bubble-copy"
            onClick={() => onOpenChange(true)}
            type="button"
          >
            <strong>{t("companion.name")}</strong>
            <span>{t(bubbleKey || context.quipKey)}</span>
          </button>
        </div>
      )}

      <button
        aria-expanded={open}
        aria-label={
          open
            ? t("companion.close")
            : `${t("companion.open", { page: t(context.titleKey) })}${
                activeAiJobs.length
                  ? `. ${t("companion.activeJobs", {
                      count: activeAiJobs.length,
                    })}`
                  : ""
              }`
        }
        className="marvin-trigger"
        onClick={() => onOpenChange(!open)}
        ref={triggerRef}
        title={t("companion.open", { page: t(context.titleKey) })}
        type="button"
      >
        <RobotPortrait />
        <span className="marvin-trigger-badge">
          {activeAiJobs.length ? (
            <span aria-hidden="true">{Math.min(activeAiJobs.length, 9)}</span>
          ) : (
            <MessageCircle size={13} />
          )}
        </span>
      </button>
    </aside>
  );
}
