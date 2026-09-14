"use client";

import {
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { hazardCopy } from "@/lib/hazard-copy";
import { hazardEventCopy } from "@/lib/hazard-event-copy";
import { hazardTarget, type HazardTarget } from "@/lib/hazard-events";
import {
  cantons,
  hazardKinds,
  type HazardCapabilities,
  type HazardConfiguration,
  type HazardMonitor,
  type HazardPreview,
  type Page,
  type Revision,
} from "@/lib/hazard-watch";
import { roadCopy, roadLabel } from "@/lib/road-copy";
import { centreCopy } from "@/lib/monitoring-centre-copy";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import { HazardEvents } from "./hazard-events";
import { HazardLifecycle } from "./hazard-lifecycle";
import { HazardEmail } from "./hazard-email";
import { AccessFailure, useData, useMutation } from "./hazard-data";
import styles from "./commute-watch.module.css";

function Facts({ config }: { config: HazardConfiguration }) {
  const { locale } = useI18n(),
    c = hazardCopy[locale],
    loc = config.location;
  return (
    <dl>
      <dt>{c.canton}</dt>
      <dd>{loc.canton}</dd>
      {loc.kind === "point" ? (
        <>
          <dt>{c.latitude}</dt>
          <dd>{loc.latitude}</dd>
          <dt>{c.longitude}</dt>
          <dd>{loc.longitude}</dd>
          <dt>{c.radius}</dt>
          <dd>{loc.radius_km}</dd>
        </>
      ) : (
        <>
          <dt>{c.municipalityCode}</dt>
          <dd>{loc.municipality_code}</dd>
        </>
      )}
      <dt>{c.hazards}</dt>
      <dd>{config.hazards.map((key) => c[key]).join(", ")}</dd>
      <dt>{c.importance}</dt>
      <dd>{c[config.minimum_importance]}</dd>
    </dl>
  );
}
function LocationPreview({ result }: { result: HazardPreview }) {
  const { locale } = useI18n(),
    c = hazardCopy[locale],
    proof = result.geography;
  const reason = proof?.reason || "boundary_catalogue_not_installed";
  const label =
    proof?.state === "verified"
      ? c.locationVerified
      : reason === "outside_switzerland"
        ? c.locationOutside
        : reason.endsWith("canton_mismatch")
          ? c.locationCantonMismatch
          : reason.includes("border")
            ? c.locationBorder
            : reason === "boundary_version_outside_review"
              ? c.catalogueExpired
              : reason.startsWith("boundary_")
                ? c.catalogueUnavailable
                : c.locationUnknown;
  return (
    <section role="status" aria-label={c.locationCheck}>
      <h3>{c.locationCheck}</h3>
      <p>{label}</p>
      {proof?.municipality_name && (
        <p>
          {c.municipality}: {proof.municipality_name} ({proof.municipality_code}
          )
        </p>
      )}
      {proof?.version && (
        <p>
          {c.catalogueEdition}: {proof.version}
        </p>
      )}
      {proof?.attribution && <p>{proof.attribution}</p>}
      {result.configuration.location.kind === "point" &&
        result.configuration.location.radius_km > 0 && (
          <p>{c.radiusUnverified}</p>
        )}
      <p>{c.pending}</p>
    </section>
  );
}
function Editor({
  row,
  done,
  cancel,
}: {
  row?: HazardMonitor;
  done: (value: HazardMonitor) => void;
  cancel: () => void;
}) {
  const { locale } = useI18n(),
    c = hazardCopy[locale],
    r = roadCopy[locale],
    mutation = useMutation();
  const [kind, setKind] = useState(row?.configuration.location.kind || "point");
  const [hazards, setHazards] = useState(
    row?.configuration.hazards || [...hazardKinds],
  );
  const [preview, setPreview] = useState<HazardPreview | null>(null),
    [error, setError] = useState("");
  const requestKey = useRef<string | null>(null),
    loc = row?.configuration.location;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPreview(null);
    if (!hazards.length) {
      setError(c.required);
      return;
    }
    const form = new FormData(event.currentTarget),
      common = { country: "CH" as const, canton: String(form.get("canton")) };
    const config: HazardConfiguration = {
      template_id: "hazard-watch",
      template_version: 1,
      name: String(form.get("name")),
      hazards,
      minimum_importance: String(
        form.get("importance"),
      ) as HazardConfiguration["minimum_importance"],
      location:
        kind === "point"
          ? {
              ...common,
              kind: "point",
              latitude: Number(form.get("latitude")),
              longitude: Number(form.get("longitude")),
              radius_km: Number(form.get("radius")),
            }
          : {
              ...common,
              kind: "municipality",
              municipality_code: String(form.get("municipality")),
            },
    };
    const action = (event.nativeEvent as SubmitEvent).submitter?.getAttribute(
      "value",
    );
    if (action === "preview") {
      void mutation.run<HazardPreview>(
        "/preview",
        { configuration: config },
        setPreview,
      );
      return;
    }
    requestKey.current ??= crypto.randomUUID();
    void mutation.run<HazardMonitor>(
      row ? `/monitors/${row.id}` : "/monitors",
      {
        configuration: config,
        ...(row
          ? { expected_version: row.version }
          : { request_key: requestKey.current }),
      },
      done,
      row ? "PATCH" : "POST",
    );
  }
  return (
    <form
      className={styles.card}
      onSubmit={submit}
      onChange={() => setPreview(null)}
    >
      <h2>{row ? r.edit : c.create}</h2>
      <fieldset disabled={mutation.busy}>
        <label>
          {c.name}
          <input
            name="name"
            required
            maxLength={100}
            defaultValue={row?.configuration.name || ""}
          />
        </label>
        <label>
          {c.canton}
          <select name="canton" required defaultValue={loc?.canton || ""}>
            <option value="">{c.choose}</option>
            {cantons.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          {c.point} / {c.municipality}
          <select
            value={kind}
            onChange={(event) => setKind(event.target.value as typeof kind)}
          >
            <option value="point">{c.point}</option>
            <option value="municipality">{c.municipality}</option>
          </select>
        </label>
        {kind === "point" ? (
          <div className={styles.fields}>
            <label>
              {c.latitude}
              <input
                name="latitude"
                type="number"
                step="any"
                required
                min={44}
                max={49}
                defaultValue={loc?.kind === "point" ? loc.latitude : ""}
              />
            </label>
            <label>
              {c.longitude}
              <input
                name="longitude"
                type="number"
                step="any"
                required
                min={4}
                max={12}
                defaultValue={loc?.kind === "point" ? loc.longitude : ""}
              />
            </label>
            <label>
              {c.radius}
              <input
                name="radius"
                type="number"
                step="any"
                required
                min={0}
                max={50}
                defaultValue={loc?.kind === "point" ? loc.radius_km : 0}
              />
            </label>
          </div>
        ) : (
          <label>
            {c.municipalityCode}
            <input
              name="municipality"
              required
              pattern="[1-9][0-9]{0,3}"
              inputMode="numeric"
              defaultValue={
                loc?.kind === "municipality" ? loc.municipality_code : ""
              }
            />
          </label>
        )}
        <fieldset>
          <legend>{c.hazards}</legend>
          {hazardKinds.map((value) => (
            <label key={value} className={styles.check}>
              <input
                type="checkbox"
                checked={hazards.includes(value)}
                onChange={(event) =>
                  setHazards((values) =>
                    event.target.checked
                      ? [...values, value]
                      : values.filter((v) => v !== value),
                  )
                }
              />
              {c[value]}
            </label>
          ))}
        </fieldset>
        <label>
          {c.importance}
          <select
            name="importance"
            defaultValue={row?.configuration.minimum_importance || "warning"}
          >
            {(["information", "warning", "alarm"] as const).map((value) => (
              <option key={value} value={value}>
                {c[value]}
              </option>
            ))}
          </select>
        </label>
        <div className={styles.actions}>
          <button type="submit" value="preview">
            {r.preview}
          </button>
          <button type="submit" value="save">
            {r.save}
          </button>
          <button type="button" onClick={cancel}>
            {r.cancel}
          </button>
        </div>
      </fieldset>
      {(error || mutation.error) && (
        <p role="alert">{error || mutation.error}</p>
      )}
      {preview && <LocationPreview result={preview} />}
    </form>
  );
}
function History({ id }: { id: string }) {
  const { locale } = useI18n(),
    r = roadCopy[locale];
  const [anchors, setAnchors] = useState<(number | null)[]>([null]);
  const before = anchors[anchors.length - 1];
  const result = useData<Page<Revision>>(
    `/monitors/${id}/revisions?limit=10${before ? `&before=${before}` : ""}`,
  );
  return (
    <section>
      <h3>{r.revisions}</h3>
      {result.error ? (
        <p role="alert">{r.failed}</p>
      ) : !result.data ? (
        <p role="status">{r.loading}</p>
      ) : (
        result.data.items.map((row) => (
          <article key={row.revision} className={styles.card}>
            <h4>
              {r.version} {row.revision} · {row.configuration.name}
            </h4>
            <Facts config={row.configuration} />
          </article>
        ))
      )}
      <div className={styles.actions}>
        {anchors.length > 1 && (
          <button onClick={() => setAnchors((v) => v.slice(0, -1))}>
            {r.previous}
          </button>
        )}
        {result.data?.next_cursor != null && (
          <button
            onClick={() =>
              setAnchors((v) => [...v, Number(result.data!.next_cursor)])
            }
          >
            {r.more}
          </button>
        )}
      </div>
    </section>
  );
}
function Detail({
  id,
  canManage,
  changed,
  removed,
  target,
}: {
  id: string;
  canManage: boolean;
  changed: () => void;
  removed: () => void;
  target: HazardTarget;
}) {
  const { locale } = useI18n(),
    c = hazardCopy[locale],
    r = roadCopy[locale];
  const onAccessFailure = useContext(AccessFailure);
  const [revision, setRevision] = useState(0),
    [editing, setEditing] = useState(false),
    [history, setHistory] = useState(false),
    [confirm, setConfirm] = useState(false);
  const result = useData<HazardMonitor>(`/monitors/${id}`, revision),
    mutation = useMutation(),
    row = result.data;
  const reload = () => {
    setRevision((v) => v + 1);
    setEditing(false);
    setConfirm(false);
    changed();
  };
  if (result.error) return <p role="alert">{r.failed}</p>;
  if (!row) return <p role="status">{r.loading}</p>;
  if (editing && canManage)
    return (
      <Editor
        key={row.version}
        row={row}
        done={reload}
        cancel={() => setEditing(false)}
      />
    );
  return (
    <section className={styles.card}>
      <h2>{row.configuration.name}</h2>
      <p>
        {roadLabel(locale, row.status)} · {r.version} {row.version}
      </p>
      <details open={!target.event}>
        <summary>{hazardEventCopy[locale].placeSettings}</summary>
        <Facts config={row.configuration} />
        <div className={styles.actions}>
          <button disabled={mutation.busy} onClick={reload}>
            {r.refresh}
          </button>
          <button
            disabled={mutation.busy}
            onClick={() => setHistory((v) => !v)}
            aria-expanded={history}
          >
            {r.revisions}
          </button>
          {canManage && (row.status === "draft" || row.status === "paused") && (
            <>
              <button disabled={mutation.busy} onClick={() => setEditing(true)}>
                {r.edit}
              </button>
            </>
          )}
          {canManage && row.status === "archived" && (
            <button disabled={mutation.busy} onClick={() => setConfirm(true)}>
              {c.remove}
            </button>
          )}
        </div>
        {confirm && (
          <div>
            <p>{c.confirmDelete}</p>
            <button
              disabled={mutation.busy}
              onClick={() =>
                void mutation.run(
                  `/monitors/${id}`,
                  { expected_version: row.version },
                  removed,
                  "DELETE",
                )
              }
            >
              {c.remove}
            </button>
            <button disabled={mutation.busy} onClick={() => setConfirm(false)}>
              {r.cancel}
            </button>
          </div>
        )}
        {mutation.error && <p role="alert">{mutation.error}</p>}
        {history && <History key={row.version} id={id} />}
        <HazardLifecycle
          key={row.version}
          row={row}
          canManage={canManage}
          changed={reload}
        />
        <HazardEmail
          key={`email:${row.version}`}
          monitorId={row.id}
          archived={row.status === "archived"}
          canManage={canManage}
          changed={reload}
          onAccessFailure={onAccessFailure}
        />
      </details>
      <HazardEvents
        row={row}
        target={target}
        canManage={canManage}
        changed={reload}
      />
    </section>
  );
}
function Workspace({
  allowed,
  canManage,
  initial,
  initialTarget,
}: {
  allowed: boolean;
  canManage: boolean;
  initial: string;
  initialTarget: HazardTarget;
}) {
  const { locale } = useI18n(),
    c = hazardCopy[locale],
    r = roadCopy[locale];
  const [blocked, setBlocked] = useState(false),
    [selected, selectMonitor] = useState(initial),
    [target, setTarget] = useState(initialTarget),
    [creating, setCreating] = useState(false),
    [revision, setRevision] = useState(0),
    [anchors, setAnchors] = useState<(string | null)[]>([null]);
  const deny = useCallback((error: unknown) => {
    if (
      error instanceof ApiError &&
      [
        "authentication_required",
        "membership_required",
        "subject_role_denied",
        "hazard_watch_disabled",
      ].includes(error.code)
    )
      setBlocked(true);
  }, []);
  return (
    <AccessFailure.Provider value={deny}>
      <View
        {...{
          allowed,
          canManage,
          blocked,
          selected,
          creating,
          revision,
          anchors,
          target,
          setSelected: (value: string) => {
            selectMonitor(value);
            setTarget({ event: "", revision: null, invalid: false });
          },
          setCreating,
          setRevision,
          setAnchors,
          setBlocked,
        }}
        c={c}
        r={r}
      />
    </AccessFailure.Provider>
  );
}
type WorkspaceState = {
  allowed: boolean;
  canManage: boolean;
  blocked: boolean;
  selected: string;
  target: HazardTarget;
  creating: boolean;
  revision: number;
  anchors: (string | null)[];
  setSelected: (value: string) => void;
  setCreating: (value: boolean) => void;
  setRevision: React.Dispatch<React.SetStateAction<number>>;
  setAnchors: React.Dispatch<React.SetStateAction<(string | null)[]>>;
  setBlocked: (value: boolean) => void;
  c: (typeof hazardCopy)["en-CH"];
  r: (typeof roadCopy)["en-CH"];
};
function View(p: WorkspaceState) {
  const { locale } = useI18n(),
    { c, r } = p,
    available = p.allowed && !p.blocked;
  const [sourceTick, setSourceTick] = useState(0);
  useEffect(() => {
    if (!available) return;
    const timer = setInterval(
      () => setSourceTick((value) => value + 1),
      60_000,
    );
    return () => clearInterval(timer);
  }, [available]);
  const capabilities = useData<HazardCapabilities>(
    available ? "/capabilities" : null,
    p.revision + sourceTick,
  );
  const anchor = p.anchors[p.anchors.length - 1];
  const result = useData<Page<HazardMonitor>>(
    available && capabilities.data
      ? `/monitors?limit=20${anchor ? `&after_id=${encodeURIComponent(anchor)}` : ""}`
      : null,
    p.revision,
  );
  const changed = () => p.setRevision((v) => v + 1);
  const reset = () => {
    p.setBlocked(false);
    p.setCreating(false);
    p.setSelected("");
    p.setAnchors([null]);
    changed();
  };
  return (
    <Shell section={c.title}>
      <div className={styles.root} data-hazard-watch>
        <Link href="/monitoring">{centreCopy[locale].title}</Link>
        <h1>{c.title}</h1>
        <p>{c.intro}</p>
        <p className={styles.notice}>{c.pending}</p>
        {available && capabilities.data?.source && (
          <section data-hazard-source aria-label={c.sourceStatus}>
            <h2>{c.sourceStatus}</h2>
            <p>
              {capabilities.data.source.state === "current"
                ? c.sourceCurrent
                : c.sourceWaiting}
            </p>
            {!!capabilities.data.source.supported_hazards.length && (
              <p>
                {c.sourceTypes}:{" "}
                {capabilities.data.source.supported_hazards
                  .map((kind) => c[kind])
                  .join(", ")}
              </p>
            )}
            {capabilities.data.source.attribution && (
              <p>{capabilities.data.source.attribution}</p>
            )}
            {capabilities.data.source.last_poll_at &&
              Number.isFinite(
                Date.parse(capabilities.data.source.last_poll_at),
              ) && (
                <p>
                  {hazardEventCopy[locale].fetched}:{" "}
                  <time dateTime={capabilities.data.source.last_poll_at}>
                    {new Intl.DateTimeFormat(locale, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    }).format(new Date(capabilities.data.source.last_poll_at))}
                  </time>
                </p>
              )}
          </section>
        )}
        <div className={styles.actions}>
          <button disabled={!p.allowed} onClick={reset}>
            {r.refresh}
          </button>
          {available && capabilities.data && p.canManage && (
            <button
              onClick={() => {
                p.setCreating(true);
                p.setSelected("");
              }}
            >
              {c.create}
            </button>
          )}
        </div>
        {p.blocked && <p role="alert">{c.unavailable}</p>}
        {p.target.invalid && !p.selected && (
          <p role="alert">{hazardEventCopy[locale].invalidLink}</p>
        )}
        {!!capabilities.error && <p role="alert">{c.unavailable}</p>}
        {available && !capabilities.error && !capabilities.data && (
          <p role="status">{r.loading}</p>
        )}
        {available && capabilities.data && (
          <div className={styles.layout}>
            <aside className={styles.list} aria-label={c.title}>
              {result.error ? (
                <p role="alert">{r.failed}</p>
              ) : !result.data ? (
                <p role="status">{r.loading}</p>
              ) : result.data.items.length ? (
                result.data.items.map((row) => (
                  <button
                    key={row.id}
                    aria-pressed={p.selected === row.id}
                    onClick={() => {
                      p.setSelected(row.id);
                      p.setCreating(false);
                    }}
                  >
                    {row.configuration.name} · {roadLabel(locale, row.status)}
                  </button>
                ))
              ) : (
                <p>{c.empty}</p>
              )}
              <div className={styles.actions}>
                {p.anchors.length > 1 && (
                  <button onClick={() => p.setAnchors((v) => v.slice(0, -1))}>
                    {r.previous}
                  </button>
                )}
                {result.data?.next_cursor && (
                  <button
                    onClick={() =>
                      p.setAnchors((v) => [
                        ...v,
                        String(result.data!.next_cursor),
                      ])
                    }
                  >
                    {r.more}
                  </button>
                )}
              </div>
            </aside>
            {p.creating && p.canManage ? (
              <Editor
                cancel={() => p.setCreating(false)}
                done={(row) => {
                  p.setCreating(false);
                  p.setSelected(row.id);
                  p.setAnchors([null]);
                  changed();
                }}
              />
            ) : p.selected ? (
              <Detail
                key={p.selected}
                id={p.selected}
                canManage={p.canManage}
                changed={changed}
                removed={reset}
                target={p.target}
              />
            ) : null}
          </div>
        )}
      </div>
    </Shell>
  );
}
export function HazardWatch() {
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
  const value = params.getAll("monitor"),
    initial =
      value.length === 1 &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
        value[0],
      )
        ? value[0]
        : "";
  const target = hazardTarget(params);
  return (
    <Workspace
      key={`${scope}:${initial}:${target.event}:${target.revision}:${target.invalid}:${visible}:${epoch}`}
      allowed={visible && scope !== "unavailable"}
      canManage={session?.role === "organization_admin"}
      initial={initial}
      initialTarget={target}
    />
  );
}
