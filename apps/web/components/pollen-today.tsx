"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { privatePollenScope } from "@/lib/pollen-drafts";
import { pollenDraftCopy } from "@/lib/pollen-draft-copy";
import { pollenRuntimeCopy } from "@/lib/pollen-runtime-copy";
import { useAuth } from "./auth-gate";

type Page = {
  items: {
    id: string;
    subject_id: string;
    station_id: string;
    allergen: string;
    reasons: string[];
  }[];
  next_cursor: string | null;
};

export function PollenToday() {
  const { session } = useAuth();
  const scope = session?.authenticated
    ? privatePollenScope(
        session.user?.id,
        session.organization?.id,
        session.role,
      )
    : null;
  return scope ? <PrivatePollenToday key={scope} /> : null;
}

function PrivatePollenToday() {
  const { locale } = useI18n(),
    copy = pollenRuntimeCopy[locale],
    labels = pollenDraftCopy[locale];
  const [page, setPage] = useState<Page | null>(null),
    [busy, setBusy] = useState(false),
    [failed, setFailed] = useState(false);
  const request = useRef<AbortController | null>(null);
  async function load(cursor?: string) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setFailed(false);
    try {
      const result = await api<Page>(
        `/monitoring-subjects/today${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
        { signal: controller.signal },
      );
      if (!controller.signal.aborted)
        setPage((old) => ({
          items: cursor
            ? [
                ...(old?.items || []),
                ...result.items.filter(
                  (item) => !old?.items.some((row) => row.id === item.id),
                ),
              ]
            : result.items,
          next_cursor: result.next_cursor,
        }));
    } catch (error) {
      if (!controller.signal.aborted) {
        setPage(null);
        setFailed(
          !(
            error instanceof ApiError &&
            [
              "monitoring_not_enabled",
              "authentication_required",
              "membership_required",
              "forbidden",
            ].includes(error.code)
          ),
        );
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  useEffect(() => {
    void load();
    const clear = () => {
      request.current?.abort();
      setPage(null);
    };
    const restore = (event: PageTransitionEvent) => {
      if (event.persisted) window.location.reload();
    };
    window.addEventListener("pagehide", clear);
    window.addEventListener("pageshow", restore);
    return () => {
      clear();
      window.removeEventListener("pagehide", clear);
      window.removeEventListener("pageshow", restore);
    };
    // Identity changes synchronously remount this private reader.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (!page?.items.length && !page?.next_cursor && !failed) return null;
  return (
    <section
      className="rounded-xl border p-4 my-5"
      data-pollen-today
      aria-busy={busy}
    >
      <h2>{labels.title} · {copy.today}</h2>
      {failed && <p role="alert">{copy.failed}</p>}
      <ul>
        {page?.items.map((item) => (
          <li key={item.id} className="py-2">
            <Link
              className="underline min-h-[44px] inline-flex items-center"
              href={`/pollen-watch#draft=${encodeURIComponent(item.subject_id)}`}
            >
              {item.station_id} ·{" "}
              {labels.allergens[item.allergen] || labels.unknown}
            </Link>
            {item.reasons.map((reason) => (
              <p key={reason}>
                {copy[reason as keyof typeof copy] || copy.material}
              </p>
            ))}
          </li>
        ))}
      </ul>
      {page?.next_cursor && (
        <button
          type="button"
          className="min-h-[44px] underline"
          disabled={busy}
          onClick={() => void load(page.next_cursor!)}
        >
          {labels.more}
        </button>
      )}
      {failed && (
        <button
          type="button"
          className="min-h-[44px] underline"
          disabled={busy}
          onClick={() => void load()}
        >
          {copy.load}
        </button>
      )}
    </section>
  );
}
