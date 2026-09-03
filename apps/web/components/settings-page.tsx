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
import { useAuth } from "./auth-gate";
import { useI18n } from "@/lib/i18n";

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
  const { t } = useI18n();
  const { canManage } = useAuth();
  const configuration = useResource<ApertusSettings>("/settings/apertus");
  const { data: health } = useResource<Health>("/health");
  const { data: profile } = useResource<Profile>("/profile");
  const [profileOpen, setProfileOpen] = useState(false);
  const [notice, setNotice] = useState("");
  return (
    <Shell section={t("nav.settings")}>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t("settings.eyebrow")}</span>
          <h1>{t("settings.title")}</h1>
          <p className="muted m-0">
            {t("settings.body")}
          </p>
        </div>
        <SlidersHorizontal className="muted" size={28} />
      </div>
      <ErrorNote message={configuration.error} />
      {notice && <SuccessNote>{notice}</SuccessNote>}
      <div className={`grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px] items-start ${canManage ? "" : "viewer-settings"}`}>
        {configuration.data ? (
          <fieldset disabled={!canManage} className="border-0 p-0 m-0 min-w-0"><ApertusForm
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
          /></fieldset>
        ) : (
          <div className="panel p-6">
            <Loading />
          </div>
        )}
        <div className="grid gap-5">
          <section className="panel p-6">
            <Sparkles size={21} className="text-primary mb-4" />
            <h2 className="mb-3">{t("settings.connection")}</h2>
            <p className="text-sm muted">
              {configuration.data?.configured
                ? t("settings.configured", { provider: configuration.data.provider === "infomaniak" ? t("settings.infomaniak") : configuration.data.provider === "docker" ? t("settings.local") : t("settings.custom") })
                : t("settings.notConfigured")}
            </p>
            <p className="text-sm muted">
              {t("settings.currentModel", { model: configuration.data?.model || t("settings.notSelected") })}
            </p>
            <a
              href={`https://huggingface.co/${configuration.data?.model || "swiss-ai/Apertus-v1.5-8B"}`}
              target="_blank"
              rel="noreferrer"
              className="text-sm inline-flex gap-2 items-center"
            >
              {t("settings.modelCard")} <ArrowUpRight size={14} />
            </a>
          </section>
          <section className="panel p-6">
            <BookOpen size={21} className="muted mb-4" />
            <h2 className="mb-2">{t("settings.company")}</h2>
            <p className="text-sm font-medium">
              {profile?.name || t("settings.myCompany")}
            </p>
            <p className="text-sm muted break-words">
              {profile?.business_areas.join(" · ") ||
                t("settings.areas")}
            </p>
            {canManage && <Button
              variant="outline"
              size="sm"
              onClick={() => setProfileOpen(true)}
            >
              {t("settings.editCompany")}
            </Button>}
          </section>
          <section className="panel p-6">
            <h2 className="mb-3">{t("settings.workspace")}</h2>
            <p className="text-sm muted">
              {t("settings.database", { database: health?.database || t("settings.checking") })}
            </p>
            <p className="text-sm muted">
              {t("settings.persistence")}
            </p>
            <p className="text-xs muted">
              {t("settings.privacy")}
            </p>
          </section>
        </div>
      </div>
      {canManage && <ProfileDialog
        open={profileOpen}
        onOpenChange={setProfileOpen}
        health={health}
      />}
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
  const { t, dateTime, number } = useI18n();
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
  function confirmNewCloudDestination(action: string) {
    if (draft.provider === "docker") return true;
    const nextBase = draft.provider === "infomaniak"
      ? infomaniakBaseUrl(draft.product_id)
      : draft.base_url;
    const newlySelected =
      initial.provider === "docker" ||
      initial.provider !== draft.provider ||
      initial.base_url !== nextBase;
    return (
      !newlySelected ||
      window.confirm(
        t("settings.confirmContact", { action }),
      )
    );
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (
      draft.provider !== "docker" &&
      (initial.provider === "docker" || initial.provider !== draft.provider) &&
      !window.confirm(
        t("settings.confirmCloud"),
      )
    ) return;
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
        t("settings.saveSuccess"),
      );
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  async function test() {
    if (!formRef.current?.reportValidity()) return;
    if (!confirmNewCloudDestination(t("settings.test"))) return;
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
    if (!confirmNewCloudDestination(t("settings.loadModels"))) return;
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
        t("settings.modelsLoaded", { count: number(result.count) }),
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
        t("settings.resetSuccess"),
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
            ? t("settings.unsaved")
            : initial.source === "workspace"
              ? t("settings.savedWorkspace")
              : t("settings.environment")}
        </span>
      </div>
      <form ref={formRef} onSubmit={save} className="p-6">
        <fieldset disabled={!!busy} className="form-stack min-w-0">
          <div className="grid sm:grid-cols-2 gap-4">
            <label>
              {t("settings.provider")}
              <select
                value={draft.provider}
                onChange={(event) =>
                  chooseProvider(event.target.value as Provider)
                }
              >
                <option value="infomaniak">{t("settings.infomaniak")}</option>
                <option value="docker">{t("settings.local")}</option>
                <option value="custom">{t("settings.custom")}</option>
              </select>
              <span className="field-help">
                {t("settings.providerHelp")}
              </span>
            </label>
            <div className="rounded-lg border p-4 text-sm">
              <strong>
                {draft.provider === "infomaniak"
                  ? t("settings.infomaniak")
                  : draft.provider === "docker"
                    ? t("settings.local")
                    : t("settings.custom")}
              </strong>
              <p className="field-help !mb-0">
                {t("settings.activeProvider")}
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
                {t("settings.productId")}
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
                  {t("settings.productIdHelp")}
                </span>
              </label>
              <label>
                {t("settings.baseUrl")}
                <Input
                  value={infomaniakBaseUrl(draft.product_id)}
                  readOnly
                  aria-readonly="true"
                  placeholder={t("settings.generatedEndpoint")}
                />
                <span className="field-help">
                  {t("settings.infomaniakUrlHelp")}
                </span>
              </label>
              <label>
                {t("settings.model")}
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
                  {models.length ? t("settings.refreshModels") : t("settings.loadModels")}
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
                {t("settings.baseUrl")}
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
                {t("settings.model")}
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
                  {models.length ? t("settings.refreshLocal") : t("settings.loadLocal")}
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
                    {t("settings.useHuggingFace")}
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
                    {t("settings.usePublicAi")}
                  </Button>
                  <a
                    href="https://platform.publicai.co/docs"
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs inline-flex items-center gap-1"
                  >
                     {t("settings.publicAiSetup")} <ArrowUpRight size={12} />
                  </a>
                  <a
                    href="https://huggingface.co/docs/inference-providers/providers/publicai"
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs inline-flex items-center gap-1"
                  >
                     {t("settings.huggingFaceSetup")} <ArrowUpRight size={12} />
                  </a>
                </div>
                <p className="field-help !mb-0">
                   {t("settings.presetHelp")}
                </p>
              </div>
              <label>
                {t("settings.baseUrl")}
                <Input
                  type="url"
                  autoComplete="url"
                  placeholder="http://localhost:8080/v1"
                  value={draft.base_url}
                  onChange={(event) => update("base_url", event.target.value)}
                  maxLength={2000}
                />
                <span className="field-help">
                   {t("settings.customUrlHelp")}
                </span>
              </label>
              <label>
                {t("settings.modelId")}
                <Input
                  value={draft.model}
                  onChange={(event) => update("model", event.target.value)}
                  required
                  maxLength={300}
                />
                <span className="field-help">
                   {t("settings.modelIdHelp")}
                </span>
              </label>
            </>
          )}
          {draft.provider === "docker" ? (
            <div className="rounded-lg border p-4 min-w-0 text-sm">
              <div className="flex items-center gap-2 font-semibold mb-2">
                <KeyRound size={15} /> {t("settings.noLocalCredential")}
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
                {draft.provider === "infomaniak" ? t("settings.apiToken") : t("settings.apiKey")}
              </div>
              <p className="text-xs muted">
                {initial.api_key_configured
                  ? "A credential is configured (" +
                    initial.key_source +
                    "). Its value is never sent back to your browser."
                  : "No credential is configured. Some local inference servers do not need one."}
              </p>
              <label>
                {t("settings.keyHandling")}
                <select
                  value={keyAction}
                  onChange={(event) => {
                    changed();
                    setKeyAction(event.target.value as KeyAction);
                    setApiKey("");
                  }}
                >
                  <option value="keep">{t("settings.keepKey")}</option>
                  <option value="replace">{t("settings.replaceKey")}</option>
                  <option value="remove">{t("settings.removeKey")}</option>
                  <option value="environment">
                    {t("settings.environmentKey")}
                  </option>
                </select>
              </label>
              {keyAction === "replace" && (
                <label className="mt-3 block">
                  {draft.provider === "infomaniak"
                    ? t("settings.newToken")
                    : t("settings.newKey")}
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
              {t("settings.requests")}
            </h3>
            <div className="grid sm:grid-cols-2 gap-4">
              <label>
                {t("settings.timeout")}
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
                {t("settings.retries")}
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
                {t("settings.concurrency")}
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
                {t("settings.context")}
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
                {t("settings.maxTokens")}
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
                {t("settings.temperature")}
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
                {t("settings.topP")}
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
                {t("settings.presence")}
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
                   {t("settings.presenceHelp")}
                </span>
              </label>
              <label>
                {t("settings.reasoning")}
                <select
                  value={draft.reasoning_effort}
                  onChange={(event) =>
                    update(
                      "reasoning_effort",
                      event.target.value as typeof draft.reasoning_effort,
                    )
                  }
                >
                  <option value="default">{t("settings.default")}</option>
                  <option value="none">{t("settings.none")}</option>
                  <option value="low">{t("settings.low")}</option>
                  <option value="medium">{t("settings.medium")}</option>
                  <option value="high">{t("settings.high")}</option>
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
            {t("settings.json")}
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
                {t("settings.verified", { latency: number(testResult.latency_ms) })}
              </strong>
              <p>{t("settings.received", { model: testResult.model })}</p>
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
              {t("settings.test")}
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
              {t("settings.save")}
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
            ? t("settings.lastSaved", { date: dateTime(initial.updated_at) })
            : t("settings.noOverrides")}
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
          {t("settings.useDefaults")}
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
