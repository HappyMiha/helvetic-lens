"use client";

import { useState } from "react";
import {
  CheckCircle2,
  CircleStop,
  Download,
  ExternalLink,
  Gauge,
  HardDrive,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { Shell } from "@/components/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  api,
  errorText,
  label,
  refreshWorkspace,
  useResource,
} from "@/lib/api";
import type { Job, LocalModel, LocalModelInventory } from "@/lib/types";
import { ErrorNote, Loading, SuccessNote } from "./common";

function bytes(value: number) {
  if (!value) return "0 GB";
  return `${(value / 1024 ** 3).toFixed(value < 1024 ** 3 ? 2 : 1)} GB`;
}

function modelAction(model: LocalModel) {
  if (["downloading", "verifying"].includes(model.state)) return "pause";
  if (model.state === "paused") return "download";
  if (model.active || model.state === "ready") return "stop";
  if (model.installed) return "start";
  return "download";
}

export function ModelLibrary() {
  const { data, error, loading, reload } = useResource<LocalModelInventory>(
    "/admin/models",
    2000,
  );
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [actionError, setActionError] = useState("");

  async function command(model: LocalModel, action: string) {
    setBusy(model.id + action);
    setActionError("");
    setMessage("");
    try {
      if (action === "license") {
        await api(`/admin/models/${model.id}/license`, {
          method: "POST",
          body: JSON.stringify({ accepted: true }),
        });
        setMessage("License acceptance saved for this exact model revision.");
      } else if (action === "remove") {
        await api(`/admin/models/${model.id}`, { method: "DELETE" });
        setMessage(
          "Verified artifact removed. Catalogue metadata remains available.",
        );
      } else {
        const result = await api<Job | LocalModel>(
          `/admin/models/${model.id}/${action}`,
          { method: "POST" },
        );
        setMessage(
          "queue" in result
            ? `${action === "download" ? "Download" : "Start"} job queued safely. Progress is persisted in Activity.`
            : `Model ${action} command accepted.`,
        );
      }
      refreshWorkspace();
      reload();
    } catch (cause) {
      setActionError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  return (
    <Shell section="Local models">
      <div className="page-heading">
        <div>
          <span className="eyebrow">LOCAL AI CONTROL PLANE</span>
          <h1>Model library</h1>
          <p>
            Choose an approved Apertus artifact, verify it locally, and run it
            on this server. Cloud connectors remain optional fallbacks.
          </p>
        </div>
        <Button variant="outline" onClick={reload} disabled={loading}>
          <RefreshCw className={loading ? "animate-spin" : ""} /> Refresh
        </Button>
      </div>
      <ErrorNote message={error || actionError} />
      {message && <SuccessNote>{message}</SuccessNote>}
      {loading && !data ? (
        <Loading text="Inspecting the local AI host…" />
      ) : data ? (
        <>
          <section className="stats-grid mb-5">
            <div className="stat-card">
              <span className="eyebrow">GPU</span>
              <strong>
                {data.hardware.cuda_devices.length || "Not detected"}
              </strong>
              <small>
                {data.hardware.cuda_devices
                  .map((gpu) => gpu.name)
                  .join(" · ") || "CPU fallback only"}
              </small>
            </div>
            <div className="stat-card">
              <span className="eyebrow">MEMORY</span>
              <strong>{bytes(data.hardware.ram_bytes)}</strong>
              <small>
                {bytes(data.hardware.disk_free_bytes)} model disk free
              </small>
            </div>
            <div className="stat-card">
              <span className="eyebrow">RUNTIME</span>
              <strong>
                {data.hardware.runtime_supported ? "Ready" : "Unavailable"}
              </strong>
              <small>
                Catalogue v{data.catalog_version} · pinned llama.cpp
              </small>
            </div>
            <div className="stat-card">
              <span className="eyebrow">ACTIVE MODEL</span>
              <strong>{data.deployment?.model_id || "None"}</strong>
              <small>{label(data.deployment?.state || "stopped")}</small>
            </div>
          </section>
          <div className="model-library-grid">
            {data.models.map((model) => (
              <ModelCard
                key={model.id}
                model={model}
                runtime={data.runtime_image}
                busy={busy}
                command={command}
              />
            ))}
          </div>
        </>
      ) : null}
    </Shell>
  );
}

function ModelCard({
  model,
  runtime,
  busy,
  command,
}: {
  model: LocalModel;
  runtime: string;
  busy: string;
  command: (model: LocalModel, action: string) => Promise<void>;
}) {
  const action = modelAction(model);
  const progress = model.download.total_bytes
    ? (model.download.downloaded_bytes / model.download.total_bytes) * 100
    : 0;
  return (
    <article className="panel model-library-card">
      <div className="panel-header items-start">
        <div>
          <div className="flex gap-2 flex-wrap mb-2">
            <Badge variant="outline">{model.quantization}</Badge>
            <Badge variant="outline">{label(model.compatibility.status)}</Badge>
            {model.download.cached_copy_available && (
              <Badge variant="secondary">Cached locally</Badge>
            )}
          </div>
          <h2>{model.display_name}</h2>
          <p className="text-xs muted m-0 mt-1">{model.upstream_repository}</p>
        </div>
        <Badge variant={model.state === "error" ? "destructive" : "outline"}>
          {label(model.state)}
        </Badge>
      </div>
      <div className="panel-body form-stack">
        <p className="m-0 text-sm">{model.compatibility.reason}</p>
        <div className="model-facts">
          <span>
            <HardDrive /> {bytes(model.size_bytes)}
          </span>
          <span>
            <Gauge /> {model.requirements.recommended_context.toLocaleString()}{" "}
            context
          </span>
          <span>
            <Zap /> {bytes(model.requirements.min_vram_bytes)} minimum VRAM
          </span>
        </div>
        {(model.download.resumable ||
          ["downloading", "verifying"].includes(model.state)) && (
          <div>
            <div className="flex justify-between text-xs muted mb-1">
              <span>{label(model.state)}</span>
              <span>{progress.toFixed(1)}%</span>
            </div>
            <progress
              className="scan-progress"
              value={model.download.downloaded_bytes}
              max={model.download.total_bytes || 1}
            />
          </div>
        )}
        <details className="text-xs muted">
          <summary>Immutable artifact details</summary>
          <p>
            Revision: <code>{model.immutable_revision}</code>
          </p>
          <p>
            SHA-256: <code>{model.sha256}</code>
          </p>
          <p>
            Runtime: <code>{runtime}</code>
          </p>
        </details>
        <ErrorNote message={model.error} />
        {!model.license_accepted ? (
          <div className="license-box">
            <p className="m-0 text-sm">
              Review{" "}
              <a href={model.license_url} target="_blank" rel="noreferrer">
                {model.license} <ExternalLink size={12} className="inline" />
              </a>
            </p>
            <Button onClick={() => command(model, "license")} disabled={!!busy}>
              <CheckCircle2 /> Accept for this revision
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => command(model, action)}
              disabled={!!busy || model.compatibility.status === "incompatible"}
            >
              {busy === model.id + action ? (
                <Loader2 className="animate-spin" />
              ) : action === "download" ? (
                model.state === "paused" ? (
                  <RotateCcw />
                ) : (
                  <Download />
                )
              ) : action === "pause" ? (
                <Pause />
              ) : action === "start" ? (
                <Play />
              ) : (
                <CircleStop />
              )}
              {action === "download" && model.state === "paused"
                ? "Resume"
                : label(action)}
            </Button>
            {model.download.resumable && (
              <Button
                variant="outline"
                onClick={() => command(model, "cancel")}
                disabled={!!busy}
              >
                <X /> Cancel transfer
              </Button>
            )}
            {model.installed && !model.active && (
              <Button
                variant="outline"
                onClick={() => command(model, "remove")}
                disabled={!!busy}
              >
                <Trash2 /> Remove
              </Button>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
