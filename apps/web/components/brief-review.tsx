"use client";

import {useEffect, useId, useRef, useState} from "react";
import {api, ApiError, invalidateResources, resourceScopeEpoch, resourceTag, resources, useResource} from "@/lib/api";
import {briefReviewCopy, type BriefReviewPage, type ReviewDecision} from "@/lib/brief-review";
import {useI18n} from "@/lib/i18n";
import {useAuth} from "./auth-gate";
import {ErrorNote, Loading} from "./common";
import {Button} from "./ui/button";

export function BriefReviewPanel({assessmentId,eventId}: {assessmentId:string;eventId:string}) {
  const {locale} = useI18n();
  const {session} = useAuth();
  const [open,setOpen] = useState(false);
  return <details data-brief-review className="border-t pt-3" open={open} onToggle={event=>setOpen(event.currentTarget.open)}>
    <summary className="min-h-11 cursor-pointer py-2 font-semibold">{briefReviewCopy[locale].title}</summary>
    {open && <Editor key={`${assessmentId}:${session?.organization?.id}:${session?.user?.id}:${locale}`} assessmentId={assessmentId} eventId={eventId} />}
  </details>;
}

function Editor({assessmentId,eventId}: {assessmentId:string;eventId:string}) {
  const {locale,dateTime} = useI18n(), {canManage} = useAuth();
  const copy=briefReviewCopy[locale];
  const [cursor,setCursor]=useState(""), [note,setNote]=useState(""), [error,setError]=useState(""), [busy,setBusy]=useState(false);
  const mounted=useRef(false), nonce=useRef<{signature:string;id:string}|null>(null), noteId=useId();
  const page=useResource(resources.briefReviews<BriefReviewPage>(assessmentId,cursor));
  const data=!page.loading && !page.error ? page.data : null;
  useEffect(()=>{mounted.current=true;return ()=>{mounted.current=false;};},[]);
  async function save(decision:ReviewDecision) {
    if(!canManage || !data || busy || note.trim().length<3) return;
    const epoch=`${resourceScopeEpoch("session")}:${resourceScopeEpoch("organization")}`;
    const current=()=>mounted.current && epoch===`${resourceScopeEpoch("session")}:${resourceScopeEpoch("organization")}`;
    const payload={decision,note:note.trim(),target_fingerprint:data.target_fingerprint,expected_previous_id:data.latest?.id||null};
    const signature=JSON.stringify(payload);
    if(nonce.current?.signature!==signature) nonce.current={signature,id:crypto.randomUUID()};
    setBusy(true);setError("");
    try {
      await api(`/interest-briefs/${encodeURIComponent(assessmentId)}/reviews`,{method:"POST",body:JSON.stringify({...payload,request_id:nonce.current.id})});
      if(!current()) return;
      nonce.current=null;setNote("");setCursor("");
      await invalidateResources(resourceTag(`brief-review:${assessmentId}`),resourceTag(`interest-brief:${eventId}`),resourceTag("digests"),resourceTag("impact-inbox"));
    } catch(cause) {if(current()) setError(cause instanceof ApiError && cause.code==="brief_review_conflict" ? copy.conflict : copy.failed);}
    finally {if(current())setBusy(false);}
  }
  return <div className="space-y-3 break-words min-w-0" aria-busy={busy||page.loading}>
    <p className="text-sm muted">{copy.help}</p>
    {page.loading && <Loading />}
    <ErrorNote message={error||(page.error?copy.failed:"")} />
    {data && <p role="status" data-review-saved>{data.latest ? data.matches_saved_assessment ? copy[data.latest.decision] : copy.changed : copy.unreviewed}</p>}
    {canManage && <><label htmlFor={noteId} className="block text-sm">{copy.note}</label>
      <textarea id={noteId} data-review-note value={note} maxLength={2000} disabled={busy} onChange={event=>setNote(event.target.value)} className="w-full min-h-24 rounded-lg border p-3" />
      <div className="flex flex-wrap gap-2">{(["confirmed","rejected","withdrawn"] as const).map((decision,index)=><Button key={decision} data-review-decision={decision} variant={index===0?"default":"outline"} className="min-h-11 whitespace-normal" disabled={busy||!data||note.trim().length<3} onClick={()=>void save(decision)}>{[copy.confirm,copy.reject,copy.withdraw][index]}</Button>)}</div>
    </>}
    <Button data-review-reload variant="outline" disabled={busy} onClick={()=>{setError("");void invalidateResources(resourceTag(`brief-review:${assessmentId}`));}}>{copy.reload}</Button>
    <details data-review-history><summary className="min-h-11 py-2 cursor-pointer">{copy.history}</summary>
      {page.loading && <Loading />}
      <ol className="space-y-3 text-sm">{data?.items.map(row=><li key={row.id}><strong>{copy[row.decision]}</strong> · <time dateTime={row.created_at}>{dateTime(row.created_at)}</time><p className="whitespace-pre-wrap">{row.note}</p></li>)}</ol>
      <div className="flex flex-wrap gap-2">{cursor&&<Button disabled={page.loading||busy} variant="outline" onClick={()=>setCursor("")}>{copy.first}</Button>}{data?.next_cursor&&<Button variant="outline" disabled={busy} onClick={()=>setCursor(data.next_cursor!)}>{copy.older}</Button>}</div>
    </details>
  </div>;
}
