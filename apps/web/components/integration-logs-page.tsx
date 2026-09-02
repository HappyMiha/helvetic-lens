"use client";

import { useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Eye,
  Loader2,
  RefreshCw,
  ScrollText,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  api,
  errorText,
  label,
  refreshWorkspace,
  useResource,
} from "@/lib/api";
import type {
  IntegrationLogDetail,
  IntegrationLogPage,
  IntegrationLogSummary,
} from "@/lib/types";
import { ErrorNote, Loading, Status, SuccessNote } from "./common";
import { ConfirmDeleteDialog } from "./confirm-delete-dialog";
import { Shell } from "./shell";

type SortBy =
  | "created_at"
  | "provider"
  | "operation"
  | "status"
  | "duration_ms"
  | "response_status";
type SortDirection = "asc" | "desc";

const PAGE_SIZE = 50;

const providerNames: Record<string, string> = {
  website: "Website",
  fedlex: "Fedlex ELI",
  firecrawl: "Firecrawl",
  infomaniak: "Infomaniak AI",
  docker: "Local Docker Apertus",
  custom: "Custom Apertus endpoint",
};

const operationNames: Record<string, string> = {
  fetch_document: "Fetch document",
  resolve_eli: "Resolve ELI metadata",
  scrape_document: "Scrape document",
  list_models: "Load models",
  chat_completion: "Chat completion",
};

function providerName(value: string) {
  return providerNames[value] || label(value);
}

function operationName(value: string) {
  return operationNames[value] || label(value);
}

function preciseDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function sizeLabel(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function shortUrl(value: string) {
  try {
    const parsed = new URL(value);
    return parsed.host + parsed.pathname;
  } catch {
    return value;
  }
}

export function IntegrationLogsPage() {
  const [provider, setProvider] = useState("");
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [clearOpen, setClearOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const path = useMemo(() => {
    const params = new URLSearchParams({
      sort_by: sortBy,
      sort_dir: sortDirection,
      limit: String(PAGE_SIZE),
      offset: String(offset),
    });
    if (provider) params.set("provider", provider);
    if (status) params.set("status", status);
    return "/integration-logs?" + params.toString();
  }, [offset, provider, sortBy, sortDirection, status]);
  const logs = useResource<IntegrationLogPage>(path, 5000);
  const detail = useResource<IntegrationLogDetail>(
    selectedId ? "/integration-logs/" + selectedId : null,
  );
  const rows = (logs.data?.items || []).filter((item) =>
    `${item.provider} ${item.operation} ${item.method} ${item.url}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const errors = rows.filter((item) => item.status === "error").length;
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil((logs.data?.total || 0) / PAGE_SIZE));

  function changeSort(next: SortBy) {
    setOffset(0);
    if (sortBy === next) {
      setSortDirection((value) => (value === "asc" ? "desc" : "asc"));
      return;
    }
    setSortBy(next);
    setSortDirection(
      next === "provider" || next === "operation" || next === "status"
        ? "asc"
        : "desc",
    );
  }

  async function clearLogs() {
    setBusy(true);
    setError("");
    setNote("");
    try {
      const result = await api<{ deleted: number }>("/integration-logs", {
        method: "DELETE",
      });
      setClearOpen(false);
      setSelectedId(null);
      setOffset(0);
      setNote(`${result.deleted} integration log(s) cleared.`);
      refreshWorkspace();
      logs.reload();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell section="Integration logs" wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">INTEGRATION DIAGNOSTICS</span>
          <h1>See every external request.</h1>
          <p className="muted m-0">
            Inspect what RegWatch sent and received from websites, Fedlex,
            Firecrawl, and Apertus providers. Credentials are always redacted.
          </p>
        </div>
        <div className="heading-actions">
          <Button
            variant="outline"
            onClick={logs.reload}
            disabled={logs.loading}
          >
            <RefreshCw className={logs.loading ? "animate-spin" : ""} />
            Refresh
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              setError("");
              setClearOpen(true);
            }}
            disabled={!logs.data?.total}
          >
            <Trash2 />
            Clear logs
          </Button>
        </div>
      </div>

      <ErrorNote message={error || logs.error} />
      {note && <SuccessNote>{note}</SuccessNote>}

      <div className="log-stats">
        <div className="stat-card">
          <span className="eyebrow">SAVED CALLS</span>
          <strong>{logs.data?.total ?? "—"}</strong>
          <span className="text-xs muted">After current filters</span>
        </div>
        <div className="stat-card">
          <span className="eyebrow">INTEGRATIONS</span>
          <strong>{logs.data?.providers.length ?? "—"}</strong>
          <span className="text-xs muted">
            Providers seen in this workspace
          </span>
        </div>
        <div className="stat-card stat-warm">
          <span className="eyebrow">VISIBLE ERRORS</span>
          <strong>{logs.data ? errors : "—"}</strong>
          <span className="text-xs muted">On this page and search</span>
        </div>
      </div>

      <section className="panel mt-6">
        <div className="filter-bar log-filter-bar">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search provider, operation, or URL…"
            aria-label="Search integration logs"
          />
          <select
            value={provider}
            aria-label="Filter by integration"
            onChange={(event) => {
              setProvider(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All integrations</option>
            {(logs.data?.providers || []).map((value) => (
              <option value={value} key={value}>
                {providerName(value)}
              </option>
            ))}
          </select>
          <select
            value={status}
            aria-label="Filter by request status"
            onChange={(event) => {
              setStatus(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All outcomes</option>
            <option value="success">Success</option>
            <option value="error">Error</option>
          </select>
        </div>

        {logs.loading && !logs.data ? (
          <Loading text="Loading integration calls…" />
        ) : rows.length ? (
          <>
            <div className="table-scroll">
              <table className="watch-table logs-table">
                <thead>
                  <tr>
                    <th>
                      <SortButton
                        field="created_at"
                        current={sortBy}
                        direction={sortDirection}
                        onSort={changeSort}
                      >
                        WHEN
                      </SortButton>
                    </th>
                    <th>
                      <SortButton
                        field="provider"
                        current={sortBy}
                        direction={sortDirection}
                        onSort={changeSort}
                      >
                        INTEGRATION
                      </SortButton>
                    </th>
                    <th>
                      <SortButton
                        field="operation"
                        current={sortBy}
                        direction={sortDirection}
                        onSort={changeSort}
                      >
                        REQUEST
                      </SortButton>
                    </th>
                    <th>
                      <SortButton
                        field="status"
                        current={sortBy}
                        direction={sortDirection}
                        onSort={changeSort}
                      >
                        OUTCOME
                      </SortButton>
                    </th>
                    <th>
                      <SortButton
                        field="duration_ms"
                        current={sortBy}
                        direction={sortDirection}
                        onSort={changeSort}
                      >
                        DURATION
                      </SortButton>
                    </th>
                    <th>SIZE</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((item) => (
                    <LogRow key={item.id} item={item} onOpen={setSelectedId} />
                  ))}
                </tbody>
              </table>
            </div>
            <div className="log-pagination">
              <span className="text-xs muted">
                {offset + 1}–
                {Math.min(offset + PAGE_SIZE, logs.data?.total || 0)} of{" "}
                {logs.data?.total || 0} · page {page} of {pages}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  size="icon-sm"
                  variant="outline"
                  aria-label="Previous log page"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  <ChevronLeft />
                </Button>
                <Button
                  size="icon-sm"
                  variant="outline"
                  aria-label="Next log page"
                  disabled={offset + PAGE_SIZE >= (logs.data?.total || 0)}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  <ChevronRight />
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">
              <ScrollText size={28} />
            </div>
            <h2>
              {logs.data?.total
                ? "No calls match this search."
                : "No integration calls yet."}
            </h2>
            <p className="muted">
              Preview or scan a document, load models, or run Apertus analysis.
              The external request and response will appear here.
            </p>
          </div>
        )}
      </section>

      <Dialog
        open={!!selectedId}
        onOpenChange={(open) => {
          if (!open) setSelectedId(null);
        }}
      >
        <DialogContent className="sm:max-w-6xl max-h-[92vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Integration request and response</DialogTitle>
            <DialogDescription>
              Stored diagnostic evidence with credentials, cookies, and token
              fields redacted before saving.
            </DialogDescription>
          </DialogHeader>
          <ErrorNote message={detail.error} />
          {detail.loading && !detail.data ? (
            <Loading text="Loading request details…" />
          ) : (
            detail.data && <LogDetail value={detail.data} />
          )}
        </DialogContent>
      </Dialog>

      <ConfirmDeleteDialog
        open={clearOpen}
        onOpenChange={setClearOpen}
        title="Clear all integration logs?"
        description="This permanently removes the saved diagnostic requests and responses. Sources, documents, versions, scans, and integration settings are not affected."
        confirmLabel="Clear all logs"
        busy={busy}
        error={clearOpen ? error : ""}
        onConfirm={() => void clearLogs()}
      />
    </Shell>
  );
}

function SortButton({
  field,
  current,
  direction,
  onSort,
  children,
}: {
  field: SortBy;
  current: SortBy;
  direction: SortDirection;
  onSort: (field: SortBy) => void;
  children: React.ReactNode;
}) {
  const Icon =
    current !== field ? ArrowUpDown : direction === "asc" ? ArrowUp : ArrowDown;
  return (
    <button className="sort-button" onClick={() => onSort(field)}>
      {children}
      <Icon size={12} />
    </button>
  );
}

function LogRow({
  item,
  onOpen,
}: {
  item: IntegrationLogSummary;
  onOpen: (id: string) => void;
}) {
  return (
    <tr>
      <td className="whitespace-nowrap">{preciseDate(item.created_at)}</td>
      <td>
        <strong>{providerName(item.provider)}</strong>
        <div className="text-xs muted mt-1">
          {operationName(item.operation)}
        </div>
      </td>
      <td>
        <button className="log-request" onClick={() => onOpen(item.id)}>
          <span className="log-method">{item.method}</span>
          <span className="log-url" title={item.url}>
            {shortUrl(item.url)}
          </span>
        </button>
      </td>
      <td>
        <Status value={item.status} />
        <div className="text-xs muted mt-1">
          {item.response_status
            ? `HTTP ${item.response_status}`
            : "No HTTP response"}
        </div>
      </td>
      <td className="whitespace-nowrap">
        <span className="inline-flex items-center gap-1">
          <Clock3 size={13} className="muted" />
          {item.duration_ms.toLocaleString()} ms
        </span>
      </td>
      <td className="whitespace-nowrap text-xs muted">
        {sizeLabel(item.request_size)} → {sizeLabel(item.response_size)}
      </td>
      <td>
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label={`Inspect ${providerName(item.provider)} request`}
          onClick={() => onOpen(item.id)}
        >
          <Eye />
        </Button>
      </td>
    </tr>
  );
}

function LogDetail({ value }: { value: IntegrationLogDetail }) {
  return (
    <div>
      <div className="log-detail-summary">
        <div>
          <span className="eyebrow">INTEGRATION</span>
          <strong>{providerName(value.provider)}</strong>
        </div>
        <div>
          <span className="eyebrow">OPERATION</span>
          <strong>{operationName(value.operation)}</strong>
        </div>
        <div>
          <span className="eyebrow">OUTCOME</span>
          <Status value={value.status} />
        </div>
        <div>
          <span className="eyebrow">DURATION</span>
          <strong>{value.duration_ms.toLocaleString()} ms</strong>
        </div>
      </div>
      <div className="log-endpoint">
        <span className="log-method">{value.method}</span>
        <code>{value.url}</code>
      </div>
      {value.error && <ErrorNote message={value.error} />}
      <div className="log-detail-grid">
        <PayloadPanel
          title="Request"
          status={`${sizeLabel(value.request_size)} saved before display limits`}
          headers={value.request_headers}
          body={value.request_body}
        />
        <PayloadPanel
          title="Response"
          status={
            value.response_status
              ? `HTTP ${value.response_status} · ${sizeLabel(value.response_size)}`
              : "No HTTP response"
          }
          headers={value.response_headers}
          body={value.response_body}
        />
      </div>
    </div>
  );
}

function PayloadPanel({
  title,
  status,
  headers,
  body,
}: {
  title: string;
  status: string;
  headers: Record<string, unknown>;
  body: unknown;
}) {
  return (
    <section className="payload-panel">
      <div className="payload-heading">
        <strong>{title}</strong>
        <span>{status}</span>
      </div>
      <details>
        <summary>Headers</summary>
        <JsonBlock value={headers} empty="No headers saved." />
      </details>
      <div className="payload-body-label">Body</div>
      <JsonBlock value={body} empty={`No ${title.toLowerCase()} body.`} />
    </section>
  );
}

function JsonBlock({ value, empty }: { value: unknown; empty: string }) {
  if (value === null || value === undefined || value === "") {
    return <div className="payload-empty">{empty}</div>;
  }
  const rendered =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return <pre className="log-payload">{rendered}</pre>;
}
