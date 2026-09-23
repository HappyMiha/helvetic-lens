"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  FileDown,
  Plus,
  Radar,
  Save,
  Sparkles,
} from "lucide-react";
import {
  api,
  errorText,
  invalidateResources,
  resourceTag,
  useResource,
} from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { useI18n } from "@/lib/i18n";
import { legalProfilesCopy } from "@/lib/legal-profiles-copy";
import {
  emptyLegalProfile,
  legalProfileResource,
  type LegalProfile,
  type LegalProfileConfig,
  type LegalProfilePage,
  type LegalTopicCard,
  type LegalSourceRequest,
  type LegalPreview,
} from "@/lib/legal-profiles";
import type { SourcePackCatalogue } from "@/lib/types";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import { ErrorNote, Loading, Status, SuccessNote } from "./common";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { TopicPreviewCoverage } from "./topic-preview-coverage";
import { TopicSourceReadiness } from "./topic-source-readiness";
import { TopicSavedMatches } from "./topic-match-review";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-2 text-sm font-medium">
      {label}
      {children}
    </label>
  );
}
function invalidateProfiles() {
  return invalidateResources(
    ...[
      "legal-profiles",
      "topics",
      "source-packs",
      "digests",
      "impact-inbox",
      "onboarding",
      "monitoring",
    ].map((tag) => resourceTag(tag, "organization")),
  );
}
function safeLink(value: string | null | undefined) {
  if (!value) return null;
  try {
    const url = new URL(value, window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

export function LegalProfilesPage({
  profileId,
  create = false,
}: {
  profileId?: string;
  create?: boolean;
}) {
  const { locale } = useI18n();
  const { session, canManage } = useAuth();
  const c = legalProfilesCopy[locale];
  const identity = `${session?.organization?.id || ""}:${session?.user?.id || ""}`;
  return (
    <Shell section={c.title} wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{c.title}</span>
          <h1>{create ? c.new : c.title}</h1>
          <p className="muted m-0 max-w-2xl">{c.intro}</p>
        </div>
        {!create && !profileId && canManage && (
          <Button asChild>
            <Link href="/monitoring-profiles/new">
              <Plus />
              {c.new}
            </Link>
          </Button>
        )}
      </div>
      <ProfileContent
        key={`${identity}:${profileId || (create ? "new" : "list")}`}
        identity={identity}
        profileId={profileId}
        create={create}
      />
    </Shell>
  );
}

function ProfileContent({
  identity,
  profileId,
  create,
}: {
  identity: string;
  profileId?: string;
  create: boolean;
}) {
  const { locale, dateTime } = useI18n();
  const { canManage } = useAuth();
  const c = legalProfilesCopy[locale];
  const [offset, setOffset] = useState(0);
  const profiles = useResource(
    legalProfileResource<LegalProfilePage>(identity, `?offset=${offset}`),
  );
  const detail = useResource(
    profileId
      ? legalProfileResource<LegalProfile>(identity, `/${profileId}`)
      : null,
  );
  // The catalogue carries every locale. Changing UI language must not replace
  // this resource with an empty snapshot and unmount an unsaved wizard.
  const packs = useResource({
    ...resources.sourcePacks(),
    id: "legal-profiles:source-packs",
    varyByLocale: false,
  });
  if (profiles.error || detail.error || packs.error)
    return (
      <>
        <ErrorNote message={profiles.error || detail.error || packs.error} />
        <Button
          onClick={() => {
            void profiles.reload();
            void detail.reload();
            void packs.reload();
          }}
        >
          {c.open}
        </Button>
      </>
    );
  if (!profiles.data || !packs.data || (profileId && !detail.data))
    return <Loading />;
  if (create || detail.data?.status === "draft")
    return canManage ? (
      <ProfileWizard
        initial={detail.data}
        catalogue={packs.data}
        delivery={profiles.data}
        onActivated={(row) => {
          detail.setData(row);
          void invalidateProfiles();
        }}
      />
    ) : (
      <p className="card p-5">{c.viewer}</p>
    );
  if (detail.data)
    return (
      <ActiveProfile
        profile={detail.data}
        catalogue={packs.data}
        onChange={detail.setData}
      />
    );
  return (
    <>
      {!canManage && <p className="muted">{c.viewer}</p>}
      {!profiles.data.items.length && (
        <div className="card grid justify-items-start gap-3 p-8">
          <Radar className="text-primary" />
          <p>{c.empty}</p>
          {canManage && (
            <Button asChild>
              <Link href="/monitoring-profiles/new">
                {c.new}
                <ArrowRight />
              </Link>
            </Button>
          )}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {profiles.data.items.map((row) => (
          <article
            key={row.id}
            className="card flex flex-col gap-3 p-5"
            data-legal-profile
          >
            <span className="text-xs font-semibold text-primary">
              {c[row.status]}
            </span>
            <h2 className="break-words">{row.config.name || c.unnamed}</h2>
            <p className="muted m-0">{row.config.sector}</p>
            <p className="line-clamp-3 grow">{row.config.goal}</p>
            <p className="text-xs muted">
              {c.updated}:{" "}
              <time dateTime={row.updated_at}>
                {dateTime(row.updated_at, {
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </time>
            </p>
            <Button asChild variant="outline">
              <Link href={`/monitoring-profiles/${row.id}`}>
                {row.status === "draft" ? c.continue : c.open}
                <ArrowRight />
              </Link>
            </Button>
          </article>
        ))}
      </div>
      {profiles.data.total > profiles.data.limit && (
        <div className="mt-5 flex flex-wrap gap-3">
          <Button
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 50))}
          >
            {c.previousPage}
          </Button>
          <Button
            disabled={offset + 50 >= profiles.data.total}
            onClick={() => setOffset(offset + 50)}
          >
            {c.nextPage}
          </Button>
        </div>
      )}
    </>
  );
}

function ProfileWizard({
  initial,
  catalogue,
  delivery,
  onActivated,
}: {
  initial: LegalProfile | null;
  catalogue: SourcePackCatalogue;
  delivery: LegalProfilePage;
  onActivated: (row: LegalProfile) => void;
}) {
  const router = useRouter();
  const { locale, dateTime } = useI18n();
  const c = legalProfilesCopy[locale];
  const [profile, setProfile] = useState(initial);
  const [config, setConfig] = useState<LegalProfileConfig>(
    () => initial?.config || emptyLegalProfile(),
  );
  const [step, setStep] = useState(initial?.step || 0);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [suggestions, setSuggestions] = useState<LegalTopicCard[]>([]);
  const [preview, setPreview] = useState<LegalPreview | null>(null);
  const [sourceName, setSourceName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceKind, setSourceKind] =
    useState<LegalSourceRequest["kind"]>("signals");
  const creationKey = useRef("");
  const heading = useRef<HTMLHeadingElement>(null);
  const dirty =
    JSON.stringify(config) !==
    JSON.stringify(profile?.config || emptyLegalProfile());
  const changed = dirty || !!sourceName || !!sourceUrl;
  useEffect(() => {
    if (!changed) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const navigation = (event: Event) => {
      if (!window.confirm(c.leave)) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    window.addEventListener("helvetic:before-navigation", navigation);
    return () => {
      window.removeEventListener("beforeunload", warn);
      window.removeEventListener("helvetic:before-navigation", navigation);
    };
  }, [changed, c.leave]);
  useEffect(() => {
    heading.current?.focus();
  }, [step]);
  function update(values: Partial<LegalProfileConfig>) {
    setConfig((old) => ({ ...old, ...values }));
    setNotice("");
    setError("");
    setPreview(null);
  }
  function check(at: number) {
    if (
      at >= 0 &&
      (!config.name.trim() || !config.sector.trim() || !config.goal.trim())
    )
      throw new Error(c.required);
    const selected = config.topics.filter((t) => t.selected);
    if (
      at >= 1 &&
      (!selected.length ||
        selected.some(
          (t) => !t.name.trim() || !t.description.trim() || !t.keywords.length,
        ))
    )
      throw new Error(c.pickTopics);
    if (
      at >= 2 &&
      (!config.source_pack_ids.length ||
        config.source_pack_ids.some(
          (id) => !catalogue.items.some((p) => p.id === id),
        ))
    )
      throw new Error(c.pickSources);
    if (at >= 2 && (sourceName || sourceUrl)) throw new Error(c.invalidSource);
    if (at >= 3 && config.delivery !== "keep" && !config.delivery_consent)
      throw new Error(c.consent);
  }
  async function persist(nextStep = step) {
    creationKey.current ||= crypto.randomUUID();
    const saved = await api<LegalProfile>(
      `/monitoring-profiles${profile ? `/${profile.id}` : ""}`,
      {
        method: profile ? "PUT" : "POST",
        body: JSON.stringify({
          config,
          step: nextStep,
          ...(profile
            ? { expected_revision: profile.revision }
            : { creation_key: creationKey.current }),
        }),
      },
    );
    setProfile(saved);
    setConfig(saved.config);
    setStep(saved.step);
    setNotice(c.saved);
    if (!profile) router.replace(`/monitoring-profiles/${saved.id}`);
    return saved;
  }
  async function run(kind: string, operation: () => Promise<void>) {
    if (busy) return;
    setBusy(kind);
    setError("");
    setNotice("");
    try {
      await operation();
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setBusy("");
    }
  }
  function move(target: number) {
    void run("save", async () => {
      if (target > step) check(step);
      await persist(target);
    });
  }
  function suggest() {
    void run("suggest", async () => {
      check(0);
      const saved = await persist();
      const result = await api<{
        profile: LegalProfile;
        suggestions: LegalTopicCard[];
      }>(`/monitoring-profiles/${saved.id}/suggest`, {
        method: "POST",
        body: JSON.stringify({
          expected_revision: saved.revision,
          feedback: config.feedback,
          locale,
        }),
      });
      setProfile(result.profile);
      setSuggestions(result.suggestions);
    });
  }
  function addSource() {
    try {
      const url = new URL(sourceUrl);
      if (
        !sourceName.trim() ||
        url.protocol !== "https:" ||
        !url.hostname ||
        url.username ||
        url.password
      )
        throw new Error();
      update({
        source_requests: [
          ...config.source_requests,
          {
            id: crypto.randomUUID(),
            label: sourceName.trim(),
            url: url.href,
            kind: sourceKind,
            status: "requested",
          },
        ],
      });
      setSourceName("");
      setSourceUrl("");
    } catch {
      setError(c.invalidSource);
    }
  }
  return (
    <div data-legal-wizard>
      <Link
        href="/monitoring-profiles"
        className="inline-flex min-h-11 items-center gap-2 text-sm mb-4"
        onClick={(event) => {
          if (changed && !window.confirm(c.leave)) event.preventDefault();
        }}
      >
        <ArrowLeft size={16} />
        {c.all}
      </Link>
      <ol className="grid grid-cols-5 gap-1 sm:gap-3 mb-7" aria-label={c.new}>
        {c.steps.map((label, index) => (
          <li
            key={label}
            className={`border-t-4 pt-3 ${index <= step ? "border-primary" : "border-border"}`}
            aria-current={index === step ? "step" : undefined}
          >
            <button
              type="button"
              disabled={!!busy || index > step}
              onClick={() => move(index)}
              className={`min-h-11 w-full text-left text-xs sm:text-sm ${index === step ? "font-bold text-primary" : "text-muted-foreground"}`}
            >
              <span className="block mb-1">
                {index < step ? (
                  <Check size={17} />
                ) : (
                  String(index + 1).padStart(2, "0")
                )}
              </span>
              {label}
            </button>
          </li>
        ))}
      </ol>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_260px]">
        <section className="card p-5 sm:p-8 min-w-0">
          <p className="eyebrow">
            {c.step} {step + 1} / 5
          </p>
          <h2
            ref={heading}
            tabIndex={-1}
            className="mb-6 focus:outline-none text-2xl"
          >
            {c.descriptions[step]}
          </h2>
          <div aria-live="polite">
            <ErrorNote message={error} />
            {notice && <SuccessNote>{notice}</SuccessNote>}
          </div>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (step < 4) move(step + 1);
            }}
          >
            <fieldset disabled={!!busy} className="grid gap-5 min-w-0">
              {step === 0 && (
                <>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {(["client", "organization"] as const).map((value) => (
                      <label
                        className={`rounded-lg border p-4 cursor-pointer flex gap-3 items-center ${config.audience === value ? "border-primary bg-primary/5" : ""}`}
                        key={value}
                      >
                        <input
                          type="radio"
                          name="audience"
                          checked={config.audience === value}
                          onChange={() => update({ audience: value })}
                        />
                        {c[value]}
                      </label>
                    ))}
                  </div>
                  <Field label={c.name}>
                    <Input
                      required
                      maxLength={160}
                      value={config.name}
                      onChange={(event) => update({ name: event.target.value })}
                      autoComplete="off"
                    />
                  </Field>
                  <Field label={c.sector}>
                    <Input
                      required
                      maxLength={160}
                      value={config.sector}
                      onChange={(event) =>
                        update({ sector: event.target.value })
                      }
                    />
                  </Field>
                  <Field label={c.goal}>
                    <textarea
                      required
                      rows={4}
                      maxLength={3000}
                      value={config.goal}
                      onChange={(event) => update({ goal: event.target.value })}
                    />
                  </Field>
                  <p className="muted text-sm m-0">{c.goalHint}</p>
                  <div className="rounded-lg bg-muted p-4 text-sm">
                    <strong>{c.coverage}</strong>
                    <p className="mb-0">{c.coverageHint}</p>
                  </div>
                  <Field label={c.extraJurisdictions}>
                    <Input
                      maxLength={240}
                      value={config.requested_jurisdictions}
                      onChange={(event) =>
                        update({ requested_jurisdictions: event.target.value })
                      }
                    />
                  </Field>
                </>
              )}
              {step === 1 && (
                <>
                  <p className="muted m-0">{c.topicsHint}</p>
                  <div className="rounded-lg bg-muted/50 border p-4 grid gap-3">
                    <Field label={c.feedback}>
                      <textarea
                        rows={2}
                        maxLength={2000}
                        value={config.feedback}
                        onChange={(event) =>
                          update({ feedback: event.target.value })
                        }
                      />
                    </Field>
                    <p className="text-xs muted m-0">{c.aiNotice}</p>
                    <Button type="button" variant="outline" onClick={suggest}>
                      <Sparkles size={16} />
                      {busy === "suggest" ? c.suggesting : c.suggest}
                    </Button>
                  </div>
                  {!!suggestions.length && (
                    <section className="rounded-lg border border-primary p-4">
                      <h3>{c.suggestions}</h3>
                      <ul className="list-disc pl-5">
                        {suggestions.map((card) => (
                          <li key={card.id}>
                            <strong>{card.name}</strong>
                            <p>{card.description}</p>
                          </li>
                        ))}
                      </ul>
                      <p className="text-sm muted">{c.replaceHint}</p>
                      <Button
                        type="button"
                        onClick={() => {
                          update({ topics: suggestions });
                          setSuggestions([]);
                        }}
                      >
                        {c.apply}
                      </Button>
                    </section>
                  )}
                  {config.topics.map((card) => (
                    <TopicCardEditor
                      key={card.id}
                      card={card}
                      onChange={(changedCard) =>
                        update({
                          topics: config.topics.map((t) =>
                            t.id === card.id ? changedCard : t,
                          ),
                        })
                      }
                      onRemove={() =>
                        update({
                          topics: config.topics.filter((t) => t.id !== card.id),
                        })
                      }
                    />
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    disabled={config.topics.length >= 6}
                    onClick={() =>
                      update({
                        topics: [
                          ...config.topics,
                          {
                            id: crypto.randomUUID(),
                            selected: true,
                            name: "",
                            description: "",
                            keywords: [],
                            reference_note: "",
                          },
                        ],
                      })
                    }
                  >
                    <Plus />
                    {c.manual}
                  </Button>
                </>
              )}
              {step === 2 && (
                <>
                  <p className="muted m-0">{c.sourcesHint}</p>
                  {catalogue.items.map((pack) => (
                    <div
                      key={pack.id}
                      className={`rounded-lg border p-4 ${config.source_pack_ids.includes(pack.id) ? "border-primary bg-primary/5" : ""}`}
                    >
                      <label className="flex items-start gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={config.source_pack_ids.includes(pack.id)}
                          onChange={(event) =>
                            update({
                              source_pack_ids: event.target.checked
                                ? [...config.source_pack_ids, pack.id]
                                : config.source_pack_ids.filter(
                                    (id) => id !== pack.id,
                                  ),
                            })
                          }
                        />
                        <span>
                          <strong>
                            {pack.name[locale] || pack.name["en-CH"]}
                          </strong>
                          <span className="block text-sm muted mt-1">
                            {pack.description[locale] ||
                              pack.description["en-CH"]}
                          </span>
                        </span>
                      </label>
                      <div className="text-xs mt-3">
                        {c.currentState}:{" "}
                        <Status value={pack.subscription.state} />
                      </div>
                      <details className="mt-3 text-sm">
                        <summary className="cursor-pointer min-h-8">
                          {c.gaps}
                        </summary>
                        <p>
                          {pack.expected_first_data[locale] ||
                            pack.expected_first_data["en-CH"]}
                        </p>
                        <ul className="list-disc pl-5">
                          {pack.known_gaps.map((gap) => (
                            <li key={gap}>{gap}</li>
                          ))}
                        </ul>
                      </details>
                    </div>
                  ))}
                  <section className="border-t pt-5 grid gap-4">
                    <h3>{c.custom}</h3>
                    <p className="text-sm muted m-0">{c.requestsHint}</p>
                    <SourceRequests
                      requests={config.source_requests}
                      onRemove={(id) =>
                        update({
                          source_requests: config.source_requests.filter(
                            (r) => r.id !== id,
                          ),
                        })
                      }
                    />
                    <Field label={c.sourceName}>
                      <Input
                        maxLength={160}
                        value={sourceName}
                        onChange={(event) => setSourceName(event.target.value)}
                      />
                    </Field>
                    <Field label={c.sourceUrl}>
                      <Input
                        type="url"
                        maxLength={2000}
                        value={sourceUrl}
                        onChange={(event) => setSourceUrl(event.target.value)}
                      />
                    </Field>
                    <Field label={c.sourceKind}>
                      <select
                        value={sourceKind}
                        onChange={(event) =>
                          setSourceKind(
                            event.target.value as LegalSourceRequest["kind"],
                          )
                        }
                      >
                        {(["binding", "pending", "signals"] as const).map(
                          (kind) => (
                            <option key={kind} value={kind}>
                              {c[kind]}
                            </option>
                          ),
                        )}
                      </select>
                    </Field>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={config.source_requests.length >= 10}
                      onClick={addSource}
                    >
                      <Plus />
                      {c.addSource}
                    </Button>
                  </section>
                </>
              )}
              {step === 3 && (
                <>
                  <div className="rounded-lg border bg-primary/5 p-4">
                    <h3 className="flex gap-2 items-center">
                      <Check size={18} />
                      {c.inApp}
                    </h3>
                    <p className="text-sm mb-0">{c.inAppHint}</p>
                  </div>
                  <p className="text-sm m-0">
                    {c.currentDelivery}:{" "}
                    {delivery.delivery.enabled
                      ? `${c.enabled} · ${delivery.delivery.frequency === "daily" ? c.daily : c.weekly}`
                      : c.disabled}
                  </p>
                  <div className="grid gap-3">
                    {(["keep", "daily", "weekly", "off"] as const).map(
                      (choice) => (
                        <label
                          key={choice}
                          className="flex items-center gap-3 rounded-lg border p-3 min-h-12"
                        >
                          <input
                            type="radio"
                            name="delivery"
                            checked={config.delivery === choice}
                            disabled={
                              (choice === "daily" || choice === "weekly") &&
                              !delivery.email_available
                            }
                            onChange={() =>
                              update({
                                delivery: choice,
                                delivery_consent: false,
                              })
                            }
                          />
                          {c[choice]}
                        </label>
                      ),
                    )}
                  </div>
                  <p className="text-sm muted m-0">{c.deliveryHint}</p>
                  {!delivery.email_available && (
                    <p className="text-sm">{c.emailUnavailable}</p>
                  )}
                  {config.delivery !== "keep" && (
                    <label className="flex items-start gap-3 text-sm">
                      <input
                        type="checkbox"
                        checked={config.delivery_consent}
                        onChange={(event) =>
                          update({ delivery_consent: event.target.checked })
                        }
                      />
                      {c.consent}
                    </label>
                  )}
                  <Link
                    className="underline text-sm"
                    href="/digests"
                    target="_blank"
                  >
                    {c.manageDelivery}
                  </Link>
                  <div className="border-t pt-4">
                    <h3>{c.preview}</h3>
                    <p className="muted text-sm">{c.previewHint}</p>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() =>
                        void run("preview", async () => {
                          check(2);
                          const saved = await persist();
                          setPreview(
                            await api<LegalPreview>(
                              `/monitoring-profiles/${saved.id}/preview`,
                              {
                                method: "POST",
                                body: JSON.stringify({
                                  expected_revision: saved.revision,
                                }),
                              },
                            ),
                          );
                        })
                      }
                    >
                      {c.preview}
                    </Button>
                  </div>
                  {preview?.topics.map((topic) => (
                    <section key={topic.id} className="border-t pt-4">
                      <h3>{topic.name}</h3>
                      <TopicPreviewCoverage
                        preview={topic}
                        capturedAtLabel={
                          topic.sample_captured_at
                            ? dateTime(topic.sample_captured_at)
                            : undefined
                        }
                      />
                      {!topic.items.length && (
                        <p className="text-sm">{c.noMatches}</p>
                      )}
                      {topic.items.map((item) => (
                        <article
                          key={item.event_id}
                          className="rounded-lg border p-4 mb-3"
                        >
                          <h4>{item.title}</h4>
                          <p className="text-xs muted">
                            {item.authority} · {dateTime(item.detected_at)}
                          </p>
                          <p className="text-sm">
                            {item.reason_signals
                              .map(
                                (signal) =>
                                  signal.value ||
                                  signal.values?.join(", ") ||
                                  signal.tokens?.join(", "),
                              )
                              .filter(Boolean)
                              .join(" · ")}
                          </p>
                          {safeLink(item.evidence_url || item.source_url) && (
                            <a
                              className="underline text-sm"
                              href={safeLink(
                                item.evidence_url || item.source_url,
                              )!}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {c.evidence}
                            </a>
                          )}
                        </article>
                      ))}
                      {topic.source_coverage && (
                        <TopicSourceReadiness
                          coverage={topic.source_coverage}
                          boundary={c.readiness}
                        />
                      )}
                    </section>
                  ))}
                </>
              )}
              {step === 4 && (
                <>
                  <p className="muted m-0">{c.reviewHint}</p>
                  <ProfileSummary
                    config={config}
                    catalogue={catalogue}
                    onEdit={move}
                  />
                  <Button
                    type="button"
                    className="min-h-12"
                    onClick={() =>
                      void run("activate", async () => {
                        check(3);
                        const saved = await persist();
                        const active = await api<LegalProfile>(
                          `/monitoring-profiles/${saved.id}/activate`,
                          {
                            method: "POST",
                            body: JSON.stringify({
                              expected_revision: saved.revision,
                            }),
                          },
                        );
                        setProfile(active);
                        setConfig(active.config);
                        onActivated(active);
                      })
                    }
                  >
                    <Check />
                    {busy === "activate" ? c.activating : c.activate}
                  </Button>
                </>
              )}
              <div className="flex flex-wrap gap-3 justify-between border-t pt-5 mt-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={step === 0}
                  onClick={() => move(step - 1)}
                >
                  <ArrowLeft size={16} />
                  {c.back}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() =>
                    void run("save", async () => {
                      await persist();
                    })
                  }
                >
                  <Save size={16} />
                  {busy === "save" ? c.saving : c.save}
                </Button>
                {step < 4 && (
                  <Button type="submit">
                    {c.next}
                    <ArrowRight size={16} />
                  </Button>
                )}
              </div>
            </fieldset>
          </form>
        </section>
        <aside className="lg:sticky lg:top-24 h-fit rounded-lg border p-5 grid gap-4 text-sm bg-muted/30">
          <Radar className="text-primary" />
          <h3 className="break-words">{config.name || c.unnamed}</h3>
          <p className="muted m-0">{config.sector}</p>
          <div>
            {c.selectedTopics}:{" "}
            <strong>{config.topics.filter((t) => t.selected).length}</strong>
          </div>
          <div>
            {c.sourceCount}: <strong>{config.source_pack_ids.length}</strong>
          </div>
          <div>{c.coverage}</div>
          <div className="border-t pt-4 text-xs muted" aria-live="polite">
            {changed
              ? c.unsaved
              : profile
                ? `${c.updated}: ${dateTime(profile.updated_at, { dateStyle: "medium", timeStyle: "short" })}`
                : c.draft}
          </div>
        </aside>
      </div>
    </div>
  );
}

function TopicCardEditor({
  card,
  onChange,
  onRemove,
}: {
  card: LegalTopicCard;
  onChange: (card: LegalTopicCard) => void;
  onRemove: () => void;
}) {
  const { locale } = useI18n();
  const c = legalProfilesCopy[locale];
  const [keywords, setKeywords] = useState(card.keywords.join(", "));
  return (
    <article
      className={`rounded-lg border p-4 grid gap-4 ${card.selected ? "border-primary/50" : ""}`}
    >
      <div className="flex gap-3 justify-between items-center">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={card.selected}
            onChange={(event) =>
              onChange({ ...card, selected: event.target.checked })
            }
          />
          {c.selected}
        </label>
        <Button type="button" variant="ghost" onClick={onRemove}>
          {c.remove}
        </Button>
      </div>
      <Field label={c.topicName}>
        <Input
          required={card.selected}
          maxLength={240}
          value={card.name}
          onChange={(event) => onChange({ ...card, name: event.target.value })}
        />
      </Field>
      <Field label={c.description}>
        <textarea
          required={card.selected}
          rows={2}
          maxLength={2000}
          value={card.description}
          onChange={(event) =>
            onChange({ ...card, description: event.target.value })
          }
        />
      </Field>
      <Field label={c.keywords}>
        <Input
          required={card.selected}
          maxLength={2400}
          value={keywords}
          onChange={(event) => {
            setKeywords(event.target.value);
            onChange({
              ...card,
              keywords: event.target.value
                .split(",")
                .map((k) => k.trim())
                .filter(Boolean),
            });
          }}
        />
      </Field>
      <details>
        <summary className="text-sm cursor-pointer min-h-8">
          {c.references}
        </summary>
        <Field label={c.references}>
          <textarea
            rows={2}
            maxLength={1000}
            value={card.reference_note}
            onChange={(event) =>
              onChange({ ...card, reference_note: event.target.value })
            }
          />
        </Field>
        <p className="text-xs muted">{c.referencesHint}</p>
      </details>
    </article>
  );
}

function SourceRequests({
  requests,
  onRemove,
}: {
  requests: LegalSourceRequest[];
  onRemove?: (id: string) => void;
}) {
  const { locale } = useI18n();
  const c = legalProfilesCopy[locale];
  return (
    <>
      {requests.map((request) => (
        <article
          key={request.id}
          className="rounded border p-3 text-sm break-words"
        >
          <a
            href={request.url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline"
          >
            {request.label}
          </a>
          <p className="text-xs muted">
            {c[request.kind]} · {c.requested}
          </p>
          {onRemove && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => onRemove(request.id)}
            >
              {c.remove}
            </Button>
          )}
        </article>
      ))}
    </>
  );
}

function ProfileSummary({
  config,
  catalogue,
  onEdit,
}: {
  config: LegalProfileConfig;
  catalogue: SourcePackCatalogue;
  onEdit?: (step: number) => void;
}) {
  const { locale } = useI18n();
  const c = legalProfilesCopy[locale];
  return (
    <div className="grid gap-5">
      {[
        <>
          <h3>{config.name}</h3>
          <p>
            {config.sector} · {c[config.audience]}
          </p>
          <p>{config.goal}</p>
          <p className="text-sm">{c.coverage}</p>
          {config.requested_jurisdictions && (
            <p className="text-sm">
              {c.extraJurisdictions}: {config.requested_jurisdictions}
            </p>
          )}
        </>,
        <>
          {config.topics
            .filter((t) => t.selected)
            .map((card) => (
              <div key={card.id} className="mb-3">
                <h3>{card.name}</h3>
                <p className="text-sm">{card.description}</p>
                <p className="muted text-sm">{card.keywords.join(", ")}</p>
                {card.reference_note && (
                  <p className="text-xs">
                    {card.reference_note}
                    <br />
                    {c.referencesHint}
                  </p>
                )}
              </div>
            ))}
        </>,
        <>
          <ul className="list-disc pl-5">
            {config.source_pack_ids.map((id) => {
              const pack = catalogue.items.find((p) => p.id === id);
              return (
                <li key={id}>
                  {pack?.name[locale] || pack?.name["en-CH"] || id}
                </li>
              );
            })}
          </ul>
          <SourceRequests requests={config.source_requests} />
          {!!config.source_requests.length && (
            <p className="muted text-xs">{c.requestsHint}</p>
          )}
        </>,
        <>
          <h3>{c.inApp}</h3>
          <p>{c[config.delivery]}</p>
          <p className="text-sm muted">{c.deliveryHint}</p>
        </>,
      ].map((content, index) => (
        <section key={index} className="border rounded-lg p-4 break-words">
          <div className="flex justify-between items-center gap-2 mb-3">
            <span className="eyebrow">{c.steps[index]}</span>
            {onEdit && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => onEdit(index)}
              >
                {c.edit}
              </Button>
            )}
          </div>
          {content}
        </section>
      ))}
    </div>
  );
}

function ActiveProfile({
  profile,
  catalogue,
  onChange,
}: {
  profile: LegalProfile;
  catalogue: SourcePackCatalogue;
  onChange: (row: LegalProfile) => void;
}) {
  const { locale, dateTime } = useI18n();
  const { canManage } = useAuth();
  const c = legalProfilesCopy[locale];
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [openTopic, setOpenTopic] = useState("");
  async function changeStatus() {
    setBusy(true);
    setError("");
    try {
      const row = await api<LegalProfile>(
        `/monitoring-profiles/${profile.id}/status`,
        {
          method: "POST",
          body: JSON.stringify({
            expected_revision: profile.revision,
            status: profile.status === "active" ? "paused" : "active",
          }),
        },
      );
      onChange(row);
      await invalidateProfiles();
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setBusy(false);
    }
  }
  function download() {
    const url = URL.createObjectURL(
      new Blob(
        [
          JSON.stringify(
            { schema: "helvetic-lens/legal-profile/v1", profile },
            null,
            2,
          ),
        ],
        { type: "application/json" },
      ),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `monitoring-profile-${profile.id}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <div className="grid gap-5" data-legal-profile-active>
      <Link
        className="inline-flex gap-2 items-center min-h-11"
        href="/monitoring-profiles"
      >
        <ArrowLeft size={16} />
        {c.all}
      </Link>
      <section className="card p-6">
        <span className="eyebrow">{c[profile.status]}</span>
        <h2>{profile.config.name}</h2>
        <p className="muted">{c.successHint}</p>
        <p className="text-xs muted">
          {c.updated}:{" "}
          {dateTime(profile.updated_at, {
            dateStyle: "medium",
            timeStyle: "short",
          })}
        </p>
        <div className="flex gap-3 flex-wrap">
          <Button asChild>
            <Link href="/">
              {c.today}
              <ArrowRight />
            </Link>
          </Button>
          <Button variant="outline" onClick={download}>
            <FileDown />
            {c.export}
          </Button>
          {canManage && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => void changeStatus()}
            >
              {profile.status === "active" ? c.pause : c.resume}
            </Button>
          )}
        </div>
        <p className="text-xs muted mt-4 mb-0">{c.pauseHint}</p>
        <ErrorNote message={error} />
      </section>
      <section className="grid gap-3">
        {profile.topics?.map((topic) => (
          <article key={topic.id} className="card p-5">
            <div className="flex gap-3 justify-between flex-wrap">
              <h3>{topic.plan.name}</h3>
              <Status value={topic.status} />
            </div>
            <p>{topic.plan.goal}</p>
            <Link
              href={`/topics#topic-${topic.id}`}
              className="underline text-sm"
            >
              {c.topicsLink}
            </Link>
            <div className="mt-4">
              <Button
                variant="outline"
                onClick={() =>
                  setOpenTopic(openTopic === topic.id ? "" : topic.id)
                }
                aria-expanded={openTopic === topic.id}
              >
                {c.preview}
              </Button>
              {openTopic === topic.id && (
                <TopicSavedMatches topicId={topic.id} />
              )}
            </div>
          </article>
        ))}
      </section>
      <details className="card p-5">
        <summary className="min-h-11 cursor-pointer font-semibold">
          {c.activationRecord}
        </summary>
        <ProfileSummary config={profile.config} catalogue={catalogue} />
      </details>
    </div>
  );
}
