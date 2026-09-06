"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BookOpen, PackageOpen, Radar } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import type { MonitoringContext } from "@/lib/types";
import { useAuth } from "./auth-gate";
import { AddDocumentDialog } from "./document-forms";
import { Button } from "./ui/button";

function sourceUrl(value?: string | null) {
  try {
    const parsed = new URL(value || "");
    return ["http:", "https:"].includes(parsed.protocol) && !parsed.username && !parsed.password ? parsed.href : "";
  } catch { return ""; }
}

export function MonitoringSetupChoices({ context, onTopic, topicDisabled, onLeave, headingLevel = 2 }: {
  context?: MonitoringContext | null;
  onTopic: () => void;
  topicDisabled?: boolean;
  onLeave: () => boolean;
  headingLevel?: 2 | 3;
}) {
  const { t } = useI18n();
  const { canManage } = useAuth();
  const router = useRouter();
  const [documentOpen, setDocumentOpen] = useState(false);
  const existing = context?.watches[0];
  const initialUrl = sourceUrl(context?.source_url);
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const ChoiceHeading = headingLevel === 2 ? "h3" : "h4";
  return (
    <section data-monitor-choices className="my-4" aria-label={t("monitorChoice.title")}>
      <Heading className="mb-3">{t("monitorChoice.title")}</Heading>
      <div className="grid gap-3 xl:grid-cols-3">
        <article className="rounded-lg border p-4 flex flex-col gap-2" data-monitor-choice="topic">
          <ChoiceHeading className="font-semibold flex items-center gap-2"><Radar size={18} />{t("monitorChoice.topic")}</ChoiceHeading>
          <p className="text-sm muted flex-1 m-0">{t("monitorChoice.topicHelp")}</p>
          <Button className="h-auto min-h-11 whitespace-normal" data-monitor-use type="button" onClick={onTopic} disabled={topicDisabled}>
            {context ? t("monitorThis.use") : t("monitorChoice.topicAction")}
          </Button>
        </article>
        <article className="rounded-lg border p-4 flex flex-col gap-2" data-monitor-choice="document">
          <ChoiceHeading className="font-semibold flex items-center gap-2"><BookOpen size={18} />{t("monitorChoice.document")}</ChoiceHeading>
          <p className="text-sm muted flex-1 m-0">{t("monitorChoice.documentHelp")}</p>
          {existing ? (
            <Button className="h-auto min-h-11 whitespace-normal" asChild variant="outline"><Link data-monitor-existing href={existing.url} onClick={event => { if (!onLeave()) event.preventDefault(); }}>{t("form.openExisting")}</Link></Button>
          ) : (
            <Button className="h-auto min-h-11 whitespace-normal" data-monitor-document type="button" variant="outline" disabled={!canManage}
              onClick={() => { if (onLeave()) setDocumentOpen(true); }}>{t("monitorChoice.documentAction")}</Button>
          )}
          {!canManage && !existing && <p className="text-xs muted m-0">{t("monitorChoice.documentRole")}</p>}
        </article>
        <article className="rounded-lg border p-4 flex flex-col gap-2" data-monitor-choice="pack">
          <ChoiceHeading className="font-semibold flex items-center gap-2"><PackageOpen size={18} />{t("monitorChoice.pack")}</ChoiceHeading>
          <p className="text-sm muted flex-1 m-0">{t("monitorChoice.packHelp")}</p>
          <Button className="h-auto min-h-11 whitespace-normal" asChild variant="outline"><Link data-monitor-packs href="/sources#source-packs" onClick={event => { if (!onLeave()) event.preventDefault(); }}>{t("monitorChoice.packAction")}</Link></Button>
        </article>
      </div>
      <p className="text-xs muted mt-3">{t("monitorChoice.boundary")}</p>
      {canManage && <AddDocumentDialog key={context ? `${context.kind}:${context.id}` : "new"}
        mode="law" open={documentOpen} onOpenChange={setDocumentOpen}
        initialUrl={initialUrl} initialName={initialUrl ? context?.title : ""}
        onCreated={record => router.push(`/laws/${encodeURIComponent(record.id)}`)} />}
    </section>
  );
}
