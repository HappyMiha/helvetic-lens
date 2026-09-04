"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  ArrowUpRight,
  Check,
  ChevronDown,
  CircleHelp,
  FileSearch,
  FileText,
  Globe2,
  History,
  Inbox,
  Landmark,
  LayoutGrid,
  Loader2,
  Mail,
  MoreHorizontal,
  PackageOpen,
  RefreshCw,
  Rocket,
  ScrollText,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Users,
} from "lucide-react";
import {
  api,
  errorText,
  resetResourceScope,
  useResource,
} from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { type AuthSession, useAuth } from "./auth-gate";
import type { Health } from "@/lib/types";
import { ErrorNote } from "./common";
import { BrandLockup } from "./brand";
import { LanguageSelector, useI18n } from "@/lib/i18n";

type NavigationItemProps = {
  active: boolean;
  children: React.ReactNode;
  href: string;
};

function NavigationItem({ active, children, href }: NavigationItemProps) {
  return (
    <Link
      aria-current={active ? "page" : undefined}
      className={`nav-item ${active ? "active" : ""}`}
      href={href}
    >
      {children}
    </Link>
  );
}

type WorkspaceOption = NonNullable<AuthSession["organizations"]>[number];

function WorkspaceSwitcher({
  busy,
  canSwitch,
  currentName,
  error,
  mobile = false,
  onSwitch,
  organizations,
}: {
  busy: string;
  canSwitch: boolean;
  currentName: string;
  error: string;
  mobile?: boolean;
  onSwitch: (organizationId: string) => Promise<void>;
  organizations: WorkspaceOption[];
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const optionsId = useId();

  useEffect(() => {
    if (!open) return;
    function closeOnOutsideClick(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    }
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div
      className={`workspace-switcher ${mobile ? "mobile-workspace-switcher" : ""}`}
      ref={containerRef}
    >
      {canSwitch ? (
        <button
          aria-controls={optionsId}
          aria-expanded={open}
          className="workspace text-left"
          onClick={() => setOpen((value) => !value)}
          ref={triggerRef}
          type="button"
        >
          <span className="eyebrow">{t("shell.workspace")}</span>
          <span className="flex items-center justify-between mt-2 font-semibold gap-2">
            <span>{currentName}</span>
            <ChevronDown className={open ? "rotate-180" : ""} size={14} />
          </span>
        </button>
      ) : (
        <div className="workspace">
          <span className="eyebrow">{t("shell.workspace")}</span>
          <span className="block mt-2 font-semibold">{currentName}</span>
        </div>
      )}
      {open && (
        <ul
          aria-label={t("shell.switchWorkspace")}
          className="workspace-menu"
          id={optionsId}
        >
          {organizations.map((organization) => (
            <li key={organization.id}>
              <button
                className="workspace-option"
                disabled={organization.current || !!busy}
                onClick={() => void onSwitch(organization.id)}
                type="button"
              >
                <span>
                  <strong>{organization.name}</strong>
                  <small>
                    {organization.role === "viewer"
                      ? t("org.viewer")
                      : t("org.admin")}
                  </small>
                </span>
                {busy === organization.id ? (
                  <Loader2 className="animate-spin" size={14} />
                ) : organization.current ? (
                  <Check size={14} />
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p className="workspace-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function Shell({
  children,
  section = "Overview",
  wide = false,
}: {
  children: React.ReactNode;
  section?: string;
  wide?: boolean;
}) {
  const pathname = usePathname();
  const { data: health, error } = useResource(resources.health());
  const { session, canManage, isPlatformAdmin } = useAuth();
  const { t } = useI18n();
  const [workspaceBusy, setWorkspaceBusy] = useState("");
  const [workspaceError, setWorkspaceError] = useState("");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const mobileMenuRef = useRef<HTMLDetailsElement>(null);
  const mobileMenuTriggerRef = useRef<HTMLElement>(null);

  const organizations = session?.organizations || [];
  const canSwitchWorkspace = session?.authenticated && organizations.length > 1;
  const monitoringActive =
    pathname === "/registry" ||
    pathname.startsWith("/laws") ||
    pathname.startsWith("/compare");
  const administrationActive =
    pathname === "/logs" ||
    pathname === "/prompts" ||
    pathname === "/settings" ||
    pathname === "/admin" ||
    pathname === "/deployments" ||
    pathname === "/connectors" ||
    pathname === "/models";
  const [administrationOpen, setAdministrationOpen] =
    useState(administrationActive);

  useEffect(() => {
    if (administrationActive) setAdministrationOpen(true);
  }, [administrationActive]);

  useEffect(() => setMobileMenuOpen(false), [pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    function closeOnOutside(event: PointerEvent) {
      if (!mobileMenuRef.current?.contains(event.target as Node)) {
        setMobileMenuOpen(false);
      }
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setMobileMenuOpen(false);
      mobileMenuTriggerRef.current?.focus();
    }
    document.addEventListener("pointerdown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [mobileMenuOpen]);

  function continueAfterProfileGuard(continueNavigation: () => void) {
    const event = new CustomEvent("helvetic:navigation-committed", {
      cancelable: true,
      detail: { continueNavigation },
    });
    if (window.dispatchEvent(event)) continueNavigation();
  }

  async function switchWorkspace(organizationId: string) {
    const proceed = window.dispatchEvent(
      new CustomEvent("helvetic:before-navigation", { cancelable: true }),
    );
    if (!proceed) return;
    setWorkspaceBusy(organizationId);
    setWorkspaceError("");
    try {
      await api("/auth/session/organization", {
        method: "POST",
        body: JSON.stringify({ organization_id: organizationId }),
      });
      resetResourceScope("organization");
      resetResourceScope("session");
      continueAfterProfileGuard(() => window.location.reload());
    } catch (cause) {
      setWorkspaceError(errorText(cause));
      setWorkspaceBusy("");
    }
  }

  async function signOut() {
    const proceed = window.dispatchEvent(
      new CustomEvent("helvetic:before-navigation", { cancelable: true }),
    );
    if (!proceed) return;
    setWorkspaceError("");
    try {
      await api("/auth/logout", { method: "POST" });
      resetResourceScope("all");
      continueAfterProfileGuard(() => window.location.assign("/login"));
    } catch (cause) {
      setWorkspaceError(errorText(cause));
    }
  }

  const workspaceItems = (
    <>
      <NavigationItem active={pathname === "/matrix"} href="/matrix">
        <LayoutGrid size={17} />
        {t("nav.matrix")}
      </NavigationItem>
      {session?.authenticated && (
        <NavigationItem active={pathname === "/digests"} href="/digests">
          <Mail size={17} />
          {t("nav.digests")}
        </NavigationItem>
      )}
      <NavigationItem active={pathname === "/activity"} href="/activity">
        <History size={17} />
        {t("nav.activity")}
      </NavigationItem>
      <NavigationItem
        active={pathname === "/organization"}
        href="/organization"
      >
        <Users size={17} />
        {t("nav.profile")}
      </NavigationItem>
    </>
  );

  const administrationItems = (
    <>
      {canManage && (
        <>
          <NavigationItem active={pathname === "/settings"} href="/settings">
            <Settings2 size={17} />
            {t("nav.settings")}
          </NavigationItem>
          <NavigationItem active={pathname === "/prompts"} href="/prompts">
            <FileText size={17} />
            {t("nav.prompts")}
          </NavigationItem>
          <NavigationItem active={pathname === "/logs"} href="/logs">
            <ScrollText size={17} />
            {t("nav.logs")}
          </NavigationItem>
        </>
      )}
      {isPlatformAdmin && (
        <>
          <span className="nav-subheading">{t("shell.platform")}</span>
          <NavigationItem active={pathname === "/admin"} href="/admin">
            <SlidersHorizontal size={17} />
            {t("nav.admin")}
          </NavigationItem>
          <NavigationItem active={pathname === "/deployments"} href="/deployments">
            <Rocket size={17} />
            {t("nav.deployments")}
          </NavigationItem>
          <NavigationItem
            active={pathname === "/connectors"}
            href="/connectors"
          >
            <RefreshCw size={17} />
            {t("nav.sync")}
          </NavigationItem>
          <NavigationItem active={pathname === "/models"} href="/models">
            <PackageOpen size={17} />
            {t("nav.models")}
          </NavigationItem>
        </>
      )}
    </>
  );

  const mobileOverflowRoute = [
    [pathname === "/sources", "nav.sources"],
    [pathname === "/matrix", "nav.matrix"],
    [pathname === "/digests", "nav.digests"],
    [pathname === "/activity", "nav.activity"],
    [pathname === "/organization", "nav.profile"],
    [pathname === "/settings", "nav.settings"],
    [pathname === "/prompts", "nav.prompts"],
    [pathname === "/logs", "nav.logs"],
    [pathname === "/admin", "nav.admin"],
    [pathname === "/deployments", "nav.deployments"],
    [pathname === "/connectors", "nav.sync"],
    [pathname === "/models", "nav.models"],
  ].find(([active]) => active);
  const mobileOverflowActive = Boolean(mobileOverflowRoute);
  const mobileOverflowLabel = mobileOverflowRoute
    ? t(mobileOverflowRoute[1] as string)
    : t("nav.more");

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link href="/" className="brand">
          <span>
            <BrandLockup />
            <small>{t("brand.tagline")}</small>
          </span>
        </Link>
        <WorkspaceSwitcher
          busy={workspaceBusy}
          canSwitch={Boolean(canSwitchWorkspace)}
          currentName={
            session?.organization?.name || t("shell.defaultWorkspace")
          }
          error={workspaceError}
          onSwitch={switchWorkspace}
          organizations={organizations}
        />
        <nav aria-label={t("shell.primaryNavigation")} className="nav-group">
          <section className="nav-section">
            <span className="nav-heading">{t("shell.dailyWork")}</span>
            <NavigationItem active={pathname === "/"} href="/">
              <Activity size={17} />
              {t("nav.today")}
            </NavigationItem>
            <NavigationItem active={monitoringActive} href="/registry">
              <Landmark size={17} />
              {t("nav.monitoring")}
            </NavigationItem>
            <NavigationItem active={pathname === "/impact"} href="/impact">
              <Inbox size={17} />
              {t("nav.impact")}
            </NavigationItem>
            <NavigationItem active={pathname === "/discover"} href="/discover">
              <FileSearch size={17} />
              {t("nav.discover")}
            </NavigationItem>
            <NavigationItem active={pathname === "/sources"} href="/sources">
              <Globe2 size={17} />
              {t("nav.sources")}
            </NavigationItem>
          </section>
          <section className="nav-section">
            <span className="nav-heading">{t("shell.workspaceSettings")}</span>
            {workspaceItems}
          </section>
          {(canManage || isPlatformAdmin) && (
            <details
              className="nav-admin"
              onToggle={(event) =>
                setAdministrationOpen(event.currentTarget.open)
              }
              open={administrationOpen}
            >
              <summary>
                <ShieldCheck size={15} />
                {t("shell.administration")}
                <ChevronDown size={13} />
              </summary>
              <div className="nav-section nav-admin-items">
                {administrationItems}
              </div>
            </details>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="model-card" role="status">
            <span className={`status-dot ${error ? "!bg-red-500" : ""}`} />
            <div>
              <strong>
                {error ? t("shell.apiUnavailable") : t("shell.systemStatus")}
              </strong>
              <span>
                {health?.apertus.configured
                  ? t("shell.localAiReady")
                  : t("shell.localAiUnavailable")}
              </span>
            </div>
          </div>
          <p className="text-xs muted leading-relaxed">
            {t("shell.evidencePromise")}
          </p>
          <a
            href="https://github.com/HappyMiha/helvetic-lens"
            target="_blank"
            rel="noreferrer"
            className="text-xs flex items-center gap-2 muted mt-4"
          >
            <CircleHelp size={14} />
            {t("shell.documentation")}
            <ArrowUpRight size={12} />
          </a>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <span className="text-xs muted">
            {t("shell.workspace")} <span className="mx-3">/</span>
            <span className="text-foreground">{section}</span>
          </span>
          <div className="flex items-center gap-5">
            <LanguageSelector compact />
            <span className="hidden sm:inline text-xs">
              <span className={`status-dot ${error ? "!bg-red-500" : ""}`} />
              {error
                ? t("shell.apiUnavailable")
                : health
                  ? t("shell.connected", { database: health.database })
                  : t("shell.connecting")}
            </span>
            {session?.authenticated ? (
              <button
                className="avatar"
                title={t("shell.signOut", { name: session.user?.name || "" })}
                onClick={() => void signOut()}
                type="button"
              >
                {(session.user?.name || "HL")
                  .split(" ")
                  .map((part) => part[0])
                  .join("")
                  .slice(0, 2)
                  .toUpperCase()}
              </button>
            ) : (
              <span className="avatar">HL</span>
            )}
          </div>
        </header>
        <nav aria-label={t("shell.mobileNavigation")} className="mobile-nav">
          <NavigationItem active={pathname === "/"} href="/">
            <Activity size={15} />
            <span>{t("mobileNav.today")}</span>
          </NavigationItem>
          <NavigationItem active={monitoringActive} href="/registry">
            <Landmark size={15} />
            <span>{t("mobileNav.monitoring")}</span>
          </NavigationItem>
          <NavigationItem active={pathname === "/impact"} href="/impact">
            <Inbox size={15} />
            <span>{t("mobileNav.impact")}</span>
          </NavigationItem>
          <NavigationItem active={pathname === "/discover"} href="/discover">
            <FileSearch size={15} />
            <span>{t("mobileNav.discover")}</span>
          </NavigationItem>
          <details
            className="mobile-nav-more"
            onToggle={(event) => setMobileMenuOpen(event.currentTarget.open)}
            open={mobileMenuOpen}
            ref={mobileMenuRef}
          >
            <summary
              aria-current={mobileOverflowActive ? "page" : undefined}
              aria-label={t("shell.mobileMenuLabel", { destination: mobileOverflowLabel })}
              className={mobileOverflowActive ? "active" : undefined}
              ref={mobileMenuTriggerRef}
            >
              <MoreHorizontal size={16} />
              <span className="mobile-nav-more-label">
                {mobileOverflowActive ? mobileOverflowLabel : t("mobileNav.more")}
              </span>
            </summary>
            <div className="mobile-nav-menu">
              <span className="nav-heading">{t("shell.dailyWork")}</span>
              <NavigationItem active={pathname === "/sources"} href="/sources">
                <Globe2 size={15} />
                {t("nav.sources")}
              </NavigationItem>
              <span className="nav-heading">
                {t("shell.workspaceSettings")}
              </span>
              <WorkspaceSwitcher
                busy={workspaceBusy}
                canSwitch={Boolean(canSwitchWorkspace)}
                currentName={
                  session?.organization?.name || t("shell.defaultWorkspace")
                }
                error={workspaceError}
                mobile
                onSwitch={switchWorkspace}
                organizations={organizations}
              />
              {workspaceItems}
              {(canManage || isPlatformAdmin) && (
                <>
                  <span className="nav-heading">
                    {t("shell.administration")}
                  </span>
                  {administrationItems}
                </>
              )}
            </div>
          </details>
        </nav>
        <div className={`content ${wide ? "content-wide" : ""}`}>
          {error && <ErrorNote message={t("shell.apiError")} />}
          {session?.authenticated && session.role === "viewer" && (
            <div className="mb-5 rounded-xl border border-[#d6decf] bg-[#f3f6ef] px-4 py-3 text-sm text-[#50604c]">
              <strong>{t("shell.readOnlyTitle")}</strong>{" "}
              {t("shell.readOnlyBody")}
            </div>
          )}
          {children}
          <footer className="workspace-footer">
            <ShieldCheck size={13} />
            {t("shell.footer")}
          </footer>
        </div>
      </main>
    </div>
  );
}
