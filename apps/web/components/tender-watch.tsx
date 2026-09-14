"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { businessMonitorCopy } from "@/lib/business-monitor-copy";
import { simapNotice, tenderCopy } from "@/lib/tender-copy";
import { tenderEmailCopy } from "@/lib/tender-email-copy";
import { tenderHistoryCopy } from "@/lib/tender-history-copy";
import { TenderEmail } from "./tender-email";
import { TenderDocuments } from "./tender-documents";
import { tenderDocumentCopy } from "@/lib/tender-document-copy";
import { tenderReviewCopy } from "@/lib/tender-review-copy";
import {
  newTenderProfile,
  sourceTitle,
  sourceExcerpts,
  tenderCantons,
  tenderLanguages,
  type TenderProfile,
  type TenderMonitor,
  type TenderCapabilities,
  type TenderPlan,
  type TenderCard,
  type TenderDossier,
  type TenderPage,
  type TenderVersion,
  type TenderReason,
} from "@/lib/tender-watch";
import { useAuth } from "./auth-gate";
import { BusinessMonitorAccess } from "./business-monitor-access";
import { BusinessItemWork, AssignmentFilter } from "./business-item-work";
import { Shell } from "./shell";
import styles from "./tender-watch.module.css";

const base = "/tender-watch";
type Copy = (typeof tenderCopy)["en-CH"];
const label = (c: Copy, key: string) => c[key as keyof Copy] || c.unknown;
const post = (body: unknown, method = "POST") => ({
  method,
  body: JSON.stringify(body),
});
const failure = (c: Copy, error: unknown) =>
  error instanceof ApiError
    ? error.code === "tender_discovery_query_required"
      ? c.queryNeeded
      : error.code === "tender_disabled"
        ? c.featureOff
        : error.code === "tender_source_not_ready"
          ? c.sourceOff
          : error.code.includes("conflict")
            ? c.conflict
            : error.code === "invalid_input" ||
                error.code === "tender_profile_invalid"
              ? c.invalid
              : c.failed
    : c.failed;

function useData<T>(path: string | null, revision = 0) {
  const [result, setResult] = useState<{
    key: string;
    data?: T;
    failed?: unknown;
  }>({ key: "" });
  const key = `${path}:${revision}`;
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    api<T>(base + path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ key, data });
      })
      .catch((failed) => {
        if (!controller.signal.aborted) setResult({ key, failed });
      });
    return () => controller.abort();
  }, [path, key]);
  return result.key === key ? result : { key };
}

function Checks({
  title,
  values,
  selected,
  changed,
}: {
  title: string;
  values: Record<string, string>;
  selected: string[];
  changed: (next: string[]) => void;
}) {
  return (
    <fieldset>
      <legend>{title}</legend>
      <div className={styles.choices}>
        {Object.entries(values).map(([value, text]) => (
          <label className={styles.check} key={value}>
            <input
              type="checkbox"
              checked={selected.includes(value)}
              onChange={(event) =>
                changed(
                  event.target.checked
                    ? [...selected, value]
                    : selected.filter((item) => item !== value),
                )
              }
            />
            {text}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function Lines({
  title,
  values,
  changed,
  maxLength = 6000,
}: {
  title: string;
  values: string[];
  changed: (next: string[]) => void;
  maxLength?: number;
}) {
  // Keep trailing newlines while typing; resynchronize when a row is replaced.
  const [text, setText] = useState(values.join("\n"));
  const canonical = values.join("\n");
  useEffect(() => {
    setText((previous) =>
      previous
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean)
        .join("\n") === canonical
        ? previous
        : canonical,
    );
  }, [canonical]);
  return (
    <label>
      {title}
      <textarea
        rows={3}
        maxLength={maxLength}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          changed(
            event.target.value
              .split("\n")
              .map((item) => item.trim())
              .filter(Boolean),
          );
        }}
      />
    </label>
  );
}

function Editor({
  monitor,
  saved,
  cancel,
}: {
  monitor?: TenderMonitor;
  saved: (row: TenderMonitor) => void;
  cancel: () => void;
}) {
  const { locale } = useI18n(),
    c = tenderCopy[locale];
  const [config, setConfig] = useState<TenderProfile>(
    () => monitor?.configuration || newTenderProfile(),
  );
  const [plan, setPlan] = useState<TenderPlan | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const requestKey = useRef<string | null>(null);
  const update = (fields: Partial<TenderProfile>) => {
    setConfig((current) => ({ ...current, ...fields }));
    setPlan(null);
    setError("");
  };
  async function run(save: boolean) {
    setBusy(true);
    setError("");
    try {
      if (save) {
        requestKey.current ||= crypto.randomUUID();
        saved(
          await api<TenderMonitor>(
            base + (monitor ? `/monitors/${monitor.id}` : "/monitors"),
            post(
              monitor
                ? { configuration: config, expected_version: monitor.version }
                : { configuration: config, request_key: requestKey.current },
              monitor ? "PATCH" : "POST",
            ),
          ),
        );
      } else
        setPlan(
          await api<TenderPlan>(
            base + "/profile-check",
            post({ configuration: config }),
          ),
        );
    } catch (e) {
      setError(failure(c, e));
    } finally {
      setBusy(false);
    }
  }
  const csv = (text: string) =>
    text
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  return (
    <section className={styles.card}>
      <h2>{monitor ? c.edit : c.create}</h2>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void run(true);
        }}
      >
        <fieldset disabled={busy}>
          <legend>{c.settings}</legend>
          <label>
            {c.name}
            <input
              required
              maxLength={100}
              value={config.name}
              onChange={(event) => update({ name: event.target.value })}
            />
          </label>
          <label>
            {c.company}
            <input
              required
              maxLength={200}
              value={config.company_name}
              onChange={(event) => update({ company_name: event.target.value })}
            />
          </label>
          <h3>{c.capabilities}</h3>
          {config.capabilities.map((capability, index) => (
            <fieldset key={index}>
              <legend>
                {c.capabilities} {index + 1}
              </legend>
              <label>
                {c.capabilityName}
                <input
                  required
                  maxLength={100}
                  value={capability.name}
                  onChange={(event) =>
                    update({
                      capabilities: config.capabilities.map((item, number) =>
                        number === index
                          ? { ...item, name: event.target.value }
                          : item,
                      ),
                    })
                  }
                />
              </label>
              <Lines
                title={c.phrases}
                values={capability.phrases}
                maxLength={1608}
                changed={(phrases) =>
                  update({
                    capabilities: config.capabilities.map((item, number) =>
                      number === index ? { ...item, phrases } : item,
                    ),
                  })
                }
              />
              <button
                type="button"
                onClick={() =>
                  update({
                    capabilities: config.capabilities.filter(
                      (_, number) => number !== index,
                    ),
                  })
                }
              >
                {c.remove}
              </button>
            </fieldset>
          ))}
          <button
            type="button"
            disabled={config.capabilities.length >= 20}
            onClick={() =>
              update({
                capabilities: [
                  ...config.capabilities,
                  { name: "", phrases: [] },
                ],
              })
            }
          >
            {c.addCapability}
          </button>
          <label>
            {c.cpv}
            <input
              defaultValue={config.cpv_codes.join(", ")}
              maxLength={400}
              onChange={(event) =>
                update({ cpv_codes: csv(event.target.value) })
              }
            />
          </label>
          <label className={styles.check}>
            <input
              type="checkbox"
              checked={config.cpv_include_descendants}
              onChange={(event) =>
                update({ cpv_include_descendants: event.target.checked })
              }
            />
            {c.descendants}
          </label>
          <Checks
            title={c.cantons}
            values={Object.fromEntries(
              tenderCantons.map((value) => [value, value]),
            )}
            selected={config.contract_cantons}
            changed={(contract_cantons) => update({ contract_cantons })}
          />
          <Checks
            title={c.languages}
            values={tenderLanguages}
            selected={config.offer_languages}
            changed={(offer_languages) => update({ offer_languages })}
          />
          <details>
            <summary>{c.advanced}</summary>
            <Checks
              title={c.authority}
              values={{
                federal: c.federal,
                cantonal: c.cantonal,
                municipal: c.municipal,
                other: c.other,
              }}
              selected={config.authority_levels}
              changed={(authority_levels) => update({ authority_levels })}
            />
            <Lines
              title={c.excludedPhrases}
              values={config.excluded_phrases}
              changed={(excluded_phrases) => update({ excluded_phrases })}
            />
            <label>
              {c.excludedCpv}
              <input
                defaultValue={config.excluded_cpv_codes.join(", ")}
                maxLength={400}
                onChange={(event) =>
                  update({ excluded_cpv_codes: csv(event.target.value) })
                }
              />
            </label>
            <Checks
              title={c.excludedTypes}
              values={{
                service: c.service,
                supply: c.supply,
                construction: c.construction,
              }}
              selected={config.excluded_contract_types}
              changed={(excluded_contract_types) =>
                update({ excluded_contract_types })
              }
            />
            <div className={styles.fields}>
              {(["minimum_contract_chf", "maximum_contract_chf"] as const).map(
                (key, index) => (
                  <label key={key}>
                    {index ? c.maxValue : c.minValue}
                    <input
                      type="number"
                      min="0"
                      max="1000000000000"
                      step="0.01"
                      value={config[key] ?? ""}
                      onChange={(event) =>
                        update({ [key]: event.target.value || null })
                      }
                    />
                  </label>
                ),
              )}
            </div>
            <label>
              {c.references}
              <input
                type="number"
                min="0"
                max="10000"
                step="1"
                value={config.available_reference_count ?? ""}
                onChange={(event) =>
                  update({
                    available_reference_count:
                      event.target.value === ""
                        ? null
                        : Number(event.target.value),
                  })
                }
              />
            </label>
            <Lines
              title={c.certificates}
              values={config.certificates || []}
              changed={(certificates) =>
                update({
                  certificates: certificates.length ? certificates : null,
                })
              }
            />
          </details>
          <p>{c.semantic}</p>
          <div className={styles.actions}>
            <button type="button" onClick={() => void run(false)}>
              {c.check}
            </button>
            <button type="submit">{monitor ? c.saveEdit : c.save}</button>
            <button type="button" onClick={cancel}>
              {c.cancel}
            </button>
          </div>
        </fieldset>
      </form>
      {busy && <p role="status">{c.loading}</p>}
      {error && <p role="alert">{error}</p>}
      {plan && (
        <section aria-live="polite">
          <h3>{c.plan}</h3>
          <ul>
            {plan.queries.map((query, index) => (
              <li key={index}>{query.query || query.cpv_codes?.join(", ")}</li>
            ))}
          </ul>
          {!plan.queries.length && <p>{c.queryNeeded}</p>}
          <p>{c.confirmed}</p>
        </section>
      )}
    </section>
  );
}

function ProfileHistory({ monitor }: { monitor: TenderMonitor }) {
  const { locale } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <details
      className={styles.card}
      onToggle={(event) => setOpen(event.currentTarget.open)}
      data-tender-profile-history
    >
      <summary>{tenderHistoryCopy[locale].title}</summary>
      {open && <ProfileRevisions monitor={monitor} />}
    </details>
  );
}

function ProfileRevisions({ monitor }: { monitor: TenderMonitor }) {
  const { locale } = useI18n(),
    c = tenderCopy[locale],
    h = tenderHistoryCopy[locale];
  const [cursor, setCursor] = useState<number | null>(null);
  const [retry, setRetry] = useState(0);
  const result = useData<
    TenderPage<{ revision: number; configuration: TenderProfile }>
  >(
    `/monitors/${monitor.id}/revisions?limit=10${cursor ? `&before_revision=${cursor}` : ""}`,
    retry,
  );
  const fields: [keyof TenderProfile, string, string][] = [
    ["name", c.name, h.none],
    ["company_name", c.company, h.none],
    ["capabilities", c.capabilities, h.none],
    ["cpv_codes", c.cpv, h.any],
    ["cpv_include_descendants", c.descendants, h.none],
    ["contract_cantons", c.cantons, h.any],
    ["offer_languages", c.languages, h.any],
    ["authority_levels", c.authority, h.any],
    ["excluded_phrases", c.excludedPhrases, h.none],
    ["excluded_cpv_codes", c.excludedCpv, h.none],
    ["excluded_contract_types", c.excludedTypes, h.none],
    ["minimum_contract_chf", c.minValue, h.any],
    ["maximum_contract_chf", c.maxValue, h.any],
    ["available_reference_count", c.references, c.unknown],
    ["certificates", c.certificates, h.none],
    ["minimum_semantic_score", h.semantic, h.any],
  ];
  function value(
    profile: TenderProfile,
    key: keyof TenderProfile,
    empty: string,
  ) {
    const item = profile[key];
    if (item === null)
      return key === "certificates" || key === "available_reference_count"
        ? c.unknown
        : empty;
    if (typeof item === "boolean") return item ? h.yes : h.no;
    if (key === "capabilities")
      return profile.capabilities.length ? (
        <ul>
          {profile.capabilities.map((capability, index) => (
            <li key={index}>
              {capability.name}: {capability.phrases.join(" · ") || h.none}
            </li>
          ))}
        </ul>
      ) : (
        empty
      );
    if (Array.isArray(item))
      return item.length
        ? (item as string[])
            .map((entry) =>
              key === "offer_languages"
                ? tenderLanguages[entry as keyof typeof tenderLanguages] ||
                  entry
                : key === "authority_levels" ||
                    key === "excluded_contract_types"
                  ? label(c, entry)
                  : entry,
            )
            .join(" · ")
        : empty;
    return String(item);
  }
  return (
    <section>
      <p>{h.help}</p>
      <p>{c.semantic}</p>
      <button
        onClick={() => {
          setCursor(null);
          setRetry((v) => v + 1);
        }}
      >
        {c.refresh}
      </button>
      {result.failed ? (
        <p role="alert">{failure(c, result.failed)}</p>
      ) : !result.data ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          {result.data.items.map((item) => (
            <details
              key={item.revision}
              className={styles.card}
              data-profile-revision={item.revision}
            >
              <summary>
                {c.retainedRevision} {item.revision}
                {item.revision === monitor.revision ? ` · ${c.current}` : ""}
              </summary>
              <dl>
                {fields.map(([key, title, empty]) => (
                  <div key={key} className={styles.profileField}>
                    <dt>
                      {title}
                      {JSON.stringify(item.configuration[key]) !==
                        JSON.stringify(monitor.configuration[key]) && (
                        <small> · {h.changed}</small>
                      )}
                    </dt>
                    <dd>{value(item.configuration, key, empty)}</dd>
                  </div>
                ))}
              </dl>
            </details>
          ))}
          <div className={styles.actions}>
            {cursor && (
              <button onClick={() => setCursor(null)}>{c.current}</button>
            )}
            {result.data.next_cursor && (
              <button
                onClick={() => setCursor(Number(result.data!.next_cursor))}
              >
                {c.more}
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function Deadline({ value }: { value: unknown }) {
  const { locale } = useI18n(),
    c = tenderCopy[locale];
  const deadline = value as { utc?: string; status?: string } | null;
  return (
    <p>
      {c.deadline}:{" "}
      {deadline?.status === "known" && deadline.utc ? (
        <time dateTime={deadline.utc}>
          {new Date(deadline.utc).toLocaleString(
            locale === "rm-CH" ? "de-CH" : locale,
            {
              timeZone: "Europe/Zurich",
              timeZoneName: "short",
            },
          )}
        </time>
      ) : (
        c.noDeadline
      )}
    </p>
  );
}

function ReviewChanges({
  dossier,
  onOriginal,
  onDocuments,
}: {
  dossier: TenderDossier;
  onOriginal: (id: string) => void;
  onDocuments: (id: string, sequence: number) => void;
}) {
  const { locale } = useI18n(),
    c = tenderCopy[locale],
    r = tenderReviewCopy[locale];
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState<number | null>(null);
  const [revision, setRevision] = useState(0);
  type Entry = {
    id: string;
    sequence: number;
    available: boolean;
    kind?: string;
    changes?: { field: string; kind: string }[];
    document_observation_id?: string | null;
  };
  const result = useData<TenderPage<Entry>>(
    open
      ? `/dossiers/${dossier.id}/review-changes?through_sequence=${dossier.sequence}&reviewed_sequence=${dossier.reviewed_sequence || 0}${cursor !== null ? `&after_sequence=${cursor}` : ""}`
      : null,
    revision,
  );
  return (
    <details
      className={styles.card}
      data-review-changes
      open={open}
      onToggle={(event) => {
        setOpen(event.currentTarget.open);
        if (!event.currentTarget.open) setRevision((value) => value + 1);
      }}
    >
      <summary>{r.title}</summary>
      {open && (
        <>
          <p>{r.help}</p>
          <p>
            {dossier.reviewed_sequence === null
              ? r.first
              : `${c.revision} ${dossier.reviewed_sequence} → ${dossier.sequence}`}
          </p>
          <button onClick={() => setRevision((value) => value + 1)}>
            {c.refresh}
          </button>
          {result.failed ? (
            <p role="alert">{failure(c, result.failed)}</p>
          ) : !result.data ? (
            <p role="status">{c.loading}</p>
          ) : (
            <>
              {!result.data.items.length && <p>{r.empty}</p>}
              {result.data.items.map((item) => (
                <section
                  key={item.id}
                  className={styles.card}
                  data-review-change={item.sequence}
                >
                  <h3>
                    {c.revision} {item.sequence}
                    {item.available && (
                      <> · {label(c, item.kind || "unknown")}</>
                    )}
                  </h3>
                  {!item.available ? (
                    <p className={styles.notice}>{r.unavailable}</p>
                  ) : (
                    <>
                      {!!item.changes?.length && (
                        <ul>
                          {item.changes.map((change) => (
                            <li key={change.field}>
                              {label(
                                c,
                                change.field === "title"
                                  ? "titleField"
                                  : change.field,
                              )}{" "}
                              ·{" "}
                              {change.kind === "coverage_changed"
                                ? c.unknowns
                                : c.material_update}
                            </li>
                          ))}
                        </ul>
                      )}
                      <button onClick={() => onOriginal(item.id)}>
                        {c.original}
                      </button>
                      {item.document_observation_id && (
                        <button
                          onClick={() =>
                            onDocuments(
                              item.document_observation_id!,
                              item.sequence,
                            )
                          }
                        >
                          {tenderDocumentCopy[locale].title}
                        </button>
                      )}
                    </>
                  )}
                </section>
              ))}
              <div className={styles.actions}>
                {cursor !== null && (
                  <button onClick={() => setCursor(null)}>{c.current}</button>
                )}
                {result.data.next_cursor !== null && (
                  <button
                    onClick={() => setCursor(Number(result.data!.next_cursor))}
                  >
                    {c.more}
                  </button>
                )}
              </div>
            </>
          )}
        </>
      )}
    </details>
  );
}

function Versions({
  dossierId,
  onOriginal,
  onDocuments,
}: {
  dossierId: string;
  onOriginal: (id: string) => void;
  onDocuments: (id: string, sequence: number) => void;
}) {
  const { locale } = useI18n(),
    c = tenderCopy[locale];
  const [cursor, setCursor] = useState<number | null>(null);
  const result = useData<TenderPage<TenderVersion>>(
    `/dossiers/${dossierId}/versions${cursor ? `?before_sequence=${cursor}` : ""}`,
  );
  return (
    <section>
      <h3>{c.changes}</h3>
      {result.failed ? (
        <p role="alert">{failure(c, result.failed)}</p>
      ) : !result.data ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          {result.data.items.map((item) => (
            <div
              className={styles.card}
              key={item.id}
              data-tender-version={item.id}
            >
              <p>
                {c.revision} {item.sequence} · {label(c, item.kind)} ·{" "}
                {c.retainedRevision} {item.profile_revision}
              </p>
              <Deadline value={item.summary.deadline} />
              <button onClick={() => onOriginal(item.id)}>{c.original}</button>
              {item.document_observation_id && (
                <button
                  onClick={() =>
                    onDocuments(item.document_observation_id!, item.sequence)
                  }
                >
                  {tenderDocumentCopy[locale].title}
                </button>
              )}
            </div>
          ))}
          <div className={styles.actions}>
            {cursor && (
              <button onClick={() => setCursor(null)}>{c.current}</button>
            )}
            {result.data.next_cursor && (
              <button
                onClick={() => setCursor(Number(result.data!.next_cursor))}
              >
                {c.more}
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function Reasons({
  title,
  entries,
}: {
  title: string;
  entries: TenderReason[];
}) {
  const { locale } = useI18n(),
    c = tenderCopy[locale];
  const fields: Record<string, keyof Copy> = {
    capability_phrase: "capabilities",
    exact_cpv: "cpv",
    cpv_descendant: "cpv",
    project_cpv_context: "projectContext",
    discovery_phase_closed: "phase",
    offer_deadline_passed: "deadline",
    publication_phase_unknown: "phase",
    excluded_phrase: "excludedPhrases",
    excluded_cpv: "excludedCpv",
    cpv_exclusions_unverified: "excludedCpv",
    excluded_contract_type: "excludedTypes",
    contract_type_exclusions_unverified: "excludedTypes",
    contract_outside_switzerland: "cantons",
    contract_location_unknown: "cantons",
    contract_canton_excluded: "cantons",
    offer_languages_unknown: "offer_languages",
    offer_languages_excluded: "offer_languages",
    authority_level_unknown: "authority",
    authority_level_excluded: "authority",
    contract_value_below_minimum: "minValue",
    contract_minimum_not_established: "minValue",
    contract_value_above_maximum: "maxValue",
    contract_maximum_not_established: "maxValue",
    cpv_hierarchy_unknown: "descendants",
    cpv_unknown: "cpv",
    company_references_unknown: "references",
    declared_reference_gap: "references",
    company_certificates_unknown: "certificates",
    declared_certificate_gap: "certificates",
    qualification_evidence_incomplete: "evidenceHelp",
  };
  return (
    <section>
      <h3>{title}</h3>
      {!entries.length ? (
        <p>{c.noReasons}</p>
      ) : (
        <ul>
          {entries.map((reason, index) => (
            <li key={index}>
              {c[fields[reason.code] || "unknowns"].split(" — ")[0]}:{" "}
              {[
                reason.capability,
                reason.phrase,
                reason.value,
                reason.values?.join(", "),
              ]
                .filter(Boolean)
                .join(" · ") || c.unknown}
              {reason.selected_code && <> · {reason.selected_code}</>}
              {reason.required !== undefined && (
                <>
                  {" "}
                  · {reason.declared ?? c.unknown} / {reason.required}
                </>
              )}
              {reason.locator && (
                <small className={styles.source}> ({reason.locator})</small>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SourceValue({ value }: { value: unknown }) {
  const { locale } = useI18n(),
    c = tenderCopy[locale];
  const excerpts = sourceExcerpts(value, locale);
  return (
    <div>
      {!excerpts.paragraphs.length && <p>{c.unknown}</p>}
      {excerpts.paragraphs.map((text, index) => (
        <p className={styles.source} key={index}>
          {text}
        </p>
      ))}
      {excerpts.truncated && <p className={styles.notice}>{c.excerpt}</p>}
    </div>
  );
}

function PublicField({
  name,
  value,
  known,
}: {
  name: string;
  value: unknown;
  known: boolean;
}) {
  const { locale } = useI18n(),
    c = tenderCopy[locale];
  const [open, setOpen] = useState(false);
  return (
    <details onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>
        {label(c, name)} · {known ? c.source : c.unknown}
      </summary>
      {open && <SourceValue value={value} />}
    </details>
  );
}

function Dossier({
  id,
  expectedVersion = "",
  monitorId,
  canManage,
  archived,
  back,
  changed,
}: {
  id: string;
  expectedVersion?: string;
  monitorId: string;
  canManage: boolean;
  archived: boolean;
  back: () => void;
  changed: () => void;
}) {
  const { locale } = useI18n(),
    c = tenderCopy[locale];
  const [selectedDocuments, setSelectedDocuments] = useState<{
    id: string;
    sequence: number;
    request: number;
  } | null>(null);
  const [revision, setRevision] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const result = useData<TenderDossier>(`/dossiers/${id}`, revision),
    row = result.data;
  const panel = useRef<HTMLElement | null>(null),
    focused = useRef(false);
  useEffect(() => {
    if (row && !focused.current) {
      focused.current = true;
      panel.current?.focus();
      panel.current?.scrollIntoView({ block: "start" });
    }
  }, [row]);
  const requests = useRef<Record<string, string>>({});
  async function act(action: string) {
    if (!row || row.monitor_id !== monitorId) return;
    setBusy(true);
    setError("");
    try {
      if (action === "follow")
        await api(
          base + `/dossiers/${id}/follow`,
          post({ expected_version: row.version, following: !row.following }),
        );
      else {
        const key = `${row.version}:${row.sequence}:${action}`;
        requests.current[key] ||= crypto.randomUUID();
        await api(
          base + `/dossiers/${id}/decision`,
          post({
            expected_version: row.version,
            sequence: row.sequence,
            decision: action,
            request_key: requests.current[key],
          }),
        );
      }
      setRevision((value) => value + 1);
      changed();
    } catch (e) {
      setError(failure(c, e));
    } finally {
      setBusy(false);
    }
  }
  async function original(versionId: string) {
    setBusy(true);
    setError("");
    try {
      const evidence = await api<{ original: unknown }>(
        base + `/dossiers/${id}/versions/${versionId}/evidence`,
      );
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(evidence.original, null, 2)], {
          type: "application/json",
        }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = `simap-${versionId}.json`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(failure(c, e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className={styles.detail}
      data-tender-dossier={id}
      ref={panel}
      tabIndex={-1}
      aria-label={c.review}
    >
      <div className={styles.actions}>
        <button onClick={back}>{c.back}</button>
        <button
          disabled={busy}
          onClick={() => setRevision((value) => value + 1)}
        >
          {c.refresh}
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {result.failed ? (
        <p role="alert">{failure(c, result.failed)}</p>
      ) : row && row.monitor_id !== monitorId ? (
        <p role="alert">{c.failed}</p>
      ) : !row ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          <article className={styles.card}>
            {expectedVersion && expectedVersion !== row.evidence_version_id && (
              <div className={styles.notice}>
                <p>{tenderEmailCopy[locale].older}</p>
                <button
                  disabled={busy}
                  onClick={() => void original(expectedVersion)}
                >
                  {c.original}
                </button>
              </div>
            )}
            <h2>
              {sourceTitle(row.material.title.value, locale) || c.tenders}
            </h2>
            <p>
              {label(c, row.review_state)}
              {row.match.verdict !== row.review_state && (
                <> · {label(c, row.match.verdict)}</>
              )}
            </p>
            <Deadline value={row.material.deadline.value} />
            <p>
              {c.phase}: {label(c, String(row.material.phase.value))}
            </p>
            {row.profile_revision !== row.current_profile_revision && (
              <p className={styles.notice}>{c.profileOld}</p>
            )}
            {row.decision && (
              <p>
                {c.internalDecision}: {label(c, row.decision)} · {c.revision}{" "}
                {row.reviewed_sequence}
              </p>
            )}
            {row.review_state === "needs_review" && row.decision && (
              <p className={styles.notice}>{c.retained}</p>
            )}
            {canManage && !archived && (
              <fieldset disabled={busy}>
                <legend>{c.internalDecision}</legend>
                <div className={styles.actions}>
                  {["bid", "no_bid", "monitor"].map((value) => (
                    <button key={value} onClick={() => void act(value)}>
                      {label(c, value)}
                    </button>
                  ))}
                  <button onClick={() => void act("follow")}>
                    {row.following ? c.unfollow : c.follow}
                  </button>
                </div>
              </fieldset>
            )}
            <BusinessItemWork
              domain="tenders"
              monitorId={monitorId}
              itemId={id}
              version={row.version}
              canManage={canManage && !archived}
              changed={() => {
                setRevision((value) => value + 1);
                changed();
              }}
            />
            <p>{c.scope}</p>
            <button
              disabled={busy}
              onClick={() => void original(row.evidence_version_id)}
            >
              {c.original}
            </button>
          </article>
          <article className={styles.card}>
            <h2>{c.review}</h2>
            {row.match.project_context.length > 0 && (
              <div className={styles.notice}>
                <Reasons
                  title={c.projectContext}
                  entries={row.match.project_context}
                />
              </div>
            )}
            <Reasons title={c.matches} entries={row.match.matches} />
            <Reasons title={c.exclusions} entries={row.match.exclusions} />
            <Reasons title={c.unknowns} entries={row.match.unknowns} />
            <Reasons title={c.gaps} entries={row.match.qualification_gaps} />
            {row.changes.length > 0 && (
              <section>
                <h3>{c.material}</h3>
                <ul>
                  {row.changes.map((item) => (
                    <li key={item.field}>
                      {label(
                        c,
                        item.field === "title" ? "titleField" : item.field,
                      )}{" "}
                      ·{" "}
                      {item.kind === "coverage_changed"
                        ? c.unknowns
                        : c.material_update}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </article>
          <article className={styles.card}>
            <h2>{c.publicFields}</h2>
            <p>{c.evidenceHelp}</p>
            {Object.entries(row.material)
              .filter(([key]) => !["title", "phase", "deadline"].includes(key))
              .map(([key, item]) => (
                <PublicField
                  key={key}
                  name={key}
                  value={item.value}
                  known={item.coverage === "known"}
                />
              ))}
          </article>
          <ReviewChanges
            key={`review:${revision}:${row.sequence}:${row.reviewed_sequence}`}
            dossier={row}
            onOriginal={(version) => void original(version)}
            onDocuments={(documentId, sequence) =>
              setSelectedDocuments((previous) => ({
                id: documentId,
                sequence,
                request: (previous?.request || 0) + 1,
              }))
            }
          />
          <Versions
            key={revision}
            dossierId={id}
            onOriginal={(version) => void original(version)}
            onDocuments={(documentId, sequence) =>
              setSelectedDocuments((previous) => ({
                id: documentId,
                sequence,
                request: (previous?.request || 0) + 1,
              }))
            }
          />
          {selectedDocuments && (
            <button onClick={() => setSelectedDocuments(null)}>
              {c.current} · {tenderDocumentCopy[locale].title}
            </button>
          )}
          <TenderDocuments
            key={`${selectedDocuments?.id || row.document_observation_id || "retained"}:${revision}:${selectedDocuments?.request || 0}`}
            dossierId={id}
            observationId={selectedDocuments?.id || row.document_observation_id}
            sequence={selectedDocuments?.sequence || row.sequence}
            initialOpen={!!selectedDocuments}
          />
        </>
      )}
    </section>
  );
}

function Cards({
  monitor,
  selected,
}: {
  monitor: TenderMonitor;
  selected: (id: string) => void;
}) {
  const { locale } = useI18n(),
    c = tenderCopy[locale];
  const [following, setFollowing] = useState(false),
    [review, setReview] = useState("");
  const [assignment, setAssignment] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const query = new URLSearchParams();
  if (following) query.set("following", "true");
  if (review) query.set("review_state", review);
  if (assignment) query.set("assignment", assignment);
  if (cursor) query.set("after_id", cursor);
  const result = useData<TenderPage<TenderCard>>(
    `/monitors/${monitor.id}/dossiers?${query}`,
  );
  return (
    <section>
      <h2>{c.tenders}</h2>
      <AssignmentFilter
        value={assignment}
        changed={(value) => {
          setAssignment(value);
          setCursor(null);
        }}
      />
      <div className={styles.actions}>
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={following}
            onChange={(event) => {
              setFollowing(event.target.checked);
              setCursor(null);
            }}
          />
          {c.following}
        </label>
        <label>
          {c.review}
          <select
            value={review}
            onChange={(event) => {
              setReview(event.target.value);
              setCursor(null);
            }}
          >
            <option value="">{c.all}</option>
            {["new", "needs_review", "reviewed"].map((value) => (
              <option key={value} value={value}>
                {label(c, value)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {result.failed ? (
        <p role="alert">{failure(c, result.failed)}</p>
      ) : !result.data ? (
        <p role="status">{c.loading}</p>
      ) : (
        <div className={styles.detail}>
          {!result.data.items.length && <p>{c.none}</p>}
          {result.data.items.map((item) => (
            <article className={styles.card} key={item.id}>
              <h3>{sourceTitle(item.summary.title, locale) || c.tenders}</h3>
              <p>
                {label(c, item.review_state)} · {label(c, item.summary.phase)} ·{" "}
                {label(c, item.summary.verdict)}
              </p>
              {item.summary.match_scope === "project_context" && (
                <p>{c.projectContext}</p>
              )}
              <Deadline value={item.summary.deadline} />
              {item.profile_revision !== item.current_profile_revision && (
                <p>{c.profileOld}</p>
              )}
              <button onClick={() => selected(item.id)}>{c.details}</button>
            </article>
          ))}
          <div className={styles.actions}>
            {cursor && (
              <button onClick={() => setCursor(null)}>{c.current}</button>
            )}
            {result.data.next_cursor && (
              <button
                onClick={() => setCursor(String(result.data!.next_cursor))}
              >
                {c.more}
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function Monitor({
  id,
  initialDossier,
  expectedVersion,
  canManage,
  capabilities,
  changed,
  deleted,
}: {
  id: string;
  initialDossier: string;
  expectedVersion: string;
  canManage: boolean;
  capabilities: TenderCapabilities;
  changed: () => void;
  deleted: () => void;
}) {
  const { session } = useAuth();
  const { locale } = useI18n(),
    c = tenderCopy[locale];
  const [revision, setRevision] = useState(0),
    [editing, setEditing] = useState(false),
    [dossier, setDossier] = useState(initialDossier);
  useEffect(() => {
    setDossier(initialDossier);
  }, [initialDossier]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const result = useData<TenderMonitor>(`/monitors/${id}`, revision),
    row = result.data;
  const reload = () => {
    setRevision((value) => value + 1);
    changed();
  };
  async function command(action: string) {
    if (!row || (action === "delete" && !window.confirm(c.confirm))) return;
    setBusy(true);
    setError("");
    try {
      await api(
        base + `/monitors/${id}${action === "delete" ? "" : "/command"}`,
        post(
          action === "delete"
            ? { expected_version: row.version }
            : { expected_version: row.version, action },
          action === "delete" ? "DELETE" : "POST",
        ),
      );
      if (action === "delete") deleted();
      else reload();
    } catch (e) {
      setError(failure(c, e));
    } finally {
      setBusy(false);
    }
  }
  if (editing && row)
    return (
      <Editor
        monitor={row}
        saved={() => {
          setEditing(false);
          reload();
        }}
        cancel={() => setEditing(false)}
      />
    );
  return (
    <section className={styles.detail}>
      {error && <p role="alert">{error}</p>}
      {result.failed ? (
        <>
          <p role="alert">{failure(c, result.failed)}</p>
          <button onClick={reload}>{c.refresh}</button>
        </>
      ) : !row ? (
        <p role="status">{c.loading}</p>
      ) : (
        <>
          <header className={styles.card}>
            <h2>{row.configuration.name}</h2>
            <p>
              {row.configuration.company_name} · {label(c, row.status)} ·{" "}
              {label(c, row.health)}
            </p>
            <p>
              {c.lastCheck}:{" "}
              {row.last_poll_at
                ? new Date(row.last_poll_at).toLocaleString(
                    locale === "rm-CH" ? "de-CH" : locale,
                  )
                : c.unknown}
            </p>
            {row.status === "active" && (
              <p>
                {c.nextCheck}:{" "}
                {row.next_poll_at
                  ? new Date(row.next_poll_at).toLocaleString(
                      locale === "rm-CH" ? "de-CH" : locale,
                    )
                  : c.unknown}
              </p>
            )}
            <div className={styles.actions}>
              <button disabled={busy} onClick={reload}>
                {c.refresh}
              </button>
              {canManage && (
                <>
                  {(row.status === "draft" || row.status === "paused") && (
                    <button
                      disabled={busy || !capabilities.public_source_available}
                      onClick={() =>
                        void command(
                          row.status === "draft" ? "start" : "resume",
                        )
                      }
                    >
                      {row.status === "draft" ? c.start : c.resume}
                    </button>
                  )}
                  {row.status === "active" && (
                    <button
                      disabled={busy}
                      onClick={() => void command("pause")}
                    >
                      {c.pause}
                    </button>
                  )}
                  {(row.status === "draft" || row.status === "paused") && (
                    <button disabled={busy} onClick={() => setEditing(true)}>
                      {c.edit}
                    </button>
                  )}
                  {row.status !== "archived" && (
                    <button
                      disabled={busy}
                      onClick={() => void command("archive")}
                    >
                      {c.archive}
                    </button>
                  )}
                  <button
                    disabled={busy}
                    onClick={() => void command("delete")}
                  >
                    {c.delete}
                  </button>
                </>
              )}
            </div>
          </header>
          <ProfileHistory key={`profile-${row.revision}`} monitor={row} />
          <BusinessMonitorAccess
            key={`access:${row.version}`}
            domain="tenders"
            monitor={row}
            changed={reload}
          />
          {row.owner_user_id === session?.user?.id && (
            <TenderEmail
              key={row.version}
              monitorId={id}
              canManage={canManage}
              archived={row.status === "archived"}
              changed={reload}
            />
          )}
          {dossier ? (
            <Dossier
              key={dossier}
              id={dossier}
              monitorId={id}
              expectedVersion={
                dossier === initialDossier ? expectedVersion : ""
              }
              canManage={canManage}
              archived={row.status === "archived"}
              back={() => {
                setDossier("");
                reload();
              }}
              changed={changed}
            />
          ) : (
            <Cards key={revision} monitor={row} selected={setDossier} />
          )}
        </>
      )}
    </section>
  );
}

export function TenderWatch() {
  const { session } = useAuth(),
    params = useSearchParams();
  const scope = session?.authenticated
    ? `${session.user?.id}:${session.organization?.id}:${session.role}`
    : "unavailable";
  const [visible, setVisible] = useState(true),
    [epoch, setEpoch] = useState(0);
  useEffect(() => {
    const refresh = () => {
      setVisible(!document.hidden);
      setEpoch((value) => value + 1);
    };
    const hide = () => {
      setVisible(false);
      setEpoch((value) => value + 1);
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
  const requested = params.get("monitor") || "";
  const initial = /^[0-9a-f-]{36}$/i.test(requested) ? requested : "";
  return (
    <Reader
      key={`${scope}:${visible}:${epoch}`}
      allowed={visible && scope !== "unavailable"}
      canManage={session?.role === "organization_admin"}
      initial={initial}
      initialDossier={
        /^[0-9a-f-]{36}$/i.test(params.get("dossier") || "")
          ? params.get("dossier")!
          : ""
      }
      expectedVersion={
        /^[0-9a-f-]{36}$/i.test(params.get("version") || "")
          ? params.get("version")!
          : ""
      }
    />
  );
}

function Reader({
  allowed,
  canManage,
  initial,
  initialDossier,
  expectedVersion,
}: {
  allowed: boolean;
  canManage: boolean;
  initial: string;
  initialDossier: string;
  expectedVersion: string;
}) {
  const { locale } = useI18n(),
    c = tenderCopy[locale];
  const [revision, setRevision] = useState(0),
    [selected, setSelected] = useState(initial),
    [creating, setCreating] = useState(false);
  const capabilities = useData<TenderCapabilities>(
    allowed ? "/capabilities" : null,
  );
  const monitors = useData<TenderPage<TenderMonitor>>(
    allowed ? "/monitors?limit=100" : null,
    revision,
  );
  useEffect(() => {
    setSelected(initial);
    setCreating(false);
  }, [initial]);
  const changed = () => setRevision((value) => value + 1);
  const failed = capabilities.failed || monitors.failed;
  return (
    <Shell section={c.title}>
      <div className={styles.root} data-tender-watch>
        <header>
          <h1>{c.title}</h1>
          <p>{c.intro}</p>
          <p>{businessMonitorCopy[locale].defaultScope}</p>
        </header>
        <p className={styles.notice}>{c.scope}</p>
        <p lang={locale === "rm-CH" ? "de" : locale.slice(0, 2)}>
          {simapNotice[locale]}{" "}
          <a
            href="https://www.simap.ch/en/about/legal"
            target="_blank"
            rel="noreferrer"
          >
            {c.source}
          </a>
        </p>
        <p>
          {c.sourceLimit} {c.noEmail}
        </p>
        {capabilities.data && !capabilities.data.public_source_available && (
          <p role="status">{c.sourceOff}</p>
        )}
        <div className={styles.actions}>
          <button disabled={!allowed} onClick={changed}>
            {c.refresh}
          </button>
          {canManage && capabilities.data && (
            <button
              onClick={() => {
                setSelected("");
                setCreating(true);
              }}
            >
              {c.create}
            </button>
          )}
        </div>
        {!canManage && <p>{c.readonly}</p>}
        {failed ? (
          <p role="alert">{failure(c, failed)}</p>
        ) : allowed && !monitors.data ? (
          <p role="status">{c.loading}</p>
        ) : null}
        <div className={styles.layout}>
          <aside className={styles.list} aria-label={c.title}>
            {monitors.data?.items.map((row) => (
              <button
                key={row.id}
                aria-pressed={selected === row.id}
                onClick={() => {
                  setSelected(row.id);
                  setCreating(false);
                }}
              >
                {row.configuration.name} · {label(c, row.status)}
              </button>
            ))}
            {monitors.data && !monitors.data.items.length && <p>{c.empty}</p>}
          </aside>
          {creating ? (
            <Editor
              saved={(row) => {
                setCreating(false);
                setSelected(row.id);
                changed();
              }}
              cancel={() => setCreating(false)}
            />
          ) : selected && capabilities.data ? (
            <Monitor
              key={selected}
              id={selected}
              initialDossier={selected === initial ? initialDossier : ""}
              expectedVersion={selected === initial ? expectedVersion : ""}
              canManage={canManage}
              capabilities={capabilities.data}
              changed={changed}
              deleted={() => {
                setSelected("");
                changed();
              }}
            />
          ) : null}
        </div>
      </div>
    </Shell>
  );
}
