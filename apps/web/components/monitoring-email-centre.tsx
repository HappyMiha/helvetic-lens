"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { centreCopy, type TemplateId } from "@/lib/monitoring-centre-copy";
import { monitoringEmailCentreCopy } from "@/lib/monitoring-email-centre-copy";
import { riverCopy } from "@/lib/river-copy";
import { monitoringNavigation } from "@/lib/monitoring-navigation";
import { Shell } from "./shell";
import { useAuth } from "./auth-gate";
import { PollenEmail } from "./pollen-email";
import { RiverEmail } from "./river-email";
import { AirEmail } from "./air-email";
import { HazardEmail } from "./hazard-email";
import { CommuteEmail } from "./commute-email";
import { RoadEmail } from "./road-email";
import { TenderEmail } from "./tender-email";
import { TrademarkEmail } from "./trademark-email";
import { AuctionEmail } from "./auction-email";

type Monitor = {
  id: string;
  domain: TemplateId;
  name: string | null;
  station_id: string | null;
  status: string;
  href: string | null;
};
type Page = { items: Monitor[]; next_cursor: string | null };
const editors = {
  pollen: PollenEmail,
  river: RiverEmail,
  air: AirEmail,
  warnings: HazardEmail,
  commute: CommuteEmail,
  traffic: RoadEmail,
  tenders: TenderEmail,
  ip: TrademarkEmail,
  auctions: AuctionEmail,
};
export function MonitoringEmailCentre() {
  const { session } = useAuth(),
    { locale } = useI18n();
  const scope = session?.authenticated
    ? `${session.user?.id}:${session.organization?.id}:${session.role}:${locale}`
    : "unavailable";
  return (
    <Centre
      key={scope}
      allowed={scope !== "unavailable"}
      canManage={session?.role === "organization_admin"}
    />
  );
}
function Centre({
  allowed,
  canManage,
}: {
  allowed: boolean;
  canManage: boolean;
}) {
  const { locale, t } = useI18n(),
    c = monitoringEmailCentreCopy[locale],
    r = riverCopy[locale],
    names = centreCopy[locale];
  const [domain, setDomain] = useState(""),
    [page, setPage] = useState<Page | null>(null),
    [selected, setSelected] = useState<Monitor | null>(null),
    [busy, setBusy] = useState(false),
    [failed, setFailed] = useState(false);
  const request = useRef<AbortController | null>(null),
    title = useRef<HTMLHeadingElement | null>(null);
  const load = useCallback(
    async (cursor?: string) => {
      if (!allowed) return;
      request.current?.abort();
      const controller = new AbortController();
      request.current = controller;
      setBusy(true);
      setFailed(false);
      const query = new URLSearchParams({ limit: "30" });
      if (domain) query.set("domain", domain);
      if (cursor) query.set("cursor", cursor);
      try {
        const value = await api<Page>(`/monitoring-centre?${query}`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setPage((old) => ({
          ...value,
          items:
            cursor && old
              ? [
                  ...old.items,
                  ...value.items.filter(
                    (item) =>
                      !old.items.some(
                        (row) =>
                          row.id === item.id && row.domain === item.domain,
                      ),
                  ),
                ]
              : value.items,
        }));
      } catch {
        if (!controller.signal.aborted) {
          setPage(null);
          setSelected(null);
          setFailed(true);
        }
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    },
    [allowed, domain],
  );
  useEffect(() => {
    setPage(null);
    setSelected(null);
    void load();
    const hide = () => {
      request.current?.abort();
      setPage(null);
      setSelected(null);
    };
    const show = (event: PageTransitionEvent) => {
      if (event.persisted) void load();
    };
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    return () => {
      request.current?.abort();
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
    };
  }, [load]);
  useEffect(() => {
    if (selected) title.current?.focus();
  }, [selected?.id, selected?.domain]);
  const denied = useCallback((problem: unknown) => {
    if (
      problem instanceof ApiError &&
      /authentication_required|membership|forbidden|not_found|role_denied|not_enabled/.test(
        problem.code,
      )
    ) {
      setSelected(null);
      setPage(null);
      setFailed(true);
    }
  }, []);
  const changed = useCallback(() => {
    /* Native editor reloads its exact saved consent revision. */
  }, []);
  const Editor = selected ? editors[selected.domain] : null;
  return (
    <Shell section={c.title}>
      <div data-monitoring-email-centre className="mx-auto max-w-5xl space-y-6">
        <header className="space-y-3">
          <h1 className="text-3xl font-semibold">{c.title}</h1>
          <p>{c.note}</p>
          <p>{c.boundary}</p>
          <div className="flex gap-5">
            <Link
              className="min-h-11 inline-flex items-center underline"
              href="/monitoring"
            >
              {names.title}
            </Link>
            <Link
              className="min-h-11 inline-flex items-center underline"
              href="/digests"
            >
              {t("nav.digests")}
            </Link>
          </div>
        </header>
        {!canManage && <p>{r.readonly}</p>}
        {!allowed && <p role="alert">{r.access_unavailable}</p>}
        {failed && <p role="alert">{r.failed}</p>}
        <div className="flex flex-wrap gap-4 items-end">
          <label className="grid gap-2">
            {names.domain}
            <select
              data-email-domain
              className="min-h-11 border rounded p-2"
              value={domain}
              onChange={(event) => {
                setSelected(null);
                setPage(null);
                setDomain(event.target.value);
              }}
            >
              <option value="">{names.all}</option>
              {monitoringNavigation.map((item) => (
                <option key={item.id} value={item.id}>
                  {names.templates[item.id][0]}
                </option>
              ))}
            </select>
          </label>
          <button
            className="min-h-11 underline"
            disabled={!allowed || busy}
            onClick={() => {
              setSelected(null);
              void load();
            }}
          >
            {r.refresh}
          </button>
        </div>
        {busy && <p role="status">{r.loading}</p>}
        <section aria-labelledby="email-monitor-choice">
          <h2 id="email-monitor-choice" className="text-xl font-semibold mb-3">
            {c.select}
          </h2>
          {page?.items.length === 0 && <p role="status">{names.empty}</p>}
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {page?.items.map((row) => (
              <li key={`${row.domain}:${row.id}`}>
                <button
                  data-email-monitor={row.domain + ":" + row.id}
                  className="w-full min-h-11 border rounded-lg p-3 text-left"
                  aria-pressed={
                    selected?.id === row.id && selected?.domain === row.domain
                  }
                  onClick={() => setSelected(row)}
                >
                  <strong className="block">
                    {row.name ||
                      row.station_id ||
                      names.templates[row.domain][0]}
                  </strong>
                  <span>{names.templates[row.domain][0]}</span>
                </button>
              </li>
            ))}
          </ul>
          {page?.next_cursor && (
            <button
              className="min-h-11 underline"
              disabled={busy}
              onClick={() => void load(page.next_cursor!)}
            >
              {r.more}
            </button>
          )}
        </section>
        {selected && Editor && (
          <section
            key={`${selected.domain}:${selected.id}`}
            data-email-editor
            className="border rounded-xl p-4 space-y-4"
          >
            <h2 ref={title} tabIndex={-1} className="text-xl font-semibold">
              {selected.name ||
                selected.station_id ||
                names.templates[selected.domain][0]}{" "}
              · {names.templates[selected.domain][0]}
            </h2>
            <button
              className="min-h-11 underline"
              onClick={() => {
                setSelected(null);
                document
                  .querySelector<HTMLButtonElement>(
                    `[data-email-monitor="${selected.domain}:${selected.id}"]`,
                  )
                  ?.focus();
              }}
            >
              {c.close}
            </button>
            <Editor
              monitorId={selected.id}
              canManage={canManage}
              archived={selected.status === "archived"}
              changed={changed}
              onAccessFailure={denied}
            />
            {selected.href && (
              <Link
                className="min-h-11 inline-flex items-center underline"
                href={selected.href}
              >
                {names.open}
              </Link>
            )}
          </section>
        )}
      </div>
    </Shell>
  );
}
