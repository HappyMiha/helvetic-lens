"use client";

import { useI18n } from "@/lib/i18n";
import type { ResponseMode } from "@/lib/types";

export function AnalysisModeNotice({ mode }: { mode?: ResponseMode }) {
  const { t } = useI18n();
  const title = mode === "selected_evidence" ? t("aiMode.selected")
    : mode === "generated_explanation" ? t("aiMode.generated")
    : mode === "deterministic" ? t("aiMode.deterministic")
    : t("aiMode.legacy");
  return (
    <div className="historical-note text-sm" data-response-mode={mode || "legacy"}>
      <strong>{title}</strong>
      {mode === "selected_evidence" && <p className="mb-0 mt-1">{t("aiMode.selectedBody")}</p>}
    </div>
  );
}
