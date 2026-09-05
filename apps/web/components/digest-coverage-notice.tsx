"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import type { DigestSummary } from "@/lib/types";

export function DigestCoverageNotice({
  summary,
}: {
  summary?: Partial<DigestSummary>;
}) {
  const { t } = useI18n();
  const eventLimit = summary?.truncated === true;
  const lawLimit = summary?.events?.some(
    (event) => event.impacts_truncated === true,
  );
  if (!eventLimit && !lawLimit) return null;
  return (
    <aside
      className="rounded-lg border border-border bg-background p-4 text-sm my-4 break-words"
      data-digest-coverage="limited"
    >
      <p className="font-semibold m-0">{t("digests.limited")}</p>
      {eventLimit && <p className="mt-2 mb-0">{t("digests.eventLimit")}</p>}
      {lawLimit && <p className="mt-2 mb-0">{t("digests.impactLimit")}</p>}
      <Link
        className="inline-flex items-center min-h-11 mt-2 underline underline-offset-4"
        href="/impact"
      >
        {t("digests.reviewFull")}
      </Link>
    </aside>
  );
}
