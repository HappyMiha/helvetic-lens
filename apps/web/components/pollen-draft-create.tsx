"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { pollenCreateCopy } from "@/lib/pollen-create-copy";
import { pollenDraftCopy } from "@/lib/pollen-draft-copy";
import {
  draftFailure,
  type PollenConfiguration,
  type PollenDraft,
  type PollenRule,
} from "@/lib/pollen-drafts";
import styles from "./pollen-draft-reader.module.css";

type Preview = {
  configuration: PollenConfiguration;
  configuration_hash: string;
  preview_kind: string;
  start_available: boolean;
};
const initial = (): PollenConfiguration => ({
  station_id: "",
  selections: [],
  timezone: "Europe/Zurich",
  delivery: { email: "off", digest_at: null, quiet_hours: null },
});
const newRule = (period: string): PollenRule => ({
  period,
  unit: "number/m3",
  category_change: false,
  threshold: { trigger_at_or_above: "", reset_at_or_below: "" },
  rapid_increase: null,
});

export function PollenDraftCreate({
  onClose,
  onSaved,
  onDenied,
}: {
  onClose: () => void;
  onSaved: (id: string) => void;
  onDenied: (error: unknown) => void;
}) {
  const { locale } = useI18n(),
    copy = pollenCreateCopy[locale],
    labels = pollenDraftCopy[locale];
  const [configuration, setConfiguration] = useState(initial);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [attempt, setAttempt] = useState<{
    request_key: string;
    configuration: PollenConfiguration;
  } | null>(null);
  const [saved, setSaved] = useState<PollenDraft | null>(null);
  const [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const inFlight = useRef(false),
    request = useRef<AbortController | null>(null);
  const heading = useRef<HTMLHeadingElement | null>(null);
  const frozen = busy || !!attempt;

  useEffect(() => {
    heading.current?.focus();
    return () => request.current?.abort();
  }, []);
  useEffect(() => {
    if (!dirty || saved) return;
    const unload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const navigation = (event: Event) => {
      if (!window.confirm(copy.discard)) event.preventDefault();
    };
    const link = (event: MouseEvent) => {
      if (!(event.target instanceof Element)) return;
      const anchor = event.target.closest("a[href]");
      if (
        anchor &&
        !anchor.getAttribute("href")?.startsWith("#") &&
        !window.confirm(copy.discard)
      ) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", unload);
    window.addEventListener("helvetic:before-navigation", navigation);
    document.addEventListener("click", link, true);
    return () => {
      window.removeEventListener("beforeunload", unload);
      window.removeEventListener("helvetic:before-navigation", navigation);
      document.removeEventListener("click", link, true);
    };
  }, [dirty, saved, copy.discard]);

  function change(next: PollenConfiguration) {
    if (frozen || saved) return;
    setConfiguration(next);
    setDirty(true);
    setPreview(null);
    setMessage("");
  }
  function rules(allergen: string, next: PollenRule[]) {
    change({
      ...configuration,
      selections: configuration.selections.map((s) =>
        s.allergen === allergen ? { ...s, rules: next } : s,
      ),
    });
  }
  function ruleChange(allergen: string, rule: PollenRule) {
    rules(
      allergen,
      configuration.selections
        .find((s) => s.allergen === allergen)!
        .rules.map((r) => (r.period === rule.period ? rule : r)),
    );
  }
  function denied(error: unknown) {
    if (
      error instanceof ApiError &&
      ["disabled", "access"].includes(draftFailure(error.code))
    ) {
      onDenied(error);
      return true;
    }
    return false;
  }
  async function check(event: FormEvent) {
    event.preventDefault();
    if (inFlight.current || attempt) return;
    if (!configuration.selections.length) {
      setMessage(copy.select);
      return;
    }
    inFlight.current = true;
    setBusy(true);
    setPreview(null);
    setMessage("");
    const controller = new AbortController();
    request.current = controller;
    try {
      const result = await api<Preview>("/monitoring-subjects/preview", {
        method: "POST",
        body: JSON.stringify({ configuration }),
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (
        result.preview_kind !== "configuration_only" ||
        result.start_available !== false
      ) {
        setMessage(copy.failed);
        return;
      }
      setPreview(result);
    } catch (error) {
      if (!controller.signal.aborted && !denied(error))
        setMessage(
          error instanceof ApiError &&
            ["subject_configuration_invalid", "invalid_input"].includes(
              error.code,
            )
            ? copy.invalid
            : copy.failed,
        );
    } finally {
      if (!controller.signal.aborted) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  }
  async function save() {
    if (inFlight.current || saved || (!preview && !attempt)) return;
    inFlight.current = true;
    setBusy(true);
    setMessage("");
    const payload = attempt || {
      request_key: crypto.randomUUID(),
      configuration: preview!.configuration,
    };
    setAttempt(payload); // Keep the original key and exact payload even if the response is lost.
    const controller = new AbortController();
    request.current = controller;
    try {
      const result = await api<PollenDraft>("/monitoring-subjects", {
        method: "POST",
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (!controller.signal.aborted) {
        setSaved(result);
        setDirty(false);
      }
    } catch (error) {
      if (!controller.signal.aborted && !denied(error)) {
        if (
          error instanceof ApiError &&
          ["subject_configuration_invalid", "invalid_input"].includes(
            error.code,
          )
        ) {
          setAttempt(null);
          setPreview(null);
          setMessage(copy.invalid);
        } else setMessage(copy.uncertain);
      }
    } finally {
      if (!controller.signal.aborted) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  }

  return (
    <section className={styles.creator} data-pollen-create>
      <h2 ref={heading} tabIndex={-1}>
        {copy.create}
      </h2>
      <p>{copy.intro}</p>
      {saved ? (
        <>
          <p role="status">{copy.saved}</p>
          <button
            className={styles.button}
            type="button"
            onClick={() => onSaved(saved.id)}
          >
            {copy.view}
          </button>
        </>
      ) : (
        <>
          <form onSubmit={(event) => void check(event)}>
            <fieldset disabled={frozen} className={styles.formFields}>
              <label>
                {labels.station}
                <input
                  name="pollen-station"
                  required
                  pattern="[A-Z]{3}"
                  maxLength={3}
                  autoComplete="off"
                  value={configuration.station_id}
                  onChange={(event) =>
                    change({
                      ...configuration,
                      station_id: event.target.value.toUpperCase(),
                    })
                  }
                />
              </label>
              <label>
                {labels.timezone}
                <input
                  name="pollen-timezone"
                  required
                  maxLength={64}
                  autoComplete="off"
                  value={configuration.timezone}
                  onChange={(event) =>
                    change({ ...configuration, timezone: event.target.value })
                  }
                />
              </label>
              <fieldset>
                <legend>{copy.allergens}</legend>
                {Object.entries(labels.allergens).map(([allergen, name]) => (
                  <label className={styles.check} key={allergen}>
                    <input
                      type="checkbox"
                      name={`allergen-${allergen}`}
                      checked={configuration.selections.some(
                        (s) => s.allergen === allergen,
                      )}
                      onChange={(event) =>
                        change({
                          ...configuration,
                          selections: event.target.checked
                            ? [
                                ...configuration.selections,
                                { allergen, rules: [] },
                              ]
                            : configuration.selections.filter(
                                (s) => s.allergen !== allergen,
                              ),
                        })
                      }
                    />
                    {name}
                  </label>
                ))}
              </fieldset>
              {configuration.selections.map((selection) => (
                <fieldset key={selection.allergen}>
                  <legend>{labels.allergens[selection.allergen]}</legend>
                  {Object.entries(labels.periods).map(([period, name]) => {
                    const rule = selection.rules.find(
                      (r) => r.period === period,
                    );
                    const prefix = `${selection.allergen}-${period}`;
                    return (
                      <fieldset key={period}>
                        <legend>
                          <label className={styles.check}>
                            <input
                              type="checkbox"
                              name={`rule-${prefix}`}
                              checked={!!rule}
                              onChange={(event) =>
                                rules(
                                  selection.allergen,
                                  event.target.checked
                                    ? [...selection.rules, newRule(period)]
                                    : selection.rules.filter(
                                        (r) => r.period !== period,
                                      ),
                                )
                              }
                            />
                            {copy.numeric}: {name}
                          </label>
                        </legend>
                        {rule && (
                          <>
                            <label className={styles.check}>
                              <input
                                type="checkbox"
                                name={`threshold-${prefix}`}
                                checked={!!rule.threshold}
                                onChange={(event) =>
                                  ruleChange(selection.allergen, {
                                    ...rule,
                                    threshold: event.target.checked
                                      ? {
                                          trigger_at_or_above: "",
                                          reset_at_or_below: "",
                                        }
                                      : null,
                                  })
                                }
                              />
                              {copy.threshold}
                            </label>
                            {rule.threshold && (
                              <div className={styles.numericFields}>
                                <label>
                                  {labels.threshold}
                                  <input
                                    name={`trigger-${prefix}`}
                                    required
                                    inputMode="decimal"
                                    pattern="[0-9]{1,6}(\.[0-9]{1,6})?"
                                    maxLength={13}
                                    value={rule.threshold.trigger_at_or_above}
                                    onChange={(event) =>
                                      ruleChange(selection.allergen, {
                                        ...rule,
                                        threshold: {
                                          ...rule.threshold!,
                                          trigger_at_or_above:
                                            event.target.value,
                                        },
                                      })
                                    }
                                  />
                                </label>
                                <label>
                                  {labels.reset}
                                  <input
                                    name={`reset-${prefix}`}
                                    required
                                    inputMode="decimal"
                                    pattern="[0-9]{1,6}(\.[0-9]{1,6})?"
                                    maxLength={13}
                                    value={rule.threshold.reset_at_or_below}
                                    onChange={(event) =>
                                      ruleChange(selection.allergen, {
                                        ...rule,
                                        threshold: {
                                          ...rule.threshold!,
                                          reset_at_or_below: event.target.value,
                                        },
                                      })
                                    }
                                  />
                                </label>
                              </div>
                            )}
                            {[
                              "observation_hourly",
                              "forecast_instant",
                            ].includes(period) && (
                              <label className={styles.check}>
                                <input
                                  type="checkbox"
                                  name={`rapid-${prefix}`}
                                  checked={!!rule.rapid_increase}
                                  onChange={(event) =>
                                    ruleChange(selection.allergen, {
                                      ...rule,
                                      rapid_increase: event.target.checked
                                        ? {
                                            minimum_increase: "",
                                            window_hours: 2,
                                          }
                                        : null,
                                    })
                                  }
                                />
                                {copy.rapid}
                              </label>
                            )}
                            {rule.rapid_increase && (
                              <div className={styles.numericFields}>
                                <label>
                                  {labels.rapid}
                                  <input
                                    name={`increase-${prefix}`}
                                    required
                                    inputMode="decimal"
                                    pattern="[0-9]{1,6}(\.[0-9]{1,6})?"
                                    maxLength={13}
                                    value={rule.rapid_increase.minimum_increase}
                                    onChange={(event) =>
                                      ruleChange(selection.allergen, {
                                        ...rule,
                                        rapid_increase: {
                                          ...rule.rapid_increase!,
                                          minimum_increase: event.target.value,
                                        },
                                      })
                                    }
                                  />
                                </label>
                                <label>
                                  {labels.hours}
                                  <input
                                    name={`window-${prefix}`}
                                    type="number"
                                    min={1}
                                    max={24}
                                    step={1}
                                    required
                                    value={
                                      Number.isNaN(
                                        rule.rapid_increase.window_hours,
                                      )
                                        ? ""
                                        : rule.rapid_increase.window_hours
                                    }
                                    onChange={(event) =>
                                      ruleChange(selection.allergen, {
                                        ...rule,
                                        rapid_increase: {
                                          ...rule.rapid_increase!,
                                          window_hours:
                                            event.target.valueAsNumber,
                                        },
                                      })
                                    }
                                  />
                                </label>
                              </div>
                            )}
                          </>
                        )}
                      </fieldset>
                    );
                  })}
                </fieldset>
              ))}
            </fieldset>
            {!attempt && (
              <button type="submit" className={styles.button} disabled={busy}>
                {copy.preview}
              </button>
            )}
          </form>
          {preview && <p role="status">{copy.checked}</p>}
          {(preview || attempt) && (
            <button
              className={styles.button}
              type="button"
              onClick={() => void save()}
              disabled={busy}
            >
              {copy.save}
            </button>
          )}
          {busy && <p role="status">{copy.busy}</p>}
          {message && (
            <p className={styles.notice} role="alert">
              {message}
            </p>
          )}
          <button
            className={styles.button}
            type="button"
            disabled={busy}
            onClick={() => {
              if (!dirty || window.confirm(copy.discard)) onClose();
            }}
          >
            {copy.cancel}
          </button>
        </>
      )}
    </section>
  );
}
