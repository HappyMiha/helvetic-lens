"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { monitoringConfigurationCopy } from "@/lib/monitoring-configuration-copy";
import { useAuth } from "./auth-gate";
import styles from "./monitoring-configuration-draft.module.css";

type Props<T> = {
  domain:
    | "pollen"
    | "river"
    | "air"
    | "warnings"
    | "commute"
    | "traffic"
    | "tenders"
    | "ip"
    | "auctions";
  configuration: T;
  disabled: boolean;
  context?: string | number;
  onUse: (configuration: T) => void;
};
type Proposal<T> = {
  configuration: T | null;
  domain: string;
  locale: string;
  request_key: string;
  input_binding: string;
  prompt_version: string;
  capability_binding: string;
  changed_fields: string[];
};

export function MonitoringConfigurationDraft<T extends object>(
  props: Props<T>,
) {
  const { session } = useAuth(),
    { locale } = useI18n();
  const key = JSON.stringify([
    session?.user?.id,
    session?.organization?.id,
    session?.role,
    locale,
    props.domain,
    props.context,
    props.configuration,
    props.disabled,
  ]);
  if (!session?.authenticated || session.role !== "organization_admin")
    return null;
  return <DraftPanel key={key} {...props} />;
}

function DraftPanel<T extends object>({
  domain,
  configuration,
  disabled,
  onUse,
}: Props<T>) {
  const { locale } = useI18n(),
    c = monitoringConfigurationCopy[locale];
  const [request, setRequest] = useState("");
  const [proposal, setProposal] = useState<Proposal<T> | null>(null);
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const controller = useRef<AbortController | null>(null);
  const detail = useRef<HTMLDetailsElement | null>(null);
  function clear() {
    controller.current?.abort();
    controller.current = null;
    setProposal(null);
    setBusy(false);
    setMessage("");
  }
  useEffect(() => {
    const hidden = () => {
      if (document.visibilityState === "hidden") {
        clear();
        setRequest("");
      }
    };
    const pagehide = () => {
      clear();
      setRequest("");
    };
    document.addEventListener("visibilitychange", hidden);
    window.addEventListener("pagehide", pagehide);
    return () => {
      controller.current?.abort();
      document.removeEventListener("visibilitychange", hidden);
      window.removeEventListener("pagehide", pagehide);
    };
  }, []);
  async function generate() {
    if (disabled || controller.current || !request.trim()) return;
    const abort = new AbortController(),
      requestKey = crypto.randomUUID();
    controller.current = abort;
    setBusy(true);
    setMessage("");
    setProposal(null);
    try {
      const value = await api<Proposal<T>>(
        "/monitoring-centre/configuration/draft",
        {
          method: "POST",
          signal: abort.signal,
          body: JSON.stringify({
            domain,
            configuration,
            locale,
            request,
            request_key: requestKey,
          }),
        },
      );
      if (abort.signal.aborted) return;
      if (
        value.request_key !== requestKey ||
        value.domain !== domain ||
        value.locale !== locale ||
        value.prompt_version !== "monitoring-configuration-draft-v1" ||
        !/^[a-f0-9]{64}$/.test(value.input_binding) ||
        !/^[a-f0-9]{64}$/.test(value.capability_binding) ||
        !Array.isArray(value.changed_fields)
      )
        throw new Error();
      if (!value.configuration) setMessage(c.invalid);
      else if (!value.changed_fields.length) setMessage(c.unchanged);
      else setProposal(value);
    } catch (error) {
      if (!abort.signal.aborted)
        setMessage(
          error instanceof ApiError &&
            error.code.startsWith("configuration_draft_") &&
            error.code !== "configuration_draft_unavailable"
            ? c.invalid
            : c.unavailable,
        );
    } finally {
      if (!abort.signal.aborted) {
        controller.current = null;
        setBusy(false);
      }
    }
  }
  return (
    <details
      ref={detail}
      className={styles.panel}
      data-configuration-draft={domain}
      onToggle={(event) => {
        if (!event.currentTarget.open) clear();
      }}
    >
      <summary>{c.title}</summary>
      <div className={styles.body}>
        <p>{c.help}</p>
        <label>
          {c.request}
          <textarea
            rows={3}
            maxLength={2000}
            value={request}
            disabled={disabled}
            onChange={(event) => {
              clear();
              setRequest(event.target.value);
            }}
          />
        </label>
        <div className={styles.actions}>
          <button
            type="button"
            disabled={disabled || busy || !request.trim()}
            onClick={() => void generate()}
          >
            {c.generate}
          </button>
          {busy && (
            <button type="button" onClick={clear}>
              {c.cancel}
            </button>
          )}
        </div>
        {(busy || message) && <p role="status">{busy ? c.busy : message}</p>}
        {proposal?.configuration && (
          <div role="status">
            <p>{c.ready}</p>
            <div className={styles.actions}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => {
                  if (disabled || !proposal.configuration) return;
                  const editor = detail.current?.parentElement;
                  onUse(structuredClone(proposal.configuration));
                  requestAnimationFrame(() => {
                    const field = Array.from(
                      editor?.querySelectorAll<HTMLElement>(
                        "input, select, textarea",
                      ) || [],
                    ).find(
                      (element) =>
                        !element.closest("[data-configuration-draft]") &&
                        !element.hasAttribute("disabled"),
                    );
                    field?.focus();
                  });
                }}
              >
                {c.apply}
              </button>
              <button type="button" onClick={clear}>
                {c.discard}
              </button>
            </div>
          </div>
        )}
      </div>
    </details>
  );
}
