"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { centreCopy, type TemplateId } from "@/lib/monitoring-centre-copy";
import { monitoringExportCopy } from "@/lib/monitoring-export-copy";
import { useAuth } from "./auth-gate";
import { Button } from "./ui/button";

type Item = {
  domain: TemplateId;
  id: string;
  sha256: string;
  canonical_json: string;
};
type Page = {
  format: string;
  scope: [string, string, string | null];
  started_at: string;
  read_at: string;
  items: Item[];
  next_cursor: string | null;
};
const path = "/monitoring-centre/configuration/export";
const format = "helvetic-lens-monitoring-configuration-v1";

export function MonitoringConfigurationExport({
  domain,
}: {
  domain: TemplateId;
}) {
  const { session } = useAuth(),
    { locale } = useI18n();
  const scope = session?.authenticated
    ? [session.organization?.id, session.user?.id]
    : null;
  if (!scope?.every(Boolean)) return null;
  return (
    <Export
      key={`${scope.join(":")}:${session?.role}:${locale}:${domain}`}
      domain={domain}
      scope={scope as [string, string]}
    />
  );
}

function Export({
  domain,
  scope,
}: {
  domain: TemplateId;
  scope: [string, string];
}) {
  const { locale } = useI18n(),
    c = monitoringExportCopy[locale];
  const [busy, setBusy] = useState(false),
    [count, setCount] = useState(0),
    [message, setMessage] = useState<"complete" | "failed" | "">("");
  const active = useRef<AbortController | null>(null),
    objectUrl = useRef<string | null>(null);
  const clear = () => {
    active.current?.abort();
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = null;
  };
  useEffect(() => {
    const hide = () => {
      clear();
      setBusy(false);
      setCount(0);
      setMessage("");
    };
    window.addEventListener("pagehide", hide);
    const changed = () => {
      if (active.current) hide();
    };
    window.addEventListener("helvetic-lens:today-changed", changed);
    return () => {
      clear();
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("helvetic-lens:today-changed", changed);
    };
  }, []);
  async function download(selected: TemplateId | null) {
    clear();
    const controller = new AbortController();
    active.current = controller;
    setBusy(true);
    setMessage("");
    setCount(0);
    try {
      const items: Item[] = [],
        cursors = new Set<string>(),
        ids = new Set<string>();
      let cursor: string | null = null,
        started = "",
        readAt = "",
        bytes = 0;
      do {
        const query = new URLSearchParams({ limit: "50" });
        if (selected) query.set("domain", selected);
        if (cursor) query.set("cursor", cursor);
        const page: Page = await api(`${path}?${query}`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (
          page.format !== format ||
          JSON.stringify(page.scope) !== JSON.stringify([...scope, selected]) ||
          (started && page.started_at !== started)
        )
          throw new Error();
        started = page.started_at;
        readAt = page.read_at;
        for (const item of page.items) {
          const id = `${item.domain}:${item.id}`;
          if (ids.has(id)) throw new Error();
          // Verify the exact server JSON bytes, preserving decimal spelling.
          const digest = await crypto.subtle.digest(
            "SHA-256",
            new TextEncoder().encode(item.canonical_json),
          );
          if (controller.signal.aborted) return;
          const hex = Array.from(new Uint8Array(digest), (n) =>
            n.toString(16).padStart(2, "0"),
          ).join("");
          const payload = JSON.parse(item.canonical_json);
          if (
            hex !== item.sha256 ||
            payload.id !== item.id ||
            payload.domain !== item.domain
          )
            throw new Error();
          ids.add(id);
          items.push({
            ...payload,
            canonical_json: item.canonical_json,
            sha256: item.sha256,
          });
          bytes += new TextEncoder().encode(JSON.stringify(item)).length;
          if (items.length > 10000 || bytes > 64 * 1024 * 1024)
            throw new Error();
        }
        setCount(items.length);
        cursor = page.next_cursor;
        if (cursor && cursors.has(cursor)) throw new Error();
        if (cursor) cursors.add(cursor);
      } while (cursor);
      // Recheck every collected record; an empty export still rechecks identity.
      for (let offset = 0; offset < Math.max(1, items.length); offset += 1000) {
        const batch = items
          .slice(offset, offset + 1000)
          .map(({ domain, id, sha256 }) => ({ domain, id, sha256 }));
        const result = await api<{ verified: number; scope: string[] }>(
          `${path}/verify`,
          {
            method: "POST",
            signal: controller.signal,
            body: JSON.stringify({ items: batch }),
          },
        );
        if (controller.signal.aborted) return;
        if (
          result.verified !== batch.length ||
          JSON.stringify(result.scope) !== JSON.stringify(scope)
        )
          throw new Error();
      }
      const archive = {
        format,
        owner_user_id: scope[1],
        organization_id: scope[0],
        category: selected,
        started_at: started,
        last_record_read_at: readAt,
        completed_at: new Date().toISOString(),
        consistency: "individual_current_records_rechecked_before_download",
        count: items.length,
        includes: [
          "owned_current_configurations",
          "configuration_revision_numbers",
          "lifecycle_state",
          "saved_email_preferences",
        ],
        excludes: [
          "connector_credentials",
          "source_documents",
          "historical_revisions",
          "decisions",
          "colleagues_monitors",
        ],
        integrity:
          "Each sha256 hashes UTF-8 canonical_json. That string preserves the exact server snapshot.",
        items,
      };
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(archive, null, 2)], {
          type: "application/json",
        }),
      );
      objectUrl.current = url;
      const link = document.createElement("a");
      link.href = url;
      link.download = `helvetic-lens-settings-${selected || "all"}-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.append(link);
      link.click();
      link.remove();
      setMessage("complete");
      // Keep the URL alive through the browser's download handoff, then release.
      window.setTimeout(() => {
        URL.revokeObjectURL(url);
        if (objectUrl.current === url) objectUrl.current = null;
      }, 1000);
    } catch {
      if (!controller.signal.aborted) setMessage("failed");
    } finally {
      if (active.current === controller) {
        active.current = null;
        setBusy(false);
      }
    }
  }
  return (
    <section
      data-configuration-export
      className="rounded-xl border p-4 space-y-3"
      aria-label={c.title}
    >
      <h2 className="text-xl font-semibold">{c.title}</h2>
      <p>{c.body}</p>
      <p className="text-sm muted">{c.privacy}</p>
      <p className="text-sm">
        {c.scope}: {centreCopy[locale].templates[domain][0]}
      </p>
      <div className="flex flex-wrap gap-3">
        <Button
          type="button"
          variant="outline"
          className="h-auto min-h-11 max-w-full whitespace-normal"
          disabled={busy}
          onClick={() => void download(null)}
        >
          {c.all}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-auto min-h-11 max-w-full whitespace-normal"
          disabled={busy}
          onClick={() => void download(domain)}
        >
          {c.category}
        </Button>
        {busy && (
          <Button
            type="button"
            variant="outline"
            className="h-auto min-h-11 max-w-full whitespace-normal"
            onClick={() => {
              clear();
              setBusy(false);
              setCount(0);
            }}
          >
            {c.cancel}
          </Button>
        )}
      </div>
      <p role="status" aria-live="polite">
        {busy
          ? `${c.progress}: ${count}`
          : message === "complete"
            ? `${c.complete}: ${count}`
            : ""}
      </p>
      {message === "failed" && <p role="alert">{c.failed}</p>}
    </section>
  );
}
