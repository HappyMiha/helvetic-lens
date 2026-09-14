"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { monitoringEvidenceCopy } from "@/lib/monitoring-evidence-copy";
import { useAuth } from "./auth-gate";
import { MonitoringEvidenceExport } from "./monitoring-evidence-export";
import styles from "./monitoring-evidence-ask.module.css";

type Props = {
  domain:
    | "pollen"
    | "river"
    | "air"
    | "warnings"
    | "commute"
    | "traffic"
    | "tenders"
    | "ip"
    | "auctions";
  monitorId: string;
  itemId: string;
  sequence?: number;
  contextVersion: string | number;
};
type Evidence = {
  binding: string;
  reference_url: string;
  locale: string;
  record: {
    domain: string;
    monitor_id: string;
    item_id: string;
    sequence: number | null;
  };
  extracts: {
    pointer: string;
    quote: string;
    context?: Record<string, string>;
  }[];
  has_matches: boolean;
  more_matches: boolean;
  checked_at: string;
  searched?: string;
  newer_available: boolean;
  current_configuration: boolean | null;
};

export function MonitoringEvidenceAsk(props: Props) {
  const { session } = useAuth(),
    { locale } = useI18n();
  const [open, setOpen] = useState(false);
  const detail = useRef<HTMLDetailsElement | null>(null);
  const key = `${session?.user?.id}:${session?.organization?.id}:${session?.role}:${locale}:${props.domain}:${props.monitorId}:${props.itemId}:${props.sequence}:${props.contextVersion}`;
  return (
    <>
      <details
        ref={detail}
        className={styles.panel}
        data-monitoring-evidence-ask={props.domain}
        onToggle={(event) => setOpen(event.currentTarget.open)}
      >
        <summary>{monitoringEvidenceCopy[locale].title}</summary>
        {open && session?.authenticated && (
          <EvidenceForm
            key={key}
            {...props}
            close={() => {
              if (detail.current) {
                detail.current.open = false;
                detail.current.querySelector("summary")?.focus();
              }
            }}
          />
        )}
      </details>
      <MonitoringEvidenceExport {...props} />
    </>
  );
}

function EvidenceForm({
  domain,
  monitorId,
  itemId,
  sequence,
  close,
}: Props & { close: () => void }) {
  const { locale, dateTime } = useI18n(),
    c = monitoringEvidenceCopy[locale];
  const [value, setValue] = useState<Evidence | null>(null),
    [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false),
    [failed, setFailed] = useState(false);
  const controller = useRef<AbortController | null>(null);
  async function load(questionText = "", binding?: string) {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setValue(null);
    if (!binding) setQuestion("");
    setFailed(false);
    setBusy(true);
    try {
      const result = await api<Evidence>("/monitoring-centre/evidence/ask", {
        method: "POST",
        signal: request.signal,
        body: JSON.stringify({
          domain,
          monitor_id: monitorId,
          item_id: itemId,
          sequence: sequence ?? null,
          locale,
          question: questionText,
          expected_binding: binding ?? null,
        }),
      });
      if (request.signal.aborted) return;
      if (
        result.locale !== locale ||
        result.record.domain !== domain ||
        result.record.monitor_id !== monitorId ||
        result.record.item_id !== itemId ||
        result.record.sequence !== (sequence ?? null) ||
        !result.reference_url?.startsWith(
          "/api/monitoring-centre/evidence/reference?",
        )
      )
        throw new Error();
      setValue({ ...result, searched: questionText });
    } catch {
      if (!request.signal.aborted) {
        setValue(null);
        setFailed(true);
      }
    } finally {
      if (!request.signal.aborted) setBusy(false);
    }
  }
  useEffect(() => {
    void load();
    function clear() {
      controller.current?.abort();
      setValue(null);
      setQuestion("");
      setBusy(false);
    }
    function hidden() {
      if (document.visibilityState === "hidden") clear();
    }
    window.addEventListener("pagehide", clear);
    document.addEventListener("visibilitychange", hidden);
    return () => {
      controller.current?.abort();
      window.removeEventListener("pagehide", clear);
      document.removeEventListener("visibilitychange", hidden);
    };
    // The parent remounts this form on every identity, locale or evidence change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className={styles.body}>
      <p>{c.mode}</p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (value && !busy) void load(question, value.binding);
        }}
      >
        <label>
          {c.question}
          <textarea
            value={question}
            maxLength={2000}
            onChange={(event) => setQuestion(event.target.value)}
          />
        </label>
        <button type="submit" disabled={!value || busy || !question.trim()}>
          {c.search}
        </button>
      </form>
      {busy && <p role="status">{c.loading}</p>}
      {failed && <p role="alert">{c.failed}</p>}
      {!busy && (
        <button type="button" onClick={() => void load()}>
          {c.refresh}
        </button>
      )}
      {value && (
        <section aria-label={c.selected}>
          <p>
            <strong>{c.selected}</strong>
          </p>
          {value.searched && (
            <p>
              {c.question}: {value.searched}
            </p>
          )}
          <p>
            {c.checked}:{" "}
            {dateTime(value.checked_at, {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </p>
          {(value.newer_available || value.current_configuration === false) && (
            <p role="status">{c.historical}</p>
          )}
          {!value.has_matches && <p role="status">{c.empty}</p>}
          <ol>
            {value.extracts.map((extract) => (
              <li key={extract.pointer}>
                {extract.context && (
                  <p>{Object.values(extract.context).join(" · ")}</p>
                )}
                <blockquote>{extract.quote}</blockquote>
                <details className={styles.reference}>
                  <summary>{c.reference}</summary>
                  <p>
                    {c.sourceField}: <code>{extract.pointer}</code>
                  </p>
                  <a
                    href={value.reference_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {c.selected}
                  </a>
                </details>
              </li>
            ))}
          </ol>
          {value.more_matches && <p>{c.more}</p>}
        </section>
      )}
      <button type="button" onClick={close}>
        {c.original}
      </button>
    </div>
  );
}
