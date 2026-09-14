"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import {
  trademarkDeadlineCopy,
  deadlineReason,
} from "@/lib/trademark-deadline-copy";
import type { TrademarkPortfolio } from "@/lib/trademark-watch";
import { useData } from "./trademark-client";

type Citation = { url: string; sha256: string; section: string };
export type DeadlineContext = {
  state: string;
  reason?: string | null;
  official_publication_date: string | null;
  calculated_review_deadline: string | null;
  days_remaining: number | null;
  as_of_date: string;
  timezone: string;
  exclusive_end: string | null;
  applicable_deadline_rule: { id: string; citations: Citation[] } | null;
  calendar: {
    id: string;
    name: string;
    jurisdiction: string;
    domicile_basis: "party" | "representative";
    citations: Citation[];
  } | null;
  calculation_trace: { step: string; date: string }[];
  publication_evidence: {
    identifier: string | null;
    source_sha256: string;
    source_document_sha256: string | null;
  } | null;
};

export function TrademarkDeadline({
  value,
  compact = false,
}: {
  value?: DeadlineContext | null;
  compact?: boolean;
}) {
  const { locale } = useI18n(),
    c = trademarkDeadlineCopy[locale];
  const available = value?.state === "available";
  const steps: Record<string, string> = {
    publication: c.publication,
    swissreg_registration_publication: c.national,
    wipo_ch_extension_publication: c.international,
    calendar_months: c.months,
    non_working_day: c.skipped,
    deadline: c.due,
  };
  return (
    <section
      data-trademark-deadline
      className="my-3 min-w-0 [overflow-wrap:anywhere]"
    >
      <p className="font-semibold">{c.title}</p>
      {available ? (
        <>
          <p>
            {c.due}:{" "}
            <time dateTime={value.calculated_review_deadline!}>
              {value.calculated_review_deadline}
            </time>
          </p>
          <p>
            {c.days}: <strong>{value.days_remaining}</strong> · {c.asOf}:{" "}
            {value.as_of_date} ({value.timezone})
          </p>
          <p>{c.dayHelp}</p>
        </>
      ) : (
        <p role="status">{deadlineReason(locale, value?.reason)}</p>
      )}
      <p>{c.warning}</p>
      {!compact && value && (
        <details>
          <summary>{c.trace}</summary>
          <p>
            {c.publication}: {value.official_publication_date || "—"}
          </p>
          {value.exclusive_end && (
            <p>
              {c.end}: {value.exclusive_end}
            </p>
          )}
          <ol>
            {value.calculation_trace.map((step, index) => (
              <li key={index}>
                {steps[step.step] || c.trace}: {step.date}
              </li>
            ))}
          </ol>
          {value.applicable_deadline_rule && (
            <p>
              {c.rule}: {value.applicable_deadline_rule.id}
            </p>
          )}
          {value.calendar && (
            <>
              <p>
                {c.calendar}: {value.calendar.name} (
                {value.calendar.jurisdiction}) ·{" "}
                {c[value.calendar.domicile_basis]}
              </p>
              <p>
                {c.version}: {value.calendar.id}
              </p>
            </>
          )}
          {value.publication_evidence && (
            <p>
              {value.publication_evidence.identifier} · {c.hash}:{" "}
              {value.publication_evidence.source_sha256} ·{" "}
              {value.publication_evidence.source_document_sha256}
            </p>
          )}
          <p>{c.citations}</p>
          <ul>
            {[
              ...(value.applicable_deadline_rule?.citations || []),
              ...(value.calendar?.citations || []),
            ].map((citation, i) => (
              <li key={i}>
                <a
                  className="underline"
                  href={citation.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {citation.section}
                </a>{" "}
                · {c.hash}: {citation.sha256}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

type Preference = NonNullable<TrademarkPortfolio["deadline_context"]>;
type Calendar = {
  key: string;
  name: string;
  jurisdiction: string;
  covers_from: string;
  covers_until: string;
};
export function TrademarkDeadlineChoice({
  value,
  change,
}: {
  value?: Preference;
  change: (value?: Preference) => void;
}) {
  const { locale } = useI18n(),
    c = trademarkDeadlineCopy[locale];
  const [key, setKey] = useState(value?.calendar_key || "");
  const [basis, setBasis] = useState<Preference["domicile_basis"] | "">(
    value?.domicile_basis || "",
  );
  const result = useData<{ items: Calendar[] }>("/deadline-calendars");
  const options = result.data?.items || [];
  return (
    <fieldset data-trademark-deadline-choice>
      <legend>{c.title}</legend>
      <p>{c.help}</p>
      {result.error ? (
        <p role="alert">{c.failed}</p>
      ) : result.data && !options.length ? (
        <p role="status">{c.empty}</p>
      ) : null}
      <label>
        {c.calendar}
        <select
          data-deadline-calendar
          value={key}
          onChange={(e) => {
            const next = e.target.value;
            setKey(next);
            if (!next) setBasis("");
            change(
              next && basis
                ? { calendar_key: next, domicile_basis: basis }
                : undefined,
            );
          }}
        >
          <option value="">{c.none}</option>
          {key && !options.some((o) => o.key === key) && (
            <option value={key}>
              {c.saved} · {key}
            </option>
          )}
          {options.map((o) => (
            <option key={o.key} value={o.key}>
              {o.name} · {o.jurisdiction} · {o.covers_from} – {o.covers_until}
            </option>
          ))}
        </select>
      </label>
      <label>
        {c.basis}
        <select
          data-deadline-domicile
          required={!!key}
          value={basis}
          disabled={!key}
          onChange={(e) => {
            const next = e.target.value as typeof basis;
            setBasis(next);
            change(
              key && next
                ? { calendar_key: key, domicile_basis: next }
                : undefined,
            );
          }}
        >
          <option value="">{c.choose}</option>
          <option value="party">{c.party}</option>
          <option value="representative">{c.representative}</option>
        </select>
      </label>
      <p>{c.warning}</p>
    </fieldset>
  );
}
