"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export function InboxPageNavigation({ page, newestHref, nextHref, busy = false }: {
  page?: { total_events: number; scanned_event_count: number; has_more: boolean };
  newestHref?: string;
  nextHref?: string;
  busy?: boolean;
}) {
  const { t } = useI18n();
  return (
    <nav className="rounded-lg border border-border bg-background p-4 my-4 text-sm break-words" aria-label={t("inboxPaging.navigation")} data-inbox-navigation>
      {page && <p className="m-0" role="status">{t("inboxPaging.counts", { shown: page.total_events, scanned: page.scanned_event_count })}</p>}
      {page?.total_events === 0 && page.has_more && <p className="mt-2 mb-0">{t("inboxPaging.emptyPage")}</p>}
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        {newestHref && <Link prefetch={false} href={newestHref} className="inline-flex items-center min-h-11 underline underline-offset-4">{t("inboxPaging.newest")}</Link>}
        {nextHref && !busy && <Link prefetch={false} href={nextHref} className="inline-flex items-center min-h-11 font-semibold underline underline-offset-4">{t("inboxPaging.next")}</Link>}
      </div>
    </nav>
  );
}
