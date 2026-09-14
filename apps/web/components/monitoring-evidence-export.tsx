"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { TemplateId } from "@/lib/monitoring-centre-copy";
import { evidenceExportCopy } from "@/lib/monitoring-evidence-export-copy";
import { useAuth, type AuthSession } from "./auth-gate";
import { Button } from "./ui/button";

type Props = {
  domain: TemplateId;
  monitorId: string;
  itemId: string;
  sequence?: number;
  revisionId?: string;
  contextVersion: string | number;
};
type Manifest = {
  format: string;
  locale: string;
  scope: { organization_id: string; user_id: string };
  selection: {
    domain: string;
    monitor_id: string;
    item_id: string;
    sequence: number;
    revision_id: string;
  };
  configuration_revision: number;
};
type Preview = {
  manifest: Manifest;
  bytes: number;
  sha256: string;
  filename: string;
  expires_at: string;
  confirmation_token: string;
};
type Download = {
  manifest: Manifest;
  bytes: number;
  sha256: string;
  filename: string;
  canonical_json: string;
};
const path = "/monitoring-centre/evidence/export",
  format = "helvetic-lens-monitoring-evidence-v1";

export function MonitoringEvidenceExport(props: Props) {
  const { session } = useAuth(),
    { locale } = useI18n();
  if (!session?.authenticated || !session.user?.id || !session.organization?.id)
    return null;
  return (
    <Export
      key={`${session.user.id}:${session.organization.id}:${session.role}:${locale}:${props.domain}:${props.monitorId}:${props.itemId}:${props.sequence}:${props.revisionId}:${props.contextVersion}`}
      {...props}
      scope={[session.organization.id, session.user.id]}
      role={session.role}
    />
  );
}

function Export({
  domain,
  monitorId,
  itemId,
  sequence,
  revisionId,
  scope,
  role,
}: Props & { scope: [string, string]; role?: string }) {
  const { locale, dateTime } = useI18n(),
    c = evidenceExportCopy[locale];
  const [preview, setPreview] = useState<Preview | null>(null),
    [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<"failed" | "complete" | "">("");
  const active = useRef<AbortController | null>(null),
    objectUrl = useRef<string | null>(null);
  function clear() {
    active.current?.abort();
    active.current = null;
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = null;
  }
  function cancel() {
    clear();
    setPreview(null);
    setBusy(false);
    setMessage("");
  }
  useEffect(() => {
    function hidden() {
      if (document.visibilityState === "hidden") cancel();
    }
    window.addEventListener("pagehide", cancel);
    window.addEventListener("helvetic-lens:today-changed", cancel);
    document.addEventListener("visibilitychange", hidden);
    return () => {
      clear();
      window.removeEventListener("pagehide", cancel);
      window.removeEventListener("helvetic-lens:today-changed", cancel);
      document.removeEventListener("visibilitychange", hidden);
    };
  }, []);
  function matches(value: Manifest) {
    const selected = value?.selection;
    return (
      value?.format === format &&
      value.locale === locale &&
      value.scope?.organization_id === scope[0] &&
      value.scope?.user_id === scope[1] &&
      selected?.domain === domain &&
      selected.monitor_id === monitorId &&
      selected.item_id === itemId &&
      Number.isSafeInteger(selected.sequence) &&
      selected.sequence >= 1 &&
      (sequence === undefined || selected.sequence === sequence) &&
      (revisionId === undefined || selected.revision_id === revisionId)
    );
  }
  async function run(save: boolean) {
    clear();
    const controller = new AbortController();
    active.current = controller;
    setBusy(true);
    setMessage("");
    try {
      if (!save) {
        setPreview(null);
        const value = await api<Preview>(`${path}/preview`, {
          method: "POST",
          signal: controller.signal,
          body: JSON.stringify({
            domain,
            monitor_id: monitorId,
            item_id: itemId,
            sequence: sequence ?? null,
            revision_id: revisionId ?? null,
            locale,
          }),
        });
        if (controller.signal.aborted) return;
        if (
          !matches(value.manifest) ||
          value.bytes > 2_000_000 ||
          !/^[a-f0-9]{64}$/.test(value.sha256) ||
          !value.confirmation_token ||
          !(Date.parse(value.expires_at) > Date.now())
        )
          throw new Error();
        setPreview(value);
      } else {
        if (!preview || !(Date.parse(preview.expires_at) > Date.now()))
          throw new Error();
        const value = await api<Download>(`${path}/download`, {
          method: "POST",
          signal: controller.signal,
          body: JSON.stringify({
            confirmation_token: preview.confirmation_token,
          }),
        });
        if (controller.signal.aborted) return;
        if (
          typeof value.canonical_json !== "string" ||
          value.canonical_json.length > 2_000_000
        )
          throw new Error();
        const bytes = new TextEncoder().encode(value.canonical_json);
        if (
          bytes.length > 2_000_000 ||
          bytes.length !== value.bytes ||
          value.bytes !== preview.bytes
        )
          throw new Error();
        const digest = await crypto.subtle.digest("SHA-256", bytes);
        if (controller.signal.aborted) return;
        const hex = Array.from(new Uint8Array(digest), (n) =>
          n.toString(16).padStart(2, "0"),
        ).join("");
        const content = JSON.parse(value.canonical_json);
        if (
          hex !== preview.sha256 ||
          hex !== value.sha256 ||
          !matches(content.manifest) ||
          JSON.stringify(content.manifest) !==
            JSON.stringify(preview.manifest) ||
          JSON.stringify(value.manifest) !== JSON.stringify(preview.manifest)
        )
          throw new Error();
        // A workspace switch in another tab must not write this private file.
        const identity = await api<AuthSession>("/auth/session", {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (
          !identity.authenticated ||
          identity.user?.id !== scope[1] ||
          identity.organization?.id !== scope[0] ||
          identity.role !== role ||
          document.visibilityState === "hidden" ||
          !(Date.parse(preview.expires_at) > Date.now())
        )
          throw new Error();
        const url = URL.createObjectURL(
          new Blob([value.canonical_json], {
            type: "application/json;charset=utf-8",
          }),
        );
        objectUrl.current = url;
        const link = document.createElement("a");
        link.href = url;
        link.download = `helvetic-lens-${domain}-${itemId}-${preview.manifest.selection.sequence}.json`;
        document.body.append(link);
        link.click();
        link.remove();
        setPreview(null);
        setMessage("complete");
        window.setTimeout(() => {
          URL.revokeObjectURL(url);
          if (objectUrl.current === url) objectUrl.current = null;
        }, 1000);
      }
    } catch {
      if (!controller.signal.aborted) {
        setPreview(null);
        setMessage("failed");
      }
    } finally {
      if (active.current === controller) {
        active.current = null;
        setBusy(false);
      }
    }
  }
  return (
    <div
      role="group"
      data-monitoring-evidence-export={domain}
      aria-label={c.title}
      className="rounded-xl border p-4 space-y-3 my-3"
    >
      <p className="font-semibold">{c.title}</p>
      <p className="text-sm">{c.body}</p>
      <p className="text-sm muted">{c.limits}</p>
      {preview && (
        <dl className="text-sm space-y-1">
          <div className="flex flex-wrap gap-2">
            <dt>{c.version}</dt>
            <dd>{preview.manifest.selection.sequence}</dd>
          </div>
          <div className="flex flex-wrap gap-2">
            <dt>{c.configuration}</dt>
            <dd>{preview.manifest.configuration_revision}</dd>
          </div>
          <div className="flex flex-wrap gap-2">
            <dt>{c.expires}</dt>
            <dd>
              <time dateTime={preview.expires_at}>
                {dateTime(preview.expires_at)}
              </time>
            </dd>
          </div>
        </dl>
      )}
      <div className="flex flex-wrap gap-3">
        <Button
          type="button"
          variant="outline"
          className="h-auto min-h-11 max-w-full whitespace-normal"
          disabled={busy}
          onClick={() => void run(!!preview)}
        >
          {preview ? c.download : c.prepare}
        </Button>
        {(busy || preview) && (
          <Button
            type="button"
            variant="outline"
            className="h-auto min-h-11"
            onClick={cancel}
          >
            {c.cancel}
          </Button>
        )}
      </div>
      {busy && <p role="status">{c.busy}</p>}
      {message && (
        <p role={message === "failed" ? "alert" : "status"}>{c[message]}</p>
      )}
    </div>
  );
}
