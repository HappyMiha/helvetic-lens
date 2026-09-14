"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { monitoringBatchCopy } from "@/lib/monitoring-batch-copy";
import { Button } from "./ui/button";

export type BatchRecord = {
  domain: string;
  monitor_id: string;
  item_id: string;
  sequence: number | null;
};
export type BatchItem = {
  id: string;
  monitor_name: string;
  href: string;
  record: BatchRecord;
};
type Prepared = {
  record: BatchRecord;
  binding: string;
  reference_url: string;
  actions: string[];
  extracts: {
    pointer: string;
    quote: string;
    context: Record<string, string>;
  }[];
  more_extracts: boolean;
};
const recordKey = (r: BatchRecord) =>
  JSON.stringify([r.domain, r.monitor_id, r.item_id, r.sequence]);

export function MonitoringBatchReview({
  items,
  clear,
  applied,
  failed,
}: {
  items: BatchItem[];
  clear: () => void;
  applied: () => void;
  failed: () => void;
}) {
  const { locale } = useI18n(),
    c = monitoringBatchCopy[locale];
  const [preview, setPreview] = useState<Prepared[] | null>(null),
    [choices, setChoices] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const hide = () => {
      request.current?.abort();
      setPreview(null);
      setChoices([]);
      clear();
    };
    const visibility = () => {
      if (document.visibilityState === "hidden") hide();
    };
    window.addEventListener("pagehide", hide);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      request.current?.abort();
      window.removeEventListener("pagehide", hide);
      document.removeEventListener("visibilitychange", visibility);
    };
    // The queue remounts this component when its visible selection changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  async function run(apply = false) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const selected = preview;
    setPreview(null);
    setBusy(true);
    try {
      if (apply && selected) {
        const result = await api<{ applied: boolean; count: number }>(
          "/monitoring-centre/review/apply",
          {
            method: "POST",
            signal: controller.signal,
            body: JSON.stringify({
              locale,
              selections: selected.map((row, index) => ({
                record: row.record,
                expected_binding: row.binding,
                action: choices[index],
              })),
            }),
          },
        );
        if (controller.signal.aborted) return;
        if (!result.applied || result.count !== items.length) throw new Error();
        applied();
      } else {
        const result = await api<{ items: Prepared[]; locale: string }>(
          "/monitoring-centre/review/preview",
          {
            method: "POST",
            signal: controller.signal,
            body: JSON.stringify({
              locale,
              records: items.map((item) => item.record),
            }),
          },
        );
        if (controller.signal.aborted) return;
        if (
          result.locale !== locale ||
          result.items.length !== items.length ||
          result.items.some(
            (row, index) =>
              recordKey(row.record) !== recordKey(items[index].record) ||
              !row.reference_url?.startsWith(
                "/api/monitoring-centre/evidence/reference?",
              ),
          )
        )
          throw new Error();
        setPreview(result.items);
        setChoices(
          result.items.map((row) =>
            row.actions.length === 1 ? row.actions[0] : "",
          ),
        );
        heading.current?.focus({ preventScroll: true });
      }
    } catch {
      if (!controller.signal.aborted) {
        setPreview(null);
        setChoices([]);
        failed();
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  return (
    <section
      data-monitoring-batch
      className="space-y-4 rounded-lg border p-3 min-w-0"
    >
      <h3 ref={heading} tabIndex={-1} className="font-semibold">
        {c.title} ({items.length}/20)
      </h3>
      <p>{c.help}</p>
      {busy && <p role="status">{c.loading}</p>}
      {preview?.map((row, index) => (
        <section
          key={recordKey(row.record)}
          className="space-y-3 border-t pt-3 min-w-0"
        >
          <h4 className="font-semibold">{items[index].monitor_name}</h4>
          <p>{c.excerpt}</p>
          <Link
            href={row.reference_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center underline"
          >
            {c.original}
          </Link>
          <ul className="space-y-2">
            {row.extracts.map((extract) => (
              <li key={extract.pointer} className="break-words">
                <p>{Object.values(extract.context || {}).join(" · ")}</p>
                <blockquote className="whitespace-pre-wrap border-l-2 pl-3">
                  {extract.quote}
                </blockquote>
              </li>
            ))}
          </ul>
          {row.more_extracts && <p>{c.more}</p>}
          <label className="block space-y-1">
            {c.choose}
            <select
              className="w-full min-h-11 border rounded p-2"
              value={choices[index] || ""}
              onChange={(event) =>
                setChoices((current) =>
                  current.map((choice, n) =>
                    n === index ? event.target.value : choice,
                  ),
                )
              }
            >
              <option value="">{c.choose}</option>
              {row.actions.map((action) => (
                <option key={action} value={action}>
                  {c[action as keyof typeof c] || action}
                </option>
              ))}
            </select>
          </label>
        </section>
      ))}
      <div className="flex gap-2 flex-wrap">
        <Button
          variant="outline"
          className="min-h-11 h-auto whitespace-normal"
          disabled={busy || !items.length}
          onClick={() => void run()}
        >
          {c.preview}
        </Button>
        {preview && (
          <Button
            className="min-h-11 h-auto whitespace-normal"
            disabled={busy || choices.some((choice) => !choice)}
            onClick={() => void run(true)}
          >
            {c.apply}
          </Button>
        )}
        <Button
          variant="outline"
          className="min-h-11 h-auto whitespace-normal"
          disabled={busy}
          onClick={clear}
        >
          {c.clear}
        </Button>
      </div>
    </section>
  );
}
