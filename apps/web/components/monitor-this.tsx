"use client";
import Link from "next/link";
import { Radar } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { Button } from "./ui/button";

export function MonitorThis({
  kind,
  id,
}: {
  kind: "event" | "law" | "comparison";
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
