"use client";

import { AlertCircle, ArrowUpRight, Check, Loader2 } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { label } from "@/lib/api";
import { translate, useI18n } from "@/lib/i18n";
import type { Citation } from "@/lib/types";

export function ErrorNote({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <div className="error-note" role="alert">
      <AlertCircle size={16} className="shrink-0 mt-0.5" />
      <span>{message}</span>
    </div>
  );
}
export function Loading({
  text,
}: {
  text?: string;
}) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-2 py-8 px-6 muted">
      <Loader2 size={17} className="animate-spin" />
      {text || t("common.loading")}
    </div>
  );
}
export function Status({ value }: { value: string | null }) {
  const { locale } = useI18n();
  const color = [
    "changed",
    "high",
    "failed",
    "error",
    "interrupted",
    "partial",
  ].includes(value || "")
    ? "status-warm"
    : ["unchanged", "complete", "succeeded", "success", "low"].includes(
          value || "",
        )
      ? "status-green"
      : [
            "historical_comparison",
            "historical",
            "saved_versions",
            "medium",
          ].includes(value || "")
        ? "status-amber"
        : "status-neutral";
  return (
    <Badge variant="outline" className={"status-badge " + color}>
      {translate(locale, `status.${value || "unknown"}`) || label(value)}
    </Badge>
  );
}
export function Citations({ values }: { values: Citation[] }) {
  const { t } = useI18n();
  return (
    <span className="citations">
      {values.map((citation, index) => (
        <Link
          href={citation.url}
          key={citation.version_id + citation.passage_id + index}
          target="_blank"
          aria-label={t("common.citation", {
            number: index + 1,
            quote: citation.quote.slice(0, 80),
          })}
          title={citation.quote}
        >
          [{index + 1}]<ArrowUpRight size={10} />
        </Link>
      ))}
    </span>
  );
}
export function SuccessNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="success-note">
      <Check size={16} />
      {children}
    </div>
  );
}
