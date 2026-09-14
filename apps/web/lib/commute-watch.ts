export type CommuteConfiguration = {
  template_id: "commute-watch";
  template_version: 1;
  name: string;
  leg_reference_ids: string[];
  weekdays: number[];
  window_start: string;
  window_end: string;
  delay_threshold_minutes: number;
  delay_reset_minutes: number;
  cancellations: boolean;
  skipped_boarding_or_alighting: boolean;
  service_notices: boolean;
  outside_window: "ignore" | "digest";
};
export type ReferenceLabel = { id: string; label: string; enabled?: boolean };
export type CommuteMonitor = {
  id: string;
  configuration: CommuteConfiguration;
  reference_labels?: ReferenceLabel[];
  version: number;
  revision: number;
  status: "draft" | "active" | "paused" | "archived";
  health: string;
  paused_on: string | null;
  notification_pause_until?: string | null;
  last_check_at: string | null;
  next_check_at: string | null;
};
export type Page<T> = { items: T[]; next_cursor: string | number | null };
export type CatalogLeg = ReferenceLabel & {
  departure_wall_time: string;
  service_day: string;
};
export type Preview = {
  interchanges?: {
    from_reference_id: string;
    to_reference_id: string;
    state: string;
    scheduled_seconds?: number;
    min_transfer_time?: number | null;
  }[];
  service_day: string;
  start_available: boolean;
  blocking_reasons: string[];
  legs: {
    reference_id: string;
    boarding_name: string;
    alighting_name: string;
    route_name: string;
    departure: string;
    arrival: string;
  }[];
};
export type Condition = {
  condition: string;
  availability: string;
  reason: string;
  observed_at?: string;
  delay_seconds?: number | null;
};
export type Current = {
  states: Record<string, Condition>;
  editions: Record<
    string,
    {
      header: [string | null, string][];
      description: [string | null, string][];
    }
  >;
};
export type CommuteEvent = {
  reference_labels?: ReferenceLabel[];
  id: string;
  available: boolean;
  monitor_id?: string;
  source?: string;
  version?: number;
  sequence?: number;
  reviewed_sequence?: number;
  configuration_revision?: number;
  service_day?: string;
  muted?: boolean;
  current?: Current;
};
export type EventVersion = {
  id: string;
  sequence: number;
  evidence_hash: string;
  created_at: string;
  evidence: {
    observations?: Record<
      string,
      { delay_seconds?: number | null; observed_at: string }
    >;
    current: Current;
    feed_sha256: string;
    entity_sha256: string | null;
    feed_observed_at: string;
    recorded_at: string;
    source: string;
    service_day: string;
    configuration_revision: number;
    legs: Record<
      string,
      { route_name: string; boarding_name: string; alighting_name: string }
    >;
  };
};
export type Revision = {
  revision: number;
  configuration: CommuteConfiguration;
  reference_labels: ReferenceLabel[];
};
export type Capabilities = {
  drafts_available: boolean;
  start_available: boolean;
  blocking_reasons: string[];
};
export function newCommute(): CommuteConfiguration {
  return {
    template_id: "commute-watch",
    template_version: 1,
    name: "",
    leg_reference_ids: [],
    weekdays: [0, 1, 2, 3, 4],
    window_start: "07:00",
    window_end: "09:00",
    delay_threshold_minutes: 5,
    delay_reset_minutes: 2,
    cancellations: true,
    skipped_boarding_or_alighting: true,
    service_notices: true,
    outside_window: "ignore",
  };
}
export function zurichDate(now = new Date()) {
  const values = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Zurich",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  return ["year", "month", "day"]
    .map((key) => values.find((part) => part.type === key)?.value)
    .join("-");
}
export function sourceEdition(
  editions: [string | null, string][],
  locale: string,
) {
  const language = locale.split("-")[0];
  return (
    editions.find(([lang]) => lang?.split("-")[0] === language) ||
    editions.find(([lang]) => lang === "en") ||
    editions[0]
  );
}
export const commuteSources: Record<string, string> = {
  swiss_gtfs_trip_updates: "opentransportdata.swiss · GTFS-RT",
  swiss_gtfs_service_alerts: "opentransportdata.swiss · GTFS-SA",
};
export const commuteProvider = "opentransportdata.swiss";
export const commuteTimezone = "Europe/Zurich";

export type CommuteTodayItem = {
  id: string;
  monitor_id: string;
  event_id: string;
  name: string;
  sequence: number;
  event_version: number;
  signal_sequence: number;
  configuration_revision: number;
  service_day: string;
  source: string;
  detected_at: string;
  states: Record<string, Condition>;
  reference_labels: ReferenceLabel[];
  priority: "urgent" | "normal";
  reasons: string[];
  href: string;
};
export type LinkedCommuteEvent = {
  event: CommuteEvent;
  snapshot: EventVersion;
  newer_available: boolean;
  current_configuration: boolean;
};

export function commuteStateLabel(
  copy: Record<string, string>,
  key?: string | null,
) {
  const aliases: Record<string, string> = {
    delay_material: "delayed",
    delay_minor: "normal",
    partial_disruption: "interrupted",
  };
  return copy[aliases[key || ""] || key || "unknown"] || copy.unknown;
}
export function savedConditions(snapshot: EventVersion): Current {
  return {
    ...snapshot.evidence.current,
    states: Object.fromEntries(
      Object.entries(snapshot.evidence.current.states).map(([id, state]) => {
        const observation = snapshot.evidence.observations?.[id];
        return [
          id,
          {
            ...state,
            ...(observation
              ? {
                  observed_at: observation.observed_at,
                  delay_seconds: observation.delay_seconds,
                }
              : {}),
          },
        ];
      }),
    ),
  };
}
export function savedLabels(snapshot: EventVersion): ReferenceLabel[] {
  return Object.entries(snapshot.evidence.legs).map(([id, leg]) => ({
    id,
    label: `${leg.route_name}: ${leg.boarding_name} → ${leg.alighting_name}`,
  }));
}
