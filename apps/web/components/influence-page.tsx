"use client";

import { useEffect, useRef, useState } from "react";
import { GitFork } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { influenceCopy } from "@/lib/influence-copy";
import { influenceDossier } from "@/lib/influence-dossier";
import type { InfluenceDossier } from "@/lib/influence-graph";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import { InfluenceEditor } from "./influence-editor";
import { InfluenceReader } from "./influence-reader";
import { DossierReview } from "./dossier-review";
import { dossierReviewCopy } from "@/lib/dossier-review-copy";
import Link from "next/link";
import styles from "./influence.module.css";

type DossierSummary = {
  id: string;
  title: string;
  revision: number;
  archived: boolean;
  updatedAt: string;
};
type Review = {
  id: string;
  revision: number;
  decision: "reviewed" | "needs_revision";
  note: string;
  actorId: string | null;
  createdAt: string;
};
type SavedDossier = DossierSummary & {
  viewedRevision: number;
  revisionCreatedAt: string;
  document: InfluenceDossier;
  documentHash: string;
  note: string;
  actorId: string | null;
  reviews: Review[];
};
type History = {
  revision: number;
  action: string;
  note: string;
  actorId: string | null;
  documentHash: string;
  createdAt: string;
};
type Page<T, Cursor = string> = { items: T[]; nextCursor: Cursor | null };
const ROOT = "/influence/dossiers";

export function InfluencePage() {
  const { locale } = useI18n();
  const { session, canManage } = useAuth();
  return (
    <Shell section={influenceCopy[locale].title} wide>
      <Workspace
        key={`${session?.organization?.id || "anonymous"}:${session?.user?.id || "none"}:${canManage}`}
        authenticated={Boolean(session?.authenticated)}
        canManage={canManage}
      />
    </Shell>
  );
}

function Workspace({
  authenticated,
  canManage,
}: {
  authenticated: boolean;
  canManage: boolean;
}) {
  const { locale } = useI18n();
  const c = influenceCopy[locale];
  const [items, setItems] = useState<DossierSummary[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [archived, setArchived] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [listReady, setListReady] = useState(false);
  const [saved, setSaved] = useState<SavedDossier | null>(null);
  const [editing, setEditing] = useState<InfluenceDossier | null>(null);
  const [creating, setCreating] = useState(false);
  const [history, setHistory] = useState<History[] | null>(null);
  const [historyCursor, setHistoryCursor] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [note, setNote] = useState("");
  const [decision, setDecision] =
    useState<Review["decision"]>("needs_revision");
  const mounted = useRef(true);
  const pending = useRef(false);
  const retry = useRef({ body: "", id: "" });
  const listEpoch = useRef(0);
  const initialChoice = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const document = saved?.document || influenceDossier;
  const historical = saved && saved.viewedRevision !== saved.revision;
  useEffect(() => {
    if (!authenticated) return;
    const abort = new AbortController();
    const epoch = ++listEpoch.current;
    setListReady(false);
    setItems([]);
    setCursor(null);
    api<Page<DossierSummary>>(`${ROOT}?archived=${archived}`, {
      signal: abort.signal,
    })
      .then((page) => {
        if (!abort.signal.aborted && epoch === listEpoch.current) {
          setItems(page.items);
          setCursor(page.nextCursor);
          setListReady(true);
          if (!initialChoice.current) {
            initialChoice.current = true;
            const requested = new URL(window.location.href).searchParams.get(
              "dossier",
            );
            const id = requested || page.items[0]?.id;
            if (id && /^[a-f0-9-]{36}$/i.test(id)) {
              api<SavedDossier>(`${ROOT}/${id}`, { signal: abort.signal })
                .then((value) => {
                  if (!abort.signal.aborted) setSaved(value);
                })
                .catch(() => {
                  if (!abort.signal.aborted) setError(c.failed);
                });
            }
          }
        }
      })
      .catch(() => {
        if (!abort.signal.aborted) setError(c.failed);
      });
    return () => {
      abort.abort();
    };
  }, [authenticated, archived, refresh, c.failed]);

  async function perform(action: () => Promise<void>) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (cause) {
      if (mounted.current)
        setError(
          cause instanceof ApiError && cause.code === "influence_conflict"
            ? c.conflict
            : `${c.failed}${cause instanceof Error ? ` ${cause.message}` : ""}`,
        );
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  function accept(result: SavedDossier) {
    if (!mounted.current) return;
    setSaved(result);
    setHistory(null);
    setHistoryCursor(null);
    setNote("");
    setMessage(c.saved);
    setRefresh((value) => value + 1);
  }
  function choose(id: string, revision?: number) {
    if (id === "reference") {
      const url = new URL(window.location.href);
      url.searchParams.delete("dossier");
      window.history.replaceState(null, "", url);
      setSaved(null);
      setHistory(null);
      setNote("");
      setError("");
      setMessage("");
      return;
    }
    void perform(async () => {
      const result = await api<SavedDossier>(
        `${ROOT}/${id}${revision ? `?revision=${revision}` : ""}`,
      );
      if (mounted.current) {
        setSaved(result);
        const url = new URL(window.location.href);
        url.searchParams.set("dossier", id);
        window.history.replaceState(null, "", url);
        setNote("");
        if (!revision) setHistory(null);
      }
    });
  }
  function edit(create: boolean, copy = false) {
    setCreating(create);
    setError("");
    setMessage("");
    setEditing(
      create && !copy
        ? {
            id: `dossier-${crypto.randomUUID()}`,
            title: "",
            checkedOn: new Date().toISOString().slice(0, 10),
            summaryLanguage: locale.slice(
              0,
              2,
            ) as InfluenceDossier["summaryLanguage"],
            entities: [],
            sources: [],
            edges: [],
            gaps: [],
          }
        : structuredClone(document),
    );
  }
  function requestId(body: unknown) {
    const serialized = JSON.stringify(body);
    if (retry.current.body !== serialized)
      retry.current = { body: serialized, id: crypto.randomUUID() };
    return retry.current.id;
  }
  async function save(document: InfluenceDossier, note: string, id: string) {
    await perform(async () => {
      const result = await api<SavedDossier>(
        creating ? ROOT : `${ROOT}/${saved!.id}`,
        {
          method: creating ? "POST" : "PATCH",
          body: JSON.stringify({
            document,
            note,
            requestId: id,
            expectedRevision: creating ? 0 : saved!.revision,
          }),
        },
      );
      if (mounted.current) {
        accept(result);
        setEditing(null);
      }
    });
  }
  function record(action: "review" | "archive") {
    if (!saved || note.trim().length < 3) {
      setError(c.required);
      return;
    }
    const payload = {
      expectedRevision: saved.revision,
      note,
      ...(action === "review" ? { decision } : { archived: !saved.archived }),
    };
    const body = {
      ...payload,
      requestId: requestId({ id: saved.id, action, ...payload }),
    };
    void perform(async () => {
      const result = await api<SavedDossier>(
        `${ROOT}/${saved.id}/${action === "review" ? "reviews" : "archive"}`,
        { method: "POST", body: JSON.stringify(body) },
      );
      accept(result);
    });
  }
  function loadHistory(before?: number) {
    if (!saved) return;
    void perform(async () => {
      const result = await api<Page<History, number>>(
        `${ROOT}/${saved.id}/history${before ? `?before_revision=${before}` : ""}`,
      );
      if (mounted.current) {
        setHistory((rows) =>
          before ? [...(rows || []), ...result.items] : result.items,
        );
        setHistoryCursor(result.nextCursor);
      }
    });
  }
  function download() {
    const content = {
      schemaVersion: "helvetic-influence-v1",
      document,
      ...(saved
        ? {
            revision: saved.viewedRevision,
            documentHash: saved.documentHash,
            reviews: saved.reviews,
          }
        : {}),
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(content, null, 2)], {
        type: "application/json",
      }),
    );
    const link = window.document.createElement("a");
    link.href = url;
    link.download = `influence-${saved?.id || "reference"}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <span className={styles.eyebrow}>
            <GitFork size={16} aria-hidden="true" />
            {c.prototype}
          </span>
          <h1>{c.title}</h1>
          <p>{c.intro}</p>
        </div>
        <div className={styles.actions}>
          {authenticated && canManage && !editing && (
            <button
              className={styles.primary}
              disabled={busy}
              onClick={() => edit(true)}
            >
              {c.new}
            </button>
          )}
        </div>
      </header>
      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
      {message && (
        <p role="status" className={styles.success}>
          {message}
        </p>
      )}
      {!canManage && authenticated && (
        <p className={styles.helper}>{c.readonly}</p>
      )}
      {editing ? (
        <InfluenceEditor
          initial={editing}
          busy={busy}
          onSave={save}
          onCancel={() => setEditing(null)}
        />
      ) : (
        <>
          <div className={styles.workspaceBar}>
            <label>
              {c.details}
              <select
                disabled={busy}
                value={saved?.id || "reference"}
                onChange={(event) => choose(event.target.value)}
              >
                <option value="reference">{c.example}</option>
                {saved && !items.some((item) => item.id === saved.id) && (
                  <option value={saved.id}>{saved.title}</option>
                )}
                {items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title} · {c.revision} {item.revision}
                  </option>
                ))}
              </select>
            </label>
            {authenticated && (
              <>
                <label>
                  {c.private}
                  <select
                    value={String(archived)}
                    disabled={busy}
                    onChange={(event) =>
                      setArchived(event.target.value === "true")
                    }
                  >
                    <option value="false">{c.active}</option>
                    <option value="true">{c.archived}</option>
                  </select>
                </label>
                <button
                  disabled={busy}
                  onClick={() => setRefresh((value) => value + 1)}
                >
                  {c.refresh}
                </button>
                {cursor && (
                  <button
                    disabled={busy}
                    onClick={() => {
                      const epoch = listEpoch.current;
                      void perform(async () => {
                        const page = await api<Page<DossierSummary>>(
                          `${ROOT}?archived=${archived}&after_id=${cursor}`,
                        );
                        if (mounted.current && epoch === listEpoch.current) {
                          setItems((rows) => [...rows, ...page.items]);
                          setCursor(page.nextCursor);
                        }
                      });
                    }}
                  >
                    {c.more}
                  </button>
                )}
              </>
            )}
          </div>
          {authenticated && listReady && items.length === 0 && (
            <p className={styles.meta}>{c.noDossiers}</p>
          )}
          {!authenticated && <p className={styles.meta}>{c.unavailable}</p>}
          <div className={styles.dossierActions}>
            <span className={styles.meta}>
              {saved
                ? `${c.private} · ${c.revision} ${saved.viewedRevision} · ${saved.archived ? c.archived : c.active}`
                : c.example}
            </span>
            <div className={styles.actions}>
              {authenticated && canManage && !saved && (
                <button disabled={busy} onClick={() => edit(true, true)}>
                  {c.copy}
                </button>
              )}
              {authenticated &&
                canManage &&
                saved &&
                !saved.archived &&
                !historical && (
                  <button disabled={busy} onClick={() => edit(false)}>
                    {c.edit}
                  </button>
                )}
              {saved && (
                <>
                  <button disabled={busy} onClick={() => loadHistory()}>
                    {c.history}
                  </button>
                  <button disabled={busy} onClick={() => choose(saved.id)}>
                    {c.latest}
                  </button>
                </>
              )}
              <button disabled={busy} onClick={download}>
                {c.export}
              </button>
            </div>
          </div>
          {busy && (
            <p role="status" className={styles.helper}>
              {c.loading}
            </p>
          )}
          {historical && <p className={styles.notice}>{c.historical}</p>}
          {document.lawId && (
            <Link className="text-link" href={`/laws/${document.lawId}`}>
              {dossierReviewCopy[locale].law} ↗
            </Link>
          )}
          <InfluenceReader
            key={`${saved?.id || "reference"}:${saved?.viewedRevision || 0}`}
            dossier={document}
          />
          {!!saved?.document.reviewNotes?.length && (
            <details className={styles.reviewSection}>
              <summary>{dossierReviewCopy[locale].title}</summary>
              <DossierReview
                key={`${saved.id}:${saved.viewedRevision}`}
                brief={{
                  ...saved,
                  revision: saved.viewedRevision,
                  updatedAt: saved.revisionCreatedAt,
                }}
              />
            </details>
          )}
          {saved && (
            <section className={styles.reviewSection}>
              <h2>{c.review}</h2>
              <p>{c.reviewHelp}</p>
              <p className={styles.meta}>
                {c.integrity}: <code>{saved.documentHash}</code>
              </p>
              {!saved.reviews.length ? (
                <p>{c.draft}</p>
              ) : (
                <ol className={styles.reviewList}>
                  {saved.reviews.map((review) => (
                    <li key={review.id}>
                      <strong>{c[review.decision]}</strong>
                      <span className={styles.meta}>
                        {new Date(review.createdAt).toLocaleString(locale)} ·{" "}
                        {c.author}: {review.actorId || c.unknownActor}
                      </span>
                      <p>{review.note}</p>
                    </li>
                  ))}
                </ol>
              )}
              {canManage && !historical && (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    record("review");
                  }}
                >
                  <fieldset className={styles.editorFields} disabled={busy}>
                    <label className={styles.field}>
                      {c.note}
                      <textarea
                        minLength={3}
                        maxLength={2000}
                        required
                        value={note}
                        onChange={(event) => setNote(event.target.value)}
                      />
                      <small>{c.reasonHelp}</small>
                    </label>
                    <div className={styles.actions}>
                      {!saved.archived && (
                        <>
                          <select
                            aria-label={c.review}
                            value={decision}
                            onChange={(event) =>
                              setDecision(
                                event.target.value as Review["decision"],
                              )
                            }
                          >
                            <option value="needs_revision">
                              {c.needs_revision}
                            </option>
                            <option value="reviewed">{c.reviewed}</option>
                          </select>
                          <button type="submit">{c.review}</button>
                        </>
                      )}
                      <button type="button" onClick={() => record("archive")}>
                        {saved.archived ? c.restore : c.archive}
                      </button>
                    </div>
                  </fieldset>
                </form>
              )}
            </section>
          )}
          {history && (
            <section className={styles.reviewSection}>
              <h2>{c.history}</h2>
              <ol className={styles.reviewList}>
                {history.map((item) => (
                  <li key={item.revision}>
                    <button
                      disabled={busy}
                      onClick={() => choose(saved!.id, item.revision)}
                    >
                      {c.revision} {item.revision}
                    </button>
                    <span className={styles.meta}>
                      {new Date(item.createdAt).toLocaleString(locale)} ·{" "}
                      {c.author}: {item.actorId || c.unknownActor}
                    </span>
                    <p>{item.note}</p>
                    <code>{item.documentHash}</code>
                  </li>
                ))}
              </ol>
              {historyCursor && (
                <button
                  disabled={busy}
                  onClick={() => loadHistory(historyCursor)}
                >
                  {c.older}
                </button>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
