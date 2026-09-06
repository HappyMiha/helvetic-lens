"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, errorText, invalidateResources, resourceScopeEpoch, useResource } from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import type { SourcePackCatalogue, PersonalSourceReview } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "./auth-gate";
import { Button } from "./ui/button";
import { ErrorNote } from "./common";

export function PersonalSourceChoice({data, changing}: {data:SourcePackCatalogue; changing:boolean}) {
  const {session} = useAuth();
  return <SourceChoice key={`${session?.user?.id}/${session?.organization?.id}`} data={data} changing={changing} />;
}
function SourceChoice({data, changing}: {data:SourcePackCatalogue; changing:boolean}) {
  const {t, dateTime, locale} = useI18n();
  const progress = useResource(resources.onboarding());
  const [busy, setBusy] = useState(false), [error,setError] = useState("");
  const mounted = useRef(true);
  useEffect(() => { mounted.current=true; return () => {mounted.current=false;}; }, []);
  const expected={catalogue_revision:data.catalogue_revision,packs:data.items.map(pack=>({id:pack.id,revision:pack.revision,enabled:pack.subscription.enabled})).sort((a,b)=>a.id.localeCompare(b.id))};
  const saved=progress.data?.source_review;
  const matches=!!saved?.current && saved.snapshot.catalogue_revision===expected.catalogue_revision &&
    saved.snapshot.packs.length===expected.packs.length && expected.packs.every(pack=>saved.snapshot.packs.some(item=>
      item.id===pack.id && item.revision===pack.revision && item.enabled===pack.enabled));
  async function save() {
    if(busy || changing) return;
    const epoch=resourceScopeEpoch("session"); setBusy(true); setError("");
    try {
      const result=await api<PersonalSourceReview>("/onboarding/source-review",{method:"POST",body:JSON.stringify(expected)});
      if(!mounted.current || epoch!==resourceScopeEpoch("session")) return;
      if(progress.data) progress.setData({...progress.data,source_review:result});
      void invalidateResources(resources.onboarding());
    } catch(cause) {
      if(mounted.current && epoch===resourceScopeEpoch("session")) setError(errorText(cause));
    } finally { if(mounted.current && epoch===resourceScopeEpoch("session")) setBusy(false); }
  }
  return <section className="mt-6 rounded-xl border p-4 space-y-3" data-source-review>
    <h3>{t("sourceReview.title")}</h3>
    <p className="text-sm muted">{t("sourceReview.body")}</p>
    <ul className="space-y-2 text-sm">{data.items.map(pack=><li key={pack.id} className="flex flex-wrap justify-between gap-2"><span>{pack.name[locale] || pack.name["en-CH"]}</span><strong>{t(pack.subscription.enabled ? "sourceReview.enabled" : "sourceReview.disabled")}</strong></li>)}</ul>
    {!data.items.some(pack=>pack.subscription.enabled) && <p className="info-note">{t("sourceReview.none")}</p>}
    <ErrorNote message={error || progress.error} />
    {saved && <p role="status" data-source-review-status className="text-sm">{t(matches ? "sourceReview.saved" : "sourceReview.changed")} <time dateTime={saved.reviewed_at}>{dateTime(saved.reviewed_at,{dateStyle:"medium",timeStyle:"short"})}</time></p>}
    <div className="flex flex-wrap gap-3">
      <Button data-save-source-review disabled={busy || changing || matches || !data.items.length} onClick={()=>void save()}>{t("sourceReview.continue")}</Button>
      <Button variant="outline" disabled={busy} onClick={()=>void invalidateResources(resources.sourcePacks(),resources.onboarding())}>{t("sourceReview.reload")}</Button>
      <Button variant="ghost" asChild><Link href="/onboarding">{t("gettingStarted.title")}</Link></Button>
    </div>
  </section>;
}
