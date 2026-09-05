"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { Status } from "./common";

export type FeedEvidence = {
  jurisdictions?: string[]; document_language?: string | null; provenance_method?: string;
  connector_health_at_detection?: string; source_artifact_url?: string;
  official_dates: Array<{ kind: string; value: string; precision: string; provenance: string; source_url?: string }>;
};
function externalLink(value?: string) {
  if (!value) return undefined;
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) ? url.href : undefined; }
  catch { return undefined; }
}
export function FeedEvidenceContext({ item }: { item: FeedEvidence }) {
  const { t, locale } = useI18n();
  const methods: Record<string, string> = { official_metadata: t("feedProvenance.official_metadata"), exact_identifier: t("feedProvenance.exact_identifier"), text_rule: t("feedProvenance.text_rule"), model_proposal: t("feedProvenance.model_proposal"), human_review: t("feedProvenance.human_review"), legacy_mapping: t("feedProvenance.legacy_mapping") };
  let language = item.document_language;
  if (language) { try { language = new Intl.DisplayNames([locale], { type: "language" }).of(language) || language; } catch { /* Preserve an unfamiliar source code. */ } }
  const dateKinds: Record<string, string> = { published_at: t("feedEvidence.published_at"), decision_date: t("feedEvidence.decision_date"), effective_from: t("feedEvidence.effective_from"), effective_to: t("feedEvidence.effective_to") };
  const precisions: Record<string, string> = { day: t("feedEvidence.precision.day"), month: t("feedEvidence.precision.month"), year: t("feedEvidence.precision.year"), instant: t("feedEvidence.precision.instant"), unknown: t("feedEvidence.precision.unknown") };
  // Only the server's saved-version route, never an arbitrary response URL.
  const saved = item.source_artifact_url?.match(/^\/evidence\/[a-zA-Z0-9-]+$/) ? item.source_artifact_url : undefined;
  return <details className="text-sm my-3 rounded-lg border px-3 scroll-mt-24" data-feed-evidence>
    <summary className="cursor-pointer min-h-[44px] flex items-center">{t("feedEvidence.context")}</summary>
    <dl className="grid gap-3 sm:grid-cols-2 py-3">
      <div><dt className="muted">{t("feedEvidence.jurisdiction")}</dt><dd>{item.jurisdictions?.length ? item.jurisdictions.join(" · ") : <Status value="unknown" />}</dd></div>
      <div><dt className="muted">{t("filter.language")}</dt><dd>{language || <Status value="unknown" />}</dd></div>
      <div><dt className="muted">{t("feedEvidence.provenance")}</dt><dd>{(item.provenance_method && (methods[item.provenance_method] || item.provenance_method)) || <Status value="unknown" />}</dd></div>
      <div><dt className="muted">{t("feedEvidence.health")}</dt><dd><Status value={item.connector_health_at_detection ?? null} /></dd></div>
    </dl>
    <p className="muted">{t("feedEvidence.healthHelp")}</p>
    <h3 className="font-semibold mt-3">{t("feed.officialDates")}</h3>
    {item.official_dates.length ? item.official_dates.map((fact, index) => <div key={index} className="border-t py-3" data-feed-date>
      <p>{dateKinds[fact.kind] || fact.kind}: <time>{fact.value}</time> · {precisions[fact.precision] || precisions.unknown}</p>
      <p>{t("feedEvidence.provenance")}: {methods[fact.provenance] || fact.provenance}</p>
      {externalLink(fact.source_url) && <a className="underline min-h-[44px] inline-flex items-center" href={externalLink(fact.source_url)} target="_blank" rel="noopener noreferrer">{t("common.officialSource")}</a>}
    </div>) : <p className="muted">{t("registry.officialDatesUnknown")}</p>}
    {saved ? <Link className="underline min-h-[44px] inline-flex items-center" href={saved}>{t("feedEvidence.saved")}</Link> : <p className="muted mb-3">{t("feedEvidence.noSaved")}</p>}
  </details>;
}
