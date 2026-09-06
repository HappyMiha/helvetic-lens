"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, History, RefreshCw, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { marvinHistoryCopy } from "@/lib/marvin-history-copy";
import { publishMarvinDeletion } from "@/lib/marvin-history-events";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import { Button } from "./ui/button";
import { ErrorNote } from "./common";
import { ConfirmDeleteDialog } from "./confirm-delete-dialog";

type Entry = {
  id: string;
  title: string;
  route: string;
  locale: string;
  created_at: string;
  updated_at: string;
  entity_kind: string | null;
  entity_id: string | null;
  has_draft: boolean;
  message_count: number;
  handoff_count: number;
};
type Page = { items: Entry[]; next_cursor: string | null };
type Conversation = {
  id: string;
  title: string;
  route: string;
  created_at: string;
  updated_at: string;
  entity: { kind: string; id: string; label?: string } | null;
  draft: string;
  messages: { id: string; role: string; content: string; created_at: string }[];
  handoffs: { id: string; question: string; created_at: string }[];
};

export function MarvinHistoryPage() {
  const { session } = useAuth();
  const { locale, t } = useI18n();
  const organization = session?.organization?.id || "local-development";
  const user = session?.user?.id || "local-development";
  if (!session?.authenticated && !session?.anonymous_development) {
    return (
      <Shell section={t("companion.name")}>
        <p role="status">{marvinHistoryCopy[locale].loading}</p>
      </Shell>
    );
  }
  return (
    <Shell section={t("companion.name")}>
      <PrivateHistory
        key={JSON.stringify([organization, user, locale])}
        organization={organization}
        user={user}
      />
    </Shell>
  );
}

function PrivateHistory({
  organization,
  user,
}: {
  organization: string;
  user: string;
}) {
  const { locale, t } = useI18n();
  const copy = marvinHistoryCopy[locale];
  const [cursors, setCursors] = useState([""]);
  const [revision, setRevision] = useState(0);
  const [page, setPage] = useState<Page | null>(null);
  const [listError, setListError] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [detailError, setDetailError] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const lifetime = useRef<AbortController | null>(null);
  const cursor = cursors[cursors.length - 1];
  const date = (value: string) =>
    new Intl.DateTimeFormat(locale, {
      dateStyle: "medium",
      timeStyle: "medium",
      timeZone: "Europe/Zurich",
    }).format(new Date(value));

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setPage(null);
    setListError(false);
    api<Page>(
      `/assistant/conversations?limit=20&cursor=${encodeURIComponent(cursor)}`,
      { signal: controller.signal },
    )
      .then((value) => {
        if (!controller.signal.aborted) setPage(value);
      })
      .catch(() => {
        if (!controller.signal.aborted) setListError(true);
      });
    return () => controller.abort();
  }, [cursor, revision]);
  useEffect(() => {
    const controller = new AbortController();
    setConversation(null);
    setDetailError(false);
    setDeleteError(false);
    setConfirm(false);
    if (selected)
      api<Conversation>(
        `/assistant/conversations/${encodeURIComponent(selected)}`,
        { signal: controller.signal },
      )
        .then((value) => {
          if (!controller.signal.aborted) setConversation(value);
        })
        .catch(() => {
          if (!controller.signal.aborted) setDetailError(true);
        });
    return () => controller.abort();
  }, [selected, revision]);
  useEffect(() => {
    if (conversation) detailHeading.current?.focus();
  }, [conversation]);

  function back() {
    setSelected(null);
    setConversation(null);
    requestAnimationFrame(() => heading.current?.focus());
  }
  async function remove() {
    if (!conversation || deleting || !lifetime.current) return;
    const value = conversation,
      signal = lifetime.current.signal;
    setDeleting(true);
    setDeleteError(false);
    try {
      await api(`/assistant/conversations/${encodeURIComponent(value.id)}`, {
        method: "DELETE",
        signal,
      });
      if (signal.aborted) return;
      publishMarvinDeletion({
        id: value.id,
        organization,
        user,
        comparison: value.entity?.kind === "comparison" ? value.entity.id : "",
      });
      setConfirm(false);
      setDeleted(true);
      back();
      setCursors([""]);
      setRevision((r) => r + 1);
    } catch {
      if (!signal.aborted) setDeleteError(true);
    } finally {
      if (!signal.aborted) setDeleting(false);
    }
  }

  return (
    <section className="marvin-history" data-marvin-history>
      <header className="page-header">
        <div>
          <span className="eyebrow">{t("companion.name")}</span>
          <h1 tabIndex={-1} ref={heading}>
            {copy.title}
          </h1>
          <p>{copy.intro}</p>
        </div>
        <Button
          variant="outline"
          onClick={() => {
            back();
            setCursors([""]);
            setRevision((r) => r + 1);
          }}
          disabled={deleting}
        >
          <RefreshCw size={16} />
          {copy.refresh}
        </Button>
      </header>
      <details className="panel marvin-history-privacy" open={!selected}>
        <summary>{copy.privacy}</summary>
        <p>{copy.retention}</p>
        <p>{copy.limits}</p>
      </details>
      <p role="status">{deleted ? copy.deleted : ""}</p>
      {!selected ? (
        <>
          {listError ? (
            <>
              <ErrorNote message={copy.error} />
              <Button onClick={() => setRevision((r) => r + 1)}>
                {copy.retry}
              </Button>
            </>
          ) : !page ? (
            <p role="status">{copy.loading}</p>
          ) : (
            <>
              {page.items.length === 0 ? (
                <p className="panel marvin-history-empty">{copy.empty}</p>
              ) : (
                <ul className="marvin-history-list">
                  {page.items.map((item) => (
                    <li className="panel" key={item.id}>
                      <div>
                        <h2>{item.title || item.route}</h2>
                        <p>
                          <time dateTime={item.updated_at}>
                            {copy.updated}: {date(item.updated_at)}
                          </time>
                        </p>
                        <p>
                          {copy.messages}: {item.message_count} ·{" "}
                          {copy.handoffs}: {item.handoff_count}
                          {item.has_draft ? ` · ${copy.draft}` : ""}
                        </p>
                        <small>
                          {copy.context}: {item.route}
                          {item.entity_id ? ` · ${item.entity_id}` : ""}
                        </small>
                      </div>
                      <Button
                        variant="outline"
                        data-history-view={item.id}
                        onClick={() => {
                          setDeleted(false);
                          setSelected(item.id);
                        }}
                      >
                        <History size={16} />
                        {copy.view}
                        <span className="sr-only">
                          : {item.title || item.route}
                        </span>
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
              <nav className="marvin-history-pager" aria-label={copy.title}>
                <Button
                  variant="outline"
                  disabled={cursors.length === 1}
                  onClick={() => setCursors((v) => v.slice(0, -1))}
                >
                  {copy.previous}
                </Button>
                <Button
                  variant="outline"
                  disabled={!page.next_cursor}
                  onClick={() => {
                    if (page.next_cursor)
                      setCursors((v) => [...v, page.next_cursor!]);
                  }}
                >
                  {copy.next}
                </Button>
              </nav>
            </>
          )}
        </>
      ) : (
        <>
          <Button variant="outline" onClick={back} disabled={deleting}>
            <ArrowLeft size={16} />
            {copy.back}
          </Button>
          {detailError ? (
            <>
              <ErrorNote message={copy.error} />
              <Button onClick={() => setRevision((r) => r + 1)}>
                {copy.retry}
              </Button>
            </>
          ) : !conversation ? (
            <p role="status">{copy.loading}</p>
          ) : (
            <article className="panel marvin-history-detail">
              <header>
                <h2 ref={detailHeading} tabIndex={-1}>
                  {conversation.title || conversation.route}
                </h2>
                <Button
                  variant="destructive"
                  data-history-delete
                  onClick={() => {
                    setDeleteError(false);
                    setConfirm(true);
                  }}
                >
                  <Trash2 size={16} />
                  {copy.remove}
                </Button>
              </header>
              <p>
                {copy.context}: {conversation.route}
                {conversation.entity
                  ? ` · ${conversation.entity.kind} · ${conversation.entity.id}`
                  : ""}
              </p>
              <p>
                {copy.created}:{" "}
                <time dateTime={conversation.created_at}>
                  {date(conversation.created_at)}
                </time>
                <br />
                {copy.updated}:{" "}
                <time dateTime={conversation.updated_at}>
                  {date(conversation.updated_at)}
                </time>
              </p>
              {conversation.draft && (
                <section>
                  <h3>{copy.draft}</h3>
                  <p className="marvin-history-text">{conversation.draft}</p>
                </section>
              )}
              {conversation.messages.length > 0 && (
                <section>
                  <h3>{copy.messages}</h3>
                  <ol>
                    {conversation.messages.map((message) => (
                      <li key={message.id}>
                        <strong>
                          {message.role === "assistant"
                            ? t("companion.name")
                            : t("companion.you")}
                        </strong>{" "}
                        ·{" "}
                        <time dateTime={message.created_at}>
                          {date(message.created_at)}
                        </time>
                        <p className="marvin-history-text">{message.content}</p>
                      </li>
                    ))}
                  </ol>
                </section>
              )}
              {conversation.handoffs.length > 0 && (
                <section>
                  <h3>{copy.handoffs}</h3>
                  <ol>
                    {conversation.handoffs.map((item) => (
                      <li key={item.id}>
                        <time dateTime={item.created_at}>
                          {date(item.created_at)}
                        </time>
                        <p className="marvin-history-text">{item.question}</p>
                      </li>
                    ))}
                  </ol>
                </section>
              )}
              {!conversation.draft &&
                !conversation.messages.length &&
                !conversation.handoffs.length && <p>{copy.noContent}</p>}
            </article>
          )}
        </>
      )}
      <ConfirmDeleteDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={copy.confirm}
        description={`${conversation?.title || ""}. ${copy.limits}`}
        confirmLabel={copy.remove}
        busy={deleting}
        error={deleteError ? copy.error : ""}
        onConfirm={remove}
      />
    </section>
  );
}
