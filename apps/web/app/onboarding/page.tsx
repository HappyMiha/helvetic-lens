"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Compass, FileSearch, Radar } from "lucide-react";
import { Shell } from "@/components/shell";
import { useAuth } from "@/components/auth-gate";
import { ErrorNote, Loading } from "@/components/common";
import { Button } from "@/components/ui/button";
import {
  api,
  errorText,
  invalidateResources,
  resourceScopeEpoch,
  useResource,
} from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { useI18n } from "@/lib/i18n";
import type { OnboardingState } from "@/lib/types";

export default function OnboardingPage() {
  const { session } = useAuth();
  const { t } = useI18n();
  return (
    <Shell section={t("gettingStarted.title")}>
      <Guide key={`${session?.user?.id}/${session?.organization?.id}`} />
    </Shell>
  );
}

function Guide() {
  const { t, dateTime } = useI18n();
  const { canManage } = useAuth();
  const router = useRouter();
  const resource = useResource(resources.onboarding());
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  async function choose(
    action: "topic" | "law" | "explore" | "later",
    href: string,
  ) {
    if (busy) return;
    const epoch = resourceScopeEpoch("session");
    setBusy(action);
    setError("");
    try {
      const saved = await api<OnboardingState>("/onboarding", {
        method: "PATCH",
        body: JSON.stringify({ action }),
      });
      if (!mounted.current || epoch !== resourceScopeEpoch("session")) return;
      resource.setData(saved);
      void invalidateResources(resources.authSession());
      router.push(href);
    } catch (cause) {
      if (mounted.current && epoch === resourceScopeEpoch("session"))
        setError(errorText(cause));
    } finally {
      if (mounted.current && epoch === resourceScopeEpoch("session"))
        setBusy("");
    }
  }
  const stateLabels = { new: "gettingStarted.new", deferred: "gettingStarted.deferred", started: "gettingStarted.started" };
  const intentLabels = { topic: "gettingStarted.topic", law: "gettingStarted.law", explore: "gettingStarted.explore" };
  const descriptions = { topic: "gettingStarted.topicBody", law: "gettingStarted.lawBody", explore: "gettingStarted.exploreBody" };
  const stepLabels: Record<string, string> = { sources: "gettingStarted.sources", interests: "gettingStarted.interests", notifications: "gettingStarted.notifications", evidence: "gettingStarted.evidence" };
  const stepDescriptions: Record<string, string> = { sources: "gettingStarted.sourcesBody", interests: "gettingStarted.interestsBody", notifications: "gettingStarted.notificationsBody", evidence: "gettingStarted.evidenceBody" };
  const choices = [
    { action: "topic" as const, href: "/topics", icon: Radar },
    { action: "law" as const, href: "/discover", icon: FileSearch },
    { action: "explore" as const, href: "/", icon: Compass },
  ];
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6" data-onboarding-guide>
      <header>
        <span className="eyebrow">{t("gettingStarted.personal")}</span>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">
          {t("gettingStarted.title")}
        </h1>
        <p className="mt-3 max-w-3xl text-muted-foreground">
          {t("gettingStarted.body")}
        </p>
      </header>
      {resource.error && (
        <>
          <ErrorNote message={resource.error} />
          <Button variant="outline" onClick={() => void resource.reload()}>
            {t("gettingStarted.retry")}
          </Button>
        </>
      )}
      {!resource.data && !resource.error && <Loading />}
      {resource.data && (
        <>
          <p
            role="status"
            className="rounded-xl border bg-muted/30 p-4"
            data-onboarding-status
          >
            {t(stateLabels[resource.data.state])}
            {resource.data.intent && (
              <span className="mt-1 block">
                {t("gettingStarted.savedIntent", {
                  intent: t(intentLabels[resource.data.intent]),
                })}
              </span>
            )}
          </p>
          <div className="grid gap-4 lg:grid-cols-3">
            {choices.map(({ action, href, icon: Icon }) => (
              <button
                type="button"
                key={action}
                disabled={Boolean(busy)}
                data-onboarding-choice={action}
                onClick={() => void choose(action, href)}
                className="flex flex-col items-start rounded-2xl border bg-card p-5 text-left transition hover:border-primary focus-visible:outline-2 focus-visible:outline-primary disabled:opacity-50"
              >
                <Icon className="text-primary" size={24} />
                <strong className="mt-3 block text-lg">
                  {t(intentLabels[action])}
                </strong>
                <span className="mt-2 block text-sm leading-6 text-muted-foreground">
                  {t(descriptions[action])}
                </span>
                <ArrowRight className="mt-4" size={18} />
              </button>
            ))}
          </div>
          {error && <ErrorNote message={error} />}
          {busy && <p role="status">{t("gettingStarted.saving")}</p>}
          <Button
            variant="outline"
            disabled={Boolean(busy)}
            data-onboarding-later
            onClick={() => void choose("later", "/")}
          >
            {t("gettingStarted.later")}
          </Button>
          <section className="rounded-2xl border bg-card p-5" aria-labelledby="recorded-progress" data-onboarding-milestones>
            <h2 id="recorded-progress" className="text-xl font-semibold">{t("onboardingProgress.title")}</h2>
            <p className="text-sm text-muted-foreground mt-2">{t("onboardingProgress.boundary")}</p>
            {resource.data.source_review && <p className="mt-3 text-sm" data-onboarding-source-review>
              {t(resource.data.source_review.current ? "sourceReview.saved" : "sourceReview.changed")} {dateTime(resource.data.source_review.reviewed_at)} {" "}
              <Link className="underline" href="/sources#source-packs">{t("sourceReview.title")}</Link>
            </p>}
            <ul className="mt-3 space-y-3">
              {([
                ["interest_saved", "onboardingProgress.interest"],
                ["notifications_saved", "onboardingProgress.notifications"],
                ["evidence_displayed", "onboardingProgress.evidence"],
              ] as const).map(([kind, key]) => {
                const recorded = resource.data?.milestones?.find(item => item.kind === kind);
                return <li key={kind} data-milestone-kind={kind} className="rounded-lg border p-3">
                  <strong className="block">{t(key)}</strong>
                  {recorded ? <p data-milestone-recorded className="mt-1 text-sm">{t("onboardingProgress.recorded")} <time dateTime={recorded.recorded_at}>{dateTime(recorded.recorded_at, {dateStyle:"medium", timeStyle:"short"})}</time></p> :
                    <p className="mt-1 text-sm text-muted-foreground">{t("onboardingProgress.notRecorded")}</p>}
                </li>;
              })}
            </ul>
          </section>
          <section
            className="rounded-2xl border bg-card p-5 sm:p-7"
            aria-labelledby="guide-steps"
          >
            <h2 id="guide-steps" className="text-xl font-semibold">
              {t("gettingStarted.steps")}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {t(canManage ? "gettingStarted.admin" : "gettingStarted.viewer")}
            </p>
            <ol className="mt-4 space-y-4">
              {[
                [
                  "sources",
                  "/sources#source-packs",
                  resource.data.organization_setup.source_package_enabled,
                ],
                [
                  "interests",
                  "/registry",
                  resource.data.organization_setup.active_document_watch ||
                    resource.data.organization_setup.active_topic,
                ],
                ["notifications", "/digests", null],
                ["evidence", "/", null],
              ].map(([step, href, exists], index) => (
                <li key={String(step)} className="rounded-xl border p-4">
                  <Link
                    href={String(href)}
                    className="inline-flex min-h-11 items-center gap-2 font-medium text-primary underline underline-offset-4"
                  >
                    {index + 1}. {t(stepLabels[String(step)])}
                    <ArrowRight size={16} />
                  </Link>
                  <p className="text-sm leading-6 text-muted-foreground">
                    {t(stepDescriptions[String(step)])}
                  </p>
                  {typeof exists === "boolean" && (
                    <p
                      className="mt-2 text-sm"
                      data-organization-availability={String(step)}
                    >
                      {t(
                        exists
                          ? "gettingStarted.available"
                          : "gettingStarted.notYet",
                      )}
                    </p>
                  )}
                </li>
              ))}
            </ol>
            <p className="mt-4 text-sm text-muted-foreground">
              {t("gettingStarted.honest")}
            </p>
          </section>
        </>
      )}
    </div>
  );
}
