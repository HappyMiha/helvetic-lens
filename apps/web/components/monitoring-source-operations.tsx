"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { centreCopy, type TemplateId } from "@/lib/monitoring-centre-copy";
import { sourceOperationsCopy } from "@/lib/source-operations-copy";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";

type Acquisition = {
  state: string;
  record_count: number;
  never_succeeded_count: number | null;
  error_count: number | null;
  oldest_success_at: string | null;
  latest_success_at: string | null;
  source_published_at: string | null;
  next_request_at: string | null;
};
type Channel = {
  id: string;
  collector: string;
  access: { state: string; expires_at: string | null };
  acquisition: Acquisition;
};
type Source = Channel & {
  id: TemplateId;
  pack: string;
  href: string;
  section_enabled: boolean;
  channels?: Channel[];
};
type Snapshot = {
  checked_at: string;
  release: string;
  packs: string[];
  items: Source[];
};

function Evidence({ channel }: { channel: Channel }) {
  const { locale, dateTime } = useI18n(),
    c = sourceOperationsCopy[locale];
  const label = (value: string) =>
    c[(value === "errors" ? "errors_state" : value) as keyof typeof c] ||
    c.unknown;
  const time = (value: string | null) => (value ? dateTime(value) : c.unknown);
  const a = channel.acquisition;
  const fields = [
    [c.collector, label(channel.collector)],
    [c.access, label(channel.access.state)],
    [c.expires, time(channel.access.expires_at)],
    [c.acquisition, label(a.state)],
    [c.records, String(a.record_count)],
    [c.errors, a.error_count === null ? c.unknown : String(a.error_count)],
    [
      c.never,
      a.never_succeeded_count === null
        ? c.unknown
        : String(a.never_succeeded_count),
    ],
    [c.oldest, time(a.oldest_success_at)],
    [c.latest, time(a.latest_success_at)],
    [c.published, time(a.source_published_at)],
    [c.next, time(a.next_request_at)],
  ];
  return (
    <dl className="grid gap-3 mt-4">
      {fields.map(([name, value]) => (
        <div key={name} className="min-w-0">
          <dt className="text-sm muted">{name}</dt>
          <dd className="break-words">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function MonitoringSourceOperations() {
  const { session, isPlatformAdmin } = useAuth();
  return (
    <Reader
      key={`${session?.user?.id}:${isPlatformAdmin}`}
      allowed={isPlatformAdmin}
    />
  );
}
function Reader({ allowed }: { allowed: boolean }) {
  const { locale, dateTime } = useI18n(),
    c = sourceOperationsCopy[locale];
  const [data, setData] = useState<Snapshot | null>(null),
    [error, setError] = useState(false);
  const [revision, setRevision] = useState(0),
    [visible, setVisible] = useState(true);
  useEffect(() => {
    const hide = () => {
      setData(null);
      setVisible(false);
    };
    const show = () => {
      setVisible(true);
      setRevision((v) => v + 1);
    };
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    return () => {
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
    };
  }, []);
  useEffect(() => {
    setData(null);
    setError(false);
    if (!allowed || !visible) return;
    const abort = new AbortController();
    api<Snapshot>("/admin/monitoring-sources", { signal: abort.signal })
      .then((value) => {
        if (!abort.signal.aborted) setData(value);
      })
      .catch(() => {
        if (!abort.signal.aborted) {
          setData(null);
          setError(true);
        }
      });
    return () => abort.abort();
  }, [allowed, visible, revision]);
  return (
    <Shell section={c.title} wide>
      <div data-monitoring-source-operations>
        <header className="page-heading">
          <div>
            <h1>{c.title}</h1>
            <p>{c.body}</p>
          </div>
          {allowed && (
            <button
              className="button"
              onClick={() => setRevision((v) => v + 1)}
            >
              {c.refresh}
            </button>
          )}
        </header>
        {!allowed ? (
          <p role="alert">{c.denied}</p>
        ) : error ? (
          <p role="alert">{c.failed}</p>
        ) : !data ? (
          <p role="status">{c.loading}</p>
        ) : (
          <>
            <p className="mb-4">{c.boundary}</p>
            <p>
              {c.checked}: {dateTime(data.checked_at)} · {c.release}:{" "}
              <span className="break-all">{data.release}</span>
            </p>
            {data.packs.map((pack) => (
              <section key={pack} className="mt-6" data-source-pack={pack}>
                <h2>{c[pack as keyof typeof c] || c.unknown}</h2>
                <div className="grid gap-4 mt-3 md:grid-cols-2">
                  {data.items
                    .filter((item) => item.pack === pack)
                    .map((item) => (
                      <article
                        className="card p-5 min-w-0"
                        key={item.id}
                        data-source-direction={item.id}
                      >
                        <h3>{centreCopy[locale].templates[item.id][0]}</h3>
                        <p>
                          {c.section}:{" "}
                          {item.section_enabled ? c.enabled : c.disabled}
                        </p>
                        <Link className="underline" href={item.href}>
                          {c.open}
                        </Link>
                        {item.channels ? (
                          item.channels.map((channel) => (
                            <section key={channel.id} className="mt-4">
                              <h4>
                                {c[channel.id as keyof typeof c] || c.unknown}
                              </h4>
                              <Evidence channel={channel} />
                            </section>
                          ))
                        ) : (
                          <Evidence channel={item} />
                        )}
                      </article>
                    ))}
                </div>
              </section>
            ))}
          </>
        )}
      </div>
    </Shell>
  );
}
