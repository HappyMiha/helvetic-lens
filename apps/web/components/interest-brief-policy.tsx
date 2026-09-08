"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorText, invalidateResources, resourceTag, useResource } from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import type { InterestBriefPolicy } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "./auth-gate";
import { ErrorNote, Loading, SuccessNote } from "./common";

type Draft = Pick<InterestBriefPolicy, "enabled" | "locale" | "max_pending" | "max_daily">;
function editable(value: InterestBriefPolicy): Draft {
  return { enabled: value.enabled, locale: value.locale, max_pending: value.max_pending, max_daily: value.max_daily };
}

export function InterestBriefPolicyCard() {
  const { t } = useI18n();
  const { canManage } = useAuth();
  const resource = useResource(resources.interestBriefPolicy());
  const [notice, setNotice] = useState("");
  const [reset, setReset] = useState(0);
  return <section className="panel p-6 mb-6" data-brief-policy aria-labelledby="brief-policy-title">
    <h2 id="brief-policy-title">{t("briefPolicy.title")}</h2>
    <p className="text-sm muted">{t("briefPolicy.body")}</p>
    <ErrorNote message={resource.error} />
    {notice && <SuccessNote>{notice}</SuccessNote>}
    {!resource.data ? <>{!resource.error && <Loading />}<Button variant="outline" onClick={() => void resource.reload().catch(() => {})}>{t("briefPolicy.reload")}</Button></> :
      <PolicyForm key={`${resource.data.revision}-${reset}`} value={resource.data} canManage={canManage}
        onSaved={(value) => { resource.setData(value); setNotice(t("briefPolicy.saved")); }}
        onEdit={() => setNotice("")}
        onReload={async () => { await resource.reload(); setReset(value => value + 1); setNotice(""); }} />}
  </section>;
}

function PolicyForm({value, canManage, onSaved, onEdit, onReload}: {
  value: InterestBriefPolicy; canManage: boolean;
  onSaved: (value: InterestBriefPolicy) => void; onEdit: () => void; onReload: () => Promise<void>;
}) {
  const { t, number } = useI18n();
  const [draft, setDraft] = useState<Draft>(() => editable(value));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dirty = JSON.stringify(draft) !== JSON.stringify(editable(value));
  function update<K extends keyof Draft>(key: K, next: Draft[K]) {
    setDraft(current => ({...current, [key]: next})); setError(""); onEdit();
  }
  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await api<InterestBriefPolicy>("/settings/interest-briefs", {
        method: "PATCH", body: JSON.stringify({...draft, revision: value.revision}),
      });
      onSaved(result);
      void invalidateResources(resourceTag("jobs", "organization"), resourceTag("monitoring", "organization")).catch(() => {});
    } catch (cause) { setError(errorText(cause)); } finally { setBusy(false); }
  }
  return <form onSubmit={save}>
    <fieldset disabled={!canManage || busy} className="border-0 p-0 m-0 min-w-0 grid gap-4">
      <label className="flex gap-3 items-start" htmlFor="brief-policy-enabled">
        <input id="brief-policy-enabled" type="checkbox" checked={draft.enabled}
          onChange={event => update("enabled", event.target.checked)} />
        <span>{t("briefPolicy.enabled")}</span>
      </label>
      <p className="text-sm muted m-0">{t("briefPolicy.userLanguages")}</p>
      <div className="grid gap-4 md:grid-cols-2">
        <label htmlFor="brief-policy-pending">{t("briefPolicy.pending")}
          <Input id="brief-policy-pending" className="mt-2" type="number" required min={1} max={value.hard_limits.max_pending}
            value={draft.max_pending} onChange={event => update("max_pending", Number(event.target.value))} />
        </label>
        <label htmlFor="brief-policy-daily">{t("briefPolicy.daily")}
          <Input id="brief-policy-daily" className="mt-2" type="number" required min={1} max={value.hard_limits.max_daily}
            value={draft.max_daily} onChange={event => update("max_daily", Number(event.target.value))} />
        </label>
      </div>
      <p className="text-sm muted m-0">{t("briefPolicy.usage", {pending: number(value.usage.pending), daily: number(value.usage.last_24_hours)})}</p>
      <p className="text-sm muted m-0">{t("briefPolicy.limits")}</p>
      <ErrorNote message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!dirty || busy}>{t(busy ? "briefPolicy.saving" : "briefPolicy.save")}</Button>
        <Button type="button" variant="outline" onClick={() => void onReload().catch(cause => setError(errorText(cause)))}>{t("briefPolicy.reload")}</Button>
      </div>
    </fieldset>
    {!canManage && <p className="text-sm muted">{t("error.viewer_read_only")}</p>}
  </form>;
}
