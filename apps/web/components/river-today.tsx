"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { riverCopy, riverAttribution } from "@/lib/river-copy";
import { riverTodayCopy } from "@/lib/river-today-copy";
import type { RiverChange, RiverSample } from "@/lib/river-watch";
import { useAuth } from "./auth-gate";

type Entry = RiverChange & {
  monitor_name: string;
  monitor_id: string;
  monitor_status: string;
  current_configuration: boolean;
  sample_state: string;
  created_at: string;
  href: string;
  evidence: RiverChange["evidence"] & {
    corrected?: boolean;
    station_id: string;
  };
};
type Cursor = { before: string; before_id: string };
type Page = { items: Entry[]; next: Cursor | null; unreviewed_count: number };

export function RiverToday({ inbox = false }: { inbox?: boolean }) {
  const { session } = useAuth();
  const [visible, setVisible] = useState(true),
    [epoch, setEpoch] = useState(0);
  useEffect(() => {
    const hide = () => setVisible(false);
    const show = () => {
      setEpoch((v) => v + 1);
      setVisible(true);
    };
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    return () => {
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
    };
  }, []);
  if (
    !visible ||
    !session?.authenticated ||
    !session.user?.id ||
    !session.organization?.id
  )
    return null;
  return (
    <Reader
      key={`${session.user.id}:${session.organization.id}:${session.role}:${epoch}:${inbox}`}
      inbox={inbox}
      canManage={session.role === "organization_admin"}
    />
  );
}

function Reading({
  sample,
  heading,
}: {
  sample: RiverSample;
  heading: string;
}) {
  const { locale, dateTime } = useI18n(),
    c = riverCopy[locale];
  return (
    <div className="border-l pl-3 my-3">
      <h4 className="font-semibold">{heading}</h4>
      <p>
        {c[sample.metric as keyof typeof c] || c.unknown}: {sample.value}{" "}
        {sample.unit === "official_level" ? "" : sample.unit}
      </p>
      <p>
        {c.time}: {dateTime(sample.timestamp)}
      </p>
      <p>
        {c.quality}: {c[sample.quality as keyof typeof c] || c.unknown}
      </p>
      {sample.datum && <p>{sample.datum}</p>}
    </div>
  );
}

function Reader({ inbox, canManage }: { inbox: boolean; canManage: boolean }) {
  const { locale, dateTime } = useI18n(),
    c = riverCopy[locale],
    t = riverTodayCopy[locale];
  const [page, setPage] = useState<Page | null>(null),
    [failed, setFailed] = useState(false),
    [conflict, setConflict] = useState(false),
    [busy, setBusy] = useState(false),
    [saving, setSaving] = useState(false);
  const [unreviewed, setUnreviewed] = useState(inbox),
    [anchors, setAnchors] = useState<(Cursor | null)[]>([null]),
    [revision, setRevision] = useState(0);
  const request = useRef<AbortController | null>(null),
    action = useRef<AbortController | null>(null);
  const cursor = anchors[anchors.length - 1];
  useEffect(() => {
    const controller = new AbortController();
    request.current = controller;
    setPage(null);
    setFailed(false);
    setBusy(true);
    const params = new URLSearchParams({
      unreviewed: String(unreviewed),
      ...(cursor || {}),
    });
    api<Page>(`/river-watch/today?${params}`, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setPage(value);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setPage(null);
          setFailed(true);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setBusy(false);
          request.current = null;
        }
      });
    return () => controller.abort();
  }, [unreviewed, cursor, revision]);
  useEffect(() => {
    const refresh = () => {
      if (!document.hidden && !request.current && !action.current)
        setRevision((v) => v + 1);
    };
    const timer = setInterval(refresh, 60000);
    window.addEventListener("focus", refresh);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", refresh);
      action.current?.abort();
    };
  }, []);
  function reload() {
    setAnchors([null]);
    setRevision((v) => v + 1);
  }
  async function review(item: Entry, decision: string) {
    if (action.current) return;
    const controller = new AbortController();
    action.current = controller;
    request.current?.abort();
    setSaving(true);
    setFailed(false);
    setConflict(false);
    try {
      await api(
        `/river-watch/monitors/${item.monitor_id}/changes/${item.id}/review`,
        {
          method: "POST",
          signal: controller.signal,
          body: JSON.stringify({
            expected_version: item.review_version,
            decision,
          }),
        },
      );
      if (!controller.signal.aborted) {
        setPage(null);
        reload();
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        setPage(null);
        if (
          error instanceof ApiError &&
          ["river_newer_change", "river_version_conflict"].includes(error.code)
        ) {
          setConflict(true);
          reload();
        } else setFailed(true);
      }
    } finally {
      if (!controller.signal.aborted) {
        action.current = null;
        setSaving(false);
        setBusy(false);
      }
    }
  }
  const label = (value: string) => c[value as keyof typeof c] || c.unknown;
  return (
    <section
      className="rounded-xl border p-4 my-5 min-w-0 [overflow-wrap:anywhere]"
      data-river-today
      aria-busy={busy || saving}
    >
      <h2 className="font-semibold">{t.title}</h2>
      <p>{t.body}</p>
      <p>{t.scope}</p>
      <div className="flex flex-wrap gap-3 items-center my-3">
        <label>
          {t.unreviewed}{" "}
          <input
            type="checkbox"
            checked={unreviewed}
            disabled={saving}
            onChange={(e) => {
              setUnreviewed(e.target.checked);
              setAnchors([null]);
              setConflict(false);
            }}
          />
        </label>
        <button
          className="underline min-h-[44px]"
          disabled={busy || saving}
          onClick={reload}
        >
          {c.refresh}
        </button>
      </div>
      {conflict && <p role="alert">{c.conflict}</p>}
      {failed && <p role="alert">{c.failed}</p>}
      {busy && <p role="status">{c.loading}</p>}
      {page && (
        <>
          <p data-river-unreviewed>
            {t.unreviewed}: {page.unreviewed_count}
          </p>
          {!page.items.length && <p>{t.empty}</p>}
          {page.items.map((item) => (
            <article
              className="border-t py-4"
              key={item.id}
              data-river-today-entry={item.id}
            >
              <h3 className="font-semibold">
                {item.monitor_name} · {label(item.kind)}
              </h3>
              <p>
                {t.station}: {item.evidence.station_id} ·{" "}
                {label(item.monitor_status)}
              </p>
              <p>{riverAttribution[locale]}</p>
              <p>
                {t.detected}: {dateTime(item.created_at)} · {c.revision}{" "}
                {item.revision}
              </p>
              <p>{t[item.sample_state as keyof typeof t] || c.unknown}</p>
              {!item.current_configuration && <p>{t.historical}</p>}
              {item.evidence.sample && (
                <Reading sample={item.evidence.sample} heading={t.reading} />
              )}
              {item.evidence.baseline ? (
                <Reading sample={item.evidence.baseline} heading={t.previous} />
              ) : (
                <p>{t.baseline}</p>
              )}
              {item.evidence.rule && (
                <p>
                  {c.rules}: {label(item.evidence.rule.kind)}{" "}
                  {item.evidence.rule.threshold} {item.evidence.rule.unit}
                  {item.evidence.rule.window_minutes
                    ? ` · ${c.window}: ${item.evidence.rule.window_minutes}`
                    : ""}
                </p>
              )}
              {item.evidence.corrected && <p>{t.corrected}</p>}
              {item.evidence.recovered && <p>{c.recovered}</p>}
              <p>{item.decision ? label(item.decision) : t.unreviewed}</p>
              <div className="flex flex-wrap gap-4 items-center">
                <Link
                  className="underline min-h-[44px] inline-flex items-center"
                  href={item.href}
                >
                  {t.evidence}
                </Link>
                {canManage && (
                  <>
                    {["reviewed", "not_relevant"].map((decision) => (
                      <button
                        key={decision}
                        data-river-review
                        className="underline min-h-[44px]"
                        disabled={busy || saving || item.decision === decision}
                        onClick={() => void review(item, decision)}
                      >
                        {label(decision)}
                      </button>
                    ))}
                  </>
                )}
              </div>
            </article>
          ))}
        </>
      )}
      <div className="flex flex-wrap gap-4">
        {anchors.length > 1 && (
          <button
            className="underline min-h-[44px]"
            disabled={busy || saving}
            onClick={() => setAnchors((a) => a.slice(0, -1))}
          >
            {t.back}
          </button>
        )}
        {page?.next && (
          <button
            className="underline min-h-[44px]"
            disabled={busy || saving}
            onClick={() => setAnchors((a) => [...a, page.next])}
          >
            {t.next}
          </button>
        )}
      </div>
    </section>
  );
}
