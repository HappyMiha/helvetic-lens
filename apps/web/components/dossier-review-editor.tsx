"use client";
import { useResource } from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { useI18n } from "@/lib/i18n";
import { dossierReviewCopy } from "@/lib/dossier-review-copy";
import type {
  DossierReviewNote,
  InfluenceDossier,
} from "@/lib/influence-graph";
import styles from "./influence.module.css";

export function DossierReviewEditor({
  draft,
  onChange,
}: {
  draft: InfluenceDossier;
  onChange: (value: InfluenceDossier) => void;
}) {
  const { locale } = useI18n();
  const c = dossierReviewCopy[locale];
  const laws = useResource(resources.laws());
  const notes = draft.reviewNotes || [];
  function patch(id: string, value: Partial<DossierReviewNote>) {
    onChange({
      ...draft,
      reviewNotes: notes.map((item) =>
        item.id === id ? { ...item, ...value } : item,
      ),
    });
  }
  return (
    <div className="space-y-5">
      <label className={styles.field}>
        <span>{c.law}</span>
        <select
          value={draft.lawId || ""}
          onChange={(event) =>
            onChange({ ...draft, lawId: event.target.value || null })
          }
        >
          <option value="">{c.none}</option>
          {draft.lawId && !laws.data?.some((law) => law.id === draft.lawId) && (
            <option value={draft.lawId}>{draft.lawId}</option>
          )}
          {laws.data?.map((law) => (
            <option value={law.id} key={law.id}>
              {law.name}
            </option>
          ))}
        </select>
      </label>
      <h3>{c.title}</h3>
      <p>{c.note}</p>
      {notes.map((item) => (
        <fieldset key={item.id} className="border rounded-lg p-4 space-y-3">
          <legend>{item.title || c.body}</legend>
          <label className={styles.field}>
            <span>{c.kind}</span>
            <select
              value={item.kind}
              onChange={(event) =>
                patch(item.id, {
                  kind: event.target.value as DossierReviewNote["kind"],
                  status: event.target.value === "task" ? "open" : "recorded",
                  dueOn: null,
                })
              }
            >
              {(["finding", "discussion", "task"] as const).map((kind) => (
                <option key={kind} value={kind}>
                  {c[kind]}
                </option>
              ))}
            </select>
          </label>
          {(["title", "author", "role"] as const).map((field) => (
            <label className={styles.field} key={field}>
              <span>{field === "title" ? c.name : c[field]}</span>
              <input
                required
                maxLength={240}
                value={item[field]}
                onChange={(event) =>
                  patch(item.id, { [field]: event.target.value })
                }
              />
            </label>
          ))}
          <label className="flex gap-2">
            <input
              type="checkbox"
              checked={item.fictional}
              onChange={(event) =>
                patch(item.id, { fictional: event.target.checked })
              }
            />
            {c.fictional}
          </label>
          <label className={styles.field}>
            <span>{c.body}</span>
            <textarea
              required
              rows={6}
              maxLength={6000}
              value={item.body}
              onChange={(event) => patch(item.id, { body: event.target.value })}
            />
          </label>
          <fieldset className="space-y-2">
            <legend>{c.sources}</legend>
            {draft.sources.map((source) => (
              <label key={source.id} className="flex gap-2">
                <input
                  type="checkbox"
                  checked={item.sourceIds.includes(source.id)}
                  disabled={
                    !item.sourceIds.includes(source.id) &&
                    item.sourceIds.length >= 12
                  }
                  onChange={(event) =>
                    patch(item.id, {
                      sourceIds: event.target.checked
                        ? [...item.sourceIds, source.id]
                        : item.sourceIds.filter((id) => id !== source.id),
                    })
                  }
                />
                {source.title}
              </label>
            ))}
          </fieldset>
          {item.kind === "task" && (
            <>
              <label className={styles.field}>
                <span>{c.status}</span>
                <select
                  value={item.status}
                  onChange={(event) =>
                    patch(item.id, {
                      status: event.target.value as DossierReviewNote["status"],
                    })
                  }
                >
                  {(
                    ["open", "in_progress", "complete", "recorded"] as const
                  ).map((status) => (
                    <option key={status} value={status}>
                      {c[status]}
                    </option>
                  ))}
                </select>
              </label>
              <label className={styles.field}>
                <span>{c.due}</span>
                <input
                  type="date"
                  value={item.dueOn || ""}
                  onChange={(event) =>
                    patch(item.id, { dueOn: event.target.value || null })
                  }
                />
              </label>
            </>
          )}
          <button
            type="button"
            className={styles.danger}
            onClick={() =>
              onChange({
                ...draft,
                reviewNotes: notes.filter((note) => note.id !== item.id),
              })
            }
          >
            {c.remove}
          </button>
        </fieldset>
      ))}
      <button
        type="button"
        className={styles.secondary}
        disabled={notes.length >= 50}
        onClick={() =>
          onChange({
            ...draft,
            reviewNotes: [
              ...notes,
              {
                id: `note-${crypto.randomUUID()}`,
                kind: "finding",
                title: "",
                author: "",
                role: "",
                fictional: false,
                body: "",
                sourceIds: [],
                status: "recorded",
                dueOn: null,
              },
            ],
          })
        }
      >
        {c.add}
      </button>
    </div>
  );
}
