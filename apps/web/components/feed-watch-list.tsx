"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { errorText, fetchResource, resourceScopeEpoch, useResource } from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { useI18n } from "@/lib/i18n";
import { ErrorNote } from "./common";
import { Button } from "./ui/button";

type Watch = {watch_id: string; name: string; url: string};
type Page = {items: Watch[]; next_cursor: string | null};

export function FeedWatchList({eventId, items, nextCursor}: {
  eventId: string; items: Watch[]; nextCursor: string | null;
}) {
  const { t } = useI18n();
  const [cursors, setCursors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const generation = useRef(0);
  useEffect(() => () => { generation.current++; }, []);
  const cursor = cursors.at(-1);
  const page = useResource(cursor === undefined ? null : resources.feedWatches<Page>(eventId, cursor));
  const shown = cursor === undefined ? items : page.data?.items || [];
  const next = cursor === undefined ? nextCursor : page.data?.next_cursor;
  async function move(stack: string[]) {
    if (busy) return;
    const current = generation.current, epoch = resourceScopeEpoch("session");
    setBusy(true); setFailure("");
    try {
      if (stack.length) await fetchResource(resources.feedWatches<Page>(eventId, stack.at(-1)!));
      if (current === generation.current && epoch === resourceScopeEpoch("session")) setCursors(stack);
    } catch (cause) {
      if (current === generation.current && epoch === resourceScopeEpoch("session")) setFailure(errorText(cause));
    } finally {
      if (current === generation.current && epoch === resourceScopeEpoch("session")) setBusy(false);
    }
  }
  return <section data-feed-watches className="border-t mt-3 pt-4" aria-busy={busy}>
    <h3 className="text-base font-semibold">{t("registry.monitored")}</h3>
    {(next || cursors.length > 0) && <p className="text-sm muted">{t("feedWatches.boundary")}</p>}
    <ul>{shown.map(document => <li key={document.watch_id}><Link href={document.url}
      className="underline min-h-[44px] inline-flex items-center">{document.name}</Link></li>)}</ul>
    {!shown.length && !page.error && <p role="status">{t("feedWatches.empty")}</p>}
    <ErrorNote message={failure || page.error} />
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
