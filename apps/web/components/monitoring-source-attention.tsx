"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { centreCopy, type TemplateId } from "@/lib/monitoring-centre-copy";
import { sourceAttentionCopy } from "@/lib/source-attention-copy";
import { sourceOperationsCopy } from "@/lib/source-operations-copy";

type Issue = {
  key: string;
  domain: TemplateId;
  channel: string;
  code: string;
  severity: "urgent" | "warning";
  fingerprint: string;
  href: string;
  expires_at: string | null;
  latest_success_at: string | null;
  next_request_at: string | null;
  acknowledged_at: string | null;
};
type Attention = { checked_at: string; items: Issue[]; unacknowledged: number };
const path = "/admin/monitoring-sources/attention";

export function MonitoringSourceAttention({ denied }: { denied: () => void }) {
  const { locale, dateTime } = useI18n(),
    c = sourceAttentionCopy[locale],
    s = sourceOperationsCopy[locale];
  const [data, setData] = useState<Attention | null>(null),
    [error, setError] = useState(false);
  const [all, setAll] = useState(false),
    [busy, setBusy] = useState(false),
    [revision, setRevision] = useState(0);
  const active = useRef<AbortController | null>(null),
    onDenied = useRef(denied);
  onDenied.current = denied;
  function failure(problem: unknown) {
    setData(null);
    setError(true);
    if (
      problem instanceof ApiError &&
      [
        "authentication_required",
        "platform_admin_required",
        "membership_required",
      ].includes(problem.code)
    )
      onDenied.current();
  }
  useEffect(() => {
    const controller = new AbortController();
    active.current = controller;
    setData(null);
    setError(false);
    setBusy(true);
    void api<Attention>(path, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((problem) => {
        if (!controller.signal.aborted) failure(problem);
      })
      .finally(() => {
        if (active.current === controller) active.current = null;
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [revision]);
  useEffect(() => {
    function hide() {
      active.current?.abort();
      setData(null);
      setBusy(false);
    }
    function visibility() {
      if (document.hidden) hide();
      else setRevision((v) => v + 1);
    }
    window.addEventListener("pagehide", hide);
    document.addEventListener("visibilitychange", visibility);
    const timer = window.setInterval(() => {
      if (!document.hidden && !active.current) setRevision((v) => v + 1);
    }, 60000);
    return () => {
      active.current?.abort();
      clearInterval(timer);
      window.removeEventListener("pagehide", hide);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  async function acknowledge(issue: Issue) {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setBusy(true);
    setError(false);
    try {
      await api(path + "/acknowledge", {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          key: issue.key,
          fingerprint: issue.fingerprint,
        }),
      });
      if (!controller.signal.aborted) setRevision((v) => v + 1);
    } catch (problem) {
      if (!controller.signal.aborted) failure(problem);
    } finally {
      if (active.current === controller) active.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  function label(issue: Issue) {
    if (issue.code === "renewal_7_days") return c.renewal7;
    if (issue.code === "renewal_30_days") return c.renewal30;
    if (issue.code === "section_disabled") return c.section;
    if (issue.code === "collector_unavailable") return c.collector;
    const state = issue.code.replace(/^(access|acquisition)_/, "");
    return `${issue.code.startsWith("access_") ? s.access : s.acquisition}: ${s[(state === "errors" ? "errors_state" : state) as keyof typeof s] || s.unknown}`;
  }
  const time = (value: string | null) => (value ? dateTime(value) : s.unknown);
  return (
    <section data-source-attention className="card p-5 my-6 min-w-0">
      <h2>{c.title}</h2>
      <p className="my-3">{c.body}</p>
      <div className="flex flex-wrap gap-3 items-end my-4">
        <button
          className="button min-h-11"
          disabled={busy}
          onClick={() => setRevision((v) => v + 1)}
        >
          {s.refresh}
        </button>
        <label>
          {c.filter}
          <select
            className="block max-w-full min-h-11"
            value={all ? "all" : "pending"}
            onChange={(event) => setAll(event.target.value === "all")}
          >
            <option value="pending">{c.pending}</option>
            <option value="all">{c.all}</option>
          </select>
        </label>
      </div>
      {error ? (
        <p role="alert">{c.failed}</p>
      ) : !data ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          <p>
            {c.pending}: {data.unacknowledged} · {s.checked}:{" "}
            {time(data.checked_at)}
          </p>
          {!data.items.some((issue) => all || !issue.acknowledged_at) && (
            <p className="my-3" role="status">
              {c.empty}
            </p>
          )}
          <ul className="grid gap-4 my-4 md:grid-cols-2">
            {data.items
              .filter((issue) => all || !issue.acknowledged_at)
              .map((issue) => (
                <li
                  key={issue.key}
                  data-source-issue={issue.key}
                  className="rounded-xl border p-4 min-w-0"
                >
                  <h3>
                    {centreCopy[locale].templates[issue.domain][0]}
                    {issue.channel !== issue.domain
                      ? ` · ${s[issue.channel as keyof typeof s] || s.unknown}`
                      : ""}
                  </h3>
                  <p className="font-semibold my-2">
                    {c[issue.severity]} · {label(issue)}
                  </p>
                  <dl className="text-sm space-y-2">
                    {[
                      [s.expires, issue.expires_at],
                      [s.latest, issue.latest_success_at],
                      [s.next, issue.next_request_at],
                    ].map(([name, value]) => (
                      <div key={name!}>
                        <dt>{name}</dt>
                        <dd>{time(value)}</dd>
                      </div>
                    ))}
                  </dl>
                  <div className="flex flex-wrap gap-3 items-center mt-4">
                    <Link
                      className="underline break-words"
                      href={`/monitoring/settings?category=${issue.domain}`}
                    >
                      {c.connector}
                    </Link>
                    {issue.acknowledged_at ? (
                      <p>
                        {c.acknowledged}: {time(issue.acknowledged_at)}
                      </p>
                    ) : (
                      <button
                        className="button h-auto min-h-11 whitespace-normal max-w-full"
                        disabled={busy}
                        onClick={() => void acknowledge(issue)}
                      >
                        {c.acknowledge}
                      </button>
                    )}
                  </div>
                </li>
              ))}
          </ul>
        </>
      )}
    </section>
  );
}
