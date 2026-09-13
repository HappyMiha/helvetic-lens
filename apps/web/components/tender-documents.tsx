"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { tenderCopy } from "@/lib/tender-copy";
import { tenderDocumentCopy } from "@/lib/tender-document-copy";
import styles from "./tender-watch.module.css";

type Passage = {
  text: string;
  locator: string;
  page: number | null;
  snapshot_id?: string;
  truncated?: boolean;
};
type TextResult = {
  snapshot_id: string;
  parse_status: "complete" | "partial" | "failed";
  passages: Passage[];
};
type Comparison = {
  status: "changed" | "unchanged" | "unavailable";
  truncated: boolean;
  total_changes: number;
  before_snapshot_id: string | null;
  after_snapshot_id: string | null;
  changes: { before: Passage[]; after: Passage[]; kind: string }[];
};
type Files = {
  items: { id: string; item_id: string; created_at: string }[];
  next_cursor: string | null;
};
type SetResult = {
  id: string;
  observed_at: string;
  coverage: string;
  next_cursor: string | null;
  items: {
    item_id: string;
    title: string | null;
    kind: string;
    access: string;
    lifecycle: string;
    snapshot_id: string | null;
    changes: string[];
    comparison_available: boolean;
  }[];
};

function useRead<T>(path: string | null, revision = 0) {
  const [result, setResult] = useState<{
    key: string;
    data?: T;
    failed?: boolean;
  }>({ key: "" });
  const key = `${path}:${revision}`;
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    api<T>(path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ key, data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ key, failed: true });
      });
    return () => controller.abort();
  }, [path, key]);
  return result.key === key ? result : { key };
}

export function TenderDocuments({
  dossierId,
  observationId,
  sequence,
  initialOpen = false,
}: {
  dossierId: string;
  observationId?: string | null;
  sequence: number;
  initialOpen?: boolean;
}) {
  const { locale } = useI18n();
  const [open, setOpen] = useState(initialOpen);
  const container = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (initialOpen) {
      container.current?.scrollIntoView({ block: "start" });
      container.current?.querySelector("summary")?.focus();
    }
  }, [initialOpen]);
  return (
    <details
      ref={container}
      className={styles.card}
      open={open}
      data-tender-documents
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        {tenderDocumentCopy[locale].title} · {tenderCopy[locale].revision}{" "}
        {sequence}
      </summary>
      {open && (
        <DocumentReader dossierId={dossierId} observationId={observationId} />
      )}
    </details>
  );
}

function DocumentReader({
  dossierId,
  observationId,
}: {
  dossierId: string;
  observationId?: string | null;
}) {
  const { locale } = useI18n(),
    c = tenderCopy[locale],
    d = tenderDocumentCopy[locale];
  const base = `/tender-watch/dossiers/${encodeURIComponent(dossierId)}`;
  const [revision, setRevision] = useState(0),
    [fileCursor, setFileCursor] = useState<string | null>(null),
    [setCursor, setSetCursor] = useState<string | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(false),
    [selection, setSelection] = useState<{
      type: "text" | "comparison";
      id: string;
    } | null>(null);
  const files = useRead<Files>(
    base +
      `/documents?limit=20${fileCursor ? `&after_id=${encodeURIComponent(fileCursor)}` : ""}`,
    revision,
  );
  const setPath = observationId
    ? base + `/document-observations/${encodeURIComponent(observationId)}`
    : null;
  const saved = useRead<SetResult>(
    setPath
      ? setPath +
          `?limit=20${setCursor ? `&after_item=${encodeURIComponent(setCursor)}` : ""}`
      : null,
    revision,
  );
  const controllers = useRef(new Set<AbortController>()),
    mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    const active = controllers.current;
    return () => {
      mounted.current = false;
      for (const controller of active) controller.abort();
      active.clear();
    };
  }, []);
  async function download(id: string) {
    const controller = new AbortController();
    controllers.current.add(controller);
    setBusy(true);
    setError(false);
    try {
      const response = await fetch(
        `/api${base}/documents/${encodeURIComponent(id)}/original`,
        {
          signal: controller.signal,
          cache: "no-store",
          credentials: "same-origin",
          redirect: "error",
        },
      );
      if (!response.ok) throw new Error(d.unavailable);
      const blob = await response.blob();
      if (!mounted.current || controller.signal.aborted) return;
      const url = URL.createObjectURL(blob),
        link = document.createElement("a");
      link.href = url;
      const extension =
        /\.(pdf|docx)"?$/.exec(
          response.headers.get("Content-Disposition") || "",
        )?.[1] || "bin";
      link.download = `tender-${id}.${extension}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      if (mounted.current && !controller.signal.aborted) {
        setError(true);
        setSelection(null);
        setRevision((v) => v + 1);
      }
    } finally {
      controllers.current.delete(controller);
      if (mounted.current) setBusy(false);
    }
  }
  function refresh() {
    setError(false);
    setSelection(null);
    setFileCursor(null);
    setSetCursor(null);
    setRevision((v) => v + 1);
  }
  const buttons = (id: string) => (
    <div className={styles.actions}>
      <button onClick={() => setSelection({ type: "text", id })}>
        {d.open}
      </button>
      <button disabled={busy} onClick={() => void download(id)}>
        {d.download}
      </button>
    </div>
  );
  return (
    <section data-document-reader>
      <p>{d.help}</p>
      <button onClick={refresh}>{c.refresh}</button>
      {error && <p role="alert">{d.unavailable}</p>}
      {busy && <p role="status">{c.loading}</p>}
      {observationId && (
        <section>
          <h3>{d.set}</h3>
          {saved.failed ? (
            <p role="alert">{d.unavailable}</p>
          ) : !saved.data ? (
            <p role="status">{c.loading}</p>
          ) : (
            <>
              <p>
                <time dateTime={saved.data.observed_at}>
                  {new Date(saved.data.observed_at).toLocaleString(
                    locale === "rm-CH" ? "de-CH" : locale,
                    { timeZone: "Europe/Zurich", timeZoneName: "short" },
                  )}
                </time>
              </p>
              {saved.data.coverage !== "complete" && (
                <p className={styles.notice}>{d.incompleteSet}</p>
              )}
              {!saved.data.items.length && <p>{d.none}</p>}
              {saved.data.items.map((item) => (
                <article
                  className={styles.card}
                  key={item.item_id}
                  data-document-item={item.item_id}
                >
                  <h4>{item.title || c.unknown}</h4>
                  {item.kind === "qa" && <p>{d.qa}</p>}
                  {item.lifecycle === "withdrawn" && <p>{d.withdrawn}</p>}
                  {item.lifecycle === "removed" && <p>{d.removed}</p>}
                  {item.access !== "available" && <p>{d.unavailable}</p>}
                  {item.snapshot_id && buttons(item.snapshot_id)}
                  {item.comparison_available && (
                    <button
                      onClick={() =>
                        setSelection({ type: "comparison", id: item.item_id })
                      }
                    >
                      {d.compare}
                    </button>
                  )}
                </article>
              ))}
              <div className={styles.actions}>
                {setCursor && (
                  <button onClick={() => setSetCursor(null)}>
                    {c.current}
                  </button>
                )}
                {saved.data.next_cursor && (
                  <button onClick={() => setSetCursor(saved.data!.next_cursor)}>
                    {c.more}
                  </button>
                )}
              </div>
            </>
          )}
        </section>
      )}
      <details data-retained-documents>
        <summary>
          <h3>{d.files}</h3>
        </summary>
        {files.failed ? (
          <p role="alert">{d.unavailable}</p>
        ) : !files.data ? (
          <p role="status">{c.loading}</p>
        ) : (
          <>
            {!files.data.items.length && <p>{d.none}</p>}
            {files.data.items.map((item) => (
              <article
                className={styles.card}
                key={item.id}
                data-retained-document={item.id}
              >
                <h4>{item.item_id}</h4>
                <p>
                  <time dateTime={item.created_at}>
                    {new Date(item.created_at).toLocaleString(
                      locale === "rm-CH" ? "de-CH" : locale,
                      { timeZone: "Europe/Zurich", timeZoneName: "short" },
                    )}
                  </time>
                </p>
                {buttons(item.id)}
              </article>
            ))}
            <div className={styles.actions}>
              {fileCursor && (
                <button onClick={() => setFileCursor(null)}>{c.current}</button>
              )}
              {files.data.next_cursor && (
                <button onClick={() => setFileCursor(files.data!.next_cursor)}>
                  {c.more}
                </button>
              )}
            </div>
          </>
        )}
      </details>
      {selection && (
        <Evidence
          key={`${selection.type}:${selection.id}:${revision}`}
          path={
            selection.type === "text"
              ? base + `/documents/${encodeURIComponent(selection.id)}/text`
              : setPath +
                `/comparison?item_id=${encodeURIComponent(selection.id)}`
          }
          type={selection.type}
          download={download}
          busy={busy}
        />
      )}
    </section>
  );
}

function Evidence({
  path,
  type,
  download,
  busy,
}: {
  path: string;
  type: "text" | "comparison";
  download: (id: string) => Promise<void>;
  busy: boolean;
}) {
  const { locale } = useI18n(),
    c = tenderCopy[locale],
    d = tenderDocumentCopy[locale];
  const [revision, setRevision] = useState(0),
    [offset, setOffset] = useState(0);
  const result = useRead<TextResult | Comparison>(path, revision);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    panel.current?.focus();
    panel.current?.scrollIntoView({ block: "start" });
  }, []);
  const passage = (item: Passage, index: number) => (
    <div key={`${item.locator}:${index}`} className={styles.profileField}>
      <p>
        {item.page !== null && (
          <>
            {d.page} {item.page} ·{" "}
          </>
        )}
        {d.location}: {item.locator}
      </p>
      <pre className={styles.source}>{item.text}</pre>
      {item.truncated && <p>{d.truncated}</p>}
    </div>
  );
  const pages = (length: number, size: number) => (
    <div className={styles.actions}>
      {offset > 0 && (
        <button onClick={() => setOffset(Math.max(0, offset - size))}>
          {d.before}
        </button>
      )}
      {offset + size < length && (
        <button onClick={() => setOffset(offset + size)}>{c.more}</button>
      )}
    </div>
  );
  let body;
  if (type === "text" && result.data) {
    const value = result.data as TextResult;
    body = (
      <>
        {value.parse_status !== "complete" && (
          <p className={styles.notice}>
            {value.parse_status === "partial" ? d.partial : d.failed}
          </p>
        )}
        <button
          disabled={busy}
          onClick={() => void download(value.snapshot_id)}
        >
          {d.download}
        </button>
        {value.passages.slice(offset, offset + 50).map(passage)}
        {pages(value.passages.length, 50)}
      </>
    );
  } else if (result.data) {
    const value = result.data as Comparison;
    body = (
      <>
        <p>{d.literal}</p>
        {value.status === "unavailable" ? (
          <p role="alert">{d.unavailable}</p>
        ) : (
          <>
            {value.status === "unchanged" && <p>{d.unchanged}</p>}
            {value.truncated && <p className={styles.notice}>{d.truncated}</p>}
            <div className={styles.actions}>
              {value.before_snapshot_id && (
                <button
                  disabled={busy}
                  onClick={() => void download(value.before_snapshot_id!)}
                >
                  {d.before} · {d.download}
                </button>
              )}
              {value.after_snapshot_id && (
                <button
                  disabled={busy}
                  onClick={() => void download(value.after_snapshot_id!)}
                >
                  {d.after} · {d.download}
                </button>
              )}
            </div>
            {value.changes.slice(offset, offset + 5).map((change, index) => (
              <div className={styles.documentComparison} key={offset + index}>
                <section>
                  <h4>{d.before}</h4>
                  {change.before.length ? change.before.map(passage) : <p>—</p>}
                </section>
                <section>
                  <h4>{d.after}</h4>
                  {change.after.length ? change.after.map(passage) : <p>—</p>}
                </section>
              </div>
            ))}
            {pages(value.changes.length, 5)}
          </>
        )}
      </>
    );
  }
  return (
    <section
      ref={panel}
      tabIndex={-1}
      className={styles.card}
      data-document-evidence={type}
      aria-label={type === "text" ? d.open : d.compare}
    >
      <h3>{type === "text" ? d.open : d.compare}</h3>
      <button
        onClick={() => {
          setOffset(0);
          setRevision((v) => v + 1);
        }}
      >
        {c.refresh}
      </button>
      {result.failed ? (
        <p role="alert">{d.unavailable}</p>
      ) : !result.data ? (
        <p role="status">{c.loading}</p>
      ) : (
        body
      )}
    </section>
  );
}
