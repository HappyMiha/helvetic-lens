"use client";
import { MonitoringConfigurationDraft } from "./monitoring-configuration-draft";

import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { businessMonitorCopy } from "@/lib/business-monitor-copy";
import { auctionCopy } from "@/lib/auction-copy";
import {
  newAuctionProfile,
  parseAuctionBudget,
  auctionCategories,
  auctionPriceKinds,
  auctionNotices,
  type AuctionProfile,
  type AuctionMonitor,
  type AuctionPage,
} from "@/lib/auction-watch";
import { useAuth } from "./auth-gate";
import { BusinessMonitorAccess } from "./business-monitor-access";
import { Shell } from "./shell";
import styles from "./commute-watch.module.css";
import ipStyles from "./auction-watch.module.css";
import { Failure, useData, useMutation } from "./auction-client";
import { AuctionTracking } from "./auction-tracking";
import { AuctionChange } from "./auction-change";
import { AuctionReminder, AuctionReminders } from "./auction-reminders";
import { AuctionEmail } from "./auction-email";
import { AsteSourceStatus } from "./aste-source-status";
import { auctionTrackingCopy } from "@/lib/auction-tracking-copy";

function ProfileForm({
  row,
  saved,
  cancel,
}: {
  row?: AuctionMonitor;
  saved: (row: AuctionMonitor) => void;
  cancel: () => void;
}) {
  const { locale } = useI18n(),
    c = auctionCopy[locale],
    mutation = useMutation();
  const [config, setConfig] = useState<AuctionProfile>(() =>
    row ? structuredClone(row.configuration) : newAuctionProfile(),
  );
  const [budget, setBudget] = useState(() =>
    row?.configuration.maximum_price_chf_cents != null
      ? (row.configuration.maximum_price_chf_cents / 100).toFixed(2)
      : "",
  );
  const [hours, setHours] = useState(
    () => row?.configuration.notify.ending_soon_hours?.toString() || "",
  );
  const [text, setText] = useState(() => ({
    locations: config.locations.join("\n"),
    keywords: config.keywords.join("\n"),
    brands: config.brands.join("\n"),
  }));
  const [invalid, setInvalid] = useState(false);
  const request = useRef<{ body: string; key: string } | null>(null);
  const draftConfiguration: AuctionProfile = {
    ...config,
    ...Object.fromEntries(
      Object.entries(text).map(([key, value]) => [
        key,
        value
          .split("\n")
          .map((v) => v.trim())
          .filter(Boolean),
      ]),
    ),
    maximum_price_chf_cents:
      parseAuctionBudget(budget) ?? (budget.trim() ? NaN : null),
    notify: {
      ...config.notify,
      ending_soon_hours: hours.trim()
        ? /^\d+$/.test(hours)
          ? Number(hours)
          : NaN
        : null,
    },
  };
  function submit() {
    const amount = parseAuctionBudget(budget);
    const reminder = !hours.trim()
      ? null
      : /^\d+$/.test(hours)
        ? Number(hours)
        : NaN;
    const fields = Object.fromEntries(
      Object.entries(text).map(([key, value]) => [
        key,
        value
          .split("\n")
          .map((v) => v.trim())
          .filter(Boolean),
      ]),
    ) as Pick<AuctionProfile, "locations" | "keywords" | "brands">;
    if (
      !config.name.trim() ||
      !config.categories.length ||
      amount === undefined ||
      (reminder !== null &&
        (!Number.isInteger(reminder) || reminder < 1 || reminder > 720)) ||
      Object.values(fields).some(
        (values) =>
          values.length > 30 || values.some((v: string) => v.length > 160),
      )
    ) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    const configuration: AuctionProfile = {
      ...config,
      ...fields,
      maximum_price_chf_cents: amount,
      notify: { ...config.notify, ending_soon_hours: reminder },
    };
    const body = JSON.stringify(configuration);
    if (!request.current || request.current.body !== body)
      request.current = { body, key: crypto.randomUUID() };
    void mutation.run<AuctionMonitor>(
      row ? `/monitors/${row.id}` : "/monitors",
      row
        ? { configuration, expected_version: row.version }
        : { configuration, request_key: request.current.key },
      saved,
      row ? "PATCH" : "POST",
    );
  }
  return (
    <form
      data-auction-form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <fieldset disabled={mutation.busy}>
        <legend>{row ? c.edit : c.create}</legend>
        <MonitoringConfigurationDraft
          domain="auctions"
          configuration={draftConfiguration}
          disabled={
            mutation.busy ||
            Number.isNaN(draftConfiguration.maximum_price_chf_cents) ||
            Number.isNaN(draftConfiguration.notify.ending_soon_hours)
          }
          context={row?.id}
          onUse={(value) => {
            setConfig(value);
            setBudget(
              value.maximum_price_chf_cents === null
                ? ""
                : (value.maximum_price_chf_cents / 100).toFixed(2),
            );
            setHours(value.notify.ending_soon_hours?.toString() || "");
            setText({
              locations: value.locations.join("\n"),
              keywords: value.keywords.join("\n"),
              brands: value.brands.join("\n"),
            });
            setInvalid(false);
          }}
        />
        <label>
          {c.portfolio}
          <input
            required
            maxLength={120}
            value={config.name}
            onChange={(e) => setConfig({ ...config, name: e.target.value })}
          />
        </label>
        <fieldset>
          <legend>{c.categories}</legend>
          {auctionCategories.map((category) => (
            <label className={styles.check} key={category}>
              <input
                type="checkbox"
                checked={config.categories.includes(category)}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    categories: e.target.checked
                      ? [...config.categories, category]
                      : config.categories.filter((v) => v !== category),
                  })
                }
              />
              {c[category]}
            </label>
          ))}
        </fieldset>
        <p>{c.geography}</p>
        {(["locations", "keywords", "brands"] as const).map((field) => (
          <label key={field}>
            {c[field]}
            <textarea
              rows={3}
              maxLength={4830}
              value={text[field]}
              onChange={(e) => setText({ ...text, [field]: e.target.value })}
            />
          </label>
        ))}
        <p>{c.lines}</p>
        <label>
          {c.budget}
          <input
            inputMode="decimal"
            maxLength={18}
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
          />
        </label>
        <label>
          {c.priceKind}
          <select
            value={config.budget_price_kind}
            onChange={(e) =>
              setConfig({
                ...config,
                budget_price_kind: e.target
                  .value as AuctionProfile["budget_price_kind"],
              })
            }
          >
            {auctionPriceKinds.map((kind) => (
              <option value={kind} key={kind}>
                {c[kind]}
              </option>
            ))}
          </select>
        </label>
        <fieldset>
          <legend>{c.notices}</legend>
          {auctionNotices.map((key) => (
            <label className={styles.check} key={key}>
              <input
                type="checkbox"
                checked={config.notify[key]}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    notify: { ...config.notify, [key]: e.target.checked },
                  })
                }
              />
              {c[key]}
            </label>
          ))}
          <label>
            {c.reminder}
            <input
              inputMode="numeric"
              maxLength={3}
              value={hours}
              onChange={(e) => setHours(e.target.value)}
            />
          </label>
        </fieldset>
        <p>{c.assessment}</p>
        <p>{c.settingsOnly}</p>
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
function Facts({ config }: { config: AuctionProfile }) {
  const { locale } = useI18n(),
    c = auctionCopy[locale];
  return (
    <div data-auction-facts>
      <dl>
        <dt>{c.categories}</dt>
        <dd>{config.categories.map((v) => c[v]).join(", ")}</dd>
        <dt>{c.geography}</dt>
        <dd>{config.cantons.join(", ")}</dd>
        {(["locations", "keywords", "brands"] as const).map((field) => (
          <div key={field}>
            <dt>{c[field]}</dt>
            <dd>{config[field].join("; ") || c.none}</dd>
          </div>
        ))}
        <dt>{c.budget}</dt>
        <dd>
          {config.maximum_price_chf_cents === null
            ? c.none
            : new Intl.NumberFormat(locale === "rm-CH" ? "de-CH" : locale, {
                style: "currency",
                currency: "CHF",
              }).format(config.maximum_price_chf_cents / 100)}
        </dd>
        <dt>{c.priceKind}</dt>
        <dd>{c[config.budget_price_kind]}</dd>
        <dt>{c.reminder}</dt>
        <dd>{config.notify.ending_soon_hours ?? c.none}</dd>
        <dt>{c.notices}</dt>
        <dd>
          {auctionNotices
            .filter((key) => config.notify[key])
            .map((key) => c[key])
            .join("; ") || c.none}
        </dd>
      </dl>
      <p>{c.settingsOnly}</p>
    </div>
  );
}

function History({ id }: { id: string }) {
  const { locale } = useI18n(),
    c = auctionCopy[locale];
  const [anchors, setAnchors] = useState<(number | null)[]>([null]);
  const before = anchors.at(-1),
    result = useData<
      AuctionPage<{ revision: number; configuration: AuctionProfile }>
    >(`/monitors/${id}/revisions?limit=5${before ? `&before=${before}` : ""}`);
  return (
    <section data-auction-history>
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
  const params = useSearchParams();
  const onAccessFailure = useContext(Failure);
  const reminders = params.getAll("reminder");
  const reminder =
    params.get("monitor") === id &&
    reminders.length === 1 &&
    /^[0-9a-f-]{36}$/i.test(reminders[0])
      ? reminders[0]
      : null;
  const events = params.getAll("event");
  const event =
    params.get("monitor") === id &&
    events.length === 1 &&
    /^[0-9a-f-]{36}$/i.test(events[0])
      ? events[0]
      : null;
  const { session } = useAuth();
  const { locale } = useI18n(),
    c = auctionCopy[locale];
  const [revision, setRevision] = useState(0),
    [editing, setEditing] = useState(false),
    [history, setHistory] = useState(false),
    [confirm, setConfirm] = useState(false);
  const result = useData<AuctionMonitor>(`/monitors/${id}`, revision),
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
      <ProfileForm
        key={row.version}
        row={row}
        saved={reload}
        cancel={() => setEditing(false)}
      />
    );
  return (
    <section data-auction-detail>
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
      {event && (
        <AuctionChange
          key={`${event}:${row.version}`}
          monitor={row}
          event={event}
          canManage={canManage}
        />
      )}
      <AuctionTracking
        key={row.version}
        monitor={row}
        canManage={canManage}
        changed={reload}
      />
      {reminder && (
        <AuctionReminder
          key={`${reminder}:${row.version}`}
          monitor={row}
          reminder={reminder}
          canManage={canManage}
        />
      )}
      <AuctionReminders key={`reminders:${row.version}`} monitor={row} />
      <BusinessMonitorAccess
        key={`access:${row.version}`}
        domain="auctions"
        monitor={row}
        changed={reload}
      />
      {row.owner_user_id === session?.user?.id && (
        <AuctionEmail
          key={`email:${row.version}`}
          monitorId={row.id}
          canManage={canManage}
          archived={row.status === "archived"}
          changed={reload}
          onAccessFailure={onAccessFailure}
        />
      )}
      {history && <History key={row.version} id={id} />}
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
    c = auctionCopy[locale];
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
  const list = useData<AuctionPage<AuctionMonitor>>(
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
      <div className={`${styles.root} ${ipStyles.root}`} data-auction-watch>
        <h1>{c.title}</h1>
        <p>{c.intro}</p>
        <p>{businessMonitorCopy[locale].defaultScope}</p>
        <AsteSourceStatus revision={revision} />
        <p className={styles.notice}>
          {auctionTrackingCopy[locale].sourceHelp}
        </p>
        <p>
          <a href="https://www.aste.ti.ch/it/" target="_blank" rel="noreferrer">
            {c.official}
          </a>
        </p>
        {!canManage && <p>{c.readonly}</p>}
        {!allowed || capabilities.error ? (
          <p role="alert">{c.unavailable}</p>
        ) : !capabilities.data ? (
          <p role="status">{c.loading}</p>
        ) : (
          <>
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
                  <ProfileForm
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
        "auction_watch_disabled",
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
export function AuctionWatch() {
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
    return () => {
      document.removeEventListener("visibilitychange", refresh);
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", refresh);
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
      key={`${scope}:${initial}:${visible}:${epoch}`}
      allowed={visible && scope !== "unavailable"}
      canManage={session?.role === "organization_admin"}
      initial={initial}
    />
  );
}
