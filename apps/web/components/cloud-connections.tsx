"use client";

import { useState } from "react";
import {
  api,
  errorText,
  invalidateResources,
  resourceKey,
  resourceTag,
  useResource,
} from "@/lib/api";
import { resources } from "@/lib/resource-keys";
import { useI18n } from "@/lib/i18n";
import { cloudConnectionsCopy } from "@/lib/cloud-connections-copy";
import type { ApertusSettings } from "@/lib/types";
import { useAuth } from "./auth-gate";
import { ErrorNote, Loading, SuccessNote } from "./common";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

type Connection = Partial<ApertusSettings> & {
  provider: "openai" | "swisscom";
  revision: number;
  base_url: string;
  model: string;
  api_key_configured: boolean;
};
const connectionResource = resourceKey<{ items: Connection[] }>({
  id: "inference-connections",
  path: "/settings/inference-connections",
  scope: "organization",
  owner: "organization",
  tags: ["inference-connections"],
});

export function CloudConnections() {
  const { locale } = useI18n();
  const c = cloudConnectionsCopy[locale];
  const resource = useResource(connectionResource);
  const [notice, setNotice] = useState("");
  return (
    <section className="grid gap-4">
      <div>
        <h2>{c.title}</h2>
        <p className="muted">{c.intro}</p>
      </div>
      {notice && <SuccessNote>{notice}</SuccessNote>}
      <ErrorNote message={resource.error} />
      {!resource.data ? (
        <Loading />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          {resource.data.items.map((row) => (
            <ConnectionForm
              key={`${row.provider}:${row.revision}`}
              initial={row}
              onEdit={() => setNotice("")}
              onSaved={(saved) => {
                resource.setData({
                  items: resource.data!.items.map((p) =>
                    p.provider === saved.provider ? saved : p,
                  ),
                });
                setNotice(c.saved);
              }}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function ConnectionForm({
  initial,
  onSaved,
  onEdit,
}: {
  initial: Connection;
  onSaved: (value: Connection) => void;
  onEdit: () => void;
}) {
  const { t, locale } = useI18n();
  const { canManage } = useAuth();
  const c = cloudConnectionsCopy[locale];
  const [base, setBase] = useState(initial.base_url),
    [model, setModel] = useState(initial.model);
  const [action, setAction] = useState("keep"),
    [key, setKey] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const dirty =
    base !== initial.base_url || model !== initial.model || action !== "keep";
  const name =
    initial.provider === "openai"
      ? t("partners.openai")
      : t("partners.swisscom");
  function edited() {
    onEdit();
    setNotice("");
    setError("");
  }
  async function run(operation: "test" | "activate") {
    setBusy(true);
    edited();
    try {
      await api(
        `/settings/inference-connections/${initial.provider}/${operation}`,
        {
          method: "POST",
          body: JSON.stringify({ revision: initial.revision }),
        },
      );
      setNotice(operation === "test" ? c.tested : c.activated);
      if (operation === "activate")
        await invalidateResources(
          resources.settings(),
          resources.health(),
          resources.organizationStatus(),
          ...[
            "comparison",
            "ai-history",
            "impact-matrix",
            "impact-inbox",
            "relation-analyses",
            "digests",
            "registry",
          ].map((tag) => resourceTag(tag, "organization")),
        );
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form
      className="panel p-6 grid gap-4"
      aria-label={name}
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        edited();
        try {
          const { revision, api_key_configured, updated_at, ...values } =
            initial;
          void api_key_configured;
          void updated_at;
          const saved = await api<Connection>(
            `/settings/inference-connections/${initial.provider}`,
            {
              method: "PATCH",
              body: JSON.stringify({
                ...values,
                revision,
                base_url: base,
                model,
                key_action: action,
                api_key: action === "replace" ? key : "",
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
      <h3>{name}</h3>
      <p className="text-sm muted">
        {initial.api_key_configured
          ? t("partners.keySaved")
          : t("partners.keyMissing")}
      </p>
      <p className="text-sm muted">{c[initial.provider]}</p>
      <fieldset
        disabled={!canManage || busy}
        className="grid gap-4 border-0 p-0 min-w-0"
      >
        <label>
          {t("settings.baseUrl")}
          <Input
            type="url"
            value={base}
            required
            readOnly={initial.provider === "openai"}
            maxLength={2000}
            onChange={(e) => {
              edited();
              setBase(e.target.value);
            }}
          />
        </label>
        <label>
          {t("settings.modelId")}
          <Input
            value={model}
            required
            maxLength={300}
            onChange={(e) => {
              edited();
              setModel(e.target.value);
            }}
          />
        </label>
        <label>
          {t("partners.keyAction")}
          <select
            value={action}
            onChange={(e) => {
              edited();
              setAction(e.target.value);
              setKey("");
            }}
          >
            <option value="keep">{t("partners.keep")}</option>
            <option value="replace">{t("partners.replace")}</option>
            <option value="remove">{c.removeKey}</option>
          </select>
        </label>
        {action === "replace" && (
          <label>
            {t("settings.apiKey")}
            <Input
              type="password"
              autoComplete="new-password"
              value={key}
              required
              maxLength={4000}
              onChange={(e) => {
                edited();
                setKey(e.target.value);
              }}
            />
          </label>
        )}
        <div className="flex flex-wrap gap-3">
          <Button type="submit">
            {busy ? t("partners.working") : t("partners.save")}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={dirty || !initial.api_key_configured}
            onClick={() => void run("test")}
          >
            {t("partners.test")}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={dirty || !initial.api_key_configured}
            onClick={() => void run("activate")}
          >
            {c.activate}
          </Button>
        </div>
      </fieldset>
      <ErrorNote message={error} />
      {notice && <SuccessNote>{notice}</SuccessNote>}
      <a
        href={`https://zh.ai-weeks.ch/tools/${initial.provider}-hacker-guide`}
        target="_blank"
        rel="noreferrer"
      >
        {c.access}
      </a>
    </form>
  );
}
