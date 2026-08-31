"use client";

import { useRef, useState } from "react";
import {
  ArrowUpRight,
  BookOpen,
  KeyRound,
  Loader2,
  Plug,
  RotateCcw,
  Save,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  api,
  dateTime,
  errorText,
  refreshWorkspace,
  useResource,
} from "@/lib/api";
import type { ApertusSettings, Health, Profile } from "@/lib/types";
import { ErrorNote, Loading, SuccessNote } from "./common";
import { ProfileDialog, Shell } from "./shell";

type KeyAction = "keep" | "replace" | "remove" | "environment";
type ConnectionResult = { model: string; base_url: string; latency_ms: number };

function draftValues(settings: ApertusSettings) {
  return {
    base_url: settings.base_url,
    model: settings.model,
    timeout_seconds: String(settings.timeout_seconds),
    context_chars: String(settings.context_chars),
    max_tokens: String(settings.max_tokens),
    temperature: String(settings.temperature),
    json_mode: settings.json_mode,
  };
}

export function SettingsPage() {
  const configuration = useResource<ApertusSettings>("/settings/apertus");
  const { data: health } = useResource<Health>("/health");
  const { data: profile } = useResource<Profile>("/profile");
  const [profileOpen, setProfileOpen] = useState(false);
  const [notice, setNotice] = useState("");
  return (
    <Shell section="Settings">
      <div className="page-heading">
        <div>
          <span className="eyebrow">WORKSPACE SETUP</span>
          <h1>Settings</h1>
          <p className="muted m-0">
            Configure Apertus and the company context behind its answers.
          </p>
        </div>
        <SlidersHorizontal className="muted" size={28} />
      </div>
      <ErrorNote message={configuration.error} />
      {notice && <SuccessNote>{notice}</SuccessNote>}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px] items-start">
        {configuration.data ? (
          <ApertusForm
            key={
              configuration.data.source + (configuration.data.updated_at || "")
            }
            initial={configuration.data}
            onSaved={(settings, message) => {
              configuration.setData(settings);
              setNotice(message);
              refreshWorkspace();
            }}
            onEdit={() => setNotice("")}
          />
        ) : (
          <div className="panel p-6">
            <Loading />
          </div>
        )}
        <div className="grid gap-5">
          <section className="panel p-6">
            <Sparkles size={21} className="text-primary mb-4" />
            <h2 className="mb-3">Your Apertus connection</h2>
            <p className="text-sm muted">
              {configuration.data?.configured
                ? "An endpoint is configured. Use Test connection to verify that it answers."
                : "No endpoint is configured yet. Monitoring and visual comparisons remain available."}
            </p>
            <p className="text-sm muted">
              RegWatch calls an OpenAI-compatible chat API. It does not download
              a model or provision a server.
            </p>
            <a
              href="https://huggingface.co/swiss-ai/Apertus-v1.5-8B"
              target="_blank"
              rel="noreferrer"
              className="text-sm inline-flex gap-2 items-center"
            >
              Apertus model card <ArrowUpRight size={14} />
            </a>
          </section>
          <section className="panel p-6">
            <BookOpen size={21} className="muted mb-4" />
            <h2 className="mb-2">Company profile</h2>
            <p className="text-sm font-medium">
              {profile?.name || "My company"}
            </p>
            <p className="text-sm muted break-words">
              {profile?.business_areas.join(" · ") ||
                "Choose the business areas you want Apertus to consider."}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setProfileOpen(true)}
            >
              Edit company profile
            </Button>
          </section>
          <section className="panel p-6">
            <h2 className="mb-3">Workspace</h2>
            <p className="text-sm muted">
              Database: {health?.database || "Checking…"}
            </p>
            <p className="text-sm muted">
              Settings and document history persist in this workspace. Model
              changes apply immediately; existing evidence and comparisons are
              kept.
            </p>
            <p className="text-xs muted">
              This is a local, single-user app. Keep the database and its
              backups private, especially if you save a model key.
            </p>
          </section>
        </div>
      </div>
      <ProfileDialog
        open={profileOpen}
        onOpenChange={setProfileOpen}
        health={health}
      />
    </Shell>
  );
}

function ApertusForm({
  initial,
  onSaved,
  onEdit,
}: {
  initial: ApertusSettings;
  onSaved: (settings: ApertusSettings, message: string) => void;
  onEdit: () => void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const [draft, setDraft] = useState(() => draftValues(initial));
  const [keyAction, setKeyAction] = useState<KeyAction>("keep");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [testResult, setTestResult] = useState<ConnectionResult | null>(null);
  const dirty =
    JSON.stringify(draft) !== JSON.stringify(draftValues(initial)) ||
    keyAction !== "keep";
  function changed() {
    onEdit();
    setError("");
    setTestResult(null);
  }
  function update<K extends keyof typeof draft>(
    key: K,
    value: (typeof draft)[K],
  ) {
    changed();
    setDraft((current) => ({ ...current, [key]: value }));
  }
  function body() {
    return JSON.stringify({
      ...draft,
      timeout_seconds: Number(draft.timeout_seconds),
      context_chars: Number(draft.context_chars),
      max_tokens: Number(draft.max_tokens),
      temperature: Number(draft.temperature),
      key_action: keyAction,
      api_key: keyAction === "replace" ? apiKey : "",
    });
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy("save");
    setError("");
    try {
      const result = await api<ApertusSettings>("/settings/apertus", {
        method: "PATCH",
        body: body(),
      });
      setApiKey("");
      onSaved(
        result,
        "Apertus settings saved and applied. No restart is needed.",
      );
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  async function test() {
    if (!formRef.current?.reportValidity()) return;
    setBusy("test");
    setError("");
    setTestResult(null);
    try {
      const result = await api<ConnectionResult>("/settings/apertus/test", {
        method: "POST",
        body: body(),
      });
      setTestResult(result);
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
      const result = await api<ApertusSettings>("/settings/apertus/reset", {
        method: "POST",
      });
      setApiKey("");
      onSaved(
        result,
        "Saved overrides removed. Apertus now uses the server environment defaults.",
      );
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  return (
    <section className="panel min-w-0">
      <div className="panel-header flex-wrap gap-3">
        <h2 className="inline-flex gap-2 items-center">
          <Sparkles size={18} /> Apertus
        </h2>
        <span className="text-xs muted">
          {dirty
            ? "Unsaved changes"
            : initial.source === "workspace"
              ? "Saved in this workspace"
              : "Using environment defaults"}
        </span>
      </div>
      <form ref={formRef} onSubmit={save} className="p-6">
        <fieldset disabled={!!busy} className="form-stack min-w-0">
          <div className="rounded-lg border p-4">
            <div className="flex flex-wrap gap-3 items-center">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  changed();
                  setDraft((current) => ({
                    ...current,
                    base_url: "https://router.huggingface.co/v1",
                    model: "swiss-ai/Apertus-v1.5-8B:publicai",
                  }));
                }}
              >
                Use Hugging Face
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  changed();
                  setDraft((current) => ({
                    ...current,
                    base_url: "https://api.publicai.co/v1",
                    model: "swiss-ai/apertus-v1.5-8b",
                  }));
                }}
              >
                Use Public AI defaults
              </Button>
              <a
                href="https://platform.publicai.co/docs"
                target="_blank"
                rel="noreferrer"
                className="text-xs inline-flex items-center gap-1"
              >
                Public AI setup <ArrowUpRight size={12} />
              </a>
              <a
                href="https://huggingface.co/docs/inference-providers/providers/publicai"
                target="_blank"
                rel="noreferrer"
                className="text-xs inline-flex items-center gap-1"
              >
                Hugging Face setup <ArrowUpRight size={12} />
              </a>
            </div>
            <p className="field-help !mb-0">
              Fills the API address and model ID only. Your key and other
              parameters stay unchanged. Test before saving.
            </p>
            <p className="field-help !mb-0">
              Hugging Face needs a Hugging Face token with Inference Providers
              permission. Direct Public AI needs a Public AI API key. These
              credentials are not interchangeable.
            </p>
          </div>
          <label>
            API base URL
            <Input
              type="url"
              autoComplete="url"
              placeholder="http://localhost:8080/v1"
              value={draft.base_url}
              onChange={(event) => update("base_url", event.target.value)}
              maxLength={2000}
            />
            <span className="field-help">
              Include /v1 if your server uses it. RegWatch adds
              /chat/completions. A Hugging Face model page is not an API base
              URL. Leave empty to disconnect.
            </span>
          </label>
          <label>
            Model ID
            <Input
              value={draft.model}
              onChange={(event) => update("model", event.target.value)}
              required
              maxLength={300}
            />
            <span className="field-help">
              Use the exact, case-sensitive name served by your endpoint.
              Provider IDs can differ from the Hugging Face model name.
            </span>
          </label>
          <div className="rounded-lg border p-4 min-w-0">
            <div className="flex items-center gap-2 text-sm font-semibold mb-2">
              <KeyRound size={15} /> API key
            </div>
            <p className="text-xs muted">
              {initial.api_key_configured
                ? "A key is configured (" +
                  initial.key_source +
                  "). Its value is never sent back to your browser."
                : "No key is configured. Some local inference servers do not need one."}
            </p>
            <label>
              Key handling
              <select
                value={keyAction}
                onChange={(event) => {
                  changed();
                  setKeyAction(event.target.value as KeyAction);
                  setApiKey("");
                }}
              >
                <option value="keep">Keep existing key</option>
                <option value="replace">Replace with a new key</option>
                <option value="remove">Use no key</option>
                <option value="environment">
                  Use the server environment key
                </option>
              </select>
            </label>
            {keyAction === "replace" && (
              <label className="mt-3 block">
                New API key
                <Input
                  type="password"
                  autoComplete="new-password"
                  placeholder="Paste your inference API key"
                  value={apiKey}
                  onChange={(event) => {
                    changed();
                    setApiKey(event.target.value);
                  }}
                  required
                  maxLength={4000}
                />
              </label>
            )}
            <p className="field-help">
              Saved keys stay in the server database, outside Git. Leave the
              existing key unchanged when editing other parameters.
            </p>
          </div>
          <div className="pt-2">
            <h3 className="text-sm font-semibold mb-4">
              Requests and generation
            </h3>
            <div className="grid sm:grid-cols-2 gap-4">
              <label>
                Request timeout (seconds)
                <Input
                  type="number"
                  min={5}
                  max={300}
                  step={1}
                  required
                  value={draft.timeout_seconds}
                  onChange={(event) =>
                    update("timeout_seconds", event.target.value)
                  }
                />
                <span className="field-help">
                  5–300 seconds. A timeout keeps the saved diff available.
                </span>
              </label>
              <label>
                Evidence budget (characters)
                <Input
                  type="number"
                  min={1000}
                  max={100000}
                  step={1}
                  required
                  value={draft.context_chars}
                  onChange={(event) =>
                    update("context_chars", event.target.value)
                  }
                />
                <span className="field-help">
                  Selected source text sent to Apertus. This is not the
                  model&apos;s token limit.
                </span>
              </label>
              <label>
                Maximum answer length (tokens)
                <Input
                  type="number"
                  min={128}
                  max={8192}
                  step={1}
                  required
                  value={draft.max_tokens}
                  onChange={(event) => update("max_tokens", event.target.value)}
                />
                <span className="field-help">
                  Allow enough space for the answer and its citations.
                </span>
              </label>
              <label>
                Temperature
                <Input
                  type="number"
                  min={0}
                  max={2}
                  step="any"
                  required
                  value={draft.temperature}
                  onChange={(event) =>
                    update("temperature", event.target.value)
                  }
                />
                <span className="field-help">
                  Default 0.1. Use a value supported by your inference server.
                </span>
              </label>
            </div>
          </div>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={draft.json_mode}
              onChange={(event) => update("json_mode", event.target.checked)}
            />
            Request structured JSON mode
          </label>
          <p className="field-help !mt-0">
            Enable only if your endpoint supports response_format: json_object.
            Answers and citations are validated with either setting.
          </p>
          <ErrorNote message={error} />
          {testResult && (
            <div role="status" className="info-note break-words">
              <strong>
                Connection verified · {testResult.latency_ms.toLocaleString()}{" "}
                ms
              </strong>
              <p>Received a real response from {testResult.model}.</p>
              <p className="text-xs">
                This checked the values in this form without saving them. A
                connection check does not yet verify an evidence-backed
                analysis.
              </p>
            </div>
          )}
          <div className="form-actions flex-wrap gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={test}
              disabled={!!busy || !draft.base_url.trim()}
            >
              {busy === "test" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Plug />
              )}
              Test connection
            </Button>
            <Button
              type="submit"
              disabled={!!busy || (!dirty && initial.source === "workspace")}
            >
              {busy === "save" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Save />
              )}
              Save settings
            </Button>
          </div>
          <p className="text-xs muted">
            Changes apply to new requests immediately. Changing the endpoint,
            model, evidence budget, or generation settings marks previous
            analyses as stale.
          </p>
        </fieldset>
      </form>
      <div className="border-t px-6 py-4 flex gap-4 flex-wrap items-center justify-between">
        <span className="text-xs muted">
          {initial.updated_at
            ? "Last saved " + dateTime(initial.updated_at)
            : "No saved overrides."}
        </span>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={reset}
          disabled={!!busy || initial.source !== "workspace"}
        >
          {busy === "reset" ? (
            <Loader2 className="animate-spin" />
          ) : (
            <RotateCcw size={14} />
          )}
          Use environment defaults
        </Button>
        <p className="text-xs muted basis-full !mb-0">
          Restoring defaults removes saved overrides, including a saved key, and
          uses the server&apos;s current environment. Your document history is
          unchanged.
        </p>
      </div>
    </section>
  );
}
