"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { businessItemCopy } from "@/lib/business-item-copy";
import { tenderCopy } from "@/lib/tender-copy";
import { trademarkReviewCopy } from "@/lib/trademark-review-copy";
import { auctionTrackingCopy } from "@/lib/auction-tracking-copy";
import { useAuth } from "./auth-gate";
import styles from "./business-item-work.module.css";

type Domain = "tenders" | "ip" | "auctions";
type Person = { id: string; name: string | null; available: boolean };
type Binding = {
  sequence: number;
  revision_id: string;
  profile_revision: number;
  fingerprint: string;
};
type Entry = {
  id: string;
  version: number;
  state: string;
  binding?: Binding;
  older_evidence?: boolean;
  actor?: Person | null;
  assigned?: Person | null;
  comment?: string;
  decision?: string | null;
  created_at?: string;
};
type Work = {
  version: number;
  visibility: "private" | "workspace";
  creator_user_id: string;
  assigned: Person | null;
  state: string;
  can_write: boolean;
  binding: Binding | null;
  decisions: string[];
  history: Entry[];
  next_before_version: number | null;
};
type Members = {
  items: { id: string; name: string | null }[];
  next_cursor: string | null;
};
type Props = {
  domain: Domain;
  monitorId: string;
  itemId: string;
  version: number;
  canManage: boolean;
  changed: () => void;
};

export function AssignmentFilter({
  value,
  changed,
}: {
  value: string;
  changed: (value: string) => void;
}) {
  const { locale } = useI18n(),
    c = businessItemCopy[locale];
  return (
    <label className={styles.filter}>
      {c.assignment}
      <select
        data-business-assignment-filter
        value={value}
        onChange={(e) => changed(e.target.value)}
      >
        <option value="">{c.all}</option>
        <option value="mine">{c.mine}</option>
        <option value="unassigned">{c.unassigned}</option>
      </select>
    </label>
  );
}

export function BusinessItemWork(props: Props) {
  const { session } = useAuth(),
    { locale } = useI18n();
  const [open, setOpen] = useState(false);
  const key = `${session?.user?.id}:${session?.organization?.id}:${session?.role}:${locale}:${props.domain}:${props.monitorId}:${props.itemId}:${props.version}`;
  return (
    <details
      className={styles.panel}
      data-business-item-work
      data-item-version={props.version}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>{businessItemCopy[locale].title}</summary>
      {open && session?.authenticated && (
        <WorkForm
          key={key}
          {...props}
          canManage={props.canManage && session.role === "organization_admin"}
        />
      )}
    </details>
  );
}

function WorkForm({
  domain,
  monitorId,
  itemId,
  version,
  canManage,
  changed,
}: Props) {
  const { session } = useAuth();
  const { locale } = useI18n(),
    c = businessItemCopy[locale];
  const copy: Record<string, unknown> =
    domain === "tenders"
      ? tenderCopy[locale]
      : domain === "ip"
        ? trademarkReviewCopy[locale]
        : auctionTrackingCopy[locale];
  const decisionLabel = (value: string): string =>
    typeof copy[value] === "string" ? (copy[value] as string) : value;
  const [saved, setSaved] = useState<Work | null>(null),
    [members, setMembers] = useState<Members | null>(null);
  const [assigned, setAssigned] = useState(""),
    [comment, setComment] = useState(""),
    [decision, setDecision] = useState("");
  const [busy, setBusy] = useState(false),
    [failed, setFailed] = useState(false),
    [success, setSuccess] = useState(false);
  const request = useRef<AbortController | null>(null),
    onChanged = useRef(changed);
  onChanged.current = changed;
  const path = `/monitoring-centre/business/${domain}/${monitorId}/items/${itemId}/work`;
  const person = (value: Person | null | undefined) =>
    value
      ? `${value.name || c.former}${value.available ? "" : ` · ${c.inactive}`}`
      : c.unassigned;
  function clear() {
    setSaved(null);
    setMembers(null);
    setAssigned("");
    setComment("");
    setDecision("");
    setSuccess(false);
  }
  const load = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    clear();
    setBusy(true);
    setFailed(false);
    try {
      const value = await api<Work>(path, { signal: controller.signal });
      if (controller.signal.aborted) return;
      if (value.version !== version) {
        setFailed(true);
        onChanged.current();
        return;
      }
      let choices: Members | null = null;
      if (canManage && value.can_write && value.visibility === "workspace") {
        choices = await api<Members>("/monitoring-centre/business/members", {
          signal: controller.signal,
        });
      }
      if (!controller.signal.aborted) {
        setSaved(value);
        setAssigned(value.assigned?.id || "");
        setMembers(choices);
      }
    } catch {
      if (!controller.signal.aborted) {
        clear();
        setFailed(true);
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }, [path, version, canManage]);
  useEffect(() => {
    void load();
    const hide = () => {
      request.current?.abort();
      clear();
      setBusy(false);
      setFailed(true);
    };
    window.addEventListener("pagehide", hide);
    return () => {
      request.current?.abort();
      window.removeEventListener("pagehide", hide);
    };
  }, [load]);
  async function save(withDecision: boolean) {
    if (
      !saved?.binding ||
      busy ||
      !saved.can_write ||
      !canManage ||
      (withDecision && !decision)
    )
      return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setFailed(false);
    setSuccess(false);
    try {
      const value = await api<Work>(path, {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          expected_version: saved.version,
          expected_binding: saved.binding,
          assigned_user_id: assigned || null,
          comment,
          decision: withDecision ? decision : null,
        }),
      });
      if (!controller.signal.aborted) {
        setSaved(value);
        setComment("");
        setDecision("");
        setSuccess(true);
        onChanged.current();
      }
    } catch {
      if (!controller.signal.aborted) {
        clear();
        setFailed(true);
        onChanged.current();
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  async function more(kind: "members" | "history") {
    if (!saved || busy) return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    try {
      if (kind === "members" && members?.next_cursor) {
        const value = await api<Members>(
          `/monitoring-centre/business/members?after_id=${encodeURIComponent(members.next_cursor)}`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted)
          setMembers({ ...value, items: [...members.items, ...value.items] });
      } else if (kind === "history" && saved.next_before_version) {
        const value = await api<Work>(
          `${path}?before_version=${saved.next_before_version}`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted) {
          if (value.version !== saved.version || value.state !== "available") {
            clear();
            setFailed(true);
            onChanged.current();
          } else
            setSaved({
              ...value,
              history: [...saved.history, ...value.history],
            });
        }
      }
    } catch {
      if (!controller.signal.aborted) {
        clear();
        setFailed(true);
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  const options =
    saved?.visibility === "private"
      ? session?.user?.id === saved.creator_user_id
        ? [{ id: saved.creator_user_id, name: session.user.name }]
        : []
      : members?.items || [];
  const canWrite = !!saved?.can_write && canManage;
  return (
    <div className={styles.form}>
      <p>{c.help}</p>
      {busy && <p role="status">{c.loading}</p>}
      {failed && <p role="alert">{c.failed}</p>}
      {success && <p role="status">{c.saved}</p>}
      <div className={styles.actions}>
        <button disabled={busy} onClick={() => void load()}>
          {c.reload}
        </button>
      </div>
      {saved && (
        <>
          {saved.state === "available" && (
            <p>
              {c.assigned}: <strong>{person(saved.assigned)}</strong>
            </p>
          )}
          {saved.state !== "available" ? (
            <p role="status">{c.unavailable}</p>
          ) : (
            <>
              {canWrite ? (
                <>
                  <label>
                    {c.assigned}
                    <select
                      data-business-item-assignee
                      value={assigned}
                      disabled={busy}
                      onChange={(e) => setAssigned(e.target.value)}
                    >
                      <option value="">{c.unassigned}</option>
                      {saved.assigned &&
                        !options.some((o) => o.id === saved.assigned!.id) && (
                          <option value={saved.assigned.id} disabled>
                            {person(saved.assigned)}
                          </option>
                        )}
                      {options.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name || c.former}
                        </option>
                      ))}
                    </select>
                  </label>
                  {saved.visibility === "workspace" && members?.next_cursor && (
                    <div className={styles.actions}>
                      <button
                        disabled={busy}
                        onClick={() => void more("members")}
                      >
                        {c.moreMembers}
                      </button>
                    </div>
                  )}
                  <label>
                    {c.comment}
                    <textarea
                      data-business-item-comment
                      maxLength={4000}
                      value={comment}
                      disabled={busy}
                      onChange={(e) => setComment(e.target.value)}
                    />
                  </label>
                  <div className={styles.actions}>
                    <button disabled={busy} onClick={() => void save(false)}>
                      {c.save}
                    </button>
                  </div>
                  <label>
                    {c.decision}
                    <select
                      data-business-item-decision
                      value={decision}
                      disabled={busy}
                      onChange={(e) => setDecision(e.target.value)}
                    >
                      <option value="">{c.choose}</option>
                      {saved.decisions.map((d) => (
                        <option key={d} value={d}>
                          {decisionLabel(d)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className={styles.actions}>
                    <button
                      disabled={busy || !decision}
                      onClick={() => void save(true)}
                    >
                      {c.decide}
                    </button>
                  </div>
                </>
              ) : (
                <p>{c.readOnly}</p>
              )}
              <p>
                <strong>{c.history}</strong>
              </p>
              {!saved.history.length && <p>{c.empty}</p>}
              <ol className={styles.history}>
                {saved.history.map((entry) => (
                  <li key={entry.id} data-business-work-entry>
                    {entry.state !== "available" ? (
                      <p>{c.hidden}</p>
                    ) : (
                      <>
                        <p>
                          <strong>
                            {entry.decision
                              ? decisionLabel(entry.decision)
                              : c.note}
                          </strong>{" "}
                          · {entry.older_evidence ? c.older : c.current}
                        </p>
                        <p>
                          {c.actor}: {person(entry.actor)} · {c.assigned}:{" "}
                          {person(entry.assigned)}
                        </p>
                        <p>
                          {c.version} {entry.version} · {c.evidence}{" "}
                          {entry.binding?.sequence} ·{" "}
                          <time dateTime={entry.created_at}>
                            {entry.created_at
                              ? new Date(entry.created_at).toLocaleString(
                                  locale,
                                  { timeZone: "Europe/Zurich" },
                                )
                              : ""}
                          </time>
                        </p>
                        {entry.comment && (
                          <p className={styles.comment}>{entry.comment}</p>
                        )}
                      </>
                    )}
                  </li>
                ))}
              </ol>
              {saved.next_before_version && (
                <div className={styles.actions}>
                  <button disabled={busy} onClick={() => void more("history")}>
                    {c.earlier}
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
