"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { accountCopy } from "@/lib/account-copy";
import { centreCopy, type TemplateId } from "@/lib/monitoring-centre-copy";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import { Button } from "./ui/button";
import styles from "./account-privacy.module.css";

type Blocker = {
  kind:
    | "workspace_administrator"
    | "platform_administrator"
    | "monitor_owner"
    | "workspace_private_data"
    | "retained_workspace_reference";
  organization_id?: string | null;
  domain?: "tenders" | "ip" | "auctions";
  monitor_id?: string;
  membership_required?: boolean;
};
type Preview = {
  can_delete: boolean;
  confirmation_token: string | null;
  categories: {
    domain: TemplateId;
    owned: number;
    handover_required: number;
  }[];
  workspaces: { id: string; name: string; disposition: string }[];
  blockers: Blocker[];
  personal_counts: Record<string, number>;
  private_document_versions: number;
  artifact_retention_hours: number;
};
const domainRoutes = {
  tenders: "/tender-watch",
  ip: "/trademark-watch",
  auctions: "/auction-watch",
};

export function AccountPrivacy() {
  const { session } = useAuth();
  const { locale } = useI18n();
  const c = accountCopy[locale];
  return (
    <Shell section={c.title}>
      <div className={styles.page}>
        <header>
          <h1>{c.title}</h1>
          <p>{c.intro}</p>
          <Link className={styles.link} href="/monitoring/settings">
            {c.export}
          </Link>
        </header>
        {session?.authenticated && session.organization && (
          <DeletionForm
            key={`${session.user?.id}:${session.organization.id}:${session.role}:${locale}`}
            organization={session.organization.id}
          />
        )}
      </div>
    </Shell>
  );
}

function DeletionForm({ organization }: { organization: string }) {
  const { locale } = useI18n();
  const c = accountCopy[locale],
    names = centreCopy[locale];
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState<"preview" | "erase" | "navigate" | null>(
    null,
  );
  const [error, setError] = useState<"failed" | "passwordError" | null>(null);
  const [password, setPassword] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [workspaceConfirmed, setWorkspaceConfirmed] = useState(false);
  const request = useRef<AbortController | null>(null);
  function reset() {
    setPreview(null);
    setPassword("");
    setConfirmed(false);
    setWorkspaceConfirmed(false);
  }
  useEffect(() => {
    const hide = () => {
      request.current?.abort();
      reset();
      setBusy(null);
    };
    window.addEventListener("pagehide", hide);
    return () => {
      request.current?.abort();
      window.removeEventListener("pagehide", hide);
    };
  }, []);

  async function load() {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    reset();
    setError(null);
    setBusy("preview");
    try {
      const value = await api<Preview>("/account/deletion", {
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (
        value.categories.length !== 9 ||
        new Set(value.categories.map((row) => row.domain)).size !== 9 ||
        value.categories.some((row) => !names.templates[row.domain])
      )
        throw new Error();
      setPreview(value);
    } catch {
      if (!controller.signal.aborted) setError("failed");
    } finally {
      if (!controller.signal.aborted) setBusy(null);
    }
  }

  async function open(organizationId: string, href: string) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy("navigate");
    setError(null);
    setPassword("");
    try {
      if (organizationId !== organization)
        await api("/auth/session/organization", {
          method: "POST",
          signal: controller.signal,
          body: JSON.stringify({ organization_id: organizationId }),
        });
      if (!controller.signal.aborted) window.location.assign(href);
    } catch {
      if (!controller.signal.aborted) {
        reset();
        setError("failed");
        setBusy(null);
      }
    }
  }

  const workspaces =
    preview?.workspaces
      .filter((row) => row.disposition === "erase_private_workspace")
      .map((row) => row.id) || [];
  async function remove() {
    if (
      !preview?.can_delete ||
      !preview.confirmation_token ||
      busy ||
      !password ||
      !confirmed ||
      (workspaces.length > 0 && !workspaceConfirmed)
    )
      return;
    const controller = new AbortController();
    request.current = controller;
    setBusy("erase");
    setError(null);
    const body = {
      password,
      confirmed,
      confirmation_token: preview.confirmation_token,
      erase_workspaces: workspaces,
    };
    setPassword("");
    try {
      const result = await api<{ deleted: boolean }>("/account/deletion", {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify(body),
      });
      if (controller.signal.aborted) return;
      if (!result.deleted) throw new Error();
      // A full navigation discards private React/resource state after the server
      // has removed both cookies. No second logout request against a deleted user.
      window.location.replace(
        `/login?account_deleted=1&locale=${encodeURIComponent(locale)}`,
      );
    } catch (cause) {
      if (!controller.signal.aborted) {
        reset();
        setError(
          cause instanceof ApiError && cause.code === "invalid_credentials"
            ? "passwordError"
            : "failed",
        );
        setBusy(null);
      }
    }
  }

  return (
    <section aria-label={c.preview} data-account-deletion>
      <div className={styles.actions}>
        <Button
          type="button"
          variant="outline"
          disabled={!!busy}
          onClick={() => void load()}
          data-account-preview
        >
          {c.preview}
        </Button>
        {busy === "preview" && (
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              request.current?.abort();
              reset();
              setBusy(null);
            }}
          >
            {c.cancel}
          </Button>
        )}
      </div>
      {busy && <p role="status">{c.busy}</p>}
      {error && <p role="alert">{c[error]}</p>}
      {preview && (
        <>
          <h2>{c.monitors}</h2>
          <dl className={styles.categories}>
            {preview.categories.map((row) => (
              <div key={row.domain}>
                <dt>{names.templates[row.domain][0]}</dt>
                <dd>{row.owned}</dd>
              </div>
            ))}
          </dl>
          <dl className={styles.summary}>
            <div>
              <dt>{c.conversations}</dt>
              <dd>{preview.personal_counts.conversations || 0}</dd>
            </div>
            <div>
              <dt>{c.sessions}</dt>
              <dd>{preview.personal_counts.sessions || 0}</dd>
            </div>
            <div>
              <dt>{c.records}</dt>
              <dd>
                {Object.entries(preview.personal_counts).reduce(
                  (count, [name, value]) =>
                    count +
                    (name === "conversations" || name === "sessions"
                      ? 0
                      : value),
                  0,
                )}
              </dd>
            </div>
            <div>
              <dt>{c.documents}</dt>
              <dd>{preview.private_document_versions}</dd>
            </div>
          </dl>
          <h2>{c.workspaces}</h2>
          <ul className={styles.workspaces}>
            {preview.workspaces.map((row) => (
              <li key={row.id}>
                <strong>{row.name}</strong>
                <p>
                  {row.disposition === "erase_private_workspace"
                    ? c.erase
                    : row.disposition === "leave_workspace"
                      ? c.leave
                      : c.blocked}
                </p>
                <Button
                  variant="outline"
                  type="button"
                  disabled={!!busy}
                  onClick={() => void open(row.id, "/organization")}
                >
                  {c.open}
                </Button>
              </li>
            ))}
          </ul>
          {preview.blockers.length > 0 && (
            <section aria-label={c.blocked}>
              <h2>{c.blocked}</h2>
              <ul className={styles.blockers}>
                {preview.blockers.map((blocker, index) => (
                  <li key={index}>
                    <p>
                      {c[blocker.kind]}{" "}
                      {blocker.organization_id &&
                        preview.workspaces.find(
                          (row) => row.id === blocker.organization_id,
                        )?.name}
                    </p>
                    {blocker.membership_required && <p>{c.membership}</p>}
                    {blocker.kind === "monitor_owner" &&
                      blocker.organization_id &&
                      blocker.domain &&
                      blocker.monitor_id && (
                        <Button
                          variant="outline"
                          type="button"
                          disabled={!!busy}
                          onClick={() =>
                            void open(
                              blocker.organization_id!,
                              `${domainRoutes[blocker.domain!]}?monitor=${encodeURIComponent(blocker.monitor_id!)}`,
                            )
                          }
                        >
                          {c.monitor} · {names.templates[blocker.domain][0]}
                        </Button>
                      )}
                  </li>
                ))}
              </ul>
            </section>
          )}
          <p>{c.retained}</p>
          <p>
            {c.files.replace(
              "{hours}",
              String(preview.artifact_retention_hours),
            )}
          </p>
          {preview.can_delete && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void remove();
              }}
            >
              <fieldset disabled={!!busy}>
                <legend>{c.remove}</legend>
                <label>
                  {c.password}
                  <input
                    type="password"
                    autoComplete="current-password"
                    maxLength={1024}
                    required
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </label>
                <label className={styles.check}>
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(event) => setConfirmed(event.target.checked)}
                  />
                  {c.confirm}
                </label>
                {workspaces.length > 0 && (
                  <label className={styles.check}>
                    <input
                      type="checkbox"
                      checked={workspaceConfirmed}
                      onChange={(event) =>
                        setWorkspaceConfirmed(event.target.checked)
                      }
                    />
                    {c.workspaceConfirm}
                  </label>
                )}
                <Button
                  variant="destructive"
                  data-account-erase
                  type="submit"
                  disabled={
                    !password ||
                    !confirmed ||
                    (workspaces.length > 0 && !workspaceConfirmed)
                  }
                >
                  {c.remove}
                </Button>
              </fieldset>
            </form>
          )}
        </>
      )}
    </section>
  );
}
