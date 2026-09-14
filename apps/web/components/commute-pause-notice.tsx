"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import {
  commutePauseCopy,
  commutePauseTimezone,
} from "@/lib/commute-pause-copy";

export function CommutePauseNotice({ until }: { until?: string | null }) {
  return until && Number.isFinite(Date.parse(until)) ? (
    <Pause key={until} until={until} />
  ) : null;
}

function Pause({ until }: { until: string }) {
  const { locale } = useI18n();
  const c = commutePauseCopy[locale];
  const [ended, setEnded] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(
      () => setEnded(true),
      Math.max(0, Date.parse(until) - Date.now()),
    );
    return () => window.clearTimeout(timer);
  }, [until]);
  return (
    <div data-commute-pause>
      {ended ? (
        <p>{c.ended}</p>
      ) : (
        <>
          <p>
            <strong>{c.title}</strong>
          </p>
          <p>
            {c.until}:{" "}
            <time dateTime={until}>
              {new Intl.DateTimeFormat(locale === "rm-CH" ? "de-CH" : locale, {
                dateStyle: "medium",
                timeStyle: "short",
                timeZone: commutePauseTimezone,
              }).format(new Date(until))}
            </time>{" "}
            · {commutePauseTimezone}
          </p>
          <p>{c.help}</p>
        </>
      )}
    </div>
  );
}
