"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { digestInterestCopy } from "@/lib/digest-interest-copy";
import type { DigestSummary } from "@/lib/types";

export function DigestCoverageNotice({
  summary,
}: {
  summary?: Partial<DigestSummary>;
}) {
  const { t, locale } = useI18n();
  const eventLimit = summary?.truncated === true;
  const offline = summary?.ai_runtime_unverified === true;
  const lawLimit = summary?.events?.some(
    (event) => event.impacts_truncated === true,
  );
  if (!eventLimit && !lawLimit && !offline) return null;
  return (
    <aside
      className="rounded-lg border border-border bg-background p-4 text-sm my-4 break-words"
      data-digest-coverage="limited"
    >
      {(eventLimit || lawLimit) && <p className="font-semibold m-0">{t("digests.limited")}</p>}
      {offline && <div data-digest-runtime="unverified">
        <p className="m-0">{digestInterestCopy[locale].runtime_unavailable}</p>
        {summary?.severity_filter_deferred && <p>{digestInterestCopy[locale].filter_deferred}</p>}
      </div>}
      {eventLimit && <p className="mt-2 mb-0">{digestInterestCopy[locale].event_limit}</p>}
      {lawLimit && <p className="mt-2 mb-0">{t("digests.impactLimit")}</p>}
      <Link
        className="inline-flex items-center min-h-11 mt-2 underline underline-offset-4"
        href="/"
      >
        {digestInterestCopy[locale].open_list}
      </Link>
    </aside>
  );
}
