"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { relatedCopy } from "@/lib/related-copy";
import { centreTimezone } from "@/lib/monitoring-centre-copy";
import {
  domainLinks,
  memberKey,
  storyHref,
  type Domain,
  type Member,
  type Page,
  type Preview,
  type Reference,
  type Story,
} from "@/lib/related-developments";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import { RelatedBindingReview } from "./related-binding-review";
import styles from "./related-developments.module.css";

const ROOT = "/related-developments";

function useRead<T>(path: string | null, epoch: number) {
  const key = `${path}:${epoch}`;
  const [result, setResult] = useState<{
    key: string;
    data?: T;
    failed?: boolean;
  } | null>(null);
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    api<T>(ROOT + path, { signal: controller.signal }).then(
      (data) => {
        if (!controller.signal.aborted) setResult({ key, data });
      },
      () => {
        if (!controller.signal.aborted) setResult({ key, failed: true });
      },
    );
    return () => controller.abort();
  }, [path, key]);
  return result?.key === key ? result : null;
}

export function RelatedDevelopments() {
  const { locale } = useI18n();
  return (
    <Shell section={relatedCopy[locale].title}>
      <Suspense fallback={<p>{relatedCopy[locale].loading}</p>}>
        <Scoped />
      </Suspense>
    </Shell>
  );
}

function Scoped() {
  const { session } = useAuth();
  const { locale } = useI18n();
  const params = useSearchParams();
  const story = params.getAll("story"),
    revision = params.getAll("revision");
  const valid =
    story.length <= 1 &&
    revision.length <= 1 &&
    (!story.length || /^[0-9a-f-]{36}$/i.test(story[0])) &&
    (!revision.length ||
      (story.length === 1 &&
        /^[1-9][0-9]*$/.test(revision[0]) &&
        Number.isSafeInteger(Number(revision[0]))));
  if (!session?.authenticated)
    return <p role="alert">{relatedCopy[locale].signIn}</p>;
  if (!valid)
    return (
      <div className={styles.root}>
        <p role="alert">{relatedCopy[locale].failed}</p>
        <Link href={ROOT}>{relatedCopy[locale].stories}</Link>
      </div>
    );
  return (
    <Workspace
      key={`${session.user?.id}:${session.organization?.id}:${session.role}:${story}:${revision}`}
      story={story[0] || ""}
      revision={revision[0] || ""}
    />
  );
}

function EventCard({ member }: { member: Member }) {
  const { locale } = useI18n();
  const c = relatedCopy[locale],
    domain = member.reference?.domain || member.domain;
  const format = (value: string) =>
    new Intl.DateTimeFormat(locale === "rm-CH" ? "de-CH" : locale, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Zurich",
    }).format(new Date(value));
  return (
    <div className={styles.card}>
      <h3>
        {domain ? c[domain] : c.unknown}
        {member.monitor_name ? ` · ${member.monitor_name}` : ""}
      </h3>
      <p className={styles.badge}>{c[member.availability]}</p>
      {member.availability !== "unavailable" && (
        <>
          <dl>
            <dt>{c.source}</dt>
            <dd>
              {member.source_identity
                ? `${member.source_identity.sender} / ${member.source_identity.identifier} / ${member.source_identity.sent}`
                : `${member.authority?.namespace}: ${member.authority?.identifier}`}
            </dd>
            <dt>{c.state}</dt>
            <dd>{member.source_state || c.unknown}</dd>
            {member.current_source_state && (
              <>
                <dt>{c.current}</dt>
                <dd>{member.current_source_state}</dd>
              </>
            )}
            <dt>{c.version}</dt>
            <dd>{member.reference?.revision}</dd>
            <dt>{c.time} · {centreTimezone}</dt>
            <dd>
              {member.time_kind === "unknown" ? (
                c.unknownTime
              ) : (
                <>
                  {member.time_kind ? c[member.time_kind] : c.unknown}
                  <br />
                  {member.source_at && (
                    <time dateTime={member.source_at}>
                      {format(member.source_at)}
                    </time>
                  )}
                  {member.source_until && (
                    <>
                      {" "}
                      —{" "}
                      <time dateTime={member.source_until}>
                        {format(member.source_until)}
                      </time>
                    </>
                  )}
                </>
              )}
            </dd>
            <dt>{c.geography}</dt>
            <dd>
              {member.geography
                ? `${member.geography.place_id} · ${member.geography.boundary_version}`
                : c.missingPlace}
            </dd>
          </dl>
          <p>{member.reviewed ? c.reviewed : c.notReviewed}</p>
        </>
      )}
      {member.href && <Link href={member.href}>{c.open}</Link>}
    </div>
  );
}

function Workspace({ story, revision }: { story: string; revision: string }) {
  const { locale } = useI18n(),
    c = relatedCopy[locale];
  const router = useRouter();
  const [epoch, setEpoch] = useState(0),
    [hidden, setHidden] = useState(false);
  const [archived, setArchived] = useState(false),
    [after, setAfter] = useState("");
  const [domain, setDomain] = useState<Domain>("warnings"),
    [candidateAfter, setCandidateAfter] = useState("");
  const [editing, setEditing] = useState(false),
    [name, setName] = useState("");
  const [chosen, setChosen] = useState<Reference[]>([]),
    [busy, setBusy] = useState(false),
    [failed, setFailed] = useState(false);
  const [notice, setNotice] = useState(false),
    [historyBefore, setHistoryBefore] = useState("");
  const [preview, setPreview] = useState<{ key: string; data: Preview } | null>(
    null,
  );
  const [inspect, setInspect] = useState<Reference | null>(null);
  const mutation = useRef<AbortController | null>(null),
    retry = useRef<{ signature: string; key: string } | null>(null);
  const selectionKey = JSON.stringify(chosen) + ":" + epoch;
  const check = preview?.key === selectionKey ? preview.data : null;
  useEffect(() => {
    function visibility() {
      setHidden(document.hidden);
      setEpoch((v) => v + 1);
    }
    function hide() {
      setHidden(true);
    }
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("focus", visibility);
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", visibility);
    const timer = window.setInterval(() => setEpoch((v) => v + 1), 60000);
    return () => {
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("focus", visibility);
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", visibility);
      window.clearInterval(timer);
      mutation.current?.abort();
    };
  }, []);
  const caps = useRead<{ can_write: boolean; can_review_bindings: boolean }>(
    hidden ? null : "/capabilities",
    epoch,
  );
  const list = useRead<Page<Story>>(
    hidden || story
      ? null
      : `/stories?archived=${archived}&after=${after}`.replace(/&after=$/, ""),
    epoch,
  );
  const detail = useRead<Story>(
    hidden || !story
      ? null
      : `/stories/${story}${revision ? `?revision=${revision}` : ""}`,
    epoch,
  );
  const history = useRead<
    Page<{ revision: number; action: keyof typeof c; created_at: string }>
  >(
    hidden || !story
      ? null
      : `/stories/${story}/history${historyBefore ? `?before=${historyBefore}` : ""}`,
    epoch,
  );
  const candidates = useRead<Page<Member>>(
    hidden || !editing
      ? null
      : `/candidates?domain=${domain}${candidateAfter ? `&after=${candidateAfter}` : ""}`,
    epoch,
  );
  const value = detail?.data;
  const writable = caps?.data?.can_write === true;
  const canSave =
    writable &&
    !busy &&
    !!check?.can_save &&
    !!name.trim() &&
    (story ? chosen.length >= 1 : chosen.length >= 2);

  async function perform<T>(
    path: string,
    body: object,
    saved: (data: T) => void,
    idempotent = false,
  ) {
    if (mutation.current) return;
    const controller = new AbortController();
    mutation.current = controller;
    setBusy(true);
    setFailed(false);
    setNotice(false);
    const signature = JSON.stringify({ path, body });
    if (idempotent && retry.current?.signature !== signature)
      retry.current = { signature, key: crypto.randomUUID() };
    try {
      const data = await api<T>(ROOT + path, {
        method: "POST",
        body: JSON.stringify(
          idempotent ? { ...body, request_key: retry.current!.key } : body,
        ),
        signal: controller.signal,
      });
      if (!controller.signal.aborted) {
        if (idempotent) retry.current = null;
        saved(data);
      }
    } catch {
      if (!controller.signal.aborted) setFailed(true);
    } finally {
      if (!controller.signal.aborted) setBusy(false);
      mutation.current = null;
    }
  }
  function edit(members: Member[] = [], title = "") {
    setChosen(
      members.flatMap((member) => (member.reference ? [member.reference] : [])),
    );
    setName(title);
    setEditing(true);
    setPreview(null);
    setFailed(false);
  }
  async function refreshMembers() {
    if (mutation.current) return;
    const controller = new AbortController();
    mutation.current = controller;
    setBusy(true);
    setFailed(false);
    setPreview(null);
    try {
      const values = await Promise.all(
        chosen.map((ref) =>
          api<Member>(
            `${ROOT}/events/${ref.domain}/${ref.monitor_id}/${ref.event_id}`,
            { signal: controller.signal },
          ),
        ),
      );
      if (!controller.signal.aborted)
        setChosen(
          values.map((member) => {
            if (!member.reference) throw new Error();
            return member.reference;
          }),
        );
    } catch {
      if (!controller.signal.aborted) setFailed(true);
    } finally {
      if (!controller.signal.aborted) setBusy(false);
      mutation.current = null;
    }
  }
  function saved(data: Story) {
    setEditing(false);
    setNotice(true);
    setEpoch((v) => v + 1);
    router.push(storyHref(data.id));
  }
  if (hidden)
    return (
      <div className={styles.root}>
        <h1>{c.title}</h1>
        <p>{c.loading}</p>
      </div>
    );
  return (
    <div className={styles.root} data-related-developments>
      <h1>{c.title}</h1>
      <p>{c.intro}</p>
      <p>{c.noTransfer}</p>
      <div className={styles.actions}>
        <Link href="/monitoring">{c.candidates}</Link>
        <Link href={ROOT}>{c.stories}</Link>
        <button
          onClick={() => {
            setEpoch((v) => v + 1);
            setFailed(false);
          }}
          disabled={busy}
        >
          {c.refresh}
        </button>
      </div>
      {(failed ||
        caps?.failed ||
        detail?.failed ||
        list?.failed ||
        candidates?.failed ||
        history?.failed) && (
        <p role="alert" className={styles.message}>
          {c.failed}
        </p>
      )}
      {notice && <p role="status">{c.saved}</p>}
      {!caps ? (
        <p role="status">{c.loading}</p>
      ) : (
        !writable && <p>{c.readonly}</p>
      )}
      {!story && (
        <section>
          <h2>{c.stories}</h2>
          <div className={styles.actions}>
            <label>
              <input
                type="checkbox"
                checked={archived}
                onChange={(event) => {
                  setArchived(event.target.checked);
                  setAfter("");
                }}
              />
              {c.archived}
            </label>
            <button disabled={!writable || busy} onClick={() => edit()}>
              {c.newStory}
            </button>
          </div>
          {!list && <p role="status">{c.loading}</p>}
          {list?.data?.items.length === 0 && <p>{c.noStories}</p>}
          <div className={styles.grid}>
            {list?.data?.items.map((item) => (
              <article className={styles.card} key={item.id}>
                <h3>
                  <Link href={storyHref(item.id)}>{item.title}</Link>
                </h3>
                <p>
                  {c.version} {item.version} · {c[item.status]}
                </p>
              </article>
            ))}
          </div>
          <div className={styles.actions}>
            {after && (
              <button onClick={() => setAfter("")}>{c.previous}</button>
            )}
            {list?.data?.next && (
              <button onClick={() => setAfter(list.data!.next!)}>
                {c.more}
              </button>
            )}
          </div>
        </section>
      )}
      {story && !detail && <p role="status">{c.loading}</p>}
      {value && (
        <section>
          <h2>{value.title}</h2>
          <p>
            {c.version} {value.revision} · {c[value.status]}
            {value.historical ? ` · ${c.historical}` : ""}
          </p>
          <p className={styles.message}>{c[value.association_state]}</p>
          <div className={styles.grid}>
            {value.members.map((member, index) => (
              <EventCard key={index} member={member} />
            ))}
          </div>
          <div className={styles.actions}>
            <button
              disabled={!writable || busy || value.status !== "active"}
              onClick={() => edit(value.members, value.title)}
            >
              {value.historical ? c.useRevision : c.edit}
            </button>
            {!value.historical && (
              <button
                disabled={!writable || busy}
                onClick={() =>
                  void perform<Story>(
                    `/stories/${story}`,
                    {
                      expected_version: value.version,
                      action: value.status === "active" ? "archive" : "restore",
                    },
                    saved,
                    true,
                  )
                }
              >
                {value.status === "active" ? c.archive : c.restore}
              </button>
            )}
            {value.historical && (
              <Link href={storyHref(story)}>{c.current}</Link>
            )}
          </div>
          <details>
            <summary>{c.history}</summary>
            {history?.data?.items.map((item) => (
              <p key={item.revision}>
                <Link href={storyHref(story, item.revision)}>
                  {c.version} {item.revision} · {c[item.action] || c.unknown}
                </Link>
              </p>
            ))}
            {history?.data?.next && (
              <button
                onClick={() => setHistoryBefore(String(history.data!.next))}
              >
                {c.more}
              </button>
            )}
            {historyBefore && (
              <button onClick={() => setHistoryBefore("")}>{c.previous}</button>
            )}
          </details>
        </section>
      )}
      {editing && (
        <section aria-label={c.edit}>
          <h2>{story ? c.edit : c.newStory}</h2>
          <p>{c.limit}</p>
          <label className={styles.field}>
            {c.name}
            <input
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={busy}
            />
          </label>
          <h3>
            {c.selected} ({chosen.length}/12)
          </h3>
          <div className={styles.grid}>
            {chosen.map((ref) => (
              <div key={memberKey(ref)}>
                <EventCard
                  member={
                    check?.members.find(
                      (member) =>
                        member.reference &&
                        memberKey(member.reference) === memberKey(ref),
                    ) || {
                      reference: ref,
                      availability: "unavailable",
                      href: null,
                    }
                  }
                />
                <button
                  disabled={busy}
                  onClick={() =>
                    setChosen((items) =>
                      items.filter(
                        (item) => memberKey(item) !== memberKey(ref),
                      ),
                    )
                  }
                >
                  {c.remove} · {c[ref.domain]}
                </button>
              </div>
            ))}
          </div>
          <div className={styles.actions}>
            <button
              disabled={busy || !chosen.length}
              onClick={() => void refreshMembers()}
            >
              {c.refreshMembers}
            </button>
            <button
              disabled={busy || !chosen.length}
              onClick={() =>
                void perform<Preview>("/preview", { members: chosen }, (data) =>
                  setPreview({ key: selectionKey, data }),
                )
              }
            >
              {c.check}
            </button>
          </div>
          {check && (
            <div className={styles.message}>
              <h3>{c.reason}</h3>
              {check.links.map((link, index) => (
                <p key={index}>
                  {link.left && link.right
                    ? `${c[link.left.domain]} ↔ ${c[link.right.domain]}: `
                    : ""}
                  {c[link.reason as keyof typeof c] || c.unverified}
                </p>
              ))}
              {!check.can_save && <p>{c.unverified}</p>}
            </div>
          )}
          <div className={styles.actions}>
            <button
              disabled={!canSave}
              onClick={() =>
                void perform<Story>(
                  story ? `/stories/${story}` : "/stories",
                  {
                    title: name,
                    members: chosen,
                    ...(story
                      ? { expected_version: value?.version, action: "revise" }
                      : {}),
                  },
                  saved,
                  true,
                )
              }
            >
              {c.save}
            </button>
            <button disabled={busy} onClick={() => setEditing(false)}>
              {c.cancel}
            </button>
          </div>
          <h3>{c.candidates}</h3>
          <label>
            {c.source}
            <select
              value={domain}
              onChange={(event) => {
                setDomain(event.target.value as Domain);
                setCandidateAfter("");
              }}
            >
              {(Object.keys(domainLinks) as Domain[]).map((id) => (
                <option key={id} value={id}>
                  {c[id]}
                </option>
              ))}
            </select>
          </label>
          <Link href={domainLinks[domain]}>{c[domain]}</Link>
          {!candidates && <p role="status">{c.loading}</p>}
          {candidates?.data?.items.length === 0 && <p>{c.empty}</p>}
          <div className={styles.grid}>
            {candidates?.data?.items.map((member, index) => {
              const ref = member.reference;
              const selected =
                !!ref &&
                chosen.some((item) => memberKey(item) === memberKey(ref));
              return (
                <article key={ref ? memberKey(ref) : member.id || index}>
                  <EventCard member={member} />
                  {ref && (
                    <label>
                      <input
                        type="checkbox"
                        checked={selected}
                        disabled={
                          busy ||
                          !writable ||
                          member.availability !== "available" ||
                          (!selected && chosen.length >= 12)
                        }
                        onChange={() =>
                          setChosen((items) =>
                            selected
                              ? items.filter(
                                  (item) => memberKey(item) !== memberKey(ref),
                                )
                              : [...items, ref],
                          )
                        }
                      />
                      {c.selected} · {member.monitor_name || c[ref.domain]}
                    </label>
                  )}
                  {ref && caps?.data?.can_review_bindings && (
                    <button onClick={() => setInspect(ref)}>
                      {c.bindingReview}
                    </button>
                  )}
                </article>
              );
            })}
          </div>
          <div className={styles.actions}>
            {candidateAfter && (
              <button onClick={() => setCandidateAfter("")}>
                {c.previous}
              </button>
            )}
            {candidates?.data?.next && (
              <button onClick={() => setCandidateAfter(candidates.data!.next!)}>
                {c.more}
              </button>
            )}
          </div>
        </section>
      )}
      {inspect && caps?.data?.can_review_bindings && (
        <RelatedBindingReview
          key={JSON.stringify(inspect)}
          reference={inspect}
          onChanged={() => setEpoch((v) => v + 1)}
          onClose={() => setInspect(null)}
        />
      )}
    </div>
  );
}
