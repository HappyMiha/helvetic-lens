"use client";

import { useState } from "react";
import {
  ArrowUpRight,
  FileText,
  Loader2,
  RotateCcw,
  Save,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  api,
  errorText,
  invalidateResources,
  resourceTag,
  useResource,
} from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import type { PromptSettings } from "@/lib/types";
import { ErrorNote, Loading, SuccessNote } from "./common";
import { ConfirmDeleteDialog } from "./confirm-delete-dialog";
import { Shell } from "./shell";
import { useAuth } from "./auth-gate";
import { useI18n } from "@/lib/i18n";

type EditablePrompt = Pick<
  PromptSettings,
  | "impact_instructions"
  | "impact_synthesis_instructions"
  | "ask_instructions"
  | "answer_synthesis_instructions"
  | "repair_instructions"
  | "ask_context_mode"
>;

const editors: {
  key: Exclude<keyof EditablePrompt, "ask_context_mode">;
  titleKey: string;
  descriptionKey: string;
}[] = [
  {
    key: "impact_instructions",
    titleKey: "prompts.impact", descriptionKey: "prompts.impactBody",
  },
  {
    key: "impact_synthesis_instructions",
    titleKey: "prompts.impactSynthesis", descriptionKey: "prompts.impactSynthesisBody",
  },
  {
    key: "ask_instructions",
    titleKey: "prompts.ask", descriptionKey: "prompts.askBody",
  },
  {
    key: "answer_synthesis_instructions",
    titleKey: "prompts.answerSynthesis", descriptionKey: "prompts.answerSynthesisBody",
  },
  {
    key: "repair_instructions",
    titleKey: "prompts.repair", descriptionKey: "prompts.repairBody",
  },
];

function editable(settings: PromptSettings): EditablePrompt {
  return {
    impact_instructions: settings.impact_instructions,
    impact_synthesis_instructions: settings.impact_synthesis_instructions,
    ask_instructions: settings.ask_instructions,
    answer_synthesis_instructions: settings.answer_synthesis_instructions,
    repair_instructions: settings.repair_instructions,
    ask_context_mode: settings.ask_context_mode,
  };
}

export function PromptSettingsPage({ platformScope = false }: { platformScope?: boolean }) {
  const { t } = useI18n();
  const { canManage, isPlatformAdmin } = useAuth();
  const allowed = platformScope ? isPlatformAdmin : canManage;
  const endpoint = platformScope ? "/admin/prompts" : "/settings/prompts";
  const configuration = useResource(
    allowed
      ? resources.prompts(platformScope ? "platform" : "organization")
      : null,
  );
  return (
    <Shell section={t("nav.prompts")} wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{platformScope ? t("prompts.platformEyebrow") : t("prompts.orgEyebrow")}</span>
          <h1>{platformScope ? t("prompts.globalTitle") : t("prompts.orgTitle")}</h1>
          <p className="muted m-0">
            {t("prompts.body")} {" "}
            {platformScope
              ? t("prompts.platformBody")
              : t("prompts.orgBody")}
          </p>
        </div>
        <FileText className="muted" size={29} />
      </div>
      {!allowed ? (
        <ErrorNote
          message={t(platformScope ? "admin.denied" : "error.viewer_read_only")}
        />
      ) : configuration.data ? (
        <fieldset className="border-0 p-0 m-0">
          <PromptForm
            key={configuration.data.fingerprint}
            initial={configuration.data}
            onSaved={configuration.setData}
            endpoint={endpoint}
            platformScope={platformScope}
          />
        </fieldset>
      ) : (
        <>
          <ErrorNote message={configuration.error} />
          {!configuration.error && (
            <section className="panel p-6">
              <Loading text={t("prompts.loading")} />
            </section>
          )}
        </>
      )}
    </Shell>
  );
}

function PromptForm({
  initial,
  onSaved,
  endpoint,
  platformScope,
}: {
  initial: PromptSettings;
  onSaved: (value: PromptSettings) => void;
  endpoint: string;
  platformScope: boolean;
}) {
  const { t, dateTime, number } = useI18n();
  const [draft, setDraft] = useState<EditablePrompt>(() => editable(initial));
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [resetOpen, setResetOpen] = useState(false);
  const dirty = JSON.stringify(draft) !== JSON.stringify(editable(initial));

  function update<K extends keyof EditablePrompt>(
    key: K,
    value: EditablePrompt[K],
  ) {
    setError("");
    setNotice("");
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy("save");
    setError("");
    try {
      const value = await api<PromptSettings>(endpoint, {
        method: "PATCH",
        body: JSON.stringify(draft),
      });
      onSaved(value);
      setDraft(editable(value));
      setNotice(
        t("prompts.savedNotice", { revision: value.revision }),
      );
      void invalidateResources(
        resources.organizationStatus(),
        ...(platformScope ? [resources.prompts("organization")] : []),
        resourceTag("comparison", "organization"),
        resourceTag("ai-history", "organization"),
        resourceTag("impact-matrix", "organization"),
        resourceTag("impact-inbox", "organization"),
        resourceTag("registry", "organization"),
      );
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  async function reset() {
    setBusy("reset");
    setError("");
    try {
      const value = await api<PromptSettings>(platformScope ? endpoint : "/settings/prompts/reset", {
        method: platformScope ? "DELETE" : "POST",
      });
      onSaved(value);
      setDraft(editable(value));
      setResetOpen(false);
      setNotice(
        platformScope
          ? t("prompts.platformRestored")
          : t("prompts.orgRestored"),
      );
      void invalidateResources(
        resources.organizationStatus(),
        ...(platformScope ? [resources.prompts("organization")] : []),
        resourceTag("comparison", "organization"),
        resourceTag("ai-history", "organization"),
        resourceTag("impact-matrix", "organization"),
        resourceTag("impact-inbox", "organization"),
        resourceTag("registry", "organization"),
      );
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <form
        onSubmit={save}
        className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_330px] items-start"
      >
        <div className="grid gap-5">
          <section className="panel p-6">
            <div className="panel-header !p-0 !pb-5 !border-0">
              <div>
                <h2>{t("prompts.contextTitle")}</h2>
                <p className="text-sm muted mb-0">
                  {t("prompts.contextBody")}
                </p>
              </div>
            </div>
            <div className="prompt-context-grid">
              <label
                className={
                  "prompt-context-option " +
                  (draft.ask_context_mode === "automatic" ? "selected" : "")
                }
              >
                <input
                  type="radio"
                  name="ask-context"
                  checked={draft.ask_context_mode === "automatic"}
                  onChange={() => update("ask_context_mode", "automatic")}
                />
                <strong>{t("prompts.automatic")}</strong>
                <span>
                  {t("prompts.automaticBody")}
                </span>
              </label>
              <label
                className={
                  "prompt-context-option " +
                  (draft.ask_context_mode === "changes_only" ? "selected" : "")
                }
              >
                <input
                  type="radio"
                  name="ask-context"
                  checked={draft.ask_context_mode === "changes_only"}
                  onChange={() => update("ask_context_mode", "changes_only")}
                />
                <strong>{t("prompts.changes")}</strong>
                <span>
                  {t("prompts.changesBody")}
                </span>
              </label>
            </div>
          </section>

          {editors.map((editor, index) => (
            <section className="panel prompt-editor" key={editor.key}>
              <div className="panel-header">
                <div>
                  <h2>{t(editor.titleKey)}</h2>
                  <p className="text-sm muted mb-0">{t(editor.descriptionKey)}</p>
                </div>
                <span className="count-pill">{index + 1}</span>
              </div>
              <div className="panel-body">
                <label className="sr-only" htmlFor={editor.key}>
                  {t("prompts.promptLabel", { title: t(editor.titleKey) })}
                </label>
                <Textarea
                  id={editor.key}
                  rows={7}
                  maxLength={12000}
                  minLength={20}
                  required
                  value={draft[editor.key]}
                  onChange={(event) => update(editor.key, event.target.value)}
                />
                <p className="field-help">
                  {t("prompts.characters", { count: number(draft[editor.key].length) })}
                </p>
              </div>
            </section>
          ))}
        </div>

        <aside className="grid gap-5 xl:sticky xl:top-6">
          <section className="panel p-6">
            <Sparkles size={22} className="text-primary mb-4" />
            <h2>{t("prompts.saved")}</h2>
            <p className="text-sm muted">
              {t("prompts.revision", { revision: initial.revision, source: initial.source, updated: initial.updated_at ? t("prompts.updated", { date: dateTime(initial.updated_at) }) : "" })}
            </p>
            <p className="text-sm muted">
              {t("prompts.cache")}
            </p>
          </section>
          <section className="panel p-6">
            <h2>{t("prompts.contract")}</h2>
            <p className="text-sm muted">
              {t("prompts.contractBody")}
            </p>
          </section>
          <section className="panel p-6">
            <h2>{t("prompts.files")}</h2>
            <p className="text-sm muted">
              {t("prompts.filesBody")}
            </p>
            <a
              className="text-link text-sm"
              href="https://developer.infomaniak.com/docs/api/post/2/ai/%7Bproduct_id%7D/openai/v1/chat/completions"
              target="_blank"
              rel="noreferrer"
            >
              {t("prompts.apiReference")} <ArrowUpRight size={13} />
            </a>
          </section>
          <ErrorNote message={error} />
          {notice && <SuccessNote>{notice}</SuccessNote>}
          <div className="grid gap-2">
            <Button type="submit" disabled={!dirty || !!busy}>
              {busy === "save" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Save />
              )}
              {t("prompts.save")}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!!busy || initial.source === "defaults"}
              onClick={() => setResetOpen(true)}
            >
              <RotateCcw />
              {t("prompts.restore")}
            </Button>
          </div>
        </aside>
      </form>
      <ConfirmDeleteDialog
        open={resetOpen}
        onOpenChange={setResetOpen}
        title={t("prompts.restoreTitle")}
        description={t("prompts.restoreBody")}
        confirmLabel={t("prompts.restore")}
        busy={busy === "reset"}
        error={resetOpen ? error : ""}
        onConfirm={() => void reset()}
      />
    </>
  );
}
