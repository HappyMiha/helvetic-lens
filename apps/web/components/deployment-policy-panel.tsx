"use client";

import { useState } from "react";
import { api, ApiError, resources, useResource } from "@/lib/api";
import { deploymentPolicyCopy } from "@/lib/deployment-policy-copy";
import { deploymentTestsCopy } from "@/lib/deployment-tests-copy";
import { useI18n } from "@/lib/i18n";
import type { DeploymentPolicyChoice, DeploymentPolicySettings, DeploymentProfile } from "@/lib/types";
import { ErrorNote, Loading } from "./common";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";

type Scope = "default" | "next";
type Draft = { revision: number; choice: DeploymentPolicyChoice | null };
const profiles: DeploymentProfile[] = ["standard", "full", "hotfix"];

export function DeploymentPolicyPanel() {
  const { locale } = useI18n();
  const copy = deploymentPolicyCopy[locale], testCopy = deploymentTestsCopy[locale];
  const policy = useResource(resources.deploymentPolicy());
  const [drafts, setDrafts] = useState<Partial<Record<Scope, Draft>>>({});
  const [saving, setSaving] = useState<Scope | null>(null);
  const [error, setError] = useState<"conflict" | "failed" | null>(null);
  const [saved, setSaved] = useState(false);
  const data = policy.data;
  const staleDraft = data && Object.values(drafts).some(draft => draft.revision !== data.revision);

  function edit(scope: Scope, choice: DeploymentPolicyChoice | null) {
    if (!data) return;
    setSaved(false);
    setDrafts(previous => ({ ...previous, [scope]: { revision: previous[scope]?.revision ?? data.revision, choice } }));
  }

  async function save(scope: Scope, draft: Draft) {
    if (saving) return;
    setSaving(scope); setError(null); setSaved(false);
    try {
      const result = await api<DeploymentPolicySettings>("/admin/deployments/policy", {
        method: "PATCH", body: JSON.stringify({ scope, expected_revision: draft.revision,
          profile: draft.choice?.profile ?? null, reason: draft.choice?.reason?.trim() || null }),
      });
      policy.setData(result);
      setDrafts(previous => {
        const remaining = { ...previous };
        delete remaining[scope];
        const other = scope === "default" ? "next" : "default";
        if (remaining[other]?.revision === draft.revision) remaining[other] = { ...remaining[other], revision: result.revision };
        return remaining;
      });
      setSaved(true);
    } catch (failure) {
      setError(failure instanceof ApiError && failure.code === "deployment_policy_conflict" ? "conflict" : "failed");
      void policy.reload();
    } finally {
      setSaving(null);
    }
  }

  return <section className="panel min-w-0" data-deployment-policy-settings>
    <div className="panel-header"><div><h2>{copy.title}</h2><p className="text-sm muted mb-0">{copy.body}</p></div></div>
    <div className="panel-body grid gap-4">
      <ErrorNote message={policy.error ? copy.unavailable : null} />
      <ErrorNote message={error ? copy[error] : null} />
      <div role="status" aria-live="polite" data-deployment-policy-feedback>{saved ? copy.saved : ""}</div>
      {(error || policy.error || staleDraft) && <Button type="button" className="min-h-11 h-auto whitespace-normal" variant="outline" disabled={!!saving} data-deployment-policy-reload onClick={() => {
        setDrafts({}); setError(null); setSaved(false); void policy.reload();
      }}>{copy.reload}</Button>}
      {!data && !policy.error && <Loading />}
      {data && !data.enabled && <p>{copy.unavailable}</p>}
      {data?.enabled && <>
        <dl className="grid gap-3 sm:grid-cols-2 rounded-md border p-4 text-sm" data-deployment-policy-summary>
          <div><dt className="muted">{copy.effective}</dt><dd className="mt-1" data-deployment-effective={(data.next ?? data.default).profile}>
            <Badge variant={(data.next ?? data.default).profile === "hotfix" ? "destructive" : "outline"}>{testCopy.profiles[(data.next ?? data.default).profile]}</Badge>
            <span className="block mt-1">{copy.sources[data.next ? "next" : "default"]}</span>
          </dd></div>
          <div><dt className="muted">{copy.returnsTo}</dt><dd className="mt-1" data-deployment-default={data.default.profile}>{testCopy.profiles[data.default.profile]}</dd></div>
        </dl>
        <div className="grid gap-5 lg:grid-cols-2">
          {(["default", "next"] as const).map(scope => {
            const draft = drafts[scope];
            const choice = draft ? draft.choice : data[scope];
            const isHotfix = choice?.profile === "hotfix";
            const stale = draft && draft.revision !== data.revision;
            return <form key={scope} className="grid content-start gap-3 min-w-0" data-deployment-policy-form={scope}
              onSubmit={event => { event.preventDefault(); if (draft) void save(scope, draft); }}>
              <label className="font-medium" htmlFor={`deployment-${scope}`}>{copy[scope]}</label>
              <select id={`deployment-${scope}`} className="w-full min-w-0 min-h-11" value={choice?.profile ?? ""} disabled={!!saving || !!policy.error}
                onChange={event => edit(scope, event.target.value ? { profile: event.target.value as DeploymentProfile, reason: null } : null)}>
                {scope === "next" && <option value="">{copy.useDefault}</option>}
                {profiles.map(profile => <option value={profile} key={profile}>{testCopy.profiles[profile]}</option>)}
              </select>
              {isHotfix && <>
                <p className="text-sm mb-0" id={`deployment-${scope}-help`}>{copy.hotfix}</p>
                <label htmlFor={`deployment-${scope}-reason`}>{copy.reason}</label>
                <Textarea id={`deployment-${scope}-reason`} required minLength={10} maxLength={500} rows={3}
                  aria-describedby={`deployment-${scope}-help`} disabled={!!saving} value={choice.reason ?? ""}
                  onChange={event => edit(scope, { profile: "hotfix", reason: event.target.value })} />
              </>}
              {stale && <p role="status" className="text-sm">{copy.conflict}</p>}
              <div className="flex flex-wrap gap-2">
                <Button type="submit" className="min-h-11 h-auto whitespace-normal" disabled={!draft || !!saving || !!policy.error || (isHotfix && (choice.reason?.trim().length ?? 0) < 10)} data-deployment-policy-save={scope}>
                  {saving === scope ? copy.saving : scope === "default" ? copy.saveDefault : copy.saveNext}
                </Button>
                {scope === "next" && data.next && <Button type="button" className="min-h-11 h-auto whitespace-normal" variant="outline" disabled={!!saving || !!policy.error} data-deployment-policy-cancel
                  onClick={() => void save("next", { revision: data.revision, choice: null })}>{copy.cancel}</Button>}
              </div>
            </form>;
          })}
        </div>
      </>}
    </div>
  </section>;
}
