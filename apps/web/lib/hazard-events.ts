import type { HazardKind } from "./hazard-watch";

export type HazardTarget = {
  event: string;
  revision: number | null;
  invalid: boolean;
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function hazardTarget(
  params: Pick<URLSearchParams, "getAll">,
): HazardTarget {
  const events = params.getAll("event"),
    revisions = params.getAll("revision"),
    monitors = params.getAll("monitor");
  if (!events.length && !revisions.length)
    return { event: "", revision: null, invalid: false };
  const valid =
    events.length === 1 &&
    uuid.test(events[0]) &&
    monitors.length === 1 &&
    uuid.test(monitors[0]) &&
    revisions.length <= 1 &&
    (!revisions.length ||
      (/^[1-9][0-9]*$/.test(revisions[0]) &&
        Number.isSafeInteger(Number(revisions[0]))));
  return valid
    ? {
        event: events[0],
        revision: revisions.length ? Number(revisions[0]) : null,
        invalid: false,
      }
    : { event: "", revision: null, invalid: true };
}
export function hazardHref(
  monitor: string,
  event?: string,
  revision?: number | null,
) {
  const params = new URLSearchParams({ monitor });
  if (event) params.set("event", event);
  if (event && revision != null) params.set("revision", String(revision));
  return `/hazard-watch?${params}`;
}
export function officialLink(value?: string | null, allowHttp = false) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return (url.protocol === "https:" ||
      (allowHttp && url.protocol === "http:")) &&
      !url.username &&
      !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}
export type WarningInfo = {
  language: string;
  event: string;
  headline?: string | null;
  description?: string | null;
  instruction?: string | null;
  web?: string | null;
  effective?: string | null;
  expires?: string | null;
  parameters?: [string, string][];
};
export type HazardEvent = {
  id: string;
  monitor_id: string;
  version: number;
  revision: number;
  historical: boolean;
  state:
    | "active"
    | "planned"
    | "resolved"
    | "cancelled"
    | "not_relevant"
    | "unavailable";
  reason?: string;
  material_sequence?: number;
  reviewed?: boolean;
  dismissed?: boolean;
  needs_review?: boolean;
  muted?: boolean;
  decision?: {
    hazards?: HazardKind[];
    importance?: "information" | "warning" | "alarm";
    certainty?: "Observed" | "Likely" | "Possible" | "Unlikely" | "Unknown";
    match?: { basis?: string };
  };
  source?: {
    attribution: string;
    last_seen_at: string;
    history_complete?: boolean;
    redistribution?: {
      url: string;
      terms_url: string;
      disclaimer: string;
    } | null;
    message: {
      identity: { sent: string };
      infos: WarningInfo[];
      profile?: string;
    };
  };
};
export type HazardMutes = {
  monitor_id: string;
  version: number;
  muted_hazards: HazardKind[];
};
export type HazardReview = {
  id: string;
  revision: number;
  material_sequence: number;
  action: "reviewed" | "not_relevant";
  created_at: string;
};
