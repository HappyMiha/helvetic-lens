"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  Building2,
  ChevronDown,
  CircleHelp,
  FileText,
  Globe2,
  History,
  Inbox,
  Landmark,
  LayoutGrid,
  Loader2,
  Mail,
  PackageOpen,
  RefreshCw,
  ScrollText,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errorText, refreshWorkspace, useResource } from "@/lib/api";
import { AdminOnly, useAuth } from "./auth-gate";
import type { Health, Profile } from "@/lib/types";
import { ErrorNote, SuccessNote } from "./common";
import { BrandLockup } from "./brand";
import { LanguageSelector, useI18n } from "@/lib/i18n";

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
  const { data: health, error } = useResource<Health>("/health", 15000);
  const { session, canManage, isPlatformAdmin } = useAuth();
  const { t } = useI18n();
  const [profileOpen, setProfileOpen] = useState(false);
  return (
    <div className="shell">
      <aside className="sidebar">
        <Link href="/" className="brand">
          <span>
            <BrandLockup />
            <small>{t("brand.tagline")}</small>
          </span>
        </Link>
        <button
          className="workspace text-left"
          onClick={() => {
            if (canManage) setProfileOpen(true);
          }}
        >
          <span className="eyebrow">{t("shell.workspace")}</span>
          <span className="flex items-center justify-between mt-2 font-semibold">
            {session?.organization?.name || t("shell.defaultWorkspace")}
            <ChevronDown size={14} />
          </span>
        </button>
        <nav className="nav-group">
          <span className="eyebrow mb-2 ml-3">{t("shell.monitor")}</span>
          <Link
            className={
              "nav-item " +
              (pathname === "/" ||
              pathname.startsWith("/laws") ||
              pathname.startsWith("/compare")
                ? "active"
                : "")
            }
            href="/"
          >
            <Activity size={17} />
            {t("nav.overview")}
          </Link>
          <Link
            className={"nav-item " + (pathname === "/registry" ? "active" : "")}
            href="/registry"
          >
            <Landmark size={17} />
            {t("nav.registry")}
          </Link>
          <Link
            className={"nav-item " + (pathname === "/impact" ? "active" : "")}
            href="/impact"
          >
            <Inbox size={17} />
            {t("nav.impact")}
          </Link>
          <Link
            className={"nav-item " + (pathname === "/matrix" ? "active" : "")}
            href="/matrix"
          >
            <LayoutGrid size={17} />
            {t("nav.matrix")}
          </Link>
          {session?.authenticated && (
            <Link
              className={
                "nav-item " + (pathname === "/digests" ? "active" : "")
              }
              href="/digests"
            >
              <Mail size={17} />
              {t("nav.digests")}
            </Link>
          )}
          {session?.authenticated && (
            <Link
              className={
                "nav-item " + (pathname === "/organization" ? "active" : "")
              }
              href="/organization"
            >
              <Users size={17} />
              {t("nav.organization")}
            </Link>
          )}
          <Link
            className={"nav-item " + (pathname === "/sources" ? "active" : "")}
            href="/sources"
          >
            <Globe2 size={17} />
            {t("nav.sources")}
          </Link>
          <Link
            className={"nav-item " + (pathname === "/activity" ? "active" : "")}
            href="/activity"
          >
            <History size={17} />
            {t("nav.activity")}
          </Link>
          <Link
            className={"nav-item " + (pathname === "/logs" ? "active" : "")}
            href="/logs"
          >
            <ScrollText size={17} />
            {t("nav.logs")}
          </Link>
          {isPlatformAdmin && (
            <Link
              className={"nav-item " + (pathname === "/admin" ? "active" : "")}
              href="/admin"
            >
              <SlidersHorizontal size={17} />
              {t("nav.admin")}
            </Link>
          )}
          {isPlatformAdmin && (
            <Link
              className={
                "nav-item " + (pathname === "/connectors" ? "active" : "")
              }
              href="/connectors"
            >
              <RefreshCw size={17} />
              {t("nav.sync")}
            </Link>
          )}
          {isPlatformAdmin && (
            <Link
              className={"nav-item " + (pathname === "/models" ? "active" : "")}
              href="/models"
            >
              <PackageOpen size={17} />
              {t("nav.models")}
            </Link>
          )}
          <AdminOnly>
            <button className="nav-item" onClick={() => setProfileOpen(true)}>
              <Building2 size={17} />
              {t("nav.profile")}
            </button>
          </AdminOnly>
          <Link
            className={"nav-item " + (pathname === "/prompts" ? "active" : "")}
            href="/prompts"
          >
            <FileText size={17} />
            {t("nav.prompts")}
          </Link>
          <Link
            className={"nav-item " + (pathname === "/settings" ? "active" : "")}
            href="/settings"
          >
            <Settings2 size={17} />
            {t("nav.settings")}
          </Link>
        </nav>
        <div className="sidebar-bottom">
          <Link
            className="model-card"
            href={isPlatformAdmin ? "/models" : "/settings"}
          >
            <Sparkles size={17} />
            <div>
              <strong>{t("shell.apertusSettings")}</strong>
              <span>
                {health?.apertus.configured
                  ? t("shell.endpointConfigured")
                  : t("shell.connectEndpoint")}
              </span>
            </div>
          </Link>
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
              <span className={"status-dot " + (error ? "!bg-red-500" : "")} />
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
                onClick={async () => {
                  await api("/auth/logout", { method: "POST" });
                  window.location.assign("/login");
                }}
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
        <nav className="mobile-nav">
          <Link href="/">{t("nav.overview")}</Link>
          <Link href="/registry">{t("nav.registry")}</Link>
          <Link href="/impact">{t("nav.impact")}</Link>
          <Link href="/matrix">{t("nav.matrix")}</Link>
          {session?.authenticated && (
            <Link href="/digests">{t("nav.digests")}</Link>
          )}
          <Link href="/sources">{t("nav.sources")}</Link>
          <Link href="/activity">{t("nav.activity")}</Link>
          {isPlatformAdmin && <Link href="/admin">{t("nav.admin")}</Link>}
          {isPlatformAdmin && <Link href="/models">{t("nav.models")}</Link>}
          <Link href="/logs">{t("nav.logs")}</Link>
          <Link href="/prompts">{t("nav.prompts")}</Link>
          <Link href="/settings">{t("nav.settings")}</Link>
        </nav>
        <div className={"content " + (wide ? "content-wide" : "")}>
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
      <ProfileDialog
        open={profileOpen}
        onOpenChange={setProfileOpen}
        health={health}
      />
    </div>
  );
}

export function ProfileDialog({
  open,
  onOpenChange,
  health,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  health: Health | null;
}) {
  const { t, number } = useI18n();
  const { data } = useResource<Profile>(open ? "/profile" : null);
  const [name, setName] = useState(""),
    [description, setDescription] = useState(""),
    [areas, setAreas] = useState("");
  const [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [success, setSuccess] = useState("");
  useEffect(() => {
    if (data) {
      setName(data.name);
      setDescription(data.description);
      setAreas(data.business_areas.join(", "));
    }
  }, [data]);
  useEffect(() => {
    if (open) {
      setError("");
      setSuccess("");
    }
  }, [open]);
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy("save");
    setError("");
    setSuccess("");
    try {
      await api("/profile", {
        method: "PATCH",
        body: JSON.stringify({
          name,
          description,
          business_areas: areas
            .split(",")
            .map((v) => v.trim())
            .filter(Boolean),
        }),
      });
      refreshWorkspace();
      setSuccess(t("profile.saved"));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  async function test() {
    setBusy("test");
    setError("");
    setSuccess("");
    try {
      const value = await api<{ latency_ms: number }>("/model/test", {
        method: "POST",
      });
      setSuccess(
        t("profile.testSuccess", { duration: number(value.latency_ms) }),
      );
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{t("profile.title")}</DialogTitle>
          <DialogDescription>{t("profile.body")}</DialogDescription>
        </DialogHeader>
        <form onSubmit={save} className="form-stack">
          <label>
            {t("profile.name")}
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={200}
            />
          </label>
          <label>
            {t("profile.description")}
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("profile.descriptionPlaceholder")}
              rows={4}
              maxLength={6000}
            />
          </label>
          <label>
            {t("profile.areas")}
            <Input
              value={areas}
              onChange={(e) => setAreas(e.target.value)}
              placeholder={t("profile.areasPlaceholder")}
            />
          </label>
          <ErrorNote message={error} />
          {success && <SuccessNote>{success}</SuccessNote>}
          <Button type="submit" disabled={!!busy || !name.trim()}>
            {busy === "save" && <Loader2 className="animate-spin" />}
            {t("profile.save")}
          </Button>
        </form>
        <div className="border-t pt-5 mt-2">
          <div className="flex items-center gap-2 font-semibold">
            <Sparkles size={16} />
            {t("profile.connection")}
          </div>
          <p className="text-xs muted break-all">
            {health?.apertus.model || "swiss-ai/Apertus-v1.5-8B"}
          </p>
          <p className="text-xs muted">{t("profile.connectionBody")}</p>
          <Button asChild variant="outline" size="sm" className="mr-2 mb-2">
            <Link href="/settings" onClick={() => onOpenChange(false)}>
              {t("shell.apertusSettings")}
            </Link>
          </Button>
          <Button variant="outline" size="sm" onClick={test} disabled={!!busy}>
            {busy === "test" ? (
              <Loader2 className="animate-spin" />
            ) : (
              <BookOpen />
            )}
            {t("profile.test")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
