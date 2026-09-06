"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "./ui/button";
import { ErrorNote } from "./common";
import { invalidateResources, useResource } from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { documentHistoryCopy } from "@/lib/document-history-copy";
import { useI18n } from "@/lib/i18n";
import type { LawDetail, LawHistoryKind, LawHistoryPage } from "@/lib/types";

export function useDocumentHistory<K extends LawHistoryKind>(
  id: string,
  kind: K,
  law: LawDetail | null,
) {
  const [cursors, setCursors] = useState<string[]>([]);
  const focus = useRef(false);
  const cursor = cursors.at(-1);
  const request = useResource(
    cursor ? resources.documentHistory(id, kind, cursor) : null,
  );
  const initial = law?.history_pages?.[kind];
  const data = cursor
    ? request.data
    : initial
      ? ({ ...initial, items: law![kind] } as LawHistoryPage<K>)
      : null;
  useEffect(() => {
    if (focus.current && !request.loading && (data || request.error)) {
      document.getElementById(`history-${kind}`)?.focus();
      focus.current = false;
    }
  }, [data, request.loading, request.error, kind]);
  return {
    kind,
    data,
    items: (cursor
      ? request.data?.items || []
      : law?.[kind] || []) as LawDetail[K],
    loading: !!cursor && request.loading,
    error: cursor ? request.error : "",
    page: Math.max(1, cursors.length),
    canPrevious: cursors.length > 1,
    next: () => {
      if (!data?.next_cursor) return;
      focus.current = true;
      setCursors((current) => [
        ...(current.length ? current : [data.first_cursor]),
        data.next_cursor!,
      ]);
    },
    previous: () => {
      focus.current = true;
      setCursors((current) => current.slice(0, -1));
    },
    retry: () => request.reload(),
    restart: () => {
      focus.current = true;
      setCursors([]);
      void invalidateResources(resources.law(id));
    },
  };
}

export function DocumentHistoryNavigation({
  history,
}: {
  history: ReturnType<typeof useDocumentHistory>;
}) {
  const { locale, number, dateTime } = useI18n();
  const copy = documentHistoryCopy[locale];
  if (!history.data && !history.error && !history.loading) return null;
  return (
    <div
      className="p-4 border-b space-y-3"
      data-history-controls={history.kind}
    >
      <p className="text-sm muted m-0">{copy.help}</p>
      <div role="status" className="text-sm">
        {history.loading
          ? copy.loading
          : `${copy.page} ${number(history.page)} · ${copy.shown}: ${number(history.items.length)}`}
        {history.data && (
          <div className="muted mt-1">
            {copy.total}: {number(history.data.total)} · {copy.before}{" "}
            {dateTime(history.data.as_of, {
              dateStyle: "medium",
              timeStyle: "long",
            })}
          </div>
        )}
      </div>
      <ErrorNote message={history.error} />
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          onClick={history.previous}
          disabled={!history.canPrevious || history.loading}
        >
          {copy.previous}
        </Button>
        <Button
          variant="outline"
          onClick={history.next}
          disabled={
            !history.data?.next_cursor || history.loading || !!history.error
          }
        >
          {copy.next}
        </Button>
        {history.error && (
          <Button
            variant="outline"
            onClick={() => void history.retry()}
            disabled={history.loading}
          >
            {copy.retry}
          </Button>
        )}
        <Button
          variant="outline"
          onClick={history.restart}
          disabled={history.loading}
        >
          {copy.restart}
        </Button>
      </div>
      {!history.loading && !history.error && history.items.length === 0 && (
        <p>{copy.empty}</p>
      )}
    </div>
  );
}
