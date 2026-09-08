"use client";

import { useEffect, useId, useRef, useState } from "react";
import { api, ApiError, invalidateResources, resourceScopeEpoch, resourceTag, resources, useResource } from "@/lib/api";
import { briefFeedbackCopy, type BriefFeedbackPage, type FeedbackDecision } from "@/lib/brief-feedback";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "./auth-gate";
import { ErrorNote, Loading } from "./common";
import { Button } from "./ui/button";

export function BriefFeedback({assessmentId}: {assessmentId: string}) {
  const {session} = useAuth();
  const {locale} = useI18n();
  const [open, setOpen] = useState(false);
  const owner = `${session?.organization?.id || "dev"}:${session?.user?.id || "anonymous-development"}`;
  return <details data-brief-feedback className="border-t pt-3" open={open} onToggle={event=>setOpen(event.currentTarget.open)}>
    <summary className="min-h-11 cursor-pointer py-2 font-semibold">{briefFeedbackCopy[locale].title}</summary>
    {open && <Editor key={`${assessmentId}:${owner}:${locale}`} assessmentId={assessmentId} owner={owner} />}
  </details>;
}

function Editor({assessmentId, owner}: {assessmentId: string; owner: string}) {
  const {locale, dateTime} = useI18n();
  const copy = briefFeedbackCopy[locale];
  const [cursor, setCursor] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(false), nonce = useRef<{signature: string; id: string} | null>(null);
  const noteId = useId();
  const page = useResource(resources.briefFeedback<BriefFeedbackPage>(assessmentId, owner, cursor));
  const data = !page.error && !page.loading ? page.data : null;
  useEffect(()=>{mounted.current=true; return ()=>{mounted.current=false;};},[]);
  async function save(decision: FeedbackDecision) {
    if(busy || !data) return;
    const epoch = `${resourceScopeEpoch("session")}:${resourceScopeEpoch("organization")}`;
    const current = ()=>mounted.current && epoch===`${resourceScopeEpoch("session")}:${resourceScopeEpoch("organization")}`;
    const payload = {decision,note:decision==="withdrawn" ? "" : note,expected_previous_id:data.latest?.id || null};
    const signature = JSON.stringify(payload);
    if(nonce.current?.signature!==signature) nonce.current={signature,id:crypto.randomUUID()};
    setBusy(true); setError("");
    try {
      await api(`/interest-briefs/${encodeURIComponent(assessmentId)}/feedback`, {method:"POST",body:JSON.stringify({...payload,request_id:nonce.current.id})});
      if(!current()) return;
      nonce.current=null; setNote(""); setCursor("");
      await invalidateResources(resourceTag(`brief-feedback:${assessmentId}`));
    } catch(cause) {
      if(current()) setError(cause instanceof ApiError && cause.code==="feedback_conflict" ? copy.conflict : cause instanceof ApiError && cause.code==="feedback_limit" ? copy.limit : copy.failed);
    } finally {if(current()) setBusy(false);}
  }
  return <div className="space-y-3 min-w-0 break-words" aria-busy={busy || page.loading}>
    <p className="text-sm muted">{copy.help}</p>
    {page.loading && <Loading />}
    <ErrorNote message={error || (page.error ? copy.failed : "")} />
    {data?.latest && <p role="status" data-feedback-saved className="text-sm">{copy.saved}: <strong>{copy[data.latest.decision]}</strong> · <time dateTime={data.latest.created_at}>{dateTime(data.latest.created_at)}</time></p>}
    <label htmlFor={noteId} className="block text-sm">{copy.note}</label>
    <textarea id={noteId} data-feedback-note maxLength={1000} value={note} disabled={busy} className="w-full min-h-24 rounded-lg border p-3" onChange={event=>setNote(event.target.value)} />
    <div className="flex flex-wrap gap-2">
      <Button data-feedback-useful disabled={busy || !data} className="min-h-11 whitespace-normal" onClick={()=>void save("useful")}>{busy ? copy.saving : copy.useful}</Button>
      <Button data-feedback-not-useful variant="outline" disabled={busy || !data} className="min-h-11 whitespace-normal" onClick={()=>void save("not_useful")}>{copy.not_useful}</Button>
      {data?.latest && data.latest.decision!=="withdrawn" && <Button data-feedback-withdraw variant="ghost" disabled={busy} className="min-h-11 whitespace-normal" onClick={()=>void save("withdrawn")}>{copy.withdraw}</Button>}
      <Button data-feedback-reload variant="outline" disabled={busy} className="min-h-11 whitespace-normal" onClick={()=>{setError(""); void invalidateResources(resourceTag(`brief-feedback:${assessmentId}`));}}>{copy.reload}</Button>
    </div>
    <details data-feedback-history open={historyOpen} onToggle={event=>setHistoryOpen(event.currentTarget.open)}><summary className="min-h-11 cursor-pointer py-2">{copy.history}</summary>
      {page.loading && <Loading />}
      <ol className="space-y-3 text-sm">{data?.items.map(item=><li key={item.id}><strong>{copy[item.decision]}</strong> · <time dateTime={item.created_at}>{dateTime(item.created_at)}</time>{item.note && <p className="whitespace-pre-wrap">{item.note}</p>}</li>)}</ol>
      <div className="flex flex-wrap gap-2 mt-3">{cursor && <Button variant="outline" disabled={busy || page.loading} onClick={()=>setCursor("")}>{copy.first}</Button>}{data?.next_cursor && <Button variant="outline" disabled={busy || page.loading} onClick={()=>setCursor(data.next_cursor!)}>{copy.next}</Button>}</div>
    </details>
  </div>;
}
