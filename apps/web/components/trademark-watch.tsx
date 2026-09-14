"use client";

import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { businessMonitorCopy } from "@/lib/business-monitor-copy";
import { trademarkCopy } from "@/lib/trademark-copy";
import {
  newBrand,
  trademarkLanguages,
  type Brand,
  type TrademarkPortfolio,
  type TrademarkMonitor,
  type TrademarkPage,
} from "@/lib/trademark-watch";
import { useAuth } from "./auth-gate";
import { BusinessMonitorAccess } from "./business-monitor-access";
import { Shell } from "./shell";
import styles from "./commute-watch.module.css";
import ipStyles from "./trademark-watch.module.css";

import { TrademarkTracking } from "./trademark-tracking";
import { TrademarkEmail } from "./trademark-email";
import { IPISourceStatus } from "./ipi-source-status";
import { TrademarkDeadlineChoice } from "./trademark-deadline";
import { Failure, useData, useMutation } from "./trademark-client";

function BrandForm({
  brand,
  change,
  remove,
}: {
  brand: Brand;
  change: (brand: Brand) => void;
  remove: () => void;
}) {
  const { locale } = useI18n(),
    c = trademarkCopy[locale];
  const [classes, setClasses] = useState(brand.relevant_classes.join(", "));
  const [variants, setVariants] = useState(brand.word_variants.join("\n")),
    [owners, setOwners] = useState(brand.owners_of_interest.join("\n"));
  function multiline(value: string) {
    return value
      .split("\n")
      .map((v) => v.trim())
      .filter(Boolean);
  }
  return (
    <fieldset data-trademark-brand>
      <legend>{brand.name || c.brand}</legend>
      <label>
        {c.brand}
        <input
          required
          maxLength={256}
          value={brand.name}
          onChange={(e) => change({ ...brand, name: e.target.value })}
        />
      </label>
      <label>
        {c.language}
        <select
          value={brand.language}
          onChange={(e) =>
            change({ ...brand, language: e.target.value as Brand["language"] })
          }
        >
          {trademarkLanguages.map((v) => (
            <option key={v} value={v}>
              {v.toUpperCase()}
            </option>
          ))}
        </select>
      </label>
      <label className={styles.check}>
        <input
          type="checkbox"
          checked={brand.exact_name}
          onChange={(e) => change({ ...brand, exact_name: e.target.checked })}
        />
        {c.exact}
      </label>
      <label className={styles.check}>
        <input
          type="checkbox"
          checked={brand.similar_names}
          onChange={(e) =>
            change({ ...brand, similar_names: e.target.checked })
          }
        />
        {c.similar}
      </label>
      <label>
        {c.variants}
        <textarea
          rows={3}
          maxLength={2056}
          value={variants}
          onChange={(e) => {
            setVariants(e.target.value);
            change({ ...brand, word_variants: multiline(e.target.value) });
          }}
        />
      </label>
      <label>
        {c.owners}
        <textarea
          rows={3}
          maxLength={2056}
          value={owners}
          onChange={(e) => {
            setOwners(e.target.value);
            change({ ...brand, owners_of_interest: multiline(e.target.value) });
          }}
        />
      </label>
      <label>
        {c.classes}
        <input
          value={classes}
          maxLength={180}
          onChange={(e) => {
            const value = e.target.value;
            setClasses(value);
            const parsed = value.trim()
              ? value
                  .split(",")
                  .map((v) =>
                    /^\s*\d{1,2}\s*$/.test(v) ? Number(v.trim()) : -1,
                  )
              : [];
            change({ ...brand, relevant_classes: parsed });
          }}
        />
      </label>
      <details>
        <summary>{c.goods}</summary>
        <p>{c.goodsHelp}</p>
        {brand.goods_services.map((interest, index) => (
          <fieldset key={index} data-trademark-goods>
            <legend>
              {c.interest} {index + 1}
            </legend>
            <label>
              {c.interest}
              <input
                required
                maxLength={100}
                value={interest.name}
                onChange={(e) =>
                  change({
                    ...brand,
                    goods_services: brand.goods_services.map((v, i) =>
                      i === index ? { ...v, name: e.target.value } : v,
                    ),
                  })
                }
              />
            </label>
            {interest.phrases.map((phrase, phraseIndex) => (
              <div className={styles.card} key={phraseIndex}>
                <label>
                  {c.phraseLanguage}
                  <select
                    value={phrase.language}
                    onChange={(e) =>
                      change({
                        ...brand,
                        goods_services: brand.goods_services.map((v, i) =>
                          i === index
                            ? {
                                ...v,
                                phrases: v.phrases.map((p, j) =>
                                  j === phraseIndex
                                    ? {
                                        ...p,
                                        language: e.target
                                          .value as Brand["language"],
                                      }
                                    : p,
                                ),
                              }
                            : v,
                        ),
                      })
                    }
                  >
                    {trademarkLanguages.map((v) => (
                      <option key={v} value={v}>
                        {v.toUpperCase()}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  {c.phrase}
                  <input
                    required
                    maxLength={200}
                    value={phrase.text}
                    onChange={(e) =>
                      change({
                        ...brand,
                        goods_services: brand.goods_services.map((v, i) =>
                          i === index
                            ? {
                                ...v,
                                phrases: v.phrases.map((p, j) =>
                                  j === phraseIndex
                                    ? { ...p, text: e.target.value }
                                    : p,
                                ),
                              }
                            : v,
                        ),
                      })
                    }
                  />
                </label>
                <button
                  type="button"
                  disabled={interest.phrases.length === 1}
                  onClick={() =>
                    change({
                      ...brand,
                      goods_services: brand.goods_services.map((v, i) =>
                        i === index
                          ? {
                              ...v,
                              phrases: v.phrases.filter(
                                (_, j) => j !== phraseIndex,
                              ),
                            }
                          : v,
                      ),
                    })
                  }
                >
                  {c.removePhrase}
                </button>
              </div>
            ))}
            <button
              type="button"
              disabled={interest.phrases.length >= 8}
              onClick={() =>
                change({
                  ...brand,
                  goods_services: brand.goods_services.map((v, i) =>
                    i === index
                      ? {
                          ...v,
                          phrases: [
                            ...v.phrases,
                            { language: brand.language, text: "" },
                          ],
                        }
                      : v,
                  ),
                })
              }
            >
              {c.addPhrase}
            </button>
            <button
              type="button"
              onClick={() =>
                change({
                  ...brand,
                  goods_services: brand.goods_services.filter(
                    (_, i) => i !== index,
                  ),
                })
              }
            >
              {c.removeGoods}
            </button>
          </fieldset>
        ))}
        <button
          type="button"
          disabled={brand.goods_services.length >= 12}
          onClick={() =>
            change({
              ...brand,
              goods_services: [
                ...brand.goods_services,
                { name: "", phrases: [{ language: brand.language, text: "" }] },
              ],
            })
          }
        >
          {c.addGoods}
        </button>
      </details>
      <button type="button" onClick={remove}>
        {c.removeBrand}
      </button>
    </fieldset>
  );
}

function PortfolioForm({
  row,
  saved,
  cancel,
}: {
  row?: TrademarkMonitor;
  saved: (row: TrademarkMonitor) => void;
  cancel: () => void;
}) {
  const { locale } = useI18n(),
    c = trademarkCopy[locale],
    mutation = useMutation();
  const [config, setConfig] = useState<TrademarkPortfolio>(() =>
    row
      ? structuredClone(row.configuration)
      : {
          template_id: "trademark-watch",
          template_version: 1,
          jurisdiction: "CH",
          name: "",
          brands: [newBrand()],
        },
  );
  const [invalid, setInvalid] = useState(false);
  const request = useRef<{ body: string; key: string } | null>(null);
  function submit() {
    if (
      !config.name.trim() ||
      !config.brands.length ||
      config.brands.some(
        (b) =>
          !b.name.trim() ||
          b.word_variants.length > 8 ||
          b.owners_of_interest.length > 8 ||
          b.relevant_classes.some(
            (n) => !Number.isInteger(n) || n < 1 || n > 45,
          ),
      )
    ) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    const body = JSON.stringify(config);
    if (!request.current || request.current.body !== body)
      request.current = { body, key: crypto.randomUUID() };
    void mutation.run<TrademarkMonitor>(
      row ? `/monitors/${row.id}` : "/monitors",
      row
        ? { configuration: config, expected_version: row.version }
        : { configuration: config, request_key: request.current.key },
      saved,
      row ? "PATCH" : "POST",
    );
  }
  return (
    <form
      data-trademark-form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <fieldset disabled={mutation.busy}>
        <legend>{row ? c.edit : c.create}</legend>
        <label>
          {c.portfolio}
          <input
            required
            maxLength={100}
            value={config.name}
            onChange={(e) => setConfig({ ...config, name: e.target.value })}
          />
        </label>
        <TrademarkDeadlineChoice
          value={config.deadline_context}
          change={(value) => setConfig({ ...config, deadline_context: value })}
        />
        <h3>{c.brands}</h3>
        {config.brands.map((brand) => (
          <BrandForm
            key={brand.key}
            brand={brand}
            change={(value) =>
              setConfig({
                ...config,
                brands: config.brands.map((b) =>
                  b.key === brand.key ? value : b,
                ),
              })
            }
            remove={() =>
              setConfig({
                ...config,
                brands: config.brands.filter((b) => b.key !== brand.key),
              })
            }
          />
        ))}
        <button
          type="button"
          disabled={config.brands.length >= 20}
          onClick={() =>
            setConfig({ ...config, brands: [...config.brands, newBrand()] })
          }
        >
          {c.addBrand}
        </button>
        <p>{c.source}</p>
        <p>{c.assessment}</p>
        <p>{c.calibration}</p>
        {(invalid || mutation.error) && (
          <p role="alert">{mutation.error || c.invalid}</p>
        )}
        <div className={styles.actions}>
          <button type="submit">{c.save}</button>
          <button type="button" onClick={cancel}>
            {c.cancel}
          </button>
        </div>
      </fieldset>
    </form>
  );
}

function Facts({ config }: { config: TrademarkPortfolio }) {
  const { locale } = useI18n(),
    c = trademarkCopy[locale];
  return (
    <div data-trademark-facts>
      {config.brands.map((brand) => (
        <details key={brand.key} open>
          <summary>{brand.name}</summary>
          <p>
            {c.language}: {brand.language.toUpperCase()} ·{" "}
            {brand.exact_name ? c.exact : ""} ·{" "}
            {brand.similar_names ? c.similar : ""}
          </p>
          {!!brand.word_variants.length && (
            <p>
              {c.variants}: {brand.word_variants.join(", ")}
            </p>
          )}
          {!!brand.owners_of_interest.length && (
            <p>
              {c.owners}: {brand.owners_of_interest.join(", ")}
            </p>
          )}
          {!!brand.relevant_classes.length && (
            <p>
              {c.classes}: {brand.relevant_classes.join(", ")}
            </p>
          )}
          <ul>
            {brand.goods_services.map((g, i) => (
              <li key={i}>
                {g.name}:{" "}
                {g.phrases
                  .map((p) => `${p.language.toUpperCase()} · ${p.text}`)
                  .join("; ")}
              </li>
            ))}
          </ul>
        </details>
      ))}
    </div>
  );
}
function History({ id }: { id: string }) {
  const { locale } = useI18n(),
    c = trademarkCopy[locale];
  const [anchors, setAnchors] = useState<(number | null)[]>([null]);
  const before = anchors.at(-1),
    result = useData<
      TrademarkPage<{ revision: number; configuration: TrademarkPortfolio }>
    >(`/monitors/${id}/revisions?limit=5${before ? `&before=${before}` : ""}`);
  return (
    <section data-trademark-history>
      <h3>{c.history}</h3>
      {result.error ? (
        <p role="alert">{c.failed}</p>
      ) : !result.data ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          {result.data.items.map((row) => (
            <details key={row.revision}>
              <summary>
                {c.version} {row.revision} · {row.configuration.name}
              </summary>
              <Facts config={row.configuration} />
            </details>
          ))}
          <div className={styles.actions}>
            <button
              disabled={anchors.length === 1}
              onClick={() => setAnchors((v) => v.slice(0, -1))}
            >
              {c.back}
            </button>
            <button
              disabled={!result.data.next_cursor}
              onClick={() =>
                setAnchors((v) => [...v, Number(result.data!.next_cursor)])
              }
            >
              {c.next}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
function Detail({
  id,
  canManage,
  changed,
  deleted,
}: {
  id: string;
  canManage: boolean;
  changed: () => void;
  deleted: () => void;
}) {
  const { session } = useAuth();
  const { locale } = useI18n(),
    c = trademarkCopy[locale];
  const [revision, setRevision] = useState(0),
    [editing, setEditing] = useState(false),
    [history, setHistory] = useState(false),
    [confirm, setConfirm] = useState(false);
  const onAccessFailure = useContext(Failure);
  const result = useData<TrademarkMonitor>(`/monitors/${id}`, revision),
    mutation = useMutation(),
    row = result.data;
  function reload() {
    setRevision((v) => v + 1);
    setEditing(false);
    setConfirm(false);
    changed();
  }
  if (result.error) return <p role="alert">{c.failed}</p>;
  if (!row) return <p role="status">{c.loading}</p>;
  if (editing && canManage)
    return (
      <PortfolioForm
        key={row.version}
        row={row}
        saved={reload}
        cancel={() => setEditing(false)}
      />
    );
  return (
    <section data-trademark-detail>
      <h2>{row.configuration.name}</h2>
      <p>
        {c[row.status]} · {c.version} {row.revision}
      </p>
      <Facts config={row.configuration} />
      <div className={styles.actions}>
        <button onClick={reload}>{c.refresh}</button>
        <button onClick={() => setHistory((v) => !v)}>{c.history}</button>
        {canManage && (row.status === "draft" || row.status === "paused") && (
          <>
            <button onClick={() => setEditing(true)}>{c.edit}</button>
            <button
              disabled={mutation.busy}
              onClick={() =>
                void mutation.run(
                  `/monitors/${id}/archive`,
                  { expected_version: row.version },
                  reload,
                )
              }
            >
              {c.archive}
            </button>
          </>
        )}
        {canManage && row.status === "archived" && (
          <button onClick={() => setConfirm(true)}>{c.remove}</button>
        )}
      </div>
      {confirm && (
        <div className={styles.card}>
          <p>{c.confirm}</p>
          <button
            disabled={mutation.busy}
            onClick={() =>
              void mutation.run(
                `/monitors/${id}`,
                { expected_version: row.version },
                deleted,
                "DELETE",
              )
            }
          >
            {c.remove}
          </button>
          <button onClick={() => setConfirm(false)}>{c.cancel}</button>
        </div>
      )}
      {mutation.error && <p role="alert">{mutation.error}</p>}
      {history && <History key={row.version} id={id} />}
      <TrademarkTracking
        key={row.version}
        row={row}
        canManage={canManage}
        changed={reload}
      />
      <BusinessMonitorAccess
        key={`access:${row.version}`}
        domain="ip"
        monitor={row}
        changed={reload}
      />
      {row.owner_user_id === session?.user?.id && (
        <TrademarkEmail
          key={`email:${row.version}`}
          monitorId={row.id}
          canManage={canManage}
          archived={row.status === "archived"}
          changed={reload}
          onAccessFailure={onAccessFailure}
        />
      )}
    </section>
  );
}
function Content({
  allowed,
  canManage,
  initial,
}: {
  allowed: boolean;
  canManage: boolean;
  initial: string;
}) {
  const { locale } = useI18n(),
    c = trademarkCopy[locale];
  const [selected, setSelected] = useState(initial),
    [creating, setCreating] = useState(false),
    [revision, setRevision] = useState(0),
    [anchors, setAnchors] = useState<(string | null)[]>([null]);
  const capabilities = useData<{ drafts_available: boolean }>(
    allowed ? "/capabilities" : null,
    revision,
  );
  const cursor = anchors.at(-1),
    available = allowed && capabilities.data?.drafts_available;
  const list = useData<TrademarkPage<TrademarkMonitor>>(
    available
      ? `/monitors?limit=20${cursor ? `&after_id=${cursor}` : ""}`
      : null,
    revision,
  );
  function changed() {
    setSelected("");
    setCreating(false);
    setRevision((v) => v + 1);
    setAnchors([null]);
  }
  return (
    <Shell section={c.title}>
      <div className={`${styles.root} ${ipStyles.root}`} data-trademark-watch>
        <h1>{c.title}</h1>
        <p>{c.intro}</p>
        <p>{businessMonitorCopy[locale].defaultScope}</p>
        <p className={styles.notice}>{c.source}</p>
        {!canManage && <p>{c.readonly}</p>}
        {!allowed || capabilities.error ? (
          <p role="alert">{c.unavailable}</p>
        ) : !capabilities.data ? (
          <p role="status">{c.loading}</p>
        ) : (
          <>
            <IPISourceStatus revision={revision} />
            <div className={styles.actions}>
              <button onClick={changed}>{c.refresh}</button>
              {canManage && (
                <button
                  onClick={() => {
                    setCreating(true);
                    setSelected("");
                  }}
                >
                  {c.create}
                </button>
              )}
            </div>
            <div className={styles.layout}>
              <aside className={styles.list} aria-label={c.saved}>
                <h2>{c.saved}</h2>
                {list.error ? (
                  <p role="alert">{c.failed}</p>
                ) : !list.data ? (
                  <p role="status">{c.loading}</p>
                ) : (
                  <>
                    {!list.data.items.length && <p>{c.empty}</p>}
                    {list.data.items.map((row) => (
                      <button
                        key={row.id}
                        aria-pressed={row.id === selected}
                        onClick={() => {
                          setSelected(row.id);
                          setCreating(false);
                        }}
                      >
                        {row.configuration.name} · {c[row.status]}
                      </button>
                    ))}
                    <div className={styles.actions}>
                      <button
                        disabled={anchors.length === 1}
                        onClick={() => {
                          setAnchors((v) => v.slice(0, -1));
                          setSelected("");
                        }}
                      >
                        {c.back}
                      </button>
                      <button
                        disabled={!list.data.next_cursor}
                        onClick={() => {
                          setAnchors((v) => [
                            ...v,
                            String(list.data!.next_cursor),
                          ]);
                          setSelected("");
                        }}
                      >
                        {c.next}
                      </button>
                    </div>
                  </>
                )}
              </aside>
              <div>
                {creating && canManage ? (
                  <PortfolioForm
                    saved={(row) => {
                      setCreating(false);
                      setSelected(row.id);
                      setRevision((v) => v + 1);
                    }}
                    cancel={() => setCreating(false)}
                  />
                ) : selected ? (
                  <Detail
                    key={`${selected}:${revision}`}
                    id={selected}
                    canManage={canManage}
                    changed={() => setRevision((v) => v + 1)}
                    deleted={changed}
                  />
                ) : (
                  <p>{c.assessment}</p>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}
function Workspace(props: {
  allowed: boolean;
  canManage: boolean;
  initial: string;
}) {
  const [denied, setDenied] = useState(false);
  const deny = useCallback((problem: unknown) => {
    if (
      problem instanceof ApiError &&
      [
        "authentication_required",
        "membership_required",
        "subject_role_denied",
        "trademark_watch_disabled",
      ].includes(problem.code)
    )
      setDenied(true);
  }, []);
  return (
    <Failure.Provider value={deny}>
      <Content
        key={String(denied)}
        {...props}
        allowed={props.allowed && !denied}
      />
    </Failure.Provider>
  );
}
export function TrademarkWatch() {
  const { session } = useAuth(),
    { locale } = useI18n(),
    params = useSearchParams();
  const scope = session?.authenticated
    ? `${session.user?.id}:${session.organization?.id}:${session.role}:${locale}`
    : "unavailable";
  const [visible, setVisible] = useState(true),
    [epoch, setEpoch] = useState(0);
  useEffect(() => {
    const refresh = () => {
      setVisible(!document.hidden);
      setEpoch((v) => v + 1);
    };
    const hide = () => {
      setVisible(false);
      setEpoch((v) => v + 1);
    };
    document.addEventListener("visibilitychange", refresh);
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", refresh);
    window.addEventListener("focus", refresh);
    return () => {
      document.removeEventListener("visibilitychange", refresh);
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", refresh);
      window.removeEventListener("focus", refresh);
    };
  }, []);
  const values = params.getAll("monitor"),
    initial =
      values.length === 1 &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
        values[0],
      )
        ? values[0]
        : "";
  return (
    <Workspace
      key={`${scope}:${initial}:${params.get("candidate")}:${params.get("event")}:${visible}:${epoch}`}
      allowed={visible && scope !== "unavailable"}
      canManage={session?.role === "organization_admin"}
      initial={initial}
    />
  );
}
