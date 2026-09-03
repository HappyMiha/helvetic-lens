"use client";

import Link from "next/link";
import {
  Activity,
  ArchiveRestore,
  Bot,
  Database,
  FileText,
  Gauge,
  HardDrive,
  RefreshCw,
  ScrollText,
  Server,
  Users,
} from "lucide-react";
import { Shell } from "./shell";
import { useAuth } from "./auth-gate";
import { ErrorNote, Loading } from "./common";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { dateTime, label, useResource } from "@/lib/api";
import type { PlatformStatus } from "@/lib/types";

function bytes(value = 0) {
  return `${(value / 1024 ** 3).toFixed(value < 1024 ** 3 ? 2 : 1)} GB`;
}

function age(seconds: number | null) {
  if (seconds === null) return "Never";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

const links = [
  ["Local model control", "/models", Bot, "Catalogue, downloads, GPU deployment and benchmark"],
  ["Official source sync", "/connectors", RefreshCw, "Global connector schedules, freshness and manual runs"],
  ["Queues and jobs", "/activity", Activity, "Progress, retries, cancellation and failed work"],
  ["Bounded diagnostics", "/logs", ScrollText, "Redacted integration requests, responses and failures"],
  ["Global prompt defaults", "/prompts?scope=platform", FileText, "Defaults inherited by organizations without overrides"],
] as const;

export function PlatformAdminPage() {
  const { isPlatformAdmin } = useAuth();
  const status = useResource<PlatformStatus>(isPlatformAdmin ? "/admin/status" : null, 10000);
  return (
    <Shell section="Platform administration" wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">PLATFORM SCOPE · LOCAL SERVER</span>
          <h1>Installation control room</h1>
          <p>Operate this Helvetic Lens server without exposing Docker or arbitrary commands to the browser.</p>
        </div>
        <Button variant="outline" onClick={status.reload} disabled={status.loading}>
          <RefreshCw className={status.loading ? "animate-spin" : ""} /> Refresh
        </Button>
      </div>
      {!isPlatformAdmin && <ErrorNote message="A platform administrator can open this installation-wide view." />}
      <ErrorNote message={status.error} />
      {status.loading && !status.data ? <Loading text="Inspecting the local server…" /> : status.data && <Dashboard data={status.data} />}
    </Shell>
  );
}

function Dashboard({ data }: { data: PlatformStatus }) {
  const active = Object.values(data.jobs.queues).reduce((sum, value) => sum + value, 0);
  const unhealthy = data.connectors.filter((item) => item.health !== "healthy").length;
  return (
    <div className="grid gap-5">
      <section className="stats-grid">
        <div className="stat-card"><span className="eyebrow">SERVICES</span><strong>{Object.values(data.services).filter((v) => v === "healthy").length}/{Object.keys(data.services).length}</strong><small>API, database, Redis, model manager</small></div>
        <div className="stat-card"><span className="eyebrow">QUEUED WORK</span><strong>{active}</strong><small>Oldest active: {age(data.jobs.oldest_active_age_seconds)}</small></div>
        <div className="stat-card"><span className="eyebrow">CONNECTORS</span><strong>{data.connectors.length - unhealthy}/{data.connectors.length}</strong><small>{unhealthy ? `${unhealthy} need attention` : "All reported healthy"}</small></div>
        <div className="stat-card"><span className="eyebrow">LOCAL MODEL</span><strong>{label(data.model.state)}</strong><small>{data.model.model_id || "No deployment"} · {data.model.available_slots || 0}/{data.model.accepted_slots || 0} slots</small></div>
      </section>

      <section className="grid md:grid-cols-2 xl:grid-cols-5 gap-3">
        {links.map(([title, href, Icon, description]) => (
          <Link href={href} className="card p-5 hover:border-primary transition-colors" key={href}>
            <Icon size={20} className="mb-3 text-primary" /><strong className="block mb-1">{title}</strong><span className="text-xs muted">{description}</span>
          </Link>
        ))}
      </section>

      <section className="grid lg:grid-cols-3 gap-5">
        <article className="panel lg:col-span-2">
          <div className="panel-header"><div><h2>Connector freshness</h2><p className="text-sm muted mb-0">Official source schedules are global.</p></div><RefreshCw /></div>
          <div className="panel-body divide-y">
            {data.connectors.map((item) => <div className="py-3 flex items-start justify-between gap-4" key={`${item.connector}:${item.stream}`}><div><strong>{label(item.connector)} · {label(item.stream)}</strong><small className="block muted">{item.message || "No diagnostic message"}</small></div><div className="text-right"><Badge variant={item.health === "healthy" ? "outline" : "destructive"}>{label(item.health)}</Badge><small className="block muted mt-1">{age(item.freshness_seconds)} old</small></div></div>)}
          </div>
        </article>
        <article className="panel">
          <div className="panel-header"><div><h2>Capacity</h2><p className="text-sm muted mb-0">Bounded host signals.</p></div><Gauge /></div>
          <div className="panel-body grid gap-4 text-sm">
            <div className="flex justify-between"><span><HardDrive className="inline mr-2" size={16} />Data disk</span><strong>{bytes(data.storage.free_bytes)} free</strong></div>
            <div className="flex justify-between"><span><Server className="inline mr-2" size={16} />GPU devices</span><strong>{data.model.cuda_devices?.length || 0}</strong></div>
            <div className="flex justify-between"><span><Gauge className="inline mr-2" size={16} />Benchmark</span><strong>{label(data.model.benchmark?.status || "unknown")}</strong></div>
            <div className="flex justify-between"><span><Database className="inline mr-2" size={16} />Backup</span><strong>{label(data.backup.status)}</strong></div>
            <div className="flex justify-between"><span><ArchiveRestore className="inline mr-2" size={16} />Log retention</span><strong>{label(String(data.storage.retention.integration_logs))}</strong></div>
            <div className="flex justify-between"><span><Users className="inline mr-2" size={16} />Organizations</span><strong>{data.resources.organizations}</strong></div>
            <div className="flex justify-between"><span><ArchiveRestore className="inline mr-2" size={16} />Failed jobs</span><strong>{data.jobs.dead_letters}</strong></div>
          </div>
        </article>
      </section>

      <section className="grid lg:grid-cols-2 gap-5">
        <article className="panel"><div className="panel-header"><h2>Recent failures</h2><Badge variant={data.jobs.recent_failures.length ? "destructive" : "outline"}>{data.jobs.recent_failures.length}</Badge></div><div className="panel-body divide-y">{data.jobs.recent_failures.length ? data.jobs.recent_failures.map((item) => <div className="py-3" key={item.id}><strong>{label(item.type)} · {label(item.queue)}</strong><small className="block muted">{item.error || "No stored detail"}</small></div>) : <p className="muted">No failed jobs are retained.</p>}</div></article>
        <article className="panel"><div className="panel-header"><h2>Administrative audit</h2><ShieldLabel /></div><div className="panel-body divide-y">{data.recent_audit.length ? data.recent_audit.map((item) => <div className="py-3 flex justify-between gap-4" key={item.id}><span><strong>{label(item.action)}</strong><small className="block muted">{item.scope} · {item.actor_kind}</small></span><span className="text-right"><Badge variant={item.result === "succeeded" ? "outline" : "destructive"}>{label(item.result)}</Badge><small className="block muted mt-1">{dateTime(item.created_at)}</small></span></div>) : <p className="muted">Actions will appear after the first administrative change.</p>}</div></article>
      </section>
    </div>
  );
}

function ShieldLabel() {
  return <span className="text-xs muted">actor · time · result</span>;
}
