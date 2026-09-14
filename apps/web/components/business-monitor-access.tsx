"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import {
  businessMonitorCopy,
  type BusinessScope,
} from "@/lib/business-monitor-copy";
import { useAuth } from "./auth-gate";
import styles from "./business-monitor-access.module.css";

type Person = { id: string; name: string | null; available: boolean };
type Scope = {
  monitor_version: number;
  visibility: "private" | "workspace";
  creator: Person;
  responsible: Person | null;
  can_change_scope: boolean;
  history: {
    version: number;
    actor: Person | null;
    scope: "private" | "workspace";
    responsible: Person | null;
    created_at: string;
  }[];
  next_before_version: number | null;
};
type Members = {
  items: { id: string; name: string | null }[];
  next_cursor: string | null;
};
type Props = {
  domain: "tenders" | "ip" | "auctions";
  monitor: BusinessScope & { id: string; version: number };
  changed: () => void;
};

export function BusinessMonitorAccess(props: Props) {
  const { session } = useAuth(),
    { locale } = useI18n();
  const [open, setOpen] = useState(false);
  const c = businessMonitorCopy[locale];
  const key = `${session?.user?.id}:${session?.organization?.id}:${session?.role}:${props.monitor.id}:${props.monitor.version}:${locale}`;
  return (
    <details
      className={styles.card}
      data-business-access
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        {c.title} ·{" "}
        {c[props.monitor.visibility === "workspace" ? "workspace" : "private"]}
      </summary>
      {open && session?.authenticated && (
        <AccessForm
          key={key}
          {...props}
          canManage={session.role === "organization_admin"}
        />
      )}
    </details>
  );
}

function AccessForm({
  domain,
  monitor,
  changed,
  canManage,
}: Props & { canManage: boolean }) {
  const { locale } = useI18n(),
    c = businessMonitorCopy[locale];
  const [saved, setSaved] = useState<Scope | null>(null),
    [members, setMembers] = useState<Members | null>(null);
  const [visibility, setVisibility] = useState<"private" | "workspace">(
      "private",
    ),
    [responsible, setResponsible] = useState("");
  const [confirmed, setConfirmed] = useState(false),
    [busy, setBusy] = useState(false),
    [failed, setFailed] = useState(false);
  const request = useRef<AbortController | null>(null);
  const onChanged = useRef(changed);
  onChanged.current = changed;
  function revoked(error: unknown) {
    if (
      error instanceof ApiError &&
      [
        "authentication_required",
        "membership_required",
        "subject_role_denied",
        "business_monitor_not_found",
        "business_monitor_unavailable",
      ].includes(error.code)
    )
      onChanged.current();
  }
  const path = `/monitoring-centre/business/${domain}/${monitor.id}/scope`;
  const load = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setSaved(null);
    setMembers(null);
    setFailed(false);
    setBusy(true);
    setConfirmed(false);
    try {
      const [scope, directory] = await Promise.all([
        api<Scope>(path, { signal: controller.signal }),
        canManage
          ? api<Members>("/monitoring-centre/business/members", {
              signal: controller.signal,
            })
          : Promise.resolve(null),
      ]);
      if (controller.signal.aborted) return;
      setSaved(scope);
      setVisibility(scope.visibility);
      setResponsible(scope.responsible?.id || "");
      setMembers(directory);
    } catch (error) {
      if (!controller.signal.aborted) {
        setFailed(true);
        revoked(error);
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }, [path, canManage]);
  useEffect(() => {
    void load();
    const hide = () => {
      request.current?.abort();
      setSaved(null);
      setMembers(null);
      setConfirmed(false);
    };
    window.addEventListener("pagehide", hide);
    return () => {
      request.current?.abort();
      window.removeEventListener("pagehide", hide);
    };
  }, [load]);
  async function save() {
    if (!saved || busy || !canManage) return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setFailed(false);
    try {
      await api<Scope>(path, {
        method: "PUT",
        signal: controller.signal,
        body: JSON.stringify({
          expected_version: saved.monitor_version,
          visibility,
          responsible_user_id:
            visibility === "private" ? null : responsible || null,
          confirmed,
        }),
      });
      if (!controller.signal.aborted) changed();
    } catch (error) {
      if (!controller.signal.aborted) {
        revoked(error);
        setSaved(null);
        setMembers(null);
        setFailed(true);
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  async function more(kind: "history" | "members") {
    if (!saved || busy) return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    try {
      if (kind === "members" && members?.next_cursor) {
        const page = await api<Members>(
          `/monitoring-centre/business/members?after_id=${encodeURIComponent(members.next_cursor)}`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted)
          setMembers({ ...page, items: [...members.items, ...page.items] });
      } else if (kind === "history" && saved.next_before_version) {
        const page = await api<Scope>(
          `${path}?before_version=${saved.next_before_version}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        if (page.monitor_version !== saved.monitor_version) throw new Error();
        setSaved({ ...page, history: [...saved.history, ...page.history] });
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        revoked(error);
        setSaved(null);
        setMembers(null);
        setFailed(true);
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  const person = (value: Person | null) =>
    value
      ? `${value.name || c.unknown}${value.available ? "" : ` · ${c.unavailable}`}`
      : c.unassigned;
  const changedScope =
    saved &&
    (saved.visibility !== visibility ||
      (saved.responsible?.id || "") !==
        (visibility === "private" ? "" : responsible));
  return (
    <div>
      {failed && <p role="alert">{c.failed}</p>}
      {busy && <p role="status">{c.loading}</p>}
      <button type="button" disabled={busy} onClick={() => void load()}>
        {c.reload}
      </button>
      {saved && (
        <>
          <p>
            {c.creator}: {person(saved.creator)}
          </p>
          <p>
            {c.responsible}: {person(saved.responsible)}
          </p>
          <p>{c.boundary}</p>
          {canManage ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void save();
              }}
            >
              <fieldset disabled={busy}>
                <legend>{c.title}</legend>
                <label>
                  {c.scope}
                  <select
                    value={visibility}
                    disabled={!saved.can_change_scope}
                    onChange={(event) => {
                      setVisibility(
                        event.target.value as "private" | "workspace",
                      );
                      setConfirmed(false);
                    }}
                  >
                    <option value="private">{c.private}</option>
                    <option value="workspace">{c.workspace}</option>
                  </select>
                </label>
                {visibility === "workspace" && (
                  <>
                    <label>
                      {c.responsible}
                      <select
                        value={responsible}
                        onChange={(event) => setResponsible(event.target.value)}
                      >
                        <option value="">{c.unassigned}</option>
                        {saved.responsible &&
                          !members?.items.some(
                            (member) => member.id === saved.responsible?.id,
                          ) && (
                            <option
                              value={saved.responsible.id}
                              disabled={!saved.responsible.available}
                            >
                              {person(saved.responsible)}
                            </option>
                          )}
                        {members?.items.map((member) => (
                          <option key={member.id} value={member.id}>
                            {member.name || c.unknown}
                          </option>
                        ))}
                      </select>
                    </label>
                    {members?.next_cursor && (
                      <button
                        type="button"
                        onClick={() => void more("members")}
                      >
                        {c.moreMembers}
                      </button>
                    )}
                  </>
                )}
                <p>{c.effect}</p>
                <p>{c.privateEffect}</p>
                {visibility === "workspace" &&
                  saved.visibility === "private" && (
                    <label className={styles.check}>
                      <input
                        type="checkbox"
                        checked={confirmed}
                        onChange={(event) => setConfirmed(event.target.checked)}
                      />
                      {c.confirm}
                    </label>
                  )}
                <button
                  type="submit"
                  disabled={
                    !changedScope ||
                    (saved.visibility === "private" &&
                      visibility === "workspace" &&
                      !confirmed)
                  }
                >
                  {c.save}
                </button>
              </fieldset>
            </form>
          ) : (
            <p>{c.readOnly}</p>
          )}
          <h3>{c.history}</h3>
          {saved.history.length ? (
            <ol className={styles.history}>
              {saved.history.map((event) => (
                <li key={event.version}>
                  <time dateTime={event.created_at}>
                    {new Date(event.created_at).toLocaleString(
                      locale === "rm-CH" ? "de-CH" : locale,
                    )}
                  </time>
                  <p>
                    {person(event.actor)} · {c[event.scope]} · {c.responsible}:{" "}
                    {person(event.responsible)}
                  </p>
                </li>
              ))}
            </ol>
          ) : (
            <p>{c.empty}</p>
          )}
          {saved.next_before_version && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void more("history")}
            >
              {c.more}
            </button>
          )}
        </>
      )}
    </div>
  );
}
