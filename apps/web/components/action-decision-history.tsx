"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText } from "@/lib/api";
import { useI18n, type Locale } from "@/lib/i18n";
import { documentHistoryCopy } from "@/lib/document-history-copy";
import type { ActionDecision } from "@/lib/types";
import { useAuth } from "./auth-gate";
import { Button } from "./ui/button";
import { ErrorNote } from "./common";

type Page = {
  items: ActionDecision[];
  total: number;
  as_of: string;
  first_cursor: string;
  next_cursor: string | null;
};
type Props = {
  comparisonId: string;
  analysisId: string;
  actionKey: string;
  count: number;
  revision?: string;
  labelDecision: (value: string) => string;
};
const help: Record<Locale, string> = {
  "en-CH":
    "Saved decisions for this action. The current decision stays above; browse earlier decisions here. Refresh to include new records.",
  "de-CH":
    "Gespeicherte Entscheidungen zu dieser Massnahme. Die aktuelle Entscheidung bleibt oben; frühere finden Sie hier. Aktualisieren Sie für neue Einträge.",
  "fr-CH":
    "Décisions enregistrées pour cette action. La décision actuelle reste affichée au-dessus ; consultez les précédentes ici. Actualisez pour voir les nouveaux enregistrements.",
  "it-CH":
    "Decisioni salvate per questa azione. La decisione attuale resta sopra; qui puoi consultare le precedenti. Aggiorna per includere nuovi elementi.",
  "rm-CH":
    "Decisiuns memorisadas per questa acziun. La decisiun actuala resta survart; qua chattais Vus las anteriuras. Actualisai per vesair novas endataziuns.",
};

export function ActionDecisionHistory(props: Props) {
  const { session } = useAuth();
  const { locale } = useI18n();
  return (
    <History
      key={[
        session?.organization?.id,
        session?.user?.id,
        props.comparisonId,
        props.analysisId,
        props.actionKey,
        locale,
      ].join(":")}
      {...props}
    />
  );
}

function History({
  comparisonId,
  analysisId,
  actionKey,
  count,
  revision,
  labelDecision,
}: Props) {
  const { locale, t, dateTime, number } = useI18n();
  const copy = documentHistoryCopy[locale];
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState<Page | null>(null);
  const [cursors, setCursors] = useState<string[]>([""]);
  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef({ cursor: "", index: 0 });
  const request = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const heading = useRef<HTMLParagraphElement>(null);
  const details = useRef<HTMLDetailsElement>(null);
  const url = `/comparisons/${comparisonId}/analyses/${analysisId}/actions/${encodeURIComponent(actionKey)}/decisions`;
  const load = useCallback(
    async (cursor = "", target = 0) => {
      request.current?.abort();
      const controller = new AbortController();
      request.current = controller;
      const id = ++sequence.current;
      const timer = window.setTimeout(() => controller.abort(), 15000);
      pending.current = { cursor, index: target };
      setBusy(true);
      setError("");
      try {
        const result = await api<Page>(
          `${url}?limit=20&cursor=${encodeURIComponent(cursor)}`,
          { signal: controller.signal },
        );
        if (sequence.current !== id) return;
        setPage(result);
        setIndex(target);
        setCursors((old) =>
          target === 0
            ? [result.first_cursor]
            : [...old.slice(0, target), cursor],
        );
        queueMicrotask(() => heading.current?.focus({ preventScroll: true }));
      } catch (cause) {
        if (sequence.current === id) setError(errorText(cause));
      } finally {
        window.clearTimeout(timer);
        if (sequence.current === id) setBusy(false);
      }
    },
    [url],
  );
  useEffect(
    () => () => {
      ++sequence.current;
      request.current?.abort();
    },
    [],
  );
  // A newly saved decision invalidates the captured page; never re-submit a mutation.
  useEffect(() => {
    setPage(null);
    setCursors([""]);
    setIndex(0);
    if (details.current?.open) void load();
  }, [revision, load]);
  return (
    <details
      ref={details}
      className="action-decision-history min-w-0 break-words"
      data-action-history={actionKey}
      onToggle={(event) => {
        const expanded = event.currentTarget.open;
        setOpen(expanded);
        if (expanded && !page && !busy) void load();
      }}
    >
      <summary className="min-h-11 py-3">
        {t("compare.recordedDecisions", { count: number(count) })}
      </summary>
      {open && (
        <div aria-busy={busy}>
          <p>{help[locale]}</p>
          <p ref={heading} tabIndex={-1} className="text-sm font-medium">
            {page
              ? `${copy.page} ${number(index + 1)} · ${copy.shown}: ${number(page.items.length)} · ${copy.total}: ${number(page.total)}`
              : copy.loading}
          </p>
          {page && (
            <p className="text-sm">
              {copy.before}: {dateTime(page.as_of)}
            </p>
          )}
          {busy && <p role="status">{copy.loading}</p>}
          {error && (
            <>
              <ErrorNote message={error} />
              <Button
                className="min-h-11 h-auto whitespace-normal"
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() =>
                  void load(pending.current.cursor, pending.current.index)
                }
              >
                {copy.retry}
              </Button>
            </>
          )}
          {page && (
            <ol>
              {page.items.map((item) => (
                <li key={item.id}>
                  {labelDecision(item.decision)} · {item.actor_label} ·{" "}
                  {dateTime(item.created_at)}
                  {item.assigned_to ? ` · ${item.assigned_to}` : ""}
                  {item.scheduled_for
                    ? ` · ${dateTime(item.scheduled_for)}`
                    : ""}
                  {item.rationale ? ` — ${item.rationale}` : ""}
                </li>
              ))}
            </ol>
          )}
          {page?.items.length === 0 && <p>{copy.empty}</p>}
          <div className="flex flex-wrap gap-2">
            <Button
              className="min-h-11 h-auto whitespace-normal"
              type="button"
              variant="outline"
              disabled={busy || index === 0}
              onClick={() => void load(cursors[index - 1], index - 1)}
            >
              {copy.previous}
            </Button>
            <Button
              className="min-h-11 h-auto whitespace-normal"
              type="button"
              variant="outline"
              disabled={busy || !page?.next_cursor}
              onClick={() =>
                page?.next_cursor && void load(page.next_cursor, index + 1)
              }
            >
              {copy.next}
            </Button>
            <Button
              className="min-h-11 h-auto whitespace-normal"
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => void load()}
            >
              {copy.restart}
            </Button>
          </div>
        </div>
      )}
    </details>
  );
}
