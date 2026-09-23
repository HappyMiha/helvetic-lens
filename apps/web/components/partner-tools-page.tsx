"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, errorText, resourceKey, useResource } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import { ErrorNote, Loading, SuccessNote } from "./common";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { CloudConnections } from "./cloud-connections";

type Partner = {
  provider: "supertext" | "elevenlabs";
  revision: number;
  enabled: boolean;
  api_key_configured: boolean;
  voice_id: string;
  model_id: string;
};
const partnerResource = resourceKey<{ items: Partner[] }>({
  id: "partner-settings",
  path: "/settings/partners",
  scope: "organization",
  owner: "organization",
  tags: ["partner-settings"],
});

export function PartnerToolsPage() {
  const { session } = useAuth();
  const { t } = useI18n();
  return (
    <Shell section={t("partners.title")}>
      <div className="page-heading">
        <div>
          <h1>{t("partners.title")}</h1>
          <p className="muted">{t("partners.intro")}</p>
        </div>
      </div>
      <Link href="/settings">{t("partners.inference")}</Link>
      <PartnerWorkspace key={session?.organization?.id ?? "development"} />
    </Shell>
  );
}

function PartnerWorkspace() {
  const { t } = useI18n();
  const { canManage } = useAuth();
  const resource = useResource(partnerResource);
  const [text, setText] = useState("");
  const [target, setTarget] = useState("en");
  const [consent, setConsent] = useState(false);
  const [translation, setTranslation] = useState("");
  const [audio, setAudio] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  useEffect(
    () => () => {
      if (audio) URL.revokeObjectURL(audio);
    },
    [audio],
  );
  const configured = (provider: Partner["provider"]) =>
    resource.data?.items.find((p) => p.provider === provider);
  async function run(provider: Partner["provider"]) {
    const row = configured(provider);
    if (!row || busy) return;
    setBusy(provider);
    setError("");
    try {
      const body = { text, consent, revision: row.revision };
      if (provider === "supertext") {
        setTranslation("");
        const result = await api<{ text: string }>(
          "/partner-tools/supertext/translate",
          {
            method: "POST",
            body: JSON.stringify({ ...body, target_lang: target }),
          },
        );
        setTranslation(result.text);
      } else {
        setAudio("");
        const result = await api<{ audio_base64: string }>(
          "/partner-tools/elevenlabs/speech",
          { method: "POST", body: JSON.stringify(body) },
        );
        const bytes = Uint8Array.from(atob(result.audio_base64), (c) =>
          c.charCodeAt(0),
        );
        setAudio(
          URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" })),
        );
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy("");
    }
  }
  return (
    <div className="grid gap-6 mt-6">
      <CloudConnections />
      <ErrorNote message={resource.error} />
      {!resource.data ? (
        <Loading />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          {resource.data.items.map((row) => (
            <PartnerForm
              key={`${row.provider}:${row.revision}`}
              initial={row}
              onSaved={(saved) => {
                resource.setData({
                  items: resource.data!.items.map((p) =>
                    p.provider === saved.provider ? saved : p,
                  ),
                });
                setConsent(false);
                setTranslation("");
                setAudio("");
              }}
            />
          ))}
        </div>
      )}
      <section className="panel p-6 grid gap-4">
        <h2>{t("partners.briefing")}</h2>
        <p className="muted">{t("partners.review")}</p>
        <fieldset
          disabled={!canManage || !!busy}
          className="grid gap-4 border-0 p-0 min-w-0"
        >
          <label>
            {t("partners.text")}
            <textarea
              className="w-full min-h-36 rounded-lg border p-3"
              value={text}
              maxLength={3000}
              onChange={(e) => {
                setText(e.target.value);
                setConsent(false);
                setTranslation("");
                setAudio("");
              }}
            />
          </label>
          <label>
            {t("partners.target")}
            <Input
              value={target}
              maxLength={20}
              onChange={(e) => {
                setTarget(e.target.value);
                setConsent(false);
                setTranslation("");
              }}
            />
          </label>
          <p className="field-help">{t("partners.languages")}</p>
          <label className="flex gap-2 items-start">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            <span>{t("partners.consent")}</span>
          </label>
          <div className="flex flex-wrap gap-3">
            <Button
              disabled={
                !consent ||
                !text.trim() ||
                !target.trim() ||
                !configured("supertext")?.enabled
              }
              onClick={() => void run("supertext")}
            >
              {busy === "supertext"
                ? t("partners.working")
                : t("partners.translate")}
            </Button>
            <Button
              variant="outline"
              disabled={
                !consent || !text.trim() || !configured("elevenlabs")?.enabled
              }
              onClick={() => void run("elevenlabs")}
            >
              {busy === "elevenlabs"
                ? t("partners.working")
                : t("partners.speak")}
            </Button>
          </div>
        </fieldset>
        <ErrorNote message={error} />
        {translation && (
          <div role="status" className="grid gap-3">
            <h3>{t("partners.translation")}</h3>
            <p className="whitespace-pre-wrap break-words">{translation}</p>
            <p className="muted text-sm">{t("partners.unverified")}</p>
            <Button
              variant="outline"
              disabled={translation.length > 3000 || !!busy || !canManage}
              onClick={() => {
                setText(translation);
                setTranslation("");
                setConsent(false);
                setAudio("");
              }}
            >
              {t("partners.useTranslation")}
            </Button>
          </div>
        )}
        {audio && (
          <div>
            <p>{t("partners.audio")}</p>
            <audio controls src={audio} aria-label={t("partners.audio")} />
          </div>
        )}
      </section>
      <section className="panel p-6">
        <h2>{t("partners.access")}</h2>
        <p className="muted">{t("partners.accessBody")}</p>
        <a
          href="https://luma.com/hack-kloten-23Sep26"
          target="_blank"
          rel="noreferrer"
        >
          {t("partners.event")}
        </a>
      </section>
    </div>
  );
}

function PartnerForm({
  initial,
  onSaved,
}: {
  initial: Partner;
  onSaved: (value: Partner) => void;
}) {
  const { t } = useI18n();
  const { canManage } = useAuth();
  const [enabled, setEnabled] = useState(initial.enabled);
  const [key, setKey] = useState("");
  const [action, setAction] = useState("keep");
  const [voice, setVoice] = useState(initial.voice_id);
  const [model, setModel] = useState(initial.model_id);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const name = initial.provider === "supertext" ? "Supertext" : "ElevenLabs";
  return (
    <form
      className="panel p-6 grid gap-4"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        setNotice("");
        try {
          const saved = await api<Partner>(
            `/settings/partners/${initial.provider}`,
            {
              method: "PATCH",
              body: JSON.stringify({
                revision: initial.revision,
                enabled,
                key_action: action,
                api_key: action === "replace" ? key : "",
                voice_id: voice,
                model_id: model,
              }),
            },
          );
          setKey("");
          onSaved(saved);
        } catch (e) {
          setError(errorText(e));
        } finally {
          setBusy(false);
        }
      }}
    >
      <h2>{name}</h2>
      <p className="text-sm muted">
        {initial.api_key_configured
          ? t("partners.keySaved")
          : t("partners.keyMissing")}
      </p>
      <fieldset
        disabled={!canManage || busy}
        className="grid gap-4 border-0 p-0 min-w-0"
      >
        <label className="flex gap-2">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          {t("partners.enable")}
        </label>
        <label>
          {t("partners.keyAction")}
          <select
            className="w-full"
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setKey("");
              if (e.target.value === "remove") setEnabled(false);
            }}
          >
            <option value="keep">{t("partners.keep")}</option>
            <option value="replace">{t("partners.replace")}</option>
            <option value="remove">{t("partners.remove")}</option>
          </select>
        </label>
        {action === "replace" && (
          <label>
            {t("settings.apiKey")}
            <Input
              type="password"
              autoComplete="new-password"
              value={key}
              maxLength={4000}
              onChange={(e) => setKey(e.target.value)}
              required
            />
          </label>
        )}
        {initial.provider === "elevenlabs" && (
          <>
            <label>
              {t("partners.voice")}
              <Input
                value={voice}
                maxLength={100}
                onChange={(e) => setVoice(e.target.value)}
              />
            </label>
            <label>
              {t("settings.modelId")}
              <Input
                value={model}
                maxLength={100}
                onChange={(e) => setModel(e.target.value)}
              />
            </label>
          </>
        )}
        <div className="flex flex-wrap gap-3">
          <Button type="submit">
            {busy ? t("partners.working") : t("partners.save")}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={
              !initial.enabled ||
              action !== "keep" ||
              enabled !== initial.enabled ||
              voice !== initial.voice_id ||
              model !== initial.model_id
            }
            onClick={async () => {
              setBusy(true);
              setError("");
              setNotice("");
              try {
                await api(`/partner-tools/${initial.provider}/test`, {
                  method: "POST",
                });
                setNotice(t("partners.testSuccess"));
              } catch (e) {
                setError(errorText(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("partners.test")}
          </Button>
        </div>
      </fieldset>
      <ErrorNote message={error} />
      {notice && <SuccessNote>{notice}</SuccessNote>}
      <a
        href={
          initial.provider === "supertext"
            ? "https://www.supertext.com/en/documentation/api"
            : "https://elevenlabs.io/docs/api-reference/text-to-speech/convert"
        }
        target="_blank"
        rel="noreferrer"
      >
        {t("partners.docs")}
      </a>
    </form>
  );
}
