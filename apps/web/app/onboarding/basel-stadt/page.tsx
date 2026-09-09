"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/shell";
import { useAuth } from "@/components/auth-gate";
import { ErrorNote, Loading } from "@/components/common";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";
import { baselCopy } from "@/lib/basel-onboarding-copy";
import {
  api,
  errorText,
  invalidateResources,
  resourceScopeEpoch,
  useResource,
} from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import type { MonitoringTopicPlan, MonitoringTopicPreview } from "@/lib/types";

const PACK = "basel-stadt-legislation";
type Preview = MonitoringTopicPreview;

export default function BaselOnboardingPage() {
  const { session } = useAuth();
  const { locale } = useI18n();
  return (
    <Shell section={baselCopy[locale].title}>
      <Guide key={`${session?.user?.id}/${session?.organization?.id}`} />
    </Shell>
  );
}

function Guide() {
  const { locale, t } = useI18n();
  const copy = baselCopy[locale];
  const { canManage } = useAuth();
  const packs = useResource(resources.sourcePacks());
  const pack = packs.data?.items.find((item) => item.id === PACK);
  const [name, setName] = useState(copy.privacy);
  const [terms, setTerms] = useState("Datenschutz, Information");
  const [exclusions, setExclusions] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [saved, setSaved] = useState(false);
  const key = useRef<string | null>(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const values = (s: string) =>
    s
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  const plan: MonitoringTopicPlan = {
    name,
    goal: name,
    concepts: values(terms),
    synonyms: [],
    exclusions: values(exclusions),
    jurisdictions: ["CH-BS"],
    languages: ["de"],
    source_pack_ids: [PACK],
    document_kinds: ["act", "ordinance", "unclassified_document"],
    event_kinds: [
      "created",
      "new_version",
      "amended",
      "repealed",
      "replaced",
      "status_changed",
    ],
    importance_floor: "low",
  };
  function changed() {
    setPreview(null);
    setSaved(false);
    key.current = null;
    setNotice("");
  }
  async function perform(action: "enable" | "collect" | "preview" | "save") {
    if (busy) return;
    const epoch = resourceScopeEpoch("session");
    const current = () =>
      mounted.current && epoch === resourceScopeEpoch("session");
    setBusy(action);
    setError("");
    setNotice("");
    try {
      if (action === "enable") {
        await api(`/source-packs/${PACK}/activate`, { method: "POST" });
        if (current())
          await invalidateResources(
            resources.sourcePacks(),
            resources.onboarding(),
          );
      } else if (action === "collect") {
        await api("/onboarding/basel-stadt/collect", { method: "POST" });
        if (current()) setNotice("queued");
      } else if (action === "preview") {
        const data = await api<Preview>("/monitoring-topics/preview", {
          method: "POST",
          body: JSON.stringify(plan),
        });
        if (current()) setPreview(data);
      } else {
        key.current ||= crypto.randomUUID();
        await api("/monitoring-topics", {
          method: "POST",
          body: JSON.stringify({ ...plan, idempotency_key: key.current }),
        });
        if (current()) {
          setSaved(true);
          setNotice("saved");
          await invalidateResources(
            resources.monitoringTopics(),
            resources.onboarding(),
          );
        }
      }
    } catch (cause) {
      if (current()) {
        setError(errorText(cause));
        if (action === "preview") setPreview(null);
      }
    } finally {
      if (current()) setBusy("");
    }
  }
  return (
    <div
      className="mx-auto w-full max-w-3xl space-y-6 [&_button]:h-auto [&_button]:min-h-11 [&_button]:whitespace-normal"
      data-basel-guide
    >
      <header>
        <h1 className="text-3xl font-semibold">{copy.title}</h1>
        <p className="mt-3 text-muted-foreground">{copy.intro}</p>
      </header>
      <Link className="inline-block min-h-11 py-2 underline" href="/onboarding">
        {copy.back}
      </Link>
      {packs.error && (
        <>
          <ErrorNote message={packs.error} />
          <Button variant="outline" onClick={() => void packs.reload()}>
            {copy.retry}
          </Button>
        </>
      )}
      {!packs.data && !packs.error && <Loading />}
      {pack && (
        <section
          className="rounded-xl border bg-card p-5 space-y-4"
          aria-labelledby="basel-sources"
        >
          <h2 id="basel-sources" className="text-xl font-semibold">
            {copy.sources}
          </h2>
          <p>{pack.description[locale]}</p>
          <p className="text-sm text-muted-foreground">
            {pack.expected_first_data[locale]}
          </p>
          <a
            className="inline-block underline min-h-11 py-2"
            href="https://data.bs.ch/explore/dataset/100354/"
            target="_blank"
            rel="noreferrer"
          >
            {copy.dataset}
          </a>
          {canManage ? (
            <div className="flex flex-wrap gap-3">
              {!pack.subscription.enabled && (
                <Button
                  data-basel-enable
                  disabled={!!busy}
                  onClick={() => void perform("enable")}
                >
                  {copy.enable}
                </Button>
              )}
              {pack.subscription.enabled && (
                <Button
                  data-basel-collect
                  disabled={!!busy}
                  variant="outline"
                  onClick={() => void perform("collect")}
                >
                  {copy.collect}
                </Button>
              )}
            </div>
          ) : (
            <p>{copy.viewer}</p>
          )}
        </section>
      )}
      {pack && (
        <section
          className="rounded-xl border bg-card p-5 space-y-4"
          aria-labelledby="basel-interest"
        >
          <h2 id="basel-interest" className="text-xl font-semibold">
            {copy.interest}
          </h2>
          <p className="text-sm text-muted-foreground">{copy.termsHelp}</p>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() => {
                changed();
                setName(copy.privacy);
                setTerms("Datenschutz, Information");
              }}
            >
              {copy.privacy}
            </Button>
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() => {
                changed();
                setName(copy.building);
                setTerms("Bau, Planung");
              }}
            >
              {copy.building}
            </Button>
          </div>
          <label className="block">
            {copy.name}
            <input
              data-basel-name
              className="mt-1 block min-h-11 w-full rounded-md border bg-background px-3 text-base"
              maxLength={240}
              disabled={!!busy}
              value={name}
              onChange={(e) => {
                changed();
                setName(e.target.value);
              }}
            />
          </label>
          <label className="block">
            {copy.terms}
            <input
              data-basel-terms
              className="mt-1 block min-h-11 w-full rounded-md border bg-background px-3 text-base"
              maxLength={2000}
              disabled={!!busy}
              value={terms}
              onChange={(e) => {
                changed();
                setTerms(e.target.value);
              }}
            />
          </label>
          <label className="block">
            {copy.exclusions}
            <input
              className="mt-1 block min-h-11 w-full rounded-md border bg-background px-3 text-base"
              maxLength={2000}
              disabled={!!busy}
              value={exclusions}
              onChange={(e) => {
                changed();
                setExclusions(e.target.value);
              }}
            />
          </label>
          <Button
            data-basel-preview
            disabled={
              !!busy ||
              !name.trim() ||
              !values(terms).length ||
              !pack.subscription.enabled
            }
            onClick={() => void perform("preview")}
          >
            {copy.preview}
          </Button>
          <p className="text-sm text-muted-foreground">{copy.scope}</p>
          {preview && (
            <div data-basel-results className="space-y-4" aria-live="polite">
              {!preview.items.length && <p>{copy.empty}</p>}
              {!!preview.matching_topics?.items.length && (
                <p>
                  {copy.existing}{" "}
                  <Link className="underline" href="/topics">
                    {copy.manage}
                  </Link>
                </p>
              )}
              {preview.items.map((item) => (
                <article key={item.event_id} className="rounded-lg border p-4">
                  <h3 className="font-semibold">{item.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {copy.matched}:{" "}
                    {item.reason_signals
                      .flatMap(
                        (signal) =>
                          signal.tokens ||
                          signal.values ||
                          (signal.value ? [signal.value] : []),
                      )
                      .join(", ")}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-4">
                    {item.evidence_url && (
                      <Link
                        data-basel-evidence
                        className="inline-block min-h-11 py-2 underline"
                        href={item.evidence_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {copy.evidence}
                      </Link>
                    )}
                    {item.source_url && (
                      <a
                        className="inline-block min-h-11 py-2 underline"
                        href={item.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {copy.source}
                      </a>
                    )}
                  </div>
                </article>
              ))}
              {canManage &&
                !saved &&
                !preview.matching_topics?.items.length && (
                  <Button
                    data-basel-save
                    disabled={!!busy || !preview.items.length}
                    onClick={() => void perform("save")}
                  >
                    {copy.save}
                  </Button>
                )}
            </div>
          )}
        </section>
      )}
      {busy && <p role="status">{t("common.loading")}</p>}
      {error && <ErrorNote message={error} />}
      {notice && (
        <p role="status" data-basel-notice>
          {notice === "queued" ? copy.queued : copy.saved}
        </p>
      )}
      {saved && (
        <div className="flex flex-wrap gap-4">
          <Link className="underline min-h-11 py-2" href="/topics">
            {copy.manage}
          </Link>
          <Link className="underline min-h-11 py-2" href="/digests">
            {copy.notifications}
          </Link>
        </div>
      )}
    </div>
  );
}
