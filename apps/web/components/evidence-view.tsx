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
import { dateTime, label, useResource } from "@/lib/api";
import type { Passage, Version } from "@/lib/types";
import { ErrorNote, Loading, Status } from "./common";
import { Shell } from "./shell";

type Evidence = Version & { law_name: string; passages: Passage[] };
const PAGE_SIZE = 60;

export function EvidenceView({
  id,
  passageId,
}: {
  id: string;
  passageId: string;
}) {
  const { data, error } = useResource<Evidence>("/versions/" + id);
  const [page, setPage] = useState(0);
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
    <Shell section="Saved source evidence">
      <Link className="back-link" href={data ? "/laws/" + data.law_id : "/"}>
        <ArrowLeft size={14} />
        Back to document
      </Link>
      <ErrorNote message={error} />
      {!data ? (
        !error && <Loading text="Opening saved evidence…" />
      ) : (
        <>
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                SAVED EVIDENCE · {data.id.slice(0, 8)}
              </span>
              <h1 lang={sourceLanguage}>{data.law_name}</h1>
              <p className="muted m-0">
                This is a stored snapshot. The live website may now contain
                different wording.
              </p>
            </div>
            <Button asChild variant="outline">
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
                  ? "Open saved PDF"
                  : "Download original file"}
              </a>
            </Button>
          </div>
          <section className="panel">
            <div className="evidence-metadata">
              <Status value={data.origin} />
              {data.synthetic && (
                <span className="synthetic-label">Synthetic demo content</span>
              )}
              <span>
                {data.declared_date
                  ? "Stated date: " + data.declared_date + " · user supplied"
                  : "Version date unknown"}
              </span>
              <span>First saved {dateTime(data.created_at)}</span>
              <span>
                {data.content_type} · {data.passage_count} passages
              </span>
            </div>
            {data.origin !== "live" && (
              <div className="info-note m-5">
                This imported snapshot is not automatically verified as an
                official historical version.
              </div>
            )}
            {data.source_url && (
              <a
                className="text-link mx-6 my-4 break-all"
                href={data.source_url}
                target="_blank"
                rel="noreferrer"
              >
                Open original source URL
                <ArrowUpRight size={13} />
              </a>
            )}
            {missingTarget ? (
              <div className="p-6">
                <ErrorNote
                  message={
                    "Passage " +
                    passageId +
                    " does not exist in this saved version. No substitute passage has been selected."
                  }
                />
                <Button asChild variant="outline" className="mt-3">
                  <Link href={"/evidence/" + id}>
                    Read the complete saved version
                  </Link>
                </Button>
              </div>
            ) : (
              <>
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
                            href={"/evidence/" + id + "?passage=" + passage.id}
                          >
                            <BookOpen size={12} />
                            {passage.id}
                            {passage.id === passageId
                              ? " · referenced passage"
                              : ""}
                          </Link>
                          {passage.page ? (
                            <a
                              href={data.artifact_url + "#page=" + passage.page}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Saved PDF · page {passage.page}
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
                    Passages {page * PAGE_SIZE + 1}–
                    {Math.min((page + 1) * PAGE_SIZE, data.passages.length)} of{" "}
                    {data.passages.length}
                  </span>
                  <div className="flex gap-2 items-center">
                    <Button
                      size="icon-sm"
                      variant="outline"
                      aria-label="Previous evidence passages"
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
                      aria-label="Next evidence passages"
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
