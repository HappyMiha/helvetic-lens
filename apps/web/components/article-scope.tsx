"use client";

import { useI18n } from "@/lib/i18n";
import { articleSelectionCopy } from "@/lib/article-selection-copy";
import type { SelectionProvenance } from "@/lib/types";

export function ArticleScope({
  provenance,
}: {
  provenance?: SelectionProvenance;
}) {
  const { locale, number } = useI18n();
  if (!provenance?.scope) return null;
  const copy = articleSelectionCopy[locale];
  return (
    <section className="info-note my-4" aria-label={copy.scope}>
      <strong>
        {copy.scope}: {provenance.scope}
      </strong>
      <p>
        {copy.officialDate}: {provenance.official_version_date || copy.unknown}
      </p>
      <details>
        <summary className="cursor-pointer">
          {copy.articles} ({number(provenance.articles.length)})
        </summary>
        <ul className="mt-2 space-y-2" lang="de">
          {provenance.articles.map((article) => (
            <li key={article.number}>
              <b>{copy.article} {article.number}</b> — {article.heading}
            </li>
          ))}
        </ul>
      </details>
      <p>{copy.limits}</p>
    </section>
  );
}
