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
import { label, useResource } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { PlatformStatus } from "@/lib/types";

function bytes(value = 0) {
  return `${(value / 1024 ** 3).toFixed(value < 1024 ** 3 ? 2 : 1)} GB`;
}

function age(seconds: number | null, never: string) {
  if (seconds === null) return never;
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

const links = [
  ["admin.modelControl", "/models", Bot, "admin.modelControlBody"],
  ["admin.sourceSync", "/connectors", RefreshCw, "admin.sourceSyncBody"],
  ["admin.jobs", "/activity", Activity, "admin.jobsBody"],
  ["admin.diagnostics", "/logs", ScrollText, "admin.diagnosticsBody"],
  ["admin.prompts", "/prompts?scope=platform", FileText, "admin.promptsBody"],
] as const;

export function PlatformAdminPage() {
  const { t } = useI18n();
  const { isPlatformAdmin } = useAuth();
  const status = useResource<PlatformStatus>(isPlatformAdmin ? "/admin/status" : null, 10000);
  return (
    <Shell section={t("nav.admin")} wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("admin.eyebrow")}</span>
          <h1>{t("admin.title")}</h1>
          <p>{t("admin.body")}</p>
        </div>
        <Button variant="outline" onClick={status.reload} disabled={status.loading}>
          <RefreshCw className={status.loading ? "animate-spin" : ""} /> {t("logs.refresh")}
        </Button>
      </div>
      {!isPlatformAdmin && <ErrorNote message={t("admin.denied")} />}
      <ErrorNote message={status.error} />
      {status.loading && !status.data ? <Loading text={t("admin.loading")} /> : status.data && <Dashboard data={status.data} />}
    </Shell>
  );
}

function Dashboard({ data }: { data: PlatformStatus }) {
  const { t, dateTime, number } = useI18n();
  const active = Object.values(data.jobs.queues).reduce((sum, value) => sum + value, 0);
  const unhealthy = data.connectors.filter((item) => item.health !== "healthy").length;
  const ai = data.ai_triage;
  const totalTokens = Object.values(ai.usage.token_counts).reduce((sum, value) => sum + value, 0);
  const milliseconds = (value: number | null) => value === null ? t("admin.noSamples") : `${number(Math.round(value))} ms`;
  const percent = (value: number | null) => value === null ? t("admin.noSamples") : number(value, { style: "percent", maximumFractionDigits: 1 });
  return (
    <div className="grid gap-5">
      <section className="stats-grid">
        <div className="stat-card"><span className="eyebrow">{t("admin.services")}</span><strong>{Object.values(data.services).filter((v) => v === "healthy").length}/{Object.keys(data.services).length}</strong><small>{t("admin.servicesBody")}</small></div>
        <div className="stat-card"><span className="eyebrow">{t("admin.queued")}</span><strong>{active}</strong><small>{t("admin.oldest", { age: age(data.jobs.oldest_active_age_seconds, t("admin.never")) })}</small></div>
        <div className="stat-card"><span className="eyebrow">{t("admin.connectors")}</span><strong>{data.connectors.length - unhealthy}/{data.connectors.length}</strong><small>{unhealthy ? t("admin.attention", { count: unhealthy }) : t("admin.healthy")}</small></div>
        <div className="stat-card"><span className="eyebrow">{t("admin.localModel")}</span><strong>{label(data.model.state)}</strong><small>{data.model.model_id || t("admin.noDeployment")} · {t("admin.slots", { available: data.model.available_slots || 0, accepted: data.model.accepted_slots || 0 })}</small></div>
      </section>

      <section className="grid md:grid-cols-2 xl:grid-cols-5 gap-3">
        {links.map(([title, href, Icon, description]) => (
          <Link href={href} className="card p-5 hover:border-primary transition-colors" key={href}>
            <Icon size={20} className="mb-3 text-primary" /><strong className="block mb-1">{t(title)}</strong><span className="text-xs muted">{t(description)}</span>
          </Link>
        ))}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div><h2>{t("admin.aiTriage")}</h2><p className="text-sm muted mb-0">{t("admin.aiTriageBody")}</p></div>
          <Gauge />
        </div>
        <div className="panel-body grid gap-4">
          <div className="stats-grid">
            <div className="stat-card"><span className="eyebrow">{t("admin.overviewP95")}</span><strong>{milliseconds(ai.latency.deterministic_overview.p95_ms)}</strong><small>{t("admin.samples", { count: ai.latency.deterministic_overview.samples })}</small></div>
            <div className="stat-card"><span className="eyebrow">{t("admin.inferenceP95")}</span><strong>{milliseconds(ai.latency.inference.p95_ms)}</strong><small>{t("admin.samples", { count: ai.latency.inference.samples })}</small></div>
            <div className="stat-card"><span className="eyebrow">{t("admin.cacheHitRate")}</span><strong>{percent(ai.usage.cache_hit_rate)}</strong><small>{t("admin.cacheReuse", { hits: ai.usage.cache_hits, requests: ai.usage.requests_including_reuse })}</small></div>
            <div className="stat-card"><span className="eyebrow">{t("admin.citationAcceptance")}</span><strong>{percent(ai.evidence.acceptance_rate)}</strong><small>{t("admin.validationSamples", { count: ai.evidence.validation_samples })}</small></div>
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm muted">
            <span>{t("admin.aiRecords", { count: ai.records.total })}</span>
            <span>{t("admin.providerCalls", { count: ai.usage.provider_calls })}</span>
            <span>{t("admin.totalTokens", { count: number(totalTokens) })}</span>
            <span>{t("admin.failedRate", { value: percent(ai.records.failed_rate) })}</span>
            <span>{t("admin.limitedRate", { value: percent(ai.records.limited_rate) })}</span>
            <span>{t("admin.actionOutcomes", { accepted: ai.actions.accepted, dismissed: ai.actions.dismissed_or_not_applicable })}</span>
          </div>
        </div>
      </section>

      <section className="grid lg:grid-cols-3 gap-5">
        <article className="panel lg:col-span-2">
          <div className="panel-header"><div><h2>{t("admin.freshness")}</h2><p className="text-sm muted mb-0">{t("admin.globalSchedules")}</p></div><RefreshCw /></div>
          <div className="panel-body divide-y">
            {data.connectors.map((item) => <div className="py-3 flex items-start justify-between gap-4" key={`${item.connector}:${item.stream}`}><div><strong>{label(item.connector)} · {label(item.stream)}</strong><small className="block muted">{item.message || t("admin.noDiagnostic")}</small></div><div className="text-right"><Badge variant={item.health === "healthy" ? "outline" : "destructive"}>{label(item.health)}</Badge><small className="block muted mt-1">{t("admin.old", { age: age(item.freshness_seconds, t("admin.never")) })}</small></div></div>)}
          </div>
        </article>
        <article className="panel">
          <div className="panel-header"><div><h2>{t("admin.capacity")}</h2><p className="text-sm muted mb-0">{t("admin.capacityBody")}</p></div><Gauge /></div>
          <div className="panel-body grid gap-4 text-sm">
            <div className="flex justify-between"><span><HardDrive className="inline mr-2" size={16} />{t("admin.dataDisk")}</span><strong>{t("admin.free", { size: bytes(data.storage.free_bytes) })}</strong></div>
            <div className="flex justify-between"><span><Server className="inline mr-2" size={16} />{t("admin.gpu")}</span><strong>{data.model.cuda_devices?.length || 0}</strong></div>
            <div className="flex justify-between"><span><Gauge className="inline mr-2" size={16} />{t("admin.benchmark")}</span><strong>{label(data.model.benchmark?.status || "unknown")}</strong></div>
            <div className="flex justify-between"><span><Database className="inline mr-2" size={16} />{t("admin.backup")}</span><strong>{label(data.backup.status)}</strong></div>
            <div className="flex justify-between"><span><ArchiveRestore className="inline mr-2" size={16} />{t("admin.retention")}</span><strong>{t("admin.retentionDays", { count: Number(data.storage.retention.integration_logs_days ?? 0) })}</strong></div>
            <div className="flex justify-between"><span><Users className="inline mr-2" size={16} />{t("admin.organizations")}</span><strong>{data.resources.organizations}</strong></div>
            <div className="flex justify-between"><span><ArchiveRestore className="inline mr-2" size={16} />{t("admin.failedJobs")}</span><strong>{data.jobs.dead_letters}</strong></div>
          </div>
        </article>
      </section>

      <section className="grid lg:grid-cols-2 gap-5">
        <article className="panel"><div className="panel-header"><h2>{t("admin.failures")}</h2><Badge variant={data.jobs.recent_failures.length ? "destructive" : "outline"}>{data.jobs.recent_failures.length}</Badge></div><div className="panel-body divide-y">{data.jobs.recent_failures.length ? data.jobs.recent_failures.map((item) => <div className="py-3" key={item.id}><strong>{label(item.type)} · {label(item.queue)}</strong><small className="block muted">{item.error || t("admin.noDetail")}</small></div>) : <p className="muted">{t("admin.noFailures")}</p>}</div></article>
        <article className="panel"><div className="panel-header"><h2>{t("admin.audit")}</h2><span className="text-xs muted">{t("admin.auditLegend")}</span></div><div className="panel-body divide-y">{data.recent_audit.length ? data.recent_audit.map((item) => <div className="py-3 flex justify-between gap-4" key={item.id}><span><strong>{label(item.action)}</strong><small className="block muted">{item.scope} · {item.actor_kind}</small></span><span className="text-right"><Badge variant={item.result === "succeeded" ? "outline" : "destructive"}>{label(item.result)}</Badge><small className="block muted mt-1">{dateTime(item.created_at)}</small></span></div>) : <p className="muted">{t("admin.noAudit")}</p>}</div></article>
      </section>
    </div>
  );
}
