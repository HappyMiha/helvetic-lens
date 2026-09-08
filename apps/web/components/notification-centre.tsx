"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import {
  api,
  errorText,
  fetchResource,
  invalidateResources,
  resourceScopeEpoch,
  resourceTag,
  useResource,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { notificationCopy } from "@/lib/notification-copy";
import { resources } from "@/lib/resource-keys";
import { documentHistoryCopy } from "@/lib/document-history-copy";
import { useAuth } from "./auth-gate";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog";
import { ErrorNote } from "./common";
import { NotificationBrief } from "./notification-brief";
import type { DigestBrief } from "@/lib/interest-brief";

type Event = {
  event_id: string;
  title: string;
  source: string;
  detected_at: string;
  brief?: DigestBrief;
};
type Page = { items: Event[]; next_cursor: string | null };

export function NotificationCentre() {
  const { session } = useAuth();
  const { locale } = useI18n();
  return (
    <Centre
      key={`${session?.user?.id}:${session?.organization?.id}:${locale}`}
    />
  );
}

function Centre() {
  const { locale } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          data-notifications-trigger
          variant="ghost"
          className="size-11 shrink-0 p-0"
          aria-label={notificationCopy[locale].title}
        >
          <Bell size={20} />
        </Button>
      </DialogTrigger>
      <DialogContent data-notification-centre className="sm:max-w-xl">
        <DialogTitle className="pr-10">
          {notificationCopy[locale].title}
        </DialogTitle>
        <DialogDescription>{notificationCopy[locale].body}</DialogDescription>
        {open && <Notifications onNavigate={() => setOpen(false)} />}
      </DialogContent>
    </Dialog>
  );
}

function Notifications({ onNavigate }: { onNavigate: () => void }) {
  const { session } = useAuth();
  const identity = JSON.stringify([
    session?.organization?.id,
    session?.user?.id,
  ]);
  const { locale, t, dateTime, number } = useI18n();
  const copy = notificationCopy[locale],
    paging = documentHistoryCopy[locale];
  const [cursors, setCursors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [saved, setSaved] = useState(false);
  const generation = useRef(0);
  const retry = useRef<string[]>([]);
  const heading = useRef<HTMLParagraphElement>(null);
  const page = useResource(
    resources.notifications<Page>(identity, cursors.at(-1) || ""),
  );
  useEffect(
    () => () => {
      generation.current++;
    },
    [],
  );
  async function move(next: string[]) {
    if (busy) return;
    const id = generation.current,
      epoch = resourceScopeEpoch("session");
    retry.current = next;
    setBusy(true);
    setFailure("");
    setSaved(false);
    try {
      await fetchResource(
        resources.notifications<Page>(identity, next.at(-1) || ""),
      );
      if (id !== generation.current || epoch !== resourceScopeEpoch("session"))
        return;
      setCursors(next);
      queueMicrotask(() => heading.current?.focus({ preventScroll: true }));
    } catch (cause) {
      if (id === generation.current) setFailure(errorText(cause));
    } finally {
      if (id === generation.current) setBusy(false);
    }
  }
  async function mark(event: Event, state: "read" | "dismissed") {
    if (busy) return;
    const id = generation.current;
    setBusy(true);
    setFailure("");
    setSaved(false);
    try {
      await api(
        `/interest-feed/events/${encodeURIComponent(event.event_id)}/state`,
        { method: "PATCH", body: JSON.stringify({ state }) },
      );
      await invalidateResources(
        resourceTag("impact-inbox", "organization"),
        resourceTag("digests", "organization"),
      );
      if (id === generation.current) {
        setSaved(true);
        queueMicrotask(() => heading.current?.focus({ preventScroll: true }));
      }
    } catch (cause) {
      if (id === generation.current) setFailure(errorText(cause));
    } finally {
      if (id === generation.current) setBusy(false);
    }
  }
  const error = failure || page.error;
  return (
    <div
      data-notification-list
      className="min-w-0 space-y-4 text-sm"
      aria-busy={busy || page.loading}
    >
      <p>{copy.cadence}</p>
      <p ref={heading} tabIndex={-1} className="font-semibold">
        {copy.count}: {page.data ? number(page.data.items.length) : "—"}
      </p>
      {error && (
        <>
          <ErrorNote message={error} />
          {page.data && <p>{copy.stale}</p>}
          <Button
            data-notification-retry
            className="min-h-11 h-auto whitespace-normal"
            disabled={busy}
            variant="outline"
            onClick={() => void move(failure ? retry.current : cursors)}
          >
            {paging.retry}
          </Button>
        </>
      )}
      {saved && <p role="status">{t("feed.saved")}</p>}
      {!page.data && !error && <p role="status">{paging.loading}</p>}
      {page.data && !page.data.items.length && !error && (
        <p data-notification-empty>
          {page.data.next_cursor ? copy.sparse : copy.empty}
        </p>
      )}
      <ul className="space-y-4">
        {page.data?.items.map((event) => (
          <li
            key={event.event_id}
            data-notification-event
            className="rounded-lg border p-4 break-words"
          >
            <Link
              className="font-semibold underline text-base inline-flex min-h-11 items-center"
              href={`/?event=${encodeURIComponent(event.event_id)}`}
              onClick={onNavigate}
            >
              {event.title}
            </Link>
            <p>{event.source}</p>
            <p>
              {t("feed.detected")}:{" "}
              {dateTime(event.detected_at, {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </p>
            <NotificationBrief brief={event.brief} eventTitle={event.title} eventUrl={`/?event=${encodeURIComponent(event.event_id)}`} onNavigate={onNavigate} stale={!!error} />
            <div className="flex flex-wrap gap-2 mt-3">
              <Button
                data-notification-read
                variant="outline"
                className="min-h-11 h-auto whitespace-normal"
                disabled={busy || !!error}
                onClick={() => void mark(event, "read")}
              >
                {copy.read}
              </Button>
              <Button
                data-notification-dismiss
                variant="ghost"
                className="min-h-11 h-auto whitespace-normal"
                disabled={busy || !!error}
                onClick={() => void mark(event, "dismissed")}
              >
                {copy.dismiss}
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button
          data-notification-back
          variant="outline"
          className="min-h-11 h-auto whitespace-normal"
          disabled={busy || !cursors.length}
          onClick={() => void move(cursors.slice(0, -1))}
        >
          {paging.previous}
        </Button>
        <Button
          data-notification-next
          variant="outline"
          className="min-h-11 h-auto whitespace-normal"
          disabled={busy || !page.data?.next_cursor}
          onClick={() =>
            page.data?.next_cursor &&
            void move([...cursors, page.data.next_cursor])
          }
        >
          {paging.next}
        </Button>
        <Button
          data-notification-latest
          variant="outline"
          className="min-h-11 h-auto whitespace-normal"
          disabled={busy}
          onClick={() => void move([])}
        >
          {paging.restart}
        </Button>
      </div>
      <nav className="flex flex-wrap gap-x-5">
        <Link
          className="underline min-h-11 inline-flex items-center"
          href="/?state=unread"
          onClick={onNavigate}
        >
          {t("nav.today")}
        </Link>
        <Link
          className="underline min-h-11 inline-flex items-center"
          href="/digests"
          onClick={onNavigate}
        >
          {t("nav.digests")}
        </Link>
      </nav>
    </div>
  );
}
