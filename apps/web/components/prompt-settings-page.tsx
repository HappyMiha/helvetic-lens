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
  dateTime,
  errorText,
  refreshWorkspace,
  useResource,
} from "@/lib/api";
import type { PromptSettings } from "@/lib/types";
import { ErrorNote, Loading, SuccessNote } from "./common";
import { ConfirmDeleteDialog } from "./confirm-delete-dialog";
import { Shell } from "./shell";

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
  title: string;
  description: string;
}[] = [
  {
    key: "impact_instructions",
    title: "Impact analysis",
    description:
      "Applied when Apertus reviews changed passages and proposes business actions.",
  },
  {
    key: "impact_synthesis_instructions",
    title: "Impact synthesis",
    description:
      "Combines validated batch reviews into the saved final assessment.",
  },
  {
    key: "ask_instructions",
    title: "Ask Apertus",
    description:
      "Controls tone and reasoning when answering questions about saved versions.",
  },
  {
    key: "answer_synthesis_instructions",
    title: "Answer synthesis",
    description: "Combines answers from complete multi-batch document context.",
  },
  {
    key: "repair_instructions",
    title: "Structured-output repair",
    description:
      "Used once when a provider returns invalid JSON or unsupported citations.",
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

export function PromptSettingsPage() {
  const configuration = useResource<PromptSettings>("/settings/prompts");
  return (
    <Shell section="Prompt settings" wide>
      <div className="page-heading">
        <div>
          <span className="eyebrow">AI BEHAVIOUR</span>
          <h1>Prompt settings</h1>
          <p className="muted m-0">
            Change how impact assessments and document answers are written.
            Every saved revision creates a new AI cache boundary while older
            conclusions remain in history.
          </p>
        </div>
        <FileText className="muted" size={29} />
      </div>
      <ErrorNote message={configuration.error} />
      {configuration.data ? (
        <PromptForm
          key={configuration.data.fingerprint}
          initial={configuration.data}
          onSaved={configuration.setData}
        />
      ) : (
        !configuration.error && (
          <section className="panel p-6">
            <Loading text="Loading saved prompts…" />
          </section>
        )
      )}
    </Shell>
  );
}

function PromptForm({
  initial,
  onSaved,
}: {
  initial: PromptSettings;
  onSaved: (value: PromptSettings) => void;
}) {
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
      const value = await api<PromptSettings>("/settings/prompts", {
        method: "PATCH",
        body: JSON.stringify(draft),
      });
      onSaved(value);
      setDraft(editable(value));
      setNotice(
        `Prompt revision ${value.revision} saved. Existing AI history was kept.`,
      );
      refreshWorkspace();
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
      const value = await api<PromptSettings>("/settings/prompts/reset", {
        method: "POST",
      });
      onSaved(value);
      setDraft(editable(value));
      setResetOpen(false);
      setNotice("Default prompts restored. Existing AI history was kept.");
      refreshWorkspace();
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
                <h2>Document context for questions</h2>
                <p className="text-sm muted mb-0">
                  Choose what Ask Apertus receives before it answers.
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
                <strong>Automatic complete context</strong>
                <span>
                  Uses the complete deterministic diff for change questions and
                  the full extracted text of both originals for other document
                  questions.
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
                <strong>Changed passages only</strong>
                <span>
                  Costs fewer tokens, but questions unrelated to the changes may
                  be marked unsupported.
                </span>
              </label>
            </div>
          </section>

          {editors.map((editor, index) => (
            <section className="panel prompt-editor" key={editor.key}>
              <div className="panel-header">
                <div>
                  <h2>{editor.title}</h2>
                  <p className="text-sm muted mb-0">{editor.description}</p>
                </div>
                <span className="count-pill">{index + 1}</span>
              </div>
              <div className="panel-body">
                <label className="sr-only" htmlFor={editor.key}>
                  {editor.title} prompt
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
                  {draft[editor.key].length.toLocaleString()} / 12,000
                  characters
                </p>
              </div>
            </section>
          ))}
        </div>

        <aside className="grid gap-5 xl:sticky xl:top-6">
          <section className="panel p-6">
            <Sparkles size={22} className="text-primary mb-4" />
            <h2>Saved prompt revision</h2>
            <p className="text-sm muted">
              Revision {initial.revision} · {initial.source}
              {initial.updated_at
                ? ` · updated ${dateTime(initial.updated_at)}`
                : ""}
            </p>
            <p className="text-sm muted">
              Repeating an identical question with the same comparison,
              settings, and prompt revision reuses the saved answer instead of
              calling the provider again.
            </p>
          </section>
          <section className="panel p-6">
            <h2>Fixed validation contract</h2>
            <p className="text-sm muted">
              The editable instructions are combined with server-controlled JSON
              schemas, complete-evidence rules, exact citation checks, and one
              repair attempt. These checks remain active even when you change
              the wording above.
            </p>
          </section>
          <section className="panel p-6">
            <h2>Original document files</h2>
            <p className="text-sm muted">
              Helvetic Lens keeps every original artifact. For general questions
              it sends the complete extracted text in bounded batches because
              the selected Apertus chat endpoint does not expose a documented
              PDF attachment contract.
            </p>
            <a
              className="text-link text-sm"
              href="https://developer.infomaniak.com/docs/api/post/2/ai/%7Bproduct_id%7D/openai/v1/chat/completions"
              target="_blank"
              rel="noreferrer"
            >
              Infomaniak chat API reference <ArrowUpRight size={13} />
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
              Save prompt revision
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!!busy || initial.source === "defaults"}
              onClick={() => setResetOpen(true)}
            >
              <RotateCcw />
              Restore defaults
            </Button>
          </div>
        </aside>
      </form>
      <ConfirmDeleteDialog
        open={resetOpen}
        onOpenChange={setResetOpen}
        title="Restore all default prompts?"
        description="Your custom prompt text will be removed. Saved documents, comparisons, AI conclusions, and question history will not be deleted."
        confirmLabel="Restore defaults"
        busy={busy === "reset"}
        error={resetOpen ? error : ""}
        onConfirm={() => void reset()}
      />
    </>
  );
}
