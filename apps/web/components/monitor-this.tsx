"use client";
import Link from "next/link";
import { Radar } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { Button } from "./ui/button";

export function MonitorThis({
  kind,
  id,
}: {
  kind: "event" | "law" | "comparison" | "answer";
  id: string;
}) {
  const { t, locale } = useI18n();
  return (
    <Button asChild variant="outline" size="sm">
      <Link
        data-monitor-this
        href={`/topics?${new URLSearchParams({ from: kind, record: id, locale })}`}
      >
        <Radar size={16} />
        {t("monitorThis.open")}
      </Link>
    </Button>
  );
}

// Only saved, supported cited answers offer this route. The server rechecks
// ownership and status; no answer text or question is put into the URL.
export function MonitorSavedAnswer({ id, status, answer }: {
  id: string;
  status: string;
  answer: { supported?: boolean; citations?: unknown[] } | null;
}) {
  if (status !== "succeeded" || answer?.supported !== true || !Array.isArray(answer.citations) || !answer.citations.length) return null;
  return <div className="mt-3" data-monitor-answer><MonitorThis kind="answer" id={id} /></div>;
}
