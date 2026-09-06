"use client";

import Link from "next/link";
import { useFeedInterestPage } from "@/lib/feed-interest-page";
import { resources } from "@/lib/resource-keys";
import { useI18n } from "@/lib/i18n";
import { ErrorNote } from "./common";
import { Button } from "./ui/button";

type Watch = {watch_id: string; name: string; url: string};

export function FeedWatchList({eventId, items, nextCursor}: {
  eventId: string; items: Watch[]; nextCursor: string | null;
}) {
  const { t } = useI18n();
  const {shown, next, cursors, busy, error, move} = useFeedInterestPage(items, nextCursor,
    cursor => resources.feedWatches(eventId, cursor));
  return <section data-feed-watches className="border-t mt-3 pt-4" aria-busy={busy}>
    <h3 className="text-base font-semibold">{t("registry.monitored")}</h3>
    {(next || cursors.length > 0) && <p className="text-sm muted">{t("feedWatches.boundary")}</p>}
    <ul>{shown.map(document => <li key={document.watch_id}><Link href={document.url}
      className="underline min-h-[44px] inline-flex items-center">{document.name}</Link></li>)}</ul>
    {!shown.length && !error && <p role="status">{t("feedWatches.empty")}</p>}
    <ErrorNote message={error} />
    <div className="flex flex-wrap gap-2 mt-2">
      {cursors.length > 0 && <Button data-watch-back variant="outline" disabled={busy}
        onClick={() => void move(cursors.slice(0, -1))}>{t("feedWatches.previous")}</Button>}
      {next && <Button data-watch-next variant="outline" disabled={busy}
        onClick={() => void move([...cursors, next])}>{t("feedWatches.next")}</Button>}
      {cursors.length > 0 && <Button data-watch-first variant="outline" disabled={busy}
        onClick={() => void move([])}>{t("feedWatches.first")}</Button>}
    </div>
  </section>;
}
