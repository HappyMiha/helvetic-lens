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
import type {
  ApertusModelList,
  ApertusModelOption,
  ApertusSettings,
  Health,
  Profile,
} from "@/lib/types";
import { ErrorNote, Loading, SuccessNote } from "./common";
import { ProfileDialog, Shell } from "./shell";

type KeyAction = "keep" | "replace" | "remove" | "environment";
type Provider = "custom" | "docker" | "infomaniak";
type ConnectionResult = {
  model: string;
  base_url: string;
  latency_ms: number;
};

const INFOMANIAK_API_ROOT = "https://api.infomaniak.com/2/ai";
const LOCAL_DOCKER_MODEL = "local-apertus";

function infomaniakBaseUrl(productId: string) {
  return productId.trim()
    ? `${INFOMANIAK_API_ROOT}/${productId.trim()}/openai/v1`
    : "";
}

function draftValues(settings: ApertusSettings) {
  return {
    provider: settings.provider,
    product_id: settings.product_id,
    base_url: settings.base_url,
    model: settings.model,
    timeout_seconds: String(settings.timeout_seconds),
    request_retries: String(settings.request_retries),
    batch_concurrency: String(settings.batch_concurrency),
    context_chars: String(settings.context_chars),
    max_tokens: String(settings.max_tokens),
    temperature: String(settings.temperature),
    top_p: String(settings.top_p),
    presence_penalty: String(settings.presence_penalty),
    reasoning_effort: settings.reasoning_effort,
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
            Configure the Apertus provider, model, request parameters, and
            company context.
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
                ? `${configuration.data.provider === "infomaniak" ? "Infomaniak" : configuration.data.provider === "docker" ? "Local Docker Apertus" : "An OpenAI-compatible endpoint"} is configured. Use Test connection to verify that it answers.`
                : "No endpoint is configured yet. Monitoring and visual comparisons remain available."}
            </p>
            <p className="text-sm muted">
              Current model: {configuration.data?.model || "Not selected"}.
              Helvetic Lens calls an OpenAI-compatible chat API. The local
              Docker provider hosts Apertus beside the app; cloud providers
              remain optional.
            </p>
            <a
              href={`https://huggingface.co/${configuration.data?.model || "swiss-ai/Apertus-v1.5-8B"}`}
              target="_blank"
              rel="noreferrer"
              className="text-sm inline-flex gap-2 items-center"
            >
              Current model card <ArrowUpRight size={14} />
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
              backups private, especially if you save a provider credential.
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
  const [models, setModels] = useState<ApertusModelOption[]>([]);
  const [modelsMessage, setModelsMessage] = useState("");
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
  function chooseProvider(provider: Provider) {
    changed();
    setModels([]);
    setModelsMessage("");
    setDraft((current) => {
      if (provider === "docker") {
        return {
          ...current,
          provider,
          base_url: "",
          model: LOCAL_DOCKER_MODEL,
          context_chars: "6000",
          max_tokens: "700",
          batch_concurrency: "1",
          json_mode: true,
        };
      }
      return {
        ...current,
        provider,
        product_id: current.product_id,
        base_url:
          provider === "infomaniak"
            ? infomaniakBaseUrl(current.product_id)
            : current.provider === "infomaniak" || current.provider === "docker"
              ? ""
              : current.base_url,
      };
    });
  }
  function customPreset(baseUrl: string, model: string) {
    changed();
    setModels([]);
    setModelsMessage("");
    setDraft((current) => ({
      ...current,
      provider: "custom",
      product_id: current.product_id,
      base_url: baseUrl,
      model,
    }));
  }
  function body() {
    const baseUrl =
      draft.provider === "infomaniak"
        ? infomaniakBaseUrl(draft.product_id)
        : draft.provider === "docker"
          ? ""
          : draft.base_url;
    return JSON.stringify({
      ...draft,
      base_url: baseUrl,
      timeout_seconds: Number(draft.timeout_seconds),
      request_retries: Number(draft.request_retries),
      batch_concurrency: Number(draft.batch_concurrency),
      context_chars: Number(draft.context_chars),
      max_tokens: Number(draft.max_tokens),
      temperature: Number(draft.temperature),
      top_p: Number(draft.top_p),
      presence_penalty: Number(draft.presence_penalty),
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
        "Apertus integration settings saved and applied. No restart is needed.",
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
  async function loadModels() {
    if (!formRef.current?.reportValidity()) return;
    setBusy("models");
    setError("");
    setModelsMessage("");
    try {
      const result = await api<ApertusModelList>("/settings/apertus/models", {
        method: "POST",
        body: body(),
      });
      setModels(result.models);
      if (draft.provider === "docker") {
        setDraft((current) => ({ ...current, base_url: result.base_url }));
      }
      const currentAvailable = result.models.some(
        (option) => option.id === draft.model,
      );
      if (!currentAvailable) {
        const preferred =
          result.models.find((option) =>
            option.id.toLowerCase().includes("apertus-v1.1-1.5b-instruct"),
          ) ||
          result.models.find((option) =>
            option.id.toLowerCase().includes("apertus-v1.5-8b"),
          ) ||
          result.models.find((option) =>
            option.id.toLowerCase().includes("apertus"),
          ) ||
          result.models[0];
        if (preferred) update("model", preferred.id);
      }
      setModelsMessage(
        `${result.count.toLocaleString()} models loaded from the provider API.`,
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
          <div className="grid sm:grid-cols-2 gap-4">
            <label>
              Inference provider
              <select
                value={draft.provider}
                onChange={(event) =>
                  chooseProvider(event.target.value as Provider)
                }
              >
                <option value="infomaniak">Infomaniak AI</option>
                <option value="docker">Local Docker Apertus</option>
                <option value="custom">Other OpenAI-compatible API</option>
              </select>
              <span className="field-help">
                Infomaniak and the local Docker service build their API
                addresses automatically and can load their available models.
              </span>
            </label>
            <div className="rounded-lg border p-4 text-sm">
              <strong>
                {draft.provider === "infomaniak"
                  ? "Infomaniak integration"
                  : draft.provider === "docker"
                    ? "Local Docker integration"
                    : "Custom integration"}
              </strong>
              <p className="field-help !mb-0">
                One active provider is used for connection checks, impact
                analysis, and Ask Apertus.
              </p>
            </div>
          </div>
          {draft.provider === "infomaniak" ? (
            <div className="rounded-lg border p-4 form-stack min-w-0">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold mb-1">Infomaniak AI</h3>
                  <p className="field-help !m-0">
                    The endpoint is generated from the Product ID, so there is
                    no URL to edit by hand.
                  </p>
                </div>
                <a
                  href="https://developer.infomaniak.com/docs/api/post/2/ai/%7Bproduct_id%7D/openai/v1/chat/completions"
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs inline-flex items-center gap-1"
                >
                  Infomaniak API docs <ArrowUpRight size={12} />
                </a>
              </div>
              <label>
                AI Product ID
                <Input
                  inputMode="numeric"
                  pattern="[0-9]+"
                  placeholder="123456"
                  value={draft.product_id}
                  onChange={(event) => {
                    const productId = event.target.value;
                    changed();
                    setModels([]);
                    setModelsMessage("");
                    setDraft((current) => ({
                      ...current,
                      product_id: productId,
                      base_url: infomaniakBaseUrl(productId),
                    }));
                  }}
                  required
                  maxLength={30}
                />
                <span className="field-help">
                  Use the numeric Product ID shown in the Infomaniak Manager.
                </span>
              </label>
              <label>
                API base URL
                <Input
                  value={infomaniakBaseUrl(draft.product_id)}
                  readOnly
                  aria-readonly="true"
                  placeholder="Generated after entering a Product ID"
                />
                <span className="field-help">
                  Helvetic Lens controls this address and adds /models or
                  /chat/completions for each request.
                </span>
              </label>
              <label>
                Model
                <select
                  value={draft.model}
                  onChange={(event) => update("model", event.target.value)}
                  required
                >
                  {!models.some((option) => option.id === draft.model) && (
                    <option value={draft.model}>{draft.model}</option>
                  )}
                  {models.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.id}
                      {option.owned_by ? ` · ${option.owned_by}` : ""}
                    </option>
                  ))}
                </select>
                <span className="field-help">
                  Load the current list from this Product ID, then choose the
                  exact model served by Infomaniak.
                </span>
              </label>
              <div className="flex flex-wrap gap-3 items-center">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={loadModels}
                  disabled={!draft.product_id.trim()}
                >
                  {busy === "models" ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    <RotateCcw size={14} />
                  )}
                  {models.length ? "Refresh model list" : "Load models"}
                </Button>
                {modelsMessage && (
                  <span role="status" className="text-xs text-primary">
                    {modelsMessage}
                  </span>
                )}
              </div>
            </div>
          ) : draft.provider === "docker" ? (
            <div className="rounded-lg border p-4 form-stack min-w-0">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold mb-1">
                    Local Docker Apertus
                  </h3>
                  <p className="field-help !m-0">
                    Uses a dedicated llama.cpp container beside Helvetic Lens.
                    The API service selects the correct host or container
                    address automatically.
                  </p>
                </div>
                <a
                  href="https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md"
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs inline-flex items-center gap-1"
                >
                  llama.cpp Docker docs <ArrowUpRight size={12} />
                </a>
              </div>
              <label>
                API base URL
                <Input
                  value={draft.base_url || "Selected automatically when tested"}
                  readOnly
                  aria-readonly="true"
                />
                <span className="field-help">
                  Local host processes use port 12435; the Compose API reaches
                  the local-apertus service on the internal network.
                </span>
              </label>
              <label>
                Local model
                <select
                  value={draft.model}
                  onChange={(event) => update("model", event.target.value)}
                  required
                >
                  {!models.some((option) => option.id === draft.model) && (
                    <option value={draft.model}>{draft.model}</option>
                  )}
                  {models.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.id}
                    </option>
                  ))}
                </select>
                <span className="field-help">
                  The 1.5B model is the lightweight local development profile.
                  Its 4,096-token slot receives a bounded meaningful-change
                  dossier or targeted question evidence; larger local Apertus
                  profiles can be selected when the host has enough memory.
                </span>
              </label>
              <div className="flex flex-wrap gap-3 items-center">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={loadModels}
                >
                  {busy === "models" ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    <RotateCcw size={14} />
                  )}
                  {models.length ? "Refresh local models" : "Load local models"}
                </Button>
                {modelsMessage && (
                  <span role="status" className="text-xs text-primary">
                    {modelsMessage}
                  </span>
                )}
              </div>
            </div>
          ) : (
            <>
              <div className="rounded-lg border p-4">
                <div className="flex flex-wrap gap-3 items-center">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      customPreset(
                        "https://router.huggingface.co/v1",
                        "swiss-ai/Apertus-v1.5-8B:publicai",
                      )
                    }
                  >
                    Use Hugging Face
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      customPreset(
                        "https://api.publicai.co/v1",
                        "swiss-ai/apertus-v1.5-8b",
                      )
                    }
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
                  Presets fill the API address and model only. Credentials and
                  generation parameters stay unchanged.
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
                  Include /v1 if required. Helvetic Lens adds /chat/completions.
                  Leave empty to disconnect.
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
                  Use the exact, case-sensitive ID served by the endpoint.
                </span>
              </label>
            </>
          )}
          {draft.provider === "docker" ? (
            <div className="rounded-lg border p-4 min-w-0 text-sm">
              <div className="flex items-center gap-2 font-semibold mb-2">
                <KeyRound size={15} /> No local credential required
              </div>
              <p className="field-help !mb-0">
                Helvetic Lens never sends the saved Infomaniak token to the
                local container. The remote credential remains preserved when
                you test or save this local provider.
              </p>
            </div>
          ) : (
            <div className="rounded-lg border p-4 min-w-0">
              <div className="flex items-center gap-2 text-sm font-semibold mb-2">
                <KeyRound size={15} />
                {draft.provider === "infomaniak" ? "API token" : "API key"}
              </div>
              <p className="text-xs muted">
                {initial.api_key_configured
                  ? "A credential is configured (" +
                    initial.key_source +
                    "). Its value is never sent back to your browser."
                  : "No credential is configured. Some local inference servers do not need one."}
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
                  <option value="keep">Keep existing credential</option>
                  <option value="replace">Replace with a new credential</option>
                  <option value="remove">Use no credential</option>
                  <option value="environment">
                    Use the server environment credential
                  </option>
                </select>
              </label>
              {keyAction === "replace" && (
                <label className="mt-3 block">
                  {draft.provider === "infomaniak"
                    ? "New API token"
                    : "New API key"}
                  <Input
                    type="password"
                    autoComplete="new-password"
                    placeholder={
                      draft.provider === "infomaniak"
                        ? "Paste your Infomaniak API token"
                        : "Paste your inference API key"
                    }
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
                Saved credentials stay in the server database, outside Git.
                Leave the existing credential unchanged when editing other
                parameters.
              </p>
            </div>
          )}
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
                Automatic retries
                <Input
                  type="number"
                  min={0}
                  max={5}
                  step={1}
                  required
                  value={draft.request_retries}
                  onChange={(event) =>
                    update("request_retries", event.target.value)
                  }
                />
                <span className="field-help">
                  Retry interrupted, rate-limited, and temporary provider
                  failures. Two retries means at most three attempts.
                </span>
              </label>
              <label>
                Concurrent model requests
                <Input
                  type="number"
                  min={1}
                  max={4}
                  step={1}
                  required
                  value={draft.batch_concurrency}
                  onChange={(event) =>
                    update("batch_concurrency", event.target.value)
                  }
                />
                <span className="field-help">
                  Controls how many requests from one bounded analysis plan may
                  run together. Use 1 for memory-constrained local models or
                  large hosted models.
                </span>
              </label>
              <label>
                Evidence target per model request (characters)
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
                  Groups the meaningful-change dossier or targeted question
                  evidence into requests of about this size. It never truncates
                  the saved exact diff or original artifacts; limited AI
                  coverage is reported explicitly.
                  {draft.provider === "docker"
                    ? " The 6,000-character local preset is calibrated for the 4,096-token runner."
                    : ""}
                </span>
              </label>
              <label>
                Maximum completion length (tokens)
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
                  Sent as max_completion_tokens to Infomaniak and max_tokens to
                  other compatible endpoints.
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
                  0–2. Lower values keep regulatory answers consistent.
                </span>
              </label>
              <label>
                Top P
                <Input
                  type="number"
                  min={0}
                  max={1}
                  step="any"
                  required
                  value={draft.top_p}
                  onChange={(event) => update("top_p", event.target.value)}
                />
                <span className="field-help">
                  0–1. Default 1 keeps nucleus sampling unrestricted.
                </span>
              </label>
              <label>
                Presence penalty
                <Input
                  type="number"
                  min={-1.99}
                  max={1.99}
                  step="any"
                  required
                  value={draft.presence_penalty}
                  onChange={(event) =>
                    update("presence_penalty", event.target.value)
                  }
                />
                <span className="field-help">
                  Greater than −2 and less than 2. Default 0 adds no penalty.
                </span>
              </label>
              <label>
                Reasoning effort
                <select
                  value={draft.reasoning_effort}
                  onChange={(event) =>
                    update(
                      "reasoning_effort",
                      event.target.value as typeof draft.reasoning_effort,
                    )
                  }
                >
                  <option value="default">Provider / model default</option>
                  <option value="none">None</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
                <span className="field-help">
                  Leave at default for Apertus models that do not support this
                  parameter.
                </span>
              </label>
            </div>
          </div>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={draft.json_mode}
              disabled={draft.provider === "docker"}
              onChange={(event) => update("json_mode", event.target.checked)}
            />
            Request structured JSON mode
          </label>
          <p className="field-help !mt-0">
            {draft.provider === "docker"
              ? "Local Docker analysis always uses the exact validation schema so the compact model cannot return free-form prose."
              : "Enable only if your endpoint supports response_format: json_object. Answers and citations are validated with either setting."}
          </p>
          <div className="info-note text-xs">
            Helvetic Lens always requests one non-streaming response. These
            fixed values keep structured parsing and citation validation
            deterministic.
          </div>
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
              disabled={
                !!busy ||
                (draft.provider === "infomaniak"
                  ? !draft.product_id.trim()
                  : draft.provider === "custom"
                    ? !draft.base_url.trim()
                    : false)
              }
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
            model, evidence warning threshold, or generation settings marks
            previous analyses as stale.
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
          Restoring defaults removes saved overrides, including a saved
          credential, and uses the server&apos;s current environment. Your
          document history is unchanged.
        </p>
      </div>
    </section>
  );
}
