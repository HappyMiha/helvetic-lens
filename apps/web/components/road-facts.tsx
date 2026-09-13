"use client";
import { useI18n, type Locale } from "@/lib/i18n";
import { roadCopy, roadLabel } from "@/lib/road-copy";
import type { RoadPayload, Corridor } from "@/lib/road-watch";
function stamp(locale: Locale, value?: string | null) {
  if (!value || !Number.isFinite(Date.parse(value))) return "—";
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Zurich",
  }).format(new Date(value));
}
export function RoadFacts({
  payload,
  labels,
  availability,
  attribution,
  headingLevel = 4,
}: {
  payload: RoadPayload | null;
  labels: Corridor[];
  availability: string;
  attribution?: string | null;
  headingLevel?: 3 | 4;
}) {
  const { locale } = useI18n(),
    c = roadCopy[locale];
  if (!payload) return <p role="status">{c.unavailable}</p>;
  const Heading = headingLevel === 3 ? "h3" : "h4";
  return (
    <>
      {availability !== "available" && (
        <p role="status">{roadLabel(locale, availability)}</p>
      )}
      {Object.entries(payload.corridors).map(([id, corridor]) => (
        <div key={id}>
          <Heading>
            {labels.find((label) => label.id === id)?.name || c.corridors}
          </Heading>
          <p>
            {roadLabel(locale, corridor.state)} ·{" "}
            {roadLabel(locale, corridor.coverage)}
          </p>
          <ul>
            {corridor.facts.map((fact, index) => (
              <li key={index}>
                <strong>{roadLabel(locale, fact.kind)}</strong>
                {" · "}
                {roadLabel(locale, fact.probability)}
                {" · "}
                {roadLabel(locale, fact.phase)}
                {fact.delay_seconds != null && (
                  <p>
                    {new Intl.NumberFormat(locale, {
                      maximumFractionDigits: 1,
                    }).format(fact.delay_seconds / 60)}{" "}
                    {c.minutes}
                  </p>
                )}
                {fact.lanes_restricted != null && (
                  <p>
                    {c.lanesRestricted}: {fact.lanes_restricted}
                  </p>
                )}
                {fact.lanes_operational != null && (
                  <p>
                    {c.lanesOperational}: {fact.lanes_operational}
                  </p>
                )}
                <p>
                  {c.validFrom}: {stamp(locale, fact.valid_from)} ·{" "}
                  {c.validUntil}:{" "}
                  {fact.valid_until ? stamp(locale, fact.valid_until) : c.noEnd}
                </p>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {attribution && (
        <p>
          {c.source}: {attribution}
        </p>
      )}
    </>
  );
}
