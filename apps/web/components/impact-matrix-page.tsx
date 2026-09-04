"use client";

import Link from "next/link";
import {
  ArrowRight,
  BookOpenCheck,
  CircleAlert,
  Grid3X3,
  History,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorNote, Loading, Status } from "@/components/common";
import { Shell } from "@/components/shell";
import { useResource } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ImpactMatrix, ImpactMatrixCell } from "@/lib/types";

function MatrixCell({
  cell,
  comparisonUrl,
}: {
  cell: ImpactMatrixCell;
  comparisonUrl: string | null;
}) {
  const { t } = useI18n();
  if (cell.state === "assessed") {
    return (
      <div className="matrix-cell matrix-cell-assessed">
        <Status value={cell.impact} />
        {cell.reason && <p>{cell.reason}</p>}
        {comparisonUrl && (
          <Link href={comparisonUrl} className="matrix-evidence-link">
            {t("matrix.openEvidence")} <ArrowRight size={13} />
          </Link>
        )}
      </div>
    );
  }
  if (cell.state === "stale") {
    return (
      <div className="matrix-cell matrix-cell-stale">
        <Status value="stale" />
        {cell.previous_impact && (
          <span className="matrix-previous">
            {t("matrix.previousImpact")}: <Status value={cell.previous_impact} />
          </span>
        )}
        {cell.reason && <p>{cell.reason}</p>}
        {comparisonUrl && (
          <Link href={comparisonUrl} className="matrix-evidence-link">
            {t("matrix.rerun")} <ArrowRight size={13} />
          </Link>
        )}
      </div>
    );
  }
  const key =
    cell.state === "failed"
      ? "failed"
      : cell.state === "unanalysed"
        ? "unanalysed"
        : "unknown";
  const explanation =
    key === "failed"
      ? t("matrix.failedBody")
      : key === "unanalysed"
        ? t("matrix.unanalysedBody")
        : t("matrix.unknownBody");
  return (
    <div className="matrix-cell matrix-cell-empty">
      <Status value={key} />
      <p>{explanation}</p>
      {comparisonUrl && (
        <Link href={comparisonUrl} className="matrix-evidence-link">
          {key === "failed" ? t("matrix.rerun") : t("matrix.openComparison")} {" "}
          <ArrowRight size={13} />
        </Link>
      )}
    </div>
  );
}

export function ImpactMatrixPage() {
  const { locale, t, number } = useI18n();
  const resource = useResource<ImpactMatrix>(
    `/impact-matrix?output_locale=${encodeURIComponent(locale)}`,
    30_000,
  );
  const data = resource.data;

  return (
    <Shell section={t("nav.matrix")} wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("matrix.eyebrow")}</span>
          <h1>{t("matrix.title")}</h1>
          <p className="muted m-0">{t("matrix.body")}</p>
        </div>
      </div>

      {data && (
        <section className="stats-grid mb-5" aria-label={t("matrix.summary")}>
          <div className="stat-card">
            <BookOpenCheck size={18} />
            <strong>{number(data.summary.current_reports)}</strong>
            <span>{t("matrix.currentReports")}</span>
          </div>
          <div className="stat-card">
            <Grid3X3 size={18} />
            <strong>{number(data.summary.assessed_cells)}</strong>
            <span>{t("matrix.assessedCells")}</span>
          </div>
          <div className="stat-card">
            <History size={18} />
            <strong>{number(data.summary.stale_reports)}</strong>
            <span>{t("matrix.staleReports")}</span>
          </div>
          <div className="stat-card">
            <CircleAlert size={18} />
            <strong>{number(data.summary.unanalysed_documents + data.summary.failed_reports)}</strong>
            <span>{t("matrix.needsAnalysis")}</span>
          </div>
        </section>
      )}

      <section className="workflow-note mb-5">
        <span className="eyebrow">{t("matrix.scopeTitle")}</span>
        <span>{t("matrix.scopeBody")}</span>
      </section>

      <ErrorNote message={resource.error} />
      {resource.loading && !data && <Loading text={t("matrix.loading")} />}

      {data && !data.profile.business_areas.length && (
        <section className="empty-state card">
          <Grid3X3 size={28} />
          <h2>{t("matrix.noAreas")}</h2>
          <p className="muted">{t("matrix.noAreasBody")}</p>
        </section>
      )}

      {data && data.profile.business_areas.length > 0 && !data.rows.length && (
        <section className="empty-state card">
          <BookOpenCheck size={28} />
          <h2>{t("matrix.empty")}</h2>
          <p className="muted">{t("matrix.emptyBody")}</p>
        </section>
      )}

      {data && data.profile.business_areas.length > 0 && data.rows.length > 0 && (
        <section className="card impact-matrix-card">
          <div className="impact-matrix-scroll">
            <table className="impact-matrix-table">
              <thead>
                <tr>
                  <th scope="col">{t("matrix.document")}</th>
                  {data.profile.business_areas.map((area) => (
                    <th scope="col" key={area}>{area}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.law_id}>
                    <th scope="row">
                      <div className="matrix-document">
                        <strong>{row.law_title}</strong>
                        {row.headline && <span>{row.headline}</span>}
                        {row.comparison_url && (
                          <Button asChild size="sm" variant="outline">
                            <Link href={row.comparison_url}>
                              {t("matrix.openComparison")} <ArrowRight size={13} />
                            </Link>
                          </Button>
                        )}
                      </div>
                    </th>
                    {row.cells.map((cell) => (
                      <td key={cell.area} data-area={cell.area}>
                        <MatrixCell cell={cell} comparisonUrl={row.comparison_url} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </Shell>
  );
}
