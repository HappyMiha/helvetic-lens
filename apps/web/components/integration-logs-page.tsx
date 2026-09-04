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
  invalidateResources,
  resources,
  resourceTag,
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
import { AdminOnly } from "./auth-gate";
import { useI18n } from "@/lib/i18n";

type SortBy =
  | "created_at"
  | "provider"
  | "operation"
  | "status"
  | "duration_ms"
  | "response_status";
type SortDirection = "asc" | "desc";

const PAGE_SIZE = 50;

function translatedName(t: (key: string) => string, kind: "provider" | "operation", value: string) {
  const key = `logs.${kind}.${value}`;
  const result = t(key);
  return result === key ? label(value) : result;
}

function sizeLabel(value: number, number: (value: number, options?: Intl.NumberFormatOptions) => string) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${number(value / 1024, { maximumFractionDigits: 1 })} KB`;
  return `${number(value / 1024 / 1024, { maximumFractionDigits: 1 })} MB`;
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
  const { t, number } = useI18n();
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
    if (query.trim()) params.set("query", query.trim());
    return "/integration-logs?" + params.toString();
  }, [offset, provider, query, sortBy, sortDirection, status]);
  const logs = useResource<IntegrationLogPage>(
    resources.integrationLogs<IntegrationLogPage>(path),
  );
  const detail = useResource<IntegrationLogDetail>(
    selectedId ? resources.integrationLog(selectedId) : null,
  );
  const rows = logs.data?.items || [];
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
      setNote(t("logs.cleared", { count: number(result.deleted) }));
      await invalidateResources(resourceTag("integration-logs"));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell section={t("nav.logs")} wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("logs.eyebrow")}</span>
          <h1>{t("logs.title")}</h1>
          <p className="muted m-0">
            {t("logs.body")}
          </p>
        </div>
        <div className="heading-actions">
          <Button
            variant="outline"
            onClick={logs.reload}
            disabled={logs.loading}
          >
            <RefreshCw className={logs.loading ? "animate-spin" : ""} />
            {t("logs.refresh")}
          </Button>
          <AdminOnly><Button
            variant="destructive"
            onClick={() => {
              setError("");
              setClearOpen(true);
            }}
            disabled={!logs.data?.total}
          >
            <Trash2 />
            {t("logs.clear")}
          </Button></AdminOnly>
        </div>
      </div>

      <ErrorNote message={error || logs.error} />
      {note && <SuccessNote>{note}</SuccessNote>}

      <div className="log-stats">
        <div className="stat-card">
          <span className="eyebrow">{t("logs.saved")}</span>
          <strong>{logs.data?.total ?? "—"}</strong>
          <span className="text-xs muted">{t("logs.filtered")}</span>
        </div>
        <div className="stat-card">
          <span className="eyebrow">{t("logs.integrations")}</span>
          <strong>{logs.data?.providers.length ?? "—"}</strong>
          <span className="text-xs muted">
            {t("logs.providersSeen")}
          </span>
        </div>
        <div className="stat-card stat-warm">
          <span className="eyebrow">{t("logs.errors")}</span>
          <strong>{logs.data ? errors : "—"}</strong>
          <span className="text-xs muted">{t("logs.pageSearch")}</span>
        </div>
      </div>

      <section className="panel mt-6">
        <div className="filter-bar log-filter-bar">
          <Input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOffset(0);
            }}
            placeholder={t("logs.search")}
            aria-label={t("logs.searchLabel")}
          />
          <select
            value={provider}
            aria-label={t("logs.filterIntegration")}
            onChange={(event) => {
              setProvider(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">{t("logs.allIntegrations")}</option>
            {(logs.data?.providers || []).map((value) => (
              <option value={value} key={value}>
                {translatedName(t, "provider", value)}
              </option>
            ))}
          </select>
          <select
            value={status}
            aria-label={t("logs.filterStatus")}
            onChange={(event) => {
              setStatus(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">{t("logs.allOutcomes")}</option>
            <option value="success">{t("logs.success")}</option>
            <option value="error">{t("logs.error")}</option>
          </select>
        </div>

        {logs.loading && !logs.data ? (
          <Loading text={t("logs.loading")} />
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
                        {t("logs.when")}
                      </SortButton>
                    </th>
                    <th>
                      <SortButton
                        field="provider"
                        current={sortBy}
                        direction={sortDirection}
                        onSort={changeSort}
                      >
                        {t("logs.integration")}
                      </SortButton>
                    </th>
                    <th>
                      <SortButton
                        field="operation"
                        current={sortBy}
                        direction={sortDirection}
                        onSort={changeSort}
                      >
                        {t("logs.request")}
                      </SortButton>
                    </th>
                    <th>
                      <SortButton
                        field="status"
                        current={sortBy}
                        direction={sortDirection}
                        onSort={changeSort}
                      >
                        {t("logs.outcome")}
                      </SortButton>
                    </th>
                    <th>
                      <SortButton
                        field="duration_ms"
                        current={sortBy}
                        direction={sortDirection}
                        onSort={changeSort}
                      >
                        {t("logs.duration")}
                      </SortButton>
                    </th>
                    <th>{t("logs.size")}</th>
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
                {t("logs.pagination", { start: number(offset + 1), end: number(Math.min(offset + PAGE_SIZE, logs.data?.total || 0)), total: number(logs.data?.total || 0), page: number(page), pages: number(pages) })}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  size="icon-sm"
                  variant="outline"
                  aria-label={t("logs.previous")}
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  <ChevronLeft />
                </Button>
                <Button
                  size="icon-sm"
                  variant="outline"
                  aria-label={t("logs.next")}
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
                ? t("logs.noMatch")
                : t("logs.empty")}
            </h2>
            <p className="muted">
              {t("logs.emptyBody")}
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
            <DialogTitle>{t("logs.detailTitle")}</DialogTitle>
            <DialogDescription>
              {t("logs.detailBody")}
            </DialogDescription>
          </DialogHeader>
          <ErrorNote message={detail.error} />
          {detail.loading && !detail.data ? (
            <Loading text={t("logs.loadingDetail")} />
          ) : (
            detail.data && <LogDetail value={detail.data} />
          )}
        </DialogContent>
      </Dialog>

      <AdminOnly><ConfirmDeleteDialog
        open={clearOpen}
        onOpenChange={setClearOpen}
        title={t("logs.clearTitle")}
        description={t("logs.clearBody")}
        confirmLabel={t("logs.clearAll")}
        busy={busy}
        error={clearOpen ? error : ""}
        onConfirm={() => void clearLogs()}
      /></AdminOnly>
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
  const { t, dateTime, number } = useI18n();
  const provider = translatedName(t, "provider", item.provider);
  return (
    <tr>
      <td className="whitespace-nowrap">{dateTime(item.created_at, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" })}</td>
      <td>
        <strong>{provider}</strong>
        <div className="text-xs muted mt-1">
          {translatedName(t, "operation", item.operation)}
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
            : t("logs.noResponse")}
        </div>
      </td>
      <td className="whitespace-nowrap">
        <span className="inline-flex items-center gap-1">
          <Clock3 size={13} className="muted" />
          {number(item.duration_ms)} ms
        </span>
      </td>
      <td className="whitespace-nowrap text-xs muted">
        {sizeLabel(item.request_size, number)} → {sizeLabel(item.response_size, number)}
      </td>
      <td>
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label={t("logs.inspect", { provider })}
          onClick={() => onOpen(item.id)}
        >
          <Eye />
        </Button>
      </td>
    </tr>
  );
}

function LogDetail({ value }: { value: IntegrationLogDetail }) {
  const { t, number } = useI18n();
  return (
    <div>
      <div className="log-detail-summary">
        <div>
          <span className="eyebrow">{t("logs.integration")}</span>
          <strong>{translatedName(t, "provider", value.provider)}</strong>
        </div>
        <div>
          <span className="eyebrow">{t("logs.operation")}</span>
          <strong>{translatedName(t, "operation", value.operation)}</strong>
        </div>
        <div>
          <span className="eyebrow">{t("logs.outcome")}</span>
          <Status value={value.status} />
        </div>
        <div>
          <span className="eyebrow">{t("logs.duration")}</span>
          <strong>{number(value.duration_ms)} ms</strong>
        </div>
      </div>
      <div className="log-endpoint">
        <span className="log-method">{value.method}</span>
        <code>{value.url}</code>
      </div>
      {value.request_id && (
        <div className="log-endpoint">
          <span className="eyebrow">{t("logs.requestId")}</span>
          <code>{value.request_id}</code>
        </div>
      )}
      {Object.keys(value.correlation || {}).length > 0 && (
        <details className="payload-panel">
          <summary>{t("logs.correlation")}</summary>
          <JsonBlock value={value.correlation} empty={t("logs.noCorrelation")} />
        </details>
      )}
      {value.error && <ErrorNote message={value.error} />}
      <div className="log-detail-grid">
        <PayloadPanel
          title={t("logs.requestTitle")}
          status={t("logs.savedBeforeLimit", { size: sizeLabel(value.request_size, number) })}
          headers={value.request_headers}
          body={value.request_body}
        />
        <PayloadPanel
          title={t("logs.responseTitle")}
          status={
            value.response_status
              ? `HTTP ${value.response_status} · ${sizeLabel(value.response_size, number)}`
              : t("logs.noResponse")
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
  const { t } = useI18n();
  return (
    <section className="payload-panel">
      <div className="payload-heading">
        <strong>{title}</strong>
        <span>{status}</span>
      </div>
      <details>
        <summary>{t("logs.headers")}</summary>
        <JsonBlock value={headers} empty={t("logs.noHeaders")} />
      </details>
      <div className="payload-body-label">{t("logs.bodyLabel")}</div>
      <JsonBlock value={body} empty={t("logs.noBody", { type: title.toLowerCase() })} />
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
