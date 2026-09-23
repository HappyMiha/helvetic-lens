"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { dossierReviewCopy } from "@/lib/dossier-review-copy";
import type { DossierReviewNote, InfluenceSource } from "@/lib/influence-graph";
import { Button } from "./ui/button";

type Brief = {
  id: string;
  title: string;
  revision: number;
  updatedAt: string;
  document: {
    reviewNotes?: DossierReviewNote[];
    sources: Pick<InfluenceSource, "id" | "url" | "title" | "publisher">[];
  };
};
export function DossierReview({
  brief,
  graphLink = false,
}: {
  brief: Brief;
  graphLink?: boolean;
}) {
  const { locale, dateTime } = useI18n();
  const c = dossierReviewCopy[locale];
  const [kind, setKind] = useState<DossierReviewNote["kind"]>("finding");
  const notes = brief.document.reviewNotes || [];
  if (!notes.length) return null;
  return (
    <section className="panel my-6" aria-label={c.title}>
      <header className="panel-header flex flex-wrap gap-4 justify-between">
        <div>
          <span className="eyebrow">{c.title}</span>
          <h2>{brief.title}</h2>
        </div>
        {graphLink && (
          <Button asChild variant="outline">
            <Link href={`/influence?dossier=${brief.id}`}>{c.graph}</Link>
          </Button>
        )}
      </header>
      <div className="p-5 border-b">
        <p className="text-sm text-muted-foreground">{c.note}</p>
        <p className="text-xs text-muted-foreground mt-2">
          {c.revision} {brief.revision} · {dateTime(brief.updatedAt)}
        </p>
        <div
          className="flex flex-wrap gap-2 mt-4"
          role="group"
          aria-label={c.kind}
        >
          {(["finding", "discussion", "task"] as const).map((value) => (
            <Button
              key={value}
              variant={kind === value ? "default" : "outline"}
              aria-pressed={kind === value}
              onClick={() => setKind(value)}
            >
              {c[value]} ({notes.filter((item) => item.kind === value).length})
            </Button>
          ))}
        </div>
      </div>
      <div className="grid gap-4 p-5 md:grid-cols-2">
        {!notes.some((item) => item.kind === kind) && <p>{c.empty}</p>}
        {notes
          .filter((item) => item.kind === kind)
          .map((item) => (
            <article key={item.id} className="rounded-lg border p-5 min-w-0">
              <p className="eyebrow">
                {item.author} · {item.role}
              </p>
              {item.fictional && (
                <p className="text-xs text-muted-foreground mt-1">
                  {c.fictional}
                </p>
              )}
              <h3 className="text-lg font-semibold mt-3">{item.title}</h3>
              {item.kind === "task" && (
                <p className="text-sm mt-2 font-medium">
                  {c[item.status]}
                  {item.dueOn ? ` · ${c.due}: ${item.dueOn}` : ""}
                </p>
              )}
              <p className="whitespace-pre-wrap text-sm leading-relaxed mt-3">
                {item.body}
              </p>
              {!!item.sourceIds.length && (
                <ul className="mt-4 space-y-2 text-sm" aria-label={c.sources}>
                  {item.sourceIds.map((id) => {
                    const source = brief.document.sources.find(
                      (row) => row.id === id,
                    );
                    return source ? (
                      <li key={id}>
                        <a
                          className="text-link"
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {source.title} ↗
                        </a>
                      </li>
                    ) : null;
                  })}
                </ul>
              )}
            </article>
          ))}
      </div>
    </section>
  );
}
export function LawReviewBriefs({ lawId }: { lawId: string }) {
  const { locale } = useI18n();
  const c = dossierReviewCopy[locale];
  const [items, setItems] = useState<Brief[]>([]);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setFailed(false);
    setItems([]);
    api<{ items: Brief[] }>(`/influence/dossiers/by-law/${lawId}`, {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setItems(value.items);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, [lawId, retry]);
  if (failed)
    return (
      <p role="alert">
        {c.failed}{" "}
        <Button
          variant="outline"
          onClick={() => setRetry((value) => value + 1)}
        >
          {c.retry}
        </Button>
      </p>
    );
  return (
    <>
      {items.map((brief) => (
        <DossierReview key={brief.id} brief={brief} graphLink />
      ))}
    </>
  );
}
