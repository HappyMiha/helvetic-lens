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
  Loader2,
  ScrollText,
  Settings2,
  ShieldCheck,
  Sparkles,
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
import type { Health, Profile } from "@/lib/types";
import { ErrorNote, SuccessNote } from "./common";

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
  const [profileOpen, setProfileOpen] = useState(false);
  return (
    <div className="shell">
      <aside className="sidebar">
        <Link href="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            HL
          </span>
          <span>
            Helvetic Lens
            <small>
              See what changed.
              <br />
              Understand what matters.
            </small>
          </span>
        </Link>
        <button
          className="workspace text-left"
          onClick={() => setProfileOpen(true)}
        >
          <span className="eyebrow">WORKSPACE</span>
          <span className="flex items-center justify-between mt-2 font-semibold">
            Swiss regulatory watch
            <ChevronDown size={14} />
          </span>
        </button>
        <nav className="nav-group">
          <span className="eyebrow mb-2 ml-3">MONITOR</span>
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
            Overview
          </Link>
          <Link
            className={"nav-item " + (pathname === "/sources" ? "active" : "")}
            href="/sources"
          >
            <Globe2 size={17} />
            Sources
          </Link>
          <Link
            className={"nav-item " + (pathname === "/activity" ? "active" : "")}
            href="/activity"
          >
            <History size={17} />
            Scan activity
          </Link>
          <Link
            className={"nav-item " + (pathname === "/logs" ? "active" : "")}
            href="/logs"
          >
            <ScrollText size={17} />
            Integration logs
          </Link>
          <button className="nav-item" onClick={() => setProfileOpen(true)}>
            <Building2 size={17} />
            Company profile
          </button>
          <Link
            className={"nav-item " + (pathname === "/prompts" ? "active" : "")}
            href="/prompts"
          >
            <FileText size={17} />
            Prompt settings
          </Link>
          <Link
            className={"nav-item " + (pathname === "/settings" ? "active" : "")}
            href="/settings"
          >
            <Settings2 size={17} />
            Settings
          </Link>
        </nav>
        <div className="sidebar-bottom">
          <Link className="model-card" href="/settings">
            <Sparkles size={17} />
            <div>
              <strong>Apertus settings</strong>
              <span>
                {health?.apertus.configured
                  ? "Endpoint configured"
                  : "Connect your model endpoint"}
              </span>
            </div>
          </Link>
          <p className="text-xs muted leading-relaxed">
            Your sources. Your versions.
            <br />
            Evidence you can inspect.
          </p>
          <a
            href="https://github.com/HappyMiha/helvetic-lens"
            target="_blank"
            rel="noreferrer"
            className="text-xs flex items-center gap-2 muted mt-4"
          >
            <CircleHelp size={14} />
            Project & documentation
            <ArrowUpRight size={12} />
          </a>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <span className="text-xs muted">
            Workspace <span className="mx-3">/</span>
            <span className="text-foreground">{section}</span>
          </span>
          <div className="flex items-center gap-5">
            <span className="hidden sm:inline text-xs">
              <span className={"status-dot " + (error ? "!bg-red-500" : "")} />
              {error
                ? "API unavailable"
                : health
                  ? "Connected · " + health.database
                  : "Connecting…"}
            </span>
            <span className="avatar">HL</span>
          </div>
        </header>
        <nav className="mobile-nav">
          <Link href="/">Overview</Link>
          <Link href="/sources">Sources</Link>
          <Link href="/activity">Activity</Link>
          <Link href="/logs">Logs</Link>
          <Link href="/prompts">Prompts</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        <div className={"content " + (wide ? "content-wide" : "")}>
          {error && (
            <ErrorNote message="The API is unavailable. Displayed records may be stale; start the backend to resume monitoring." />
          )}
          {children}
          <footer className="workspace-footer">
            <ShieldCheck size={13} />
            Saved evidence, visible changes. AI outputs support human review.
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
      setSuccess(
        "Profile saved. Earlier impact analyses are marked stale if the profile changed.",
      );
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
      setSuccess("Apertus responded in " + value.latency_ms + " ms.");
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
          <DialogTitle>Company profile</DialogTitle>
          <DialogDescription>
            Give Apertus context for a useful impact assessment. One profile
            keeps the MVP simple.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={save} className="form-stack">
          <label>
            Company name
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={200}
            />
          </label>
          <label>
            What does your company do?
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="A Swiss software company processing customer data…"
              rows={4}
              maxLength={6000}
            />
          </label>
          <label>
            Business areas
            <Input
              value={areas}
              onChange={(e) => setAreas(e.target.value)}
              placeholder="Legal, IT, HR, Operations"
            />
          </label>
          <ErrorNote message={error} />
          {success && <SuccessNote>{success}</SuccessNote>}
          <Button type="submit" disabled={!!busy || !name.trim()}>
            {busy === "save" && <Loader2 className="animate-spin" />}Save
            profile
          </Button>
        </form>
        <div className="border-t pt-5 mt-2">
          <div className="flex items-center gap-2 font-semibold">
            <Sparkles size={16} />
            Apertus connection
          </div>
          <p className="text-xs muted break-all">
            {health?.apertus.model || "swiss-ai/Apertus-v1.5-8B"}
          </p>
          <p className="text-xs muted">
            Open Settings to edit the endpoint, model, key, and request limits.
            Saved settings apply immediately; existing keys are never returned
            to this browser.
          </p>
          <Button asChild variant="outline" size="sm" className="mr-2 mb-2">
            <Link href="/settings" onClick={() => onOpenChange(false)}>
              Apertus settings
            </Link>
          </Button>
          <Button variant="outline" size="sm" onClick={test} disabled={!!busy}>
            {busy === "test" ? (
              <Loader2 className="animate-spin" />
            ) : (
              <BookOpen />
            )}
            Test real connection
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
