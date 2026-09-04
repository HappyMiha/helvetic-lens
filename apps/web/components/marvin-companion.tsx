"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BellOff,
  Bot,
  ChevronRight,
  Eye,
  MessageCircle,
  Settings2,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

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
const DEFAULT_PREFERENCES: CompanionPreferences = {
  enabled: true,
  spontaneous: true,
  tone: "very_dry",
};

type AssistantContextResponse = {
  persona: { quip_allowed: boolean };
};

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

function routeContext(pathname: string): RouteContext {
  if (pathname.startsWith("/compare/")) {
    return {
      actionHref: pathname,
      actionKey: "companion.action.reviewComparison",
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
  const { t } = useI18n();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [preferences, setPreferences] =
    useState<CompanionPreferences>(DEFAULT_PREFERENCES);
  const [hydrated, setHydrated] = useState(false);
  const [bubbleVisible, setBubbleVisible] = useState(false);
  const [bubbleKey, setBubbleKey] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [serverQuipAllowed, setServerQuipAllowed] = useState(false);
  const interactionCount = useRef(0);
  const deepScrollSeen = useRef(false);
  const context = useMemo(() => routeContext(pathname), [pathname]);

  useEffect(() => {
    setPreferences(readPreferences());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    let active = true;
    setServerQuipAllowed(false);
    api<AssistantContextResponse>("/assistant/context", {
      method: "POST",
      body: JSON.stringify({
        schema_version: "assistant-context.v1",
        intent: "explain_screen",
        route: contractRoute(pathname),
      }),
    })
      .then((response) => {
        if (active) setServerQuipAllowed(response.persona.quip_allowed);
      })
      .catch(() => {
        if (active) setServerQuipAllowed(false);
      });
    return () => {
      active = false;
    };
  }, [hydrated, pathname]);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
    } catch {
      // Private browsing may deny storage; keep the in-memory preference.
    }
  }, [hydrated, preferences]);

  useEffect(() => {
    setBubbleVisible(false);
    setBubbleKey(null);
    setSettingsOpen(false);
    interactionCount.current = 0;
    deepScrollSeen.current = false;
    if (
      !hydrated ||
      !preferences.enabled ||
      !preferences.spontaneous ||
      preferences.tone === "neutral" ||
      !serverQuipAllowed ||
      seenRecently(pathname)
    ) {
      return;
    }
    const delay = 6500 + (pathname.length % 4) * 1200;
    const timer = window.setTimeout(() => {
      if (document.visibilityState !== "visible" || open) return;
      rememberRoute(pathname);
      setBubbleKey(context.quipKey);
      setBubbleVisible(true);
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
  ]);

  useEffect(() => {
    if (
      !hydrated ||
      !preferences.enabled ||
      !preferences.spontaneous ||
      preferences.tone === "neutral" ||
      !serverQuipAllowed ||
      open
    ) {
      return;
    }

    function showActivityRemark(key: string) {
      if (seenRecently(`${pathname}:activity`)) return;
      rememberRoute(`${pathname}:activity`);
      setBubbleKey(key);
      setBubbleVisible(true);
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
      showActivityRemark("companion.quip.deepScroll");
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
    serverQuipAllowed,
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

  if (!hydrated || !preferences.enabled) return null;

  const showQuip = preferences.tone !== "neutral";

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
              <span className="marvin-context-chip">
                <Eye size={13} />
                {t(context.titleKey)}
              </span>
              <span
                className={`marvin-model-status ${
                  localAiReady ? "is-ready" : ""
                }`}
              >
                <span className="status-dot" />
                {localAiReady
                  ? t("companion.localReady")
                  : t("companion.localUnavailable")}
              </span>
            </div>

            <div className="marvin-message">
              <span className="eyebrow">{t("companion.observation")}</span>
              <p>{t(context.descriptionKey)}</p>
            </div>

            {showQuip && (
              <blockquote className="marvin-quip">
                “{t(context.quipKey)}”
              </blockquote>
            )}

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
            : t("companion.open", { page: t(context.titleKey) })
        }
        className="marvin-trigger"
        onClick={() => onOpenChange(!open)}
        ref={triggerRef}
        title={t("companion.open", { page: t(context.titleKey) })}
        type="button"
      >
        <RobotPortrait />
        <span className="marvin-trigger-badge">
          <MessageCircle size={13} />
        </span>
      </button>
    </aside>
  );
}
