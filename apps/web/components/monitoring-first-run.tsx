"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { centreCopy, type TemplateId } from "@/lib/monitoring-centre-copy";
import { monitoringNavigation } from "@/lib/monitoring-navigation";
import { monitoringFirstRunCopy } from "@/lib/monitoring-first-run-copy";

const business = new Set<TemplateId>(["tenders", "ip", "auctions"]);

export function MonitoringFirstRun({
  selected,
  busy,
  ready,
  canManage,
  onChoose,
}: {
  selected?: TemplateId | null;
  busy: boolean;
  ready: boolean;
  canManage: boolean;
  onChoose: (domain: TemplateId, href: string) => void;
}) {
  const { locale } = useI18n();
  const copy = monitoringFirstRunCopy[locale],
    names = centreCopy[locale].templates;
  const saved = monitoringNavigation.find((item) => item.id === selected);
  return (
    <section
      aria-labelledby="monitoring-first-run-heading"
      data-monitoring-first-run
      className="rounded-2xl border bg-card p-5 sm:p-7 space-y-4"
    >
      <h2 id="monitoring-first-run-heading" className="text-2xl font-semibold">
        {copy.title}
      </h2>
      <p className="max-w-3xl text-sm leading-6">{copy.body}</p>
      <p className="max-w-3xl text-sm leading-6">{copy.steps}</p>
      {!canManage && (
        <p className="text-sm" data-monitoring-first-run-viewer>
          {copy.viewer}
        </p>
      )}
      {saved && (
        <div className="rounded-lg border p-4" data-monitoring-first-run-saved>
          <p className="font-semibold">
            {copy.saved}: {names[saved.id][0]}
          </p>
          <Link
            className="min-h-11 inline-flex items-center underline"
            href={saved.href}
          >
            {copy.continue}
          </Link>
        </div>
      )}
      {([false, true] as const).map((work) => (
        <div key={String(work)}>
          <h3 className="font-semibold mb-3">
            {work ? copy.business : copy.personal}
          </h3>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {monitoringNavigation
              .filter((item) => business.has(item.id) === work)
              .map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    data-onboarding-template={item.id}
                    disabled={busy || !ready}
                    onClick={() => onChoose(item.id, item.href)}
                    className="w-full h-full min-h-11 rounded-xl border p-4 text-left hover:bg-muted/40 focus-visible:outline-2 focus-visible:outline-primary disabled:opacity-50"
                  >
                    <strong className="block">{names[item.id][0]}</strong>
                    <span className="block mt-2 text-sm leading-6">
                      {names[item.id][1]}
                    </span>
                  </button>
                </li>
              ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
