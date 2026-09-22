"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { influenceCopy } from "@/lib/influence-copy";
import { useI18n } from "@/lib/i18n";
import {
  evidenceStatuses,
  nextInfluenceEntityPosition,
  type InfluenceDossier,
  type InfluenceEdge,
  type InfluenceEvidence,
  type InfluenceSource,
} from "@/lib/influence-graph";
import styles from "./influence.module.css";

type Area = "details" | "entities" | "sources" | "relations";
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className={styles.field}>
      <span>{label}</span>
      {children}
    </label>
  );
}
const identifier = (prefix: string) => `${prefix}-${crypto.randomUUID()}`;

export function InfluenceEditor({
  initial,
  busy,
  onSave,
  onCancel,
}: {
  initial: InfluenceDossier;
  busy: boolean;
  onSave: (
    document: InfluenceDossier,
    note: string,
    requestId: string,
  ) => Promise<void>;
  onCancel: () => void;
}) {
  const { locale } = useI18n();
  const c = influenceCopy[locale];
  const [draft, setDraft] = useState(() => structuredClone(initial));
  const [area, setArea] = useState<Area>("details");
  const [current, setCurrent] = useState(0);
  const [note, setNote] = useState("");
  const retry = useRef({ body: "", id: "" });
  const dirty =
    JSON.stringify(draft) !== JSON.stringify(initial) || Boolean(note);
  useEffect(() => {
    if (!dirty) return;
    const unload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    const navigate = (event: Event) => {
      if (busy || !window.confirm(c.discard)) event.preventDefault();
    };
    const link = (event: MouseEvent) => {
      const anchor = (event.target as Element)?.closest?.(
        "a[href]",
      ) as HTMLAnchorElement | null;
      if (
        !anchor ||
        anchor.target === "_blank" ||
        anchor.hasAttribute("download") ||
        anchor.getAttribute("href")?.startsWith("#")
      )
        return;
      if (busy || !window.confirm(c.discard)) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", unload);
    window.addEventListener("helvetic:before-navigation", navigate);
    document.addEventListener("click", link, true);
    return () => {
      window.removeEventListener("beforeunload", unload);
      window.removeEventListener("helvetic:before-navigation", navigate);
      document.removeEventListener("click", link, true);
    };
  }, [dirty, busy, c.discard]);
  const entity = draft.entities[current];
  const source = draft.sources[current];
  const edge = draft.edges[current];
  const rows =
    area === "entities"
      ? draft.entities
      : area === "sources"
        ? draft.sources
        : area === "relations"
          ? draft.edges
          : [];
  function patchEdge(patch: Partial<InfluenceEdge>) {
    setDraft({
      ...draft,
      edges: draft.edges.map((item, index) =>
        index === current ? { ...item, ...patch } : item,
      ),
    });
  }
  function patchSource(patch: Partial<InfluenceSource>) {
    setDraft({
      ...draft,
      sources: draft.sources.map((item, index) =>
        index === current ? { ...item, ...patch } : item,
      ),
    });
  }
  function updateEvidence(
    side: "supporting" | "disputing",
    index: number,
    patch: Partial<InfluenceEvidence>,
  ) {
    patchEdge({
      [side]: edge[side].map((item, position) =>
        position === index ? { ...item, ...patch } : item,
      ),
    });
  }
  function add() {
    if (area === "entities") {
      const index = draft.entities.length;
      setCurrent(index);
      setDraft({
        ...draft,
        entities: [
          ...draft.entities,
          {
            id: identifier("entity"),
            name: "",
            kind: "person",
            country: null,
            ...nextInfluenceEntityPosition(draft.entities, c.graphFull),
          },
        ],
      });
    } else if (area === "sources") {
      setCurrent(draft.sources.length);
      setDraft({
        ...draft,
        sources: [
          ...draft.sources,
          {
            id: identifier("source"),
            title: "",
            publisher: "",
            url: "",
            kind: "reporting",
            language: draft.summaryLanguage,
            publishedOn: null,
            checkedOn: draft.checkedOn,
            snapshotText: null,
          },
        ],
      });
    } else if (area === "relations") {
      setCurrent(draft.edges.length);
      setDraft({
        ...draft,
        edges: [
          ...draft.edges,
          {
            id: identifier("edge"),
            from: draft.entities[0]?.id || "",
            to: draft.entities[1]?.id || "",
            kind: "business",
            status: "not_established",
            label: "",
            statement: "",
            asOf: null,
            supporting: [],
            disputing: [],
            limits: [],
          },
        ],
      });
    }
  }
  function remove() {
    const key =
      area === "relations"
        ? "edges"
        : area === "sources"
          ? "sources"
          : "entities";
    setDraft({
      ...draft,
      [key]: draft[key].filter((_, index) => index !== current),
    });
    setCurrent(0);
  }
  const canRemove =
    area === "relations" ||
    (area === "entities" &&
      entity &&
      !draft.edges.some(
        (item) => item.from === entity.id || item.to === entity.id,
      )) ||
    (area === "sources" &&
      source &&
      !draft.edges.some(
        (item) =>
          [...item.supporting, ...item.disputing].some(
            (ref) => ref.sourceId === source.id,
          ) || item.money?.evidenceSourceId === source.id,
      ));
  const maxRows = area === "relations" ? 250 : 100;
  return (
    <form
      className={styles.editor}
      onSubmit={(event) => {
        event.preventDefault();
        const document = {
          ...draft,
          gaps: draft.gaps.map((item) => item.trim()).filter(Boolean),
          edges: draft.edges.map((item) => ({
            ...item,
            limits: item.limits.map((line) => line.trim()).filter(Boolean),
          })),
        };
        const body = JSON.stringify({ document, note });
        if (retry.current.body !== body)
          retry.current = { body, id: crypto.randomUUID() };
        void onSave(document, note, retry.current.id);
      }}
    >
      <div className={styles.editorHeader}>
        <h2>{c.edit}</h2>
        <p>{c.workspaceHelp}</p>
      </div>
      <fieldset disabled={busy} className={styles.editorFields}>
        <div className={styles.toolbar}>
          <Field label={c.details}>
            <select
              value={area}
              onChange={(event) => {
                setArea(event.target.value as Area);
                setCurrent(0);
              }}
            >
              {(["details", "entities", "sources", "relations"] as const).map(
                (key) => (
                  <option key={key} value={key}>
                    {c[key]}
                  </option>
                ),
              )}
            </select>
          </Field>
          {area !== "details" && (
            <>
              <Field label={c.selected}>
                <select
                  value={current}
                  onChange={(event) => setCurrent(Number(event.target.value))}
                >
                  {rows.map((item, index) => (
                    <option key={item.id} value={index}>
                      {index + 1}.{" "}
                      {"name" in item
                        ? item.name
                        : "title" in item
                          ? item.title
                          : item.label}
                    </option>
                  ))}
                </select>
              </Field>
              <button
                type="button"
                disabled={rows.length >= maxRows}
                onClick={add}
              >
                {c.add}
              </button>
              <button type="button" disabled={!canRemove} onClick={remove}>
                {c.remove}
              </button>
            </>
          )}
        </div>
        <div className={styles.formGrid}>
          {area === "details" && (
            <>
              <Field label={c.name}>
                <input
                  required
                  maxLength={240}
                  value={draft.title}
                  onChange={(event) =>
                    setDraft({ ...draft, title: event.target.value })
                  }
                />
              </Field>
              <Field label={c.date}>
                <input
                  required
                  type="date"
                  value={draft.checkedOn}
                  onChange={(event) =>
                    setDraft({ ...draft, checkedOn: event.target.value })
                  }
                />
              </Field>
              <Field label={c.language}>
                <select
                  value={draft.summaryLanguage}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      summaryLanguage: event.target
                        .value as InfluenceDossier["summaryLanguage"],
                    })
                  }
                >
                  {["en", "de", "fr", "it", "rm", "uk"].map((language) => (
                    <option key={language}>{language}</option>
                  ))}
                </select>
              </Field>
              <Field label={c.missing}>
                <textarea
                  rows={5}
                  value={draft.gaps.join("\n")}
                  onChange={(event) =>
                    setDraft({ ...draft, gaps: event.target.value.split("\n") })
                  }
                />
              </Field>
            </>
          )}
          {area === "entities" && entity && (
            <>
              <Field label={c.name}>
                <input
                  required
                  maxLength={240}
                  value={entity.name}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      entities: draft.entities.map((item, index) =>
                        index === current
                          ? { ...item, name: event.target.value }
                          : item,
                      ),
                    })
                  }
                />
              </Field>
              <Field label={c.kind}>
                <select
                  value={entity.kind}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      entities: draft.entities.map((item, index) =>
                        index === current
                          ? {
                              ...item,
                              kind: event.target.value as typeof entity.kind,
                            }
                          : item,
                      ),
                    })
                  }
                >
                  {Object.entries(c.entityKinds).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={c.country}>
                <input
                  maxLength={2}
                  pattern="[A-Z]{2}"
                  value={entity.country || ""}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      entities: draft.entities.map((item, index) =>
                        index === current
                          ? {
                              ...item,
                              country: event.target.value.toUpperCase() || null,
                            }
                          : item,
                      ),
                    })
                  }
                />
              </Field>
            </>
          )}
          {area === "sources" && source && (
            <>
              <Field label={c.name}>
                <input
                  required
                  maxLength={240}
                  value={source.title}
                  onChange={(event) =>
                    patchSource({ title: event.target.value })
                  }
                />
              </Field>
              <Field label={c.publisher}>
                <input
                  required
                  maxLength={240}
                  value={source.publisher}
                  onChange={(event) =>
                    patchSource({ publisher: event.target.value })
                  }
                />
              </Field>
              <Field label={c.url}>
                <input
                  required
                  type="url"
                  maxLength={3000}
                  value={source.url}
                  onChange={(event) => patchSource({ url: event.target.value })}
                />
              </Field>
              <Field label={c.kind}>
                <select
                  value={source.kind}
                  onChange={(event) =>
                    patchSource({
                      kind: event.target.value as typeof source.kind,
                    })
                  }
                >
                  {Object.entries(c.sourceKinds).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={c.sourceDate}>
                <input
                  type="date"
                  value={source.publishedOn || ""}
                  onChange={(event) =>
                    patchSource({ publishedOn: event.target.value || null })
                  }
                />
              </Field>
              <Field label={c.checked}>
                <input
                  required
                  type="date"
                  value={source.checkedOn}
                  onChange={(event) =>
                    patchSource({ checkedOn: event.target.value })
                  }
                />
              </Field>
              <Field label={c.language}>
                <select
                  value={source.language}
                  onChange={(event) =>
                    patchSource({
                      language: event.target.value as typeof source.language,
                    })
                  }
                >
                  {["en", "de", "fr", "it", "rm", "uk"].map((language) => (
                    <option key={language}>{language}</option>
                  ))}
                </select>
              </Field>
              <Field label={c.extract}>
                <textarea
                  maxLength={16000}
                  rows={6}
                  value={source.snapshotText || ""}
                  onChange={(event) =>
                    patchSource({ snapshotText: event.target.value || null })
                  }
                />
                <small>{c.extractHelp}</small>
              </Field>
            </>
          )}
          {area === "relations" && edge && (
            <>
              <Field label={c.from}>
                <select
                  required
                  value={edge.from}
                  onChange={(event) => patchEdge({ from: event.target.value })}
                >
                  <option value="">—</option>
                  {draft.entities.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={c.to}>
                <select
                  required
                  value={edge.to}
                  onChange={(event) => patchEdge({ to: event.target.value })}
                >
                  <option value="">—</option>
                  {draft.entities.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={c.label}>
                <input
                  required
                  maxLength={240}
                  value={edge.label}
                  onChange={(event) => patchEdge({ label: event.target.value })}
                />
              </Field>
              <Field label={c.kind}>
                <select
                  value={edge.kind}
                  onChange={(event) =>
                    patchEdge({
                      kind: event.target.value as typeof edge.kind,
                      money:
                        event.target.value === "dividend" ? edge.money : null,
                    })
                  }
                >
                  {Object.entries(c.relationKinds).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={c.status}>
                <select
                  value={edge.status}
                  onChange={(event) =>
                    patchEdge({
                      status: event.target.value as typeof edge.status,
                    })
                  }
                >
                  {evidenceStatuses.map((status) => (
                    <option key={status} value={status}>
                      {c.statuses[status]}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={c.effective}>
                <input
                  type="date"
                  value={edge.asOf || ""}
                  onChange={(event) =>
                    patchEdge({ asOf: event.target.value || null })
                  }
                />
              </Field>
              <Field label={c.statement}>
                <textarea
                  required
                  rows={3}
                  maxLength={2000}
                  value={edge.statement}
                  onChange={(event) =>
                    patchEdge({ statement: event.target.value })
                  }
                />
              </Field>
              <Field label={c.limitLines}>
                <textarea
                  required
                  rows={3}
                  value={edge.limits.join("\n")}
                  onChange={(event) =>
                    patchEdge({ limits: event.target.value.split("\n") })
                  }
                />
              </Field>
              {(["supporting", "disputing"] as const).map((side) => (
                <section className={styles.formSection} key={side}>
                  <h3>{c[side]}</h3>
                  {edge[side].map((ref, index) => (
                    <div className={styles.evidenceForm} key={index}>
                      <Field label={c.source}>
                        <select
                          required
                          value={ref.sourceId}
                          onChange={(event) =>
                            updateEvidence(side, index, {
                              sourceId: event.target.value,
                            })
                          }
                        >
                          <option value="">—</option>
                          {draft.sources.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.title}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label={c.locator}>
                        <input
                          required
                          maxLength={240}
                          value={ref.locator}
                          onChange={(event) =>
                            updateEvidence(side, index, {
                              locator: event.target.value,
                            })
                          }
                        />
                      </Field>
                      <Field label={c.summary}>
                        <textarea
                          required
                          maxLength={2000}
                          value={ref.summary}
                          onChange={(event) =>
                            updateEvidence(side, index, {
                              summary: event.target.value,
                            })
                          }
                        />
                      </Field>
                      <Field label={c.quote}>
                        <textarea
                          maxLength={1000}
                          value={ref.quote || ""}
                          onChange={(event) =>
                            updateEvidence(side, index, {
                              quote: event.target.value || null,
                            })
                          }
                        />
                      </Field>
                      <button
                        type="button"
                        onClick={() =>
                          patchEdge({
                            [side]: edge[side].filter(
                              (_, position) => position !== index,
                            ),
                          })
                        }
                      >
                        {c.remove}
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    disabled={!draft.sources.length || edge[side].length >= 12}
                    onClick={() =>
                      patchEdge({
                        [side]: [
                          ...edge[side],
                          {
                            sourceId: draft.sources[0].id,
                            locator: "",
                            summary: "",
                          },
                        ],
                      })
                    }
                  >
                    {side === "supporting" ? c.addEvidence : c.addCounter}
                  </button>
                </section>
              ))}
              {edge.kind === "dividend" && (
                <section className={styles.formSection}>
                  <h3>{c.money}</h3>
                  {!edge.money ? (
                    <button
                      type="button"
                      onClick={() =>
                        patchEdge({
                          money: {
                            amount: 0,
                            currency: "CHF",
                            periodStart: draft.checkedOn,
                            periodEnd: draft.checkedOn,
                            basis: "paid",
                            evidenceSourceId:
                              edge.supporting[0]?.sourceId || "",
                          },
                        })
                      }
                    >
                      {c.add}
                    </button>
                  ) : (
                    <div className={styles.formGrid}>
                      <Field label={c.amount}>
                        <input
                          type="number"
                          required
                          min="0.01"
                          step="any"
                          value={edge.money.amount}
                          onChange={(event) =>
                            patchEdge({
                              money: {
                                ...edge.money!,
                                amount: Number(event.target.value),
                              },
                            })
                          }
                        />
                      </Field>
                      <Field label={c.currency}>
                        <input
                          required
                          pattern="[A-Z]{3}"
                          maxLength={3}
                          value={edge.money.currency}
                          onChange={(event) =>
                            patchEdge({
                              money: {
                                ...edge.money!,
                                currency: event.target.value.toUpperCase(),
                              },
                            })
                          }
                        />
                      </Field>
                      <Field label={c.periodStart}>
                        <input
                          required
                          type="date"
                          value={edge.money.periodStart}
                          onChange={(event) =>
                            patchEdge({
                              money: {
                                ...edge.money!,
                                periodStart: event.target.value,
                              },
                            })
                          }
                        />
                      </Field>
                      <Field label={c.periodEnd}>
                        <input
                          required
                          type="date"
                          value={edge.money.periodEnd}
                          onChange={(event) =>
                            patchEdge({
                              money: {
                                ...edge.money!,
                                periodEnd: event.target.value,
                              },
                            })
                          }
                        />
                      </Field>
                      <Field label={c.basis}>
                        <select
                          value={edge.money.basis}
                          onChange={(event) =>
                            patchEdge({
                              money: {
                                ...edge.money!,
                                basis: event.target.value as
                                  "paid" | "proposed",
                              },
                            })
                          }
                        >
                          <option value="paid">{c.paid}</option>
                          <option value="proposed">{c.proposed}</option>
                        </select>
                      </Field>
                      <Field label={c.source}>
                        <select
                          required
                          value={edge.money.evidenceSourceId}
                          onChange={(event) =>
                            patchEdge({
                              money: {
                                ...edge.money!,
                                evidenceSourceId: event.target.value,
                              },
                            })
                          }
                        >
                          <option value="">—</option>
                          {draft.sources.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.title}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <button
                        type="button"
                        onClick={() => patchEdge({ money: null })}
                      >
                        {c.remove}
                      </button>
                    </div>
                  )}
                </section>
              )}
            </>
          )}
        </div>
        <div className={styles.saveBar}>
          <Field label={c.note}>
            <textarea
              required
              minLength={3}
              maxLength={2000}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <small>{c.reasonHelp}</small>
          </Field>
          <div className={styles.actions}>
            <button type="submit" className={styles.primary}>
              {busy ? c.loading : c.save}
            </button>
            <button
              type="button"
              onClick={() => {
                if (!dirty || window.confirm(c.discard)) onCancel();
              }}
            >
              {c.cancel}
            </button>
          </div>
        </div>
      </fieldset>
    </form>
  );
}
