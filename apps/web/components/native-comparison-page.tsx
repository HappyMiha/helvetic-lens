"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  api,
  invalidateResources,
  resourceScopeEpoch,
  resourceTag,
  resources,
  useResource,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { readRegistryPosition, registryScope } from "@/lib/registry-position";
import {
  nativeBaselineCopy,
  type NativeBaselineCandidates,
  type NativeComparisonPage,
  type NativeSnapshot,
} from "@/lib/native-baseline";
import {
  baselineCommand,
  chooseBaseline,
  comparisonSelection,
  nativeSnapshotHref,
  type BaselineDraft,
  type CommittedBaseline,
} from "@/lib/comparison-selection";
import { comparisonReadingCopy } from "@/lib/comparison-reading-copy";
import { sourceTimestamp } from "@/lib/source-reading";
import {
  SavedComparisonSummary,
  ComparisonPassages,
} from "./native-comparison-reading";
import styles from "./comparison-reading.module.css";
import { useAuth } from "./auth-gate";
import { ErrorNote, Loading } from "./common";
import { Shell } from "./shell";
import { Button } from "./ui/button";

export function NativeComparisonWorkspace({ eventId }: { eventId: string }) {
  const { session } = useAuth();
  return (
    <Workspace
      key={`${eventId}:${session?.organization?.id}:${session?.user?.id}`}
      eventId={eventId}
    />
  );
}

function Workspace({ eventId }: { eventId: string }) {
  const { locale, t, dateTime, number } = useI18n();
  const copy = nativeBaselineCopy[locale];
  const reading = comparisonReadingCopy[locale];
  const { canManage, session } = useAuth();
  const [returnRoute, setReturnRoute] = useState("/registry");
  useEffect(() => {
    try {
      const scope = registryScope(
        session?.user?.id,
        session?.organization?.id,
        session?.anonymous_development,
      );
      const position = readRegistryPosition(window.sessionStorage, scope);
      if (
        position?.target ===
        window.location.pathname + window.location.search + window.location.hash
      )
        setReturnRoute(position.route);
    } catch {
      /* The ordinary registry link works with disabled storage. */
    }
  }, [
    session?.user?.id,
    session?.organization?.id,
    session?.anonymous_development,
  ]);
  const [view, setView] = useState({ offset: 0, material: true, pin: "" });
  const page = useResource(
    resources.nativeComparison<NativeComparisonPage>(
      eventId,
      view.offset,
      view.material,
      view.pin,
    ),
  );
  const [candidatePages, setCandidatePages] = useState([""]);
  const candidates = useResource(
    resources.nativeBaselines<NativeBaselineCandidates>(
      eventId,
      candidatePages.at(-1) || "",
    ),
  );
  const [selection, setSelection] = useState<BaselineDraft | null>(null);
  const [committed, setCommitted] = useState<CommittedBaseline | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const generation = useRef(0),
    writing = useRef(false);
  const data = page.error ? null : page.data;
  const selected = comparisonSelection(
    data,
    canManage ? selection : null,
    committed,
  );
  const draft = selected.value;
  useEffect(
    () => () => {
      generation.current++;
    },
    [],
  );
  const choices = [...(candidates.data?.items || [])];
  if (draft && !choices.some((item) => item.id === draft.id))
    choices.unshift(draft);
  if (data?.before && !choices.some((item) => item.id === data.before?.id))
    choices.unshift(data.before);
  const describe = (snapshot: NativeSnapshot) =>
    `${snapshot.version_key} · ${copy.savedAt} ${sourceTimestamp(snapshot.saved_at) ? dateTime(snapshot.saved_at) : reading.unknown} · ${snapshot.id.slice(0, 8)}`;
  const valid =
    !page.error &&
    !page.loading &&
    !candidates.error &&
    !candidates.loading &&
    !selected.conflict &&
    !selected.pending &&
    data &&
    candidates.data?.after_version_id === data.after.id;

  async function save(clear = false) {
    const command = baselineCommand(
      data,
      selection,
      committed,
      !!(canManage && valid),
      clear,
    );
    if (!data || !command || writing.current) return;
    const token = generation.current,
      epoch = resourceScopeEpoch("session");
    writing.current = true;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const receipt = await api<{
        revision: number;
        comparison_id: string | null;
      }>(`/registry/events/${encodeURIComponent(eventId)}/comparison`, {
        method: "PUT",
        body: JSON.stringify(command),
      });
      if (
        token !== generation.current ||
        epoch !== resourceScopeEpoch("session")
      )
        return;
      setView({ offset: 0, material: view.material, pin: "" });
      setCommitted({ after: data.after.id, ...receipt, previous: data });
      setSelection(null);
      setMessage(clear ? copy.cleared : reading.saved);
      // A committed write is not a failed save if the following read fails.
      void invalidateResources(resourceTag(`native-baseline:${eventId}`)).catch(
        () => {},
      );
    } catch {
      if (
        token === generation.current &&
        epoch === resourceScopeEpoch("session")
      )
        setError(copy.error);
    } finally {
      writing.current = false;
      if (
        token === generation.current &&
        epoch === resourceScopeEpoch("session")
      )
        setBusy(false);
    }
  }

  function reset() {
    setError("");
    setMessage("");
    setCandidatePages([""]);
    setView({ offset: 0, material: view.material, pin: "" });
    void invalidateResources(resourceTag(`native-baseline:${eventId}`)).catch(
      () => {},
    );
  }
  return (
    <Shell section={copy.title}>
      <div
        className={
          styles.workspace + " [&_button]:min-h-11 [&_button]:whitespace-normal"
        }
      >
        <Link className="back-link" href={returnRoute}>
          {t("registryReturn.back")}
        </Link>
        <div className="page-heading">
          <div>
            <h1>{copy.title}</h1>
            <p className="muted max-w-3xl">{copy.help}</p>
          </div>
          <Button
            data-native-refresh
            variant="outline"
            onClick={reset}
            disabled={busy}
          >
            {t("logs.refresh")}
          </Button>
        </div>
        <ErrorNote message={page.error || error} />
        {message && (
          <p role="status">{selected.pending ? reading.pending : message}</p>
        )}
        {page.loading && !data && <Loading text={t("evidence.opening")} />}
        {data && (
          <>
            <section className={styles.editor} data-native-baseline>
              <h2 className="break-words" lang={data.language}>
                {data.title}
              </h2>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="min-w-0">
                  <h3>{copy.after}</h3>
                  <p className="break-words text-sm">{describe(data.after)}</p>
                  {nativeSnapshotHref(data.after) && (
                    <Link
                      href={nativeSnapshotHref(data.after)!}
                      className="inline-flex min-h-11 items-center underline"
                    >
                      {t("common.evidence")}
                    </Link>
                  )}
                </div>
                <div className="min-w-0">
                  <label
                    htmlFor="native-baseline"
                    className="block font-semibold mb-2"
                  >
                    {copy.before}
                  </label>
                  <select
                    id="native-baseline"
                    className="w-full min-h-11 max-w-full"
                    value={draft?.id || ""}
                    disabled={
                      !canManage ||
                      busy ||
                      selected.pending ||
                      selected.conflict ||
                      !!page.error
                    }
                    onChange={(event) =>
                      setSelection(
                        chooseBaseline(
                          data,
                          choices.find(
                            (row) => row.id === event.target.value,
                          ) || null,
                        ),
                      )
                    }
                  >
                    <option value="">{copy.choose}</option>
                    {choices.map((row) => (
                      <option key={row.id} value={row.id}>
                        {describe(row)}
                      </option>
                    ))}
                  </select>
                  <ErrorNote message={candidates.error} />
                  {candidates.error && (
                    <Button variant="outline" onClick={candidates.reload}>
                      {t("gettingStarted.retry")}
                    </Button>
                  )}
                  {!candidates.loading &&
                    !candidates.error &&
                    !choices.length && (
                      <p className="text-sm muted">{copy.empty}</p>
                    )}
                  <div className="flex flex-wrap gap-2 mt-2">
                    {candidatePages.length > 1 && (
                      <Button
                        variant="outline"
                        disabled={busy || candidates.loading}
                        onClick={() =>
                          setCandidatePages((value) => value.slice(0, -1))
                        }
                      >
                        {t("materialPage.previous")}
                      </Button>
                    )}
                    {candidates.data?.next_after && (
                      <Button
                        data-native-more
                        variant="outline"
                        disabled={busy || candidates.loading}
                        onClick={() =>
                          setCandidatePages((value) => [
                            ...value,
                            candidates.data!.next_after!,
                          ])
                        }
                      >
                        {copy.more}
                      </Button>
                    )}
                    {draft && nativeSnapshotHref(draft) && (
                      <Link
                        className="inline-flex min-h-11 items-center underline"
                        href={nativeSnapshotHref(draft)!}
                      >
                        {t("common.evidence")}
                      </Link>
                    )}
                  </div>
                </div>
              </div>
              {canManage && selected.dirty && (
                <aside className={styles.choiceNotice} data-baseline-draft>
                  <p role="status">
                    {selected.conflict ? reading.conflict : reading.unsaved}
                  </p>
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() => {
                      setSelection(null);
                      setError("");
                    }}
                  >
                    {reading.useSaved}
                  </Button>
                </aside>
              )}
              {canManage ? (
                <div className="flex flex-wrap gap-3 mt-4" aria-busy={busy}>
                  <Button
                    data-native-save
                    className="hl-primary-action"
                    onClick={() => void save()}
                    disabled={!draft || !selected.dirty || !valid || busy}
                  >
                    {busy ? copy.saving : copy.save}
                  </Button>
                  <Button
                    data-native-clear
                    variant="outline"
                    onClick={() => void save(true)}
                    disabled={!valid || busy || data.status === "unselected"}
                  >
                    {copy.clear}
                  </Button>
                </div>
              ) : (
                <p className="text-sm muted">{copy.readOnly}</p>
              )}
              <p className="text-sm muted mb-0">{copy.notice}</p>
            </section>
            {selected.pending ? null : data.status !== "ready" ? (
              <p role="status" className="panel p-5">
                {data.status === "stale" ? copy.stale : copy.unselected}
              </p>
            ) : (
              <section
                className={styles.diff}
                data-native-diff
                aria-busy={page.loading}
              >
                <SavedComparisonSummary
                  data={data}
                  locale={locale}
                  formatDate={dateTime}
                />
                <div className="flex flex-wrap gap-3 pb-4">
                  <label className="flex gap-2 items-center min-h-11">
                    <input
                      data-native-all
                      type="checkbox"
                      checked={!view.material}
                      disabled={busy || page.loading}
                      onChange={(event) =>
                        setView({
                          offset: 0,
                          material: !event.target.checked,
                          pin: data.comparison_id || "",
                        })
                      }
                    />
                    {copy.all}
                  </label>
                </div>
                {data.items.length === 0 && (
                  <p className="p-5">{copy.noChanges}</p>
                )}
                {data.items.map((item) => (
                  <article
                    data-native-change={item.id}
                    key={item.id}
                    className={styles.change}
                  >
                    <h3 className="text-sm">
                      {item.classification === "unchanged"
                        ? copy.unchanged
                        : t(`materialPage.${item.classification}`)}
                    </h3>
                    <ComparisonPassages
                      data={data}
                      item={item}
                      locale={locale}
                      evidenceLabel={t("common.evidence")}
                    />
                  </article>
                ))}
                <div
                  className="p-4 flex flex-wrap items-center gap-3"
                  role="navigation"
                  aria-label={copy.title}
                >
                  <span className="text-sm muted">
                    {number(
                      data.items.length
                        ? (data.pagination?.offset || 0) + 1
                        : 0,
                    )}
                    –
                    {number((data.pagination?.offset || 0) + data.items.length)}{" "}
                    / {number(data.pagination?.total || 0)}
                  </span>
                  <Button
                    data-native-previous
                    variant="outline"
                    disabled={
                      busy ||
                      page.loading ||
                      data.pagination?.previous_offset == null
                    }
                    onClick={() =>
                      setView({
                        ...view,
                        offset: data.pagination!.previous_offset!,
                        pin: data.comparison_id!,
                      })
                    }
                  >
                    {t("materialPage.previous")}
                  </Button>
                  <Button
                    data-native-next
                    variant="outline"
                    disabled={
                      busy ||
                      page.loading ||
                      data.pagination?.next_offset == null
                    }
                    onClick={() =>
                      setView({
                        ...view,
                        offset: data.pagination!.next_offset!,
                        pin: data.comparison_id!,
                      })
                    }
                  >
                    {t("materialPage.next")}
                  </Button>
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </Shell>
  );
}
