"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { pollenDraftCopy } from "@/lib/pollen-draft-copy";
import { pollenCreateCopy } from "@/lib/pollen-create-copy";
import { PollenDraftCreate } from "./pollen-draft-create";
import {
  draftFailure,
  privatePollenScope,
  type DraftPage,
  type PollenConfiguration,
  type PollenDraft,
  type PollenRevision,
  type RevisionPage,
} from "@/lib/pollen-drafts";
import { useAuth } from "./auth-gate";
import { Shell } from "./shell";
import styles from "./pollen-draft-reader.module.css";

export function PollenDraftReader() {
  const { session } = useAuth();
  const scope = session?.authenticated
    ? privatePollenScope(
        session.user?.id,
        session.organization?.id,
        session.role,
      )
    : null;
  // Remount synchronously before rendering any data from a different principal.
  return <Reader key={scope || "unavailable"} allowed={!!scope} />;
}

function Settings({
  configuration,
  historical = false,
}: {
  configuration: PollenConfiguration;
  historical?: boolean;
}) {
  const { locale } = useI18n();
  const copy = pollenDraftCopy[locale];
  const Heading = historical ? "h3" : "h4";
  return (
    <div className={styles.settings}>
      <p>
        <strong>{copy.station}:</strong> {configuration.station_id}
      </p>
      {configuration.selections.map((selection) => (
        <section key={selection.allergen}>
          <Heading>
            {copy.allergens[selection.allergen] || copy.unknown}
          </Heading>
          {!selection.rules.length && <p>{copy.noRules}</p>}
          {selection.rules.map((rule) => (
            <div className={styles.rule} key={rule.period}>
              <p>
                <strong>{copy.periods[rule.period] || copy.unknown}</strong>
              </p>
              {rule.threshold && (
                <p>
                  {copy.threshold}: {rule.threshold.trigger_at_or_above}{" "}
                  {rule.unit}
                  <br />
                  {copy.reset}: {rule.threshold.reset_at_or_below} {rule.unit}
                </p>
              )}
              {rule.rapid_increase && (
                <p>
                  {copy.rapid}: {rule.rapid_increase.minimum_increase}{" "}
                  {rule.unit}
                  {" / "}
                  {rule.rapid_increase.window_hours} {copy.hours}
                </p>
              )}
              {rule.category_change && <p>{copy.category}</p>}
            </div>
          ))}
        </section>
      ))}
      <p>
        {copy.delivery}:{" "}
        {copy.email[configuration.delivery.email] || copy.unknown}
        {configuration.delivery.digest_at && (
          <> · {configuration.delivery.digest_at}</>
        )}
      </p>
      {configuration.delivery.quiet_hours && (
        <p>
          {copy.quiet}: {configuration.delivery.quiet_hours.start}
          {"–"}
          {configuration.delivery.quiet_hours.end}
        </p>
      )}
      <p>
        {copy.timezone}: {configuration.timezone}
      </p>
    </div>
  );
}

function Reader({ allowed }: { allowed: boolean }) {
  const { canManage } = useAuth();
  const [creating, setCreating] = useState(false);
  const { locale } = useI18n();
  const copy = pollenDraftCopy[locale];
  const [items, setItems] = useState<PollenDraft[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [selected, setSelected] = useState<PollenDraft | null>(null);
  const [history, setHistory] = useState<PollenRevision[]>([]);
  const [before, setBefore] = useState<number | null>(null);
  const [loading, setLoading] = useState(allowed);
  const [detailLoading, setDetailLoading] = useState(false);
  const [failure, setFailure] = useState<ReturnType<
    typeof draftFailure
  > | null>(null);
  const listRequest = useRef<AbortController | null>(null);
  const detailRequest = useRef<AbortController | null>(null);
  const detailHeading = useRef<HTMLHeadingElement | null>(null);

  useEffect(() => {
    if (!selected) return;
    detailHeading.current?.focus({ preventScroll: true });
    if (window.matchMedia("(max-width: 700px)").matches) {
      detailHeading.current?.scrollIntoView({ block: "start" });
    }
  }, [selected?.id]);

  function clearDetail() {
    detailRequest.current?.abort();
    setSelected(null);
    setHistory([]);
    setBefore(null);
    setDetailLoading(false);
  }
  function failed(error: unknown) {
    setCreating(false);
    // Never keep potentially revoked private records visible after a failed read.
    listRequest.current?.abort();
    clearDetail();
    setItems([]);
    setCursor(null);
    setLoading(false);
    setFailure(
      draftFailure(error instanceof ApiError ? error.code : "request_failed"),
    );
  }
  async function loadList(next: string | null = null) {
    if (!allowed) return;
    listRequest.current?.abort();
    const controller = new AbortController();
    listRequest.current = controller;
    if (!next) {
      clearDetail();
      setItems([]);
      setCursor(null);
    }
    setLoading(true);
    setFailure(null);
    try {
      const page = await api<DraftPage>(
        `/monitoring-subjects?limit=20${next ? `&cursor=${encodeURIComponent(next)}` : ""}`,
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      setItems((old) =>
        next
          ? [
              ...old,
              ...page.items.filter(
                (item) => !old.some((saved) => saved.id === item.id),
              ),
            ]
          : page.items,
      );
      setCursor(page.next_cursor);
    } catch (error) {
      if (!controller.signal.aborted) failed(error);
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }
  async function openDraft(id: string) {
    clearDetail();
    setFailure(null);
    setDetailLoading(true);
    const controller = new AbortController();
    detailRequest.current = controller;
    try {
      const path = `/monitoring-subjects/${encodeURIComponent(id)}`;
      const [draft, page] = await Promise.all([
        api<PollenDraft>(path, { signal: controller.signal }),
        api<RevisionPage>(`${path}/history?limit=10`, {
          signal: controller.signal,
        }),
      ]);
      if (controller.signal.aborted) return;
      setSelected(draft);
      setHistory(page.items);
      setBefore(page.next_before_revision);
    } catch (error) {
      if (!controller.signal.aborted) failed(error);
    } finally {
      if (!controller.signal.aborted) setDetailLoading(false);
    }
  }
  async function moreHistory() {
    if (!selected || before === null) return;
    detailRequest.current?.abort();
    const controller = new AbortController();
    detailRequest.current = controller;
    setDetailLoading(true);
    try {
      const page = await api<RevisionPage>(
        `/monitoring-subjects/${encodeURIComponent(selected.id)}/history?limit=10&before_revision=${before}`,
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      setHistory((old) => [
        ...old,
        ...page.items.filter(
          (item) => !old.some((saved) => saved.revision === item.revision),
        ),
      ]);
      setBefore(page.next_before_revision);
    } catch (error) {
      if (!controller.signal.aborted) failed(error);
    } finally {
      if (!controller.signal.aborted) setDetailLoading(false);
    }
  }
  useEffect(() => {
    void loadList();
    return () => {
      listRequest.current?.abort();
      detailRequest.current?.abort();
    };
    // Reader is keyed by the complete authenticated principal, including role.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Shell section={copy.title}>
      <div className={styles.reader} data-pollen-drafts>
        <header>
          <h1>{copy.title}</h1>
          <p>{copy.note}</p>
        </header>
        {!allowed ? (
          <p role="status">{copy.access}</p>
        ) : creating ? (
          <PollenDraftCreate
            onClose={() => setCreating(false)}
            onDenied={failed}
            onSaved={(id) => {
              setCreating(false);
              void loadList();
              void openDraft(id);
            }}
          />
        ) : (
          <>
            <button
              className={styles.button}
              type="button"
              onClick={() => void loadList()}
              disabled={loading}
            >
              {copy.refresh}
            </button>
            {canManage && !loading && !failure && (
              <button
                className={styles.button}
                type="button"
                onClick={() => {
                  clearDetail();
                  setCreating(true);
                }}
              >
                {pollenCreateCopy[locale].create}
              </button>
            )}
            {failure && (
              <p className={styles.notice} role="alert">
                {copy[failure]}
              </p>
            )}
            <div className={styles.columns}>
              <section aria-label={copy.title} aria-busy={loading}>
                {loading && <p role="status">{copy.loading}</p>}
                {!loading && !failure && !items.length && <p>{copy.empty}</p>}
                <ul className={styles.list}>
                  {items.map((item) => (
                    <li key={item.id}>
                      <button
                        className={styles.button}
                        type="button"
                        aria-pressed={selected?.id === item.id}
                        onClick={() => void openDraft(item.id)}
                      >
                        <strong>
                          {copy.station} {item.configuration.station_id}
                        </strong>
                        <span>
                          {item.configuration.selections
                            .map(
                              (s) => copy.allergens[s.allergen] || copy.unknown,
                            )
                            .join(", ")}
                        </span>
                        <small>
                          {copy.revision} {item.revision}
                        </small>
                      </button>
                    </li>
                  ))}
                </ul>
                {cursor && (
                  <button
                    className={styles.button}
                    type="button"
                    disabled={loading}
                    onClick={() => void loadList(cursor)}
                  >
                    {copy.more}
                  </button>
                )}
              </section>
              <section aria-label={copy.settings} aria-busy={detailLoading}>
                {detailLoading && <p role="status">{copy.loading}</p>}
                {!selected && !detailLoading && !failure && (
                  <p>{copy.select}</p>
                )}
                {selected && (
                  <>
                    <h2 ref={detailHeading} tabIndex={-1}>
                      {copy.settings}
                    </h2>
                    <h3>
                      {copy.revision} {selected.revision}
                    </h3>
                    <Settings configuration={selected.configuration} />
                    <button
                      className={styles.button}
                      type="button"
                      disabled
                      aria-describedby="pollen-start-blocked"
                    >
                      {copy.start}
                    </button>
                    <p id="pollen-start-blocked" className={styles.notice}>
                      {copy.blocked}
                    </p>
                    <h2>{copy.history}</h2>
                    {history.map((item) => (
                      <details key={item.revision} className={styles.history}>
                        <summary>
                          {copy.revision} {item.revision}
                        </summary>
                        <Settings
                          configuration={item.configuration}
                          historical
                        />
                      </details>
                    ))}
                    {before !== null && (
                      <button
                        className={styles.button}
                        type="button"
                        disabled={detailLoading}
                        onClick={() => void moreHistory()}
                      >
                        {copy.more}
                      </button>
                    )}
                  </>
                )}
              </section>
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}
