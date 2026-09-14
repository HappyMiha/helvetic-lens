"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { tenderCopy, simapNotice } from "@/lib/tender-copy";
import { tenderTodayCopy } from "@/lib/tender-today-copy";
import { sourceTitle, type TenderCard } from "@/lib/tender-watch";
import { useAuth } from "./auth-gate";

type Entry = TenderCard & {
  monitor_name: string;
  monitor_status: string;
  observed_at: string;
  href: string;
};
type Page = {
  items: Entry[];
  pending_count: number;
  next_cursor: string | null;
};
export function TenderToday({ inbox = false }: { inbox?: boolean }) {
  const { session } = useAuth();
  const [visible, setVisible] = useState(true),
    [epoch, setEpoch] = useState(0);
  useEffect(() => {
    const hide = () => setVisible(false),
      show = () => {
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
    />
  );
}

function Reader({ inbox }: { inbox: boolean }) {
  const { locale, dateTime } = useI18n(),
    c = tenderCopy[locale],
    t = tenderTodayCopy[locale];
  const [page, setPage] = useState<Page | null>(null),
    [failed, setFailed] = useState(false),
    [busy, setBusy] = useState(false),
    [review, setReview] = useState(inbox ? "pending" : ""),
    [following, setFollowing] = useState(false),
    [anchors, setAnchors] = useState<(string | null)[]>([null]),
    [revision, setRevision] = useState(0);
  const cursor = anchors[anchors.length - 1],
    request = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    request.current = controller;
    setPage(null);
    setFailed(false);
    setBusy(true);
    const params = new URLSearchParams({ following: String(following) });
    if (review) params.set("review_state", review);
    if (cursor) params.set("after_version", cursor);
    api<Page>(`/tender-watch/today?${params}`, { signal: controller.signal })
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
  }, [review, following, cursor, revision]);
  useEffect(() => {
    const refresh = () => {
      if (!document.hidden && !request.current) setRevision((v) => v + 1);
    };
    const timer = setInterval(refresh, 60_000);
    window.addEventListener("focus", refresh);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", refresh);
    };
  }, []);
  const label = (value: string) => c[value as keyof typeof c] || c.unknown;
  return (
    <section
      className="rounded-xl border p-4 my-5 min-w-0 [overflow-wrap:anywhere]"
      data-tender-today
      aria-busy={busy}
    >
      <h2 className="font-semibold">{t.title}</h2>
      <p>{t.body}</p>
      <p>{t.private}</p>
      <p>{simapNotice[locale]}</p>
      <div className="flex flex-wrap gap-4 items-center my-3">
        <label>
          {c.review}{" "}
          <select
            value={review}
            onChange={(e) => {
              setReview(e.target.value);
              setAnchors([null]);
            }}
          >
            <option value="">{c.all}</option>
            <option value="pending">{t.pending}</option>
            {["new", "needs_review", "reviewed"].map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input
            type="checkbox"
            checked={following}
            onChange={(e) => {
              setFollowing(e.target.checked);
              setAnchors([null]);
            }}
          />{" "}
          {c.following}
        </label>
        <button
          className="underline min-h-[44px]"
          disabled={busy}
          onClick={() => {
            setAnchors([null]);
            setRevision((v) => v + 1);
          }}
        >
          {c.refresh}
        </button>
      </div>
      {busy && <p role="status">{c.loading}</p>}
      {failed && <p role="alert">{c.failed}</p>}
      {page && (
        <>
          <p data-tender-pending>
            {t.count}: {page.pending_count}
          </p>
          {!page.items.length && <p>{c.none}</p>}
          {page.items.map((item) => (
            <article
              className="border-t py-4"
              key={item.id}
              data-tender-today-entry={item.id}
            >
              <h3 className="font-semibold">
                {sourceTitle(item.summary.title, locale) || c.tenders}
              </h3>
              {item.summary.title_truncated && <p>{c.excerpt}</p>}
              <p>
                {item.monitor_name} · {label(item.monitor_status)}
                {item.following ? ` · ${c.following}` : ""}
              </p>
              <p>
                {label(item.review_state)} · {label(item.summary.phase)} ·{" "}
                {label(item.summary.verdict)}
              </p>
              {item.summary.match_scope === "project_context" && (
                <p>{c.projectContext}</p>
              )}
              <p>
                {c.deadline}:{" "}
                {item.summary.deadline.status === "known" &&
                item.summary.deadline.utc ? (
                  <time dateTime={item.summary.deadline.utc}>
                    {new Date(item.summary.deadline.utc).toLocaleString(
                      locale === "rm-CH" ? "de-CH" : locale,
                      { timeZone: "Europe/Zurich", timeZoneName: "short" },
                    )}
                  </time>
                ) : (
                  c.noDeadline
                )}
              </p>
              <p>
                {t.observed}: {dateTime(item.observed_at)} · {c.revision}{" "}
                {item.sequence}
              </p>
              {item.profile_revision !== item.current_profile_revision && (
                <p>{c.profileOld}</p>
              )}
              {item.decision && (
                <p>
                  {c.internalDecision}: {label(item.decision)} · {c.revision}{" "}
                  {item.reviewed_sequence}
                </p>
              )}
              {item.decision && item.review_state === "needs_review" && (
                <p>{c.retained}</p>
              )}
              <Link
                className="underline min-h-[44px] inline-flex items-center"
                href={item.href}
              >
                {t.open}
              </Link>
            </article>
          ))}
        </>
      )}
      <p>{c.evidenceHelp}</p>
      <div className="flex flex-wrap gap-4">
        {anchors.length > 1 && (
          <button
            className="underline min-h-[44px]"
            disabled={busy}
            onClick={() => setAnchors((a) => a.slice(0, -1))}
          >
            {t.previous}
          </button>
        )}
        {page?.next_cursor && (
          <button
            className="underline min-h-[44px]"
            disabled={busy}
            onClick={() => setAnchors((a) => [...a, page.next_cursor])}
          >
            {t.next}
          </button>
        )}
      </div>
    </section>
  );
}
