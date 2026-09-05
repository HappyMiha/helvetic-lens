"use client";

import { useEffect, useState } from "react";
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
import { label, useResource } from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { useI18n } from "@/lib/i18n";
import type { Passage, Version } from "@/lib/types";
import { ErrorNote, Loading, Status } from "./common";
import { Shell } from "./shell";

type Evidence = Omit<Version, "law_id" | "artifact_url"> & { law_id: string | null; artifact_url: string | null; law_name: string; passages: Passage[]; plain_text?: string | null };
const PAGE_SIZE = 60;

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
  const { data, error } = useResource(native ? resources.corpusVersion<Evidence>(id) : resources.version<Evidence>(id));
  const [page, setPage] = useState(0);
  const route = (native ? "/corpus-evidence/" : "/evidence/") + encodeURIComponent(id);
  const safeSource = data?.source_url && /^https?:\/\//i.test(data.source_url) ? data.source_url : null;
  const targetIndex =
    data?.passages.findIndex((passage) => passage.id === passageId) ?? -1;
  const missingTarget = !!data && !!passageId && targetIndex < 0;
  useEffect(() => {
    if (targetIndex >= 0) setPage(Math.floor(targetIndex / PAGE_SIZE));
  }, [targetIndex]);
  useEffect(() => {
    if (targetIndex >= 0 && page === Math.floor(targetIndex / PAGE_SIZE))
      document
        .getElementById("passage-" + passageId)
        ?.scrollIntoView({ block: "center" });
  }, [page, targetIndex, passageId]);
  const pages = Math.max(
    1,
    Math.ceil((data?.passages.length || 0) / PAGE_SIZE),
  );
  const sourceLanguage = data?.identity_json?.language || undefined;
  return (
    <Shell section={t("evidence.section")}>
      <Link className="back-link" href={data?.law_id ? "/laws/" + data.law_id : "/"}>
        <ArrowLeft size={14} />
        {t(native ? "nav.today" : "evidence.back")}
      </Link>
      <ErrorNote message={error} />
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
          <section className="panel">
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
                {!data.passages.length && <div className="p-6 whitespace-pre-wrap break-words" data-native-text>{data.plain_text || t("nativeEvidence.noText")}</div>}
                <div className="evidence-passages">
                  {data.passages
                    .slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
                    .map((passage) => (
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
                        <p>{passage.text}</p>
                      </article>
                    ))}
                </div>
                <div className="pagination">
                  <span>
                    {t("evidence.range", {
                      start: number(data.passages.length ? page * PAGE_SIZE + 1 : 0),
                      end: number(Math.min((page + 1) * PAGE_SIZE, data.passages.length)),
                      total: number(data.passages.length),
                    })}
                  </span>
                  <div className="flex gap-2 items-center">
                    <Button
                      size="icon-sm"
                      variant="outline"
                      aria-label={t("evidence.previous")}
                      disabled={page === 0}
                      onClick={() => setPage((value) => value - 1)}
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
                      disabled={page >= pages - 1}
                      onClick={() => setPage((value) => value + 1)}
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
