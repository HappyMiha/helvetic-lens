"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { centreCopy, type TemplateId } from "@/lib/monitoring-centre-copy";
import { monitoringNavigation } from "@/lib/monitoring-navigation";
import { monitoringSettingsCopy } from "@/lib/monitoring-settings-copy";
import { accountCopy } from "@/lib/account-copy";
import { useAuth } from "./auth-gate";
import { EmbeddedMonitoring } from "./embedded-monitoring";
import { Shell } from "./shell";
import { PollenDraftReader } from "./pollen-draft-reader";
import { RiverWatch } from "./river-watch";
import { AirWatch } from "./air-watch";
import { HazardWatch } from "./hazard-watch";
import { CommuteWatch } from "./commute-watch";
import { RoadWatch } from "./road-watch";
import { TenderWatch } from "./tender-watch";
import { TrademarkWatch } from "./trademark-watch";
import { AuctionWatch } from "./auction-watch";
import { MonitoringConfigurationExport } from "./monitoring-configuration-export";

const editors = {
  pollen: PollenDraftReader,
  river: RiverWatch,
  air: AirWatch,
  warnings: HazardWatch,
  commute: CommuteWatch,
  traffic: RoadWatch,
  tenders: TenderWatch,
  ip: TrademarkWatch,
  auctions: AuctionWatch,
};
type Field = {
  id: string;
  kind: string;
  value?: string | number | boolean;
  configured?: boolean;
  minimum?: number;
  maximum?: number;
  choices?: string[];
};
type Result = { checked_at: string; channels: { id: string; state: string }[] };
type Configuration = {
  domain: TemplateId;
  revision: number;
  fields: Field[];
  check: Result | null;
  credential_error?: boolean;
  advanced?: Record<string, unknown>;
};
const secretKind = (kind: string) =>
  ["login", "password", "secret"].includes(kind);

export function MonitoringSettings() {
  const { session } = useAuth(),
    { locale } = useI18n();
  const scope = session?.authenticated
    ? `${session.user?.id}:${session.organization?.id}:${session.role}:${session.platform_admin}:${locale}`
    : "unavailable";
  return <Settings key={scope} allowed={scope !== "unavailable"} />;
}

function Settings({ allowed }: { allowed: boolean }) {
  const { locale } = useI18n(),
    c = monitoringSettingsCopy[locale],
    names = centreCopy[locale];
  const params = useSearchParams();
  const selected = params.get("category");
  const domain: TemplateId =
    monitoringNavigation.find((item) => item.id === selected)?.id || "pollen";
  const [admin, setAdmin] = useState(false),
    [failed, setFailed] = useState(false),
    [visible, setVisible] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    if (allowed)
      api<{ can_configure_connectors: boolean }>("/monitoring-settings", {
        signal: controller.signal,
      })
        .then((value) => {
          if (!controller.signal.aborted)
            setAdmin(value.can_configure_connectors);
        })
        .catch(() => {
          if (!controller.signal.aborted) setFailed(true);
        });
    const hide = () => {
      controller.abort();
      setVisible(false);
      setAdmin(false);
    };
    const show = (event: PageTransitionEvent) => {
      if (event.persisted) window.location.reload();
    };
    window.addEventListener("pageshow", show);
    window.addEventListener("pagehide", hide);
    return () => {
      controller.abort();
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
    };
  }, [allowed]);
  const Editor = editors[domain];
  return (
    <Shell section={c.title}>
      <div data-monitoring-settings className="mx-auto max-w-6xl space-y-6">
        <header className="space-y-3">
          <h1 className="text-3xl font-semibold">{c.title}</h1>
          <p>{c.intro}</p>
          <p>{c.note}</p>
          <Link
            href="/account"
            className="inline-flex min-h-11 items-center underline"
          >
            {accountCopy[locale].title}
          </Link>
        </header>
        <nav
          aria-label={c.category}
          className="grid grid-cols-1 gap-2 sm:grid-cols-3"
        >
          {monitoringNavigation.map((item) => (
            <Link
              key={item.id}
              href={`/monitoring/settings?category=${item.id}`}
              aria-current={domain === item.id ? "page" : undefined}
              className={`min-h-11 rounded-xl border p-3 ${domain === item.id ? "border-emerald-700 bg-emerald-50 font-semibold text-emerald-950" : ""}`}
            >
              {names.templates[item.id][0]}
            </Link>
          ))}
        </nav>
        {failed && <p role="alert">{c.failed}</p>}
        {allowed && visible && (
          <div key={domain} className="space-y-8">
            <MonitoringConfigurationExport domain={domain} />
            <Connector domain={domain} admin={admin} />
            <section aria-label={c.monitors} data-native-settings>
              <EmbeddedMonitoring.Provider value={true}>
                <Suspense fallback={<p>{c.busy}</p>}>
                  <Editor />
                </Suspense>
              </EmbeddedMonitoring.Provider>
            </section>
          </div>
        )}
      </div>
    </Shell>
  );
}

function Connector({ domain, admin }: { domain: TemplateId; admin: boolean }) {
  const { locale } = useI18n(),
    c = monitoringSettingsCopy[locale];
  const [configuration, setConfiguration] = useState<Configuration | null>(
      null,
    ),
    [values, setValues] = useState<Record<string, string | number | boolean>>(
      {},
    ),
    [secrets, setSecrets] = useState<Record<string, string>>({}),
    [modes, setModes] = useState<Record<string, string>>({}),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState<"saved" | "failed" | "">("");
  const controller = useRef<AbortController | null>(null);
  const path = `/admin/monitoring-connectors/${domain}`;
  const reset = useCallback(() => {
    setSecrets({});
    setModes({});
    setValues({});
  }, []);
  const load = useCallback(async () => {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    reset();
    setConfiguration(null);
    setBusy(true);
    setMessage("");
    try {
      const value = await api<Configuration>(path, { signal: request.signal });
      if (!request.signal.aborted) setConfiguration(value);
    } catch {
      if (!request.signal.aborted) setMessage("failed");
    } finally {
      if (!request.signal.aborted) setBusy(false);
    }
  }, [path, reset]);
  useEffect(() => {
    if (admin) void load();
    else {
      reset();
      setConfiguration(null);
    }
    return () => controller.current?.abort();
  }, [admin, load, reset]);
  const dirty =
    Object.keys(values).length > 0 ||
    Object.values(modes).some((mode) => mode !== "keep");
  async function act(check: boolean) {
    if (!configuration) return;
    const request = new AbortController();
    controller.current?.abort();
    controller.current = request;
    setBusy(true);
    setMessage("");
    const changes: Record<string, string> = {};
    for (const [key, mode] of Object.entries(modes))
      if (mode === "clear") changes[key] = "";
      else if (mode === "replace") changes[key] = secrets[key] || "";
    try {
      const result = await api<Configuration | Result>(
        path + (check ? "/check" : ""),
        {
          method: check ? "POST" : "PATCH",
          body: JSON.stringify(
            check
              ? { revision: configuration.revision }
              : { revision: configuration.revision, values, secrets: changes },
          ),
          signal: request.signal,
        },
      );
      if (request.signal.aborted) return;
      if (check)
        setConfiguration({ ...configuration, check: result as Result });
      else {
        setConfiguration(result as Configuration);
        reset();
        setMessage("saved");
      }
    } catch {
      if (!request.signal.aborted) {
        reset();
        setConfiguration(null);
        setMessage("failed");
      }
    } finally {
      if (!request.signal.aborted) setBusy(false);
    }
  }
  function label(field: Field) {
    const id = field.id;
    const channel = id.includes("gtfs_rt")
      ? "GTFS-RT · "
      : id.includes("gtfs_sa")
        ? "Service Alerts · "
        : "";
    if (id === "commute_static_enabled") return c.static;
    if (id.endsWith("_enabled")) return c.enabled;
    if (id.endsWith("_dataset_id")) return c.dataset;
    if (id.endsWith("_cache_max_bytes")) return c.cache;
    if (id.endsWith("_storage_max_bytes")) return c.storage;
    if (id.endsWith("_max_versions")) return c.versions;
    if (field.kind === "permission") return channel + c.permission;
    return (
      channel +
      (field.kind === "login"
        ? c.login
        : field.kind === "password"
          ? c.password
          : c.key)
    );
  }
  function state(value: string) {
    return value === "http_accessible"
      ? c.ready
      : value === "authenticated"
        ? c.authenticated
        : value === "access_denied"
          ? c.denied
          : value === "credentials_required"
            ? c.missing
            : value === "rate_limited"
              ? c.limited
              : value === "unexpected_response"
                ? c.unexpected
                : value === "redirect_not_followed"
                  ? c.redirect
                  : c.unavailable;
  }
  return (
    <section
      className="rounded-xl border p-4 space-y-4"
      data-connector-settings
      aria-labelledby="connector-title"
    >
      <h2 id="connector-title" className="text-xl font-semibold">
        {c.connector}
      </h2>
      {!["commute", "traffic", "ip"].includes(domain) && <p>{c.public}</p>}
      <p>{c.boundary}</p>
      {!admin ? (
        <p>{c.admin}</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-5">
            <button
              className="min-h-11 underline"
              type="button"
              disabled={busy}
              onClick={() => void load()}
            >
              {c.reload}
            </button>
            <Link
              href="/admin/monitoring-sources"
              className="min-h-11 inline-flex items-center underline"
            >
              {c.operations}
            </Link>
          </div>
          {message && (
            <p role={message === "failed" ? "alert" : "status"}>{c[message]}</p>
          )}
          {busy && <p role="status">{c.busy}</p>}
          {configuration && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void act(false);
              }}
              className="space-y-4"
            >
              {configuration.credential_error && (
                <p role="alert">
                  {c.failed} {c.replace}:{" "}
                  {configuration.fields
                    .filter((field) => secretKind(field.kind))
                    .map(label)
                    .join(", ")}
                </p>
              )}
              <fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2">
                {configuration.fields.map((field) => (
                  <div key={field.id} className="min-w-0 space-y-2">
                    {secretKind(field.kind) ? (
                      <fieldset className="space-y-2">
                        <legend>{label(field)}</legend>
                        <p className="text-sm">
                          {field.configured ? c.configured : c.missing}
                        </p>
                        <select
                          aria-label={`${label(field)} · ${c.replace}`}
                          value={modes[field.id] || "keep"}
                          className="w-full min-h-11 border rounded p-2"
                          onChange={(event) => {
                            setModes({
                              ...modes,
                              [field.id]: event.target.value,
                            });
                            setSecrets({ ...secrets, [field.id]: "" });
                          }}
                        >
                          <option value="keep">{c.keep}</option>
                          <option value="replace">{c.replace}</option>
                          <option value="clear">{c.clear}</option>
                        </select>
                        {modes[field.id] === "replace" && (
                          <label className="grid gap-2">
                            {c.value}
                            <input
                              data-credential={field.id}
                              autoComplete="new-password"
                              spellCheck={false}
                              type="password"
                              required
                              maxLength={
                                field.kind === "login"
                                  ? 320
                                  : field.kind === "password"
                                    ? 4096
                                    : 8192
                              }
                              className="w-full min-h-11 border rounded p-2"
                              value={secrets[field.id] || ""}
                              onChange={(event) =>
                                setSecrets({
                                  ...secrets,
                                  [field.id]: event.target.value,
                                })
                              }
                            />
                          </label>
                        )}
                      </fieldset>
                    ) : (
                      <label className="grid gap-2">
                        {label(field)}
                        {field.kind === "boolean" ? (
                          <input
                            className="h-6 w-6"
                            type="checkbox"
                            checked={Boolean(values[field.id] ?? field.value)}
                            onChange={(event) =>
                              setValues({
                                ...values,
                                [field.id]: event.target.checked,
                              })
                            }
                          />
                        ) : field.kind === "permission" && field.choices ? (
                          <select
                            className="w-full min-h-11 border rounded p-2"
                            value={String(
                              values[field.id] ?? field.value ?? "",
                            )}
                            onChange={(event) =>
                              setValues({
                                ...values,
                                [field.id]: event.target.value,
                              })
                            }
                          >
                            <option value="">{c.automatic}</option>
                            {field.choices.map((choice) => (
                              <option key={choice} value={choice}>
                                {choice}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <input
                            className="w-full min-h-11 border rounded p-2"
                            type={field.kind === "integer" ? "number" : "text"}
                            min={field.minimum}
                            max={field.maximum}
                            maxLength={100}
                            required={field.kind === "integer"}
                            value={String(
                              values[field.id] ?? field.value ?? "",
                            )}
                            onChange={(event) =>
                              setValues({
                                ...values,
                                [field.id]:
                                  field.kind === "integer"
                                    ? Number(event.target.value)
                                    : event.target.value,
                              })
                            }
                          />
                        )}
                      </label>
                    )}
                  </div>
                ))}
              </fieldset>
              {dirty && <p>{c.changed}</p>}
              {configuration.advanced &&
                Object.keys(configuration.advanced).length > 0 && (
                  <details>
                    <summary className="min-h-11 cursor-pointer">
                      {c.readOnly}
                    </summary>
                    <pre className="whitespace-pre-wrap break-all text-xs">
                      {JSON.stringify(configuration.advanced, null, 2)}
                    </pre>
                  </details>
                )}
              <div className="flex flex-wrap gap-3">
                {configuration.fields.length > 0 && (
                  <button
                    className="min-h-11 rounded border px-4"
                    disabled={busy || !dirty}
                    type="submit"
                  >
                    {c.save}
                  </button>
                )}
                <button
                  type="button"
                  className="min-h-11 rounded border px-4"
                  disabled={busy || dirty}
                  onClick={() => void act(true)}
                >
                  {c.check}
                </button>
              </div>
              {configuration.check && (
                <div role="status" className="space-y-2">
                  <h3 className="font-semibold">{c.results}</h3>
                  <time dateTime={configuration.check.checked_at}>
                    {new Date(configuration.check.checked_at).toLocaleString(
                      locale,
                    )}
                  </time>
                  <ul>
                    {configuration.check.channels.map((channel) => (
                      <li key={channel.id}>
                        {channel.id === "trip_updates"
                          ? c.tripUpdates + ": "
                          : channel.id === "service_alerts"
                            ? c.serviceAlerts + ": "
                            : ""}
                        {state(channel.state)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </form>
          )}
        </>
      )}
    </section>
  );
}
