"use client";
import type { BriefRecovery } from "@/lib/interest-brief";
import { useI18n } from "@/lib/i18n";
import { Status } from "./common";
export function BriefRecoveryHistory({recovery}: {recovery: BriefRecovery}) {
  const {t, dateTime} = useI18n();
  if (!recovery.history.length) return null;
  return <details data-brief-retry-history>
    <summary className="min-h-11 py-2 cursor-pointer">{t("briefRecovery.history")}</summary>
    <ol className="space-y-3">{recovery.history.map((entry, index) => <li key={index}>
      <p>{dateTime(entry.requested_at)}</p><Status value={entry.previous_state} />
      <p>{t("briefRecovery.attempts", {used: entry.assessment_attempts, limit: recovery.attempt_limit})}</p>
      {entry.previous_error_code && <code className="break-all">{entry.previous_error_code}</code>}
    </li>)}</ol>
  </details>;
}
