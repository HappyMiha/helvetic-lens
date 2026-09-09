"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { invalidateResources, resourceTag, resources, useResource } from "@/lib/api";
import { interestBriefCopy, type SavedInterestBrief } from "@/lib/interest-brief";
import { ErrorNote, Loading } from "./common";
import { Button } from "./ui/button";
import { BriefRecoveryHistory } from "./brief-recovery-history";
import { InterestBriefRequest } from "./interest-brief-request";
import { BriefFeedback } from "./brief-feedback";
import { BriefReviewPanel } from "./brief-review";
import {briefReviewCopy} from "@/lib/brief-review";
import {SavedBriefBody} from "./saved-brief-body";
import {BriefHistory} from "./brief-history";
import {ASSISTANT_BRIEF_EVENT, assistantBriefCopy} from "@/lib/assistant-brief";

export function FeedInterestBrief({eventId}: {eventId: string}) {
  const [open, setOpen] = useState(false);
  const {locale} = useI18n();
  return <><details data-feed-brief className="border-t mt-4 pt-3" open={open}
    onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="min-h-11 cursor-pointer font-semibold py-2"><h3 className="inline text-base">{interestBriefCopy[locale].title}</h3></summary>
    {open && <SavedBriefContent key={`${eventId}:${locale}`} eventId={eventId} />}
  </details><BriefHistory key={`${eventId}:${locale}`} eventId={eventId}/>
    <Button data-open-marvin-brief variant="outline" className="mt-3 min-h-11 whitespace-normal" onClick={()=>window.dispatchEvent(new CustomEvent(ASSISTANT_BRIEF_EVENT,{detail:{eventId}}))}>{assistantBriefCopy[locale].open}</Button></>;
}

export function SavedBriefContent({eventId,readOnly=false}: {eventId: string;readOnly?:boolean}) {
  const {locale, t} = useI18n();
  const copy = interestBriefCopy[locale];
  const page = useResource(resources.interestBrief<SavedInterestBrief>(eventId, locale.slice(0, 2)));
  const data = !page.error && !page.loading ? page.data : undefined;
  const result = data?.status === "available" || data?.status === "rejected" ? data.result : null;
  return <div className="space-y-3 min-w-0 break-words" aria-busy={page.loading}>
    {!readOnly && <p className="text-sm muted">{copy.help}</p>}
    {page.loading && <Loading />}
    <ErrorNote message={page.error} />
    {data && <p className="text-sm muted">{t("briefPolicy.locale")}: <span lang={data.locale}>{({de:"Deutsch",fr:"Français",it:"Italiano",rm:"Rumantsch",en:"English"} as Record<string,string>)[data.locale] || data.locale}</span></p>}
    {data && <p role="status" data-brief-status={data.status} className="text-sm">{copy.status[data.status]}</p>}
    {data?.review && data.status!=="rejected" && <p className="text-sm" data-brief-review-status>{briefReviewCopy[locale][data.review.decision]}</p>}
    {data?.error_code && <ErrorNote message={t(({
      invalid_model_output: "briefRecovery.invalidOutput", invalid_citation: "briefRecovery.invalidOutput",
      model_timeout: "briefRecovery.timeout", cancelled: "briefRecovery.cancelled",
    } as Record<string, string>)[data.error_code] || "briefRecovery.unavailable")} />}
    {result && <details open={data?.status!=="rejected"} key={`${data?.assessment_id}:${data?.status}`} className="space-y-3">
      <summary className="min-h-11 py-2 cursor-pointer font-semibold">{data?.status==="rejected" ? briefReviewCopy[locale].original : copy.title}</summary>
      <SavedBriefBody data={data!} /></details>}
    {!readOnly && result && data?.assessment_id && <BriefFeedback key={data.assessment_id} assessmentId={data.assessment_id} />}
    {!readOnly && result && data?.assessment_id && <BriefReviewPanel key={`review:${data.assessment_id}`} assessmentId={data.assessment_id} eventId={eventId} />}
    {!readOnly && data && !result && <InterestBriefRequest eventId={eventId} canRequest={data.status !== "failed"} recovery={data.recovery} />}
    {data?.recovery && <BriefRecoveryHistory recovery={data.recovery} />}
    <Button data-refresh-brief variant="outline" className="min-h-11 whitespace-normal" disabled={page.loading}
      onClick={() => void invalidateResources(resourceTag(`interest-brief:${eventId}`)).catch(() => {})}>{copy.refresh}</Button>
  </div>;
}
