"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { errorText, fetchResource, label, resourceScopeEpoch, useResource } from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { useAuth } from "./auth-gate";
import { registryScope, readRegistryPosition } from "@/lib/registry-position";
import { useI18n } from "@/lib/i18n";
import type { Passage, Version } from "@/lib/types";
import { ErrorNote, Loading, Status } from "./common";
import { Shell } from "./shell";
import { useEvidenceMilestone } from "@/lib/evidence-milestone";

type Evidence = Omit<Version, "law_id" | "artifact_url"> & { law_id: string | null; artifact_url: string | null; law_name: string; passages: Passage[]; plain_text?: string | null; pagination: {offset:number;end:number;total:number;size:number;mode:"passages"|"text";next_offset:number|null;previous_offset:number|null;target_found:boolean|null} };


export function EvidenceView({
  id,
  passageId,
  native = false,
}: {
  id: string;
  passageId: string;
  native?: boolean;
}) {
  const { t, dateTime, number } = useI18n();
  const {session}=useAuth();
  const scope=registryScope(session?.user?.id,session?.organization?.id,session?.anonymous_development);
  const returnIdentity=JSON.stringify([scope,id,native,passageId]);
  const [returnPosition,setReturnPosition]=useState<{identity:string;route:string}|null>(null);
  const registryReturn=returnPosition?.identity===returnIdentity ? returnPosition.route : null;
  useEffect(()=>{
    setReturnPosition(null);
    try {
      const position=readRegistryPosition(window.sessionStorage,scope);
      if(position?.target===window.location.pathname+window.location.search+window.location.hash) setReturnPosition({identity:returnIdentity,route:position.route});
    } catch { /* Navigation works normally when browser storage is disabled. */ }
  },[scope,returnIdentity]);
  const [offset, setOffset] = useState<number | null>(null);
  useEffect(() => setOffset(null), [id, passageId]);
  const { data, error, reload } = useResource(resources.evidencePage<Evidence>(id, native, offset ?? 0, offset === null ? passageId : ""));
  const [changing, setChanging] = useState(false);
  const [pageError, setPageError] = useState("");
  const generation = useRef(0);
  useEffect(() => { generation.current++; setChanging(false); setPageError(""); return () => { generation.current++; }; }, [id, native, passageId]);
  async function changePage(next: number | null) {
    if (next === null || changing) return;
    const current = generation.current, epoch = resourceScopeEpoch("session");
    setChanging(true); setPageError("");
    try {
      await fetchResource(resources.evidencePage<Evidence>(id, native, next, ""));
      if (current === generation.current && epoch === resourceScopeEpoch("session")) setOffset(next);
    } catch (cause) {
      if (current === generation.current && epoch === resourceScopeEpoch("session")) setPageError(errorText(cause));
    } finally {
      if (current === generation.current && epoch === resourceScopeEpoch("session")) setChanging(false);
    }
  }
  const page = data ? Math.floor(data.pagination.offset / data.pagination.size) : 0;
  const route = (native ? "/corpus-evidence/" : "/evidence/") + encodeURIComponent(id);
  const safeSource = data?.source_url && /^https?:\/\//i.test(data.source_url) ? data.source_url : null;
  const targetIndex =
    data?.passages.findIndex((passage) => passage.id === passageId) ?? -1;
  const missingTarget = data?.pagination.target_found === false;
  useEffect(() => {
    if (targetIndex >= 0) document.getElementById("passage-" + passageId)?.scrollIntoView({block:"center"});
  }, [data, targetIndex, passageId]);
  const displayedEvidence = useRef<HTMLElement>(null);
  useEvidenceMilestone(displayedEvidence, id, native, Boolean(data && !error && !missingTarget && !data.synthetic &&
    (data.passages.some(passage => passage.text.trim()) || data.plain_text?.trim())), page);
  const pages = data ? Math.max(1, Math.ceil(data.pagination.total / data.pagination.size)) : 1;
  const sourceLanguage = data?.identity_json?.language || undefined;
  return (
    <Shell section={t("evidence.section")}>
      <Link className="back-link" data-registry-return={registryReturn ? "" : undefined} href={registryReturn || (data?.law_id ? "/laws/" + data.law_id : "/")}>
        <ArrowLeft size={14} />
        {t(registryReturn ? "registryReturn.back" : native ? "nav.today" : "evidence.back")}
      </Link>
      <ErrorNote message={error} />
      {error && <div className="flex gap-2 my-4"><Button variant="outline" onClick={()=>void reload()}>{t("gettingStarted.retry")}</Button><Button variant="outline" onClick={()=>setOffset(0)}>{t("evidence.readComplete")}</Button></div>}
      {!data ? (
        !error && <Loading text={t("evidence.opening")} />
      ) : (
        <>
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                {t("evidence.eyebrow")} · {data.id.slice(0, 8)}
              </span>
              <h1 lang={sourceLanguage}>{data.law_name}</h1>
              <p className="muted m-0">
                {t("evidence.snapshotNotice")}
              </p>
            </div>
            {data.artifact_url ? <Button asChild variant="outline">
              <a
                href={
                  data.artifact_url +
                  (data.content_type === "application/pdf" &&
                  targetIndex >= 0 &&
                  data.passages[targetIndex].page
                    ? "#page=" + data.passages[targetIndex].page
                    : "")
                }
                target="_blank"
                rel="noreferrer"
              >
                <Download />
                {data.content_type === "application/pdf"
                  ? t("evidence.openPdf")
                  : t("evidence.downloadOriginal")}
              </a>
            </Button> : <p className="muted max-w-md" role="status">{t("nativeEvidence.noArtifact")}</p>}
          </div>
          <section className="panel" ref={displayedEvidence} aria-busy={changing}>
            <div className="evidence-metadata">
              {native ? <span>{t("nativeEvidence.record")}</span> : <Status value={data.origin} />}
              {data.synthetic && (
                <span className="synthetic-label">{t("evidence.synthetic")}</span>
              )}
              <span>
                {data.declared_date
                  ? t("evidence.statedDate", { date: data.declared_date })
                  : t("evidence.unknownDate")}
              </span>
              <span>{t("evidence.firstSaved", { date: dateTime(data.created_at) })}</span>
              <span>
                {t("evidence.contentMeta", { type: data.content_type, passages: number(data.passage_count) })}
              </span>
            </div>
            {(native || data.origin !== "live") && (
              <div className="info-note m-5">
                {t(native ? "nativeEvidence.notice" : "evidence.importNotice")}
              </div>
            )}
            {safeSource && (
              <a
                className="text-link mx-6 my-4 break-all"
                href={safeSource || undefined}
                target="_blank"
                rel="noreferrer"
              >
                {t("evidence.openSource")}
                <ArrowUpRight size={13} />
              </a>
            )}
            <p className="text-sm muted mx-6">{t("onboardingProgress.displayNotice")}</p>
            {missingTarget ? (
              <div className="p-6">
                <ErrorNote
                  message={
                    t("evidence.missingPassage", { passage: passageId })
                  }
                />
                <Button asChild variant="outline" className="mt-3">
                  <Link href={route}>
                    {t("evidence.readComplete")}
                  </Link>
                </Button>
              </div>
            ) : (
              <>
                {!data.passages.length && <div className="p-6 whitespace-pre-wrap break-words" data-native-text data-evidence-display-text={data.plain_text ? true : undefined}>{data.plain_text || t("nativeEvidence.noText")}</div>}
                <div className="evidence-passages">
                  {data.passages.map((passage) => (
                      <article
                        lang={sourceLanguage}
                        id={"passage-" + passage.id}
                        className={
                          "evidence-passage " +
                          (passage.id === passageId ? "evidence-target" : "")
                        }
                        key={passage.id}
                      >
                        <div className="passage-meta">
                          <Link
                            href={route + "?passage=" + encodeURIComponent(passage.id)}
                          >
                            <BookOpen size={12} />
                            {passage.id}
                            {passage.id === passageId
                              ? ` · ${t("evidence.referenced")}`
                              : ""}
                          </Link>
                          {passage.page && data.artifact_url && data.content_type === "application/pdf" ? (
                            <a
                              href={data.artifact_url + "#page=" + passage.page}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {t("evidence.pdfPage", { page: passage.page })}
                              <ArrowUpRight size={11} />
                            </a>
                          ) : (
                            <span>{label(data.origin)}</span>
                          )}
                        </div>
                        <p data-evidence-display-text={passage.text.trim() ? true : undefined}>{passage.text}</p>
                      </article>
                    ))}
                </div>
                <ErrorNote message={pageError} />
                {changing && <p role="status" className="muted mx-6">{t("evidence.opening")}</p>}
                <div className="pagination">
                  <span>
                    {t(data.pagination.mode === "text" ? "evidencePages.textRange" : "evidence.range", {
                      start: number(data.pagination.total ? data.pagination.offset + 1 : 0),
                      end: number(data.pagination.end),
                      total: number(data.pagination.total),
                    })}
                  </span>
                  <div className="flex gap-2 items-center">
                    <Button
                      size="icon-sm"
                      variant="outline"
                      aria-label={t("evidence.previous")}
                      disabled={changing || data.pagination.previous_offset === null}
                      onClick={() => void changePage(data.pagination.previous_offset)}
                    >
                      <ChevronLeft />
                    </Button>
                    <span>
                      {page + 1} / {pages}
                    </span>
                    <Button
                      size="icon-sm"
                      variant="outline"
                      aria-label={t("evidence.next")}
                      disabled={changing || data.pagination.next_offset === null}
                      onClick={() => void changePage(data.pagination.next_offset)}
                    >
                      <ChevronRight />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </section>
        </>
      )}
    </Shell>
  );
}
