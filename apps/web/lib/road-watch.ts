export const roadKinds = [
  "road_closure",
  "carriageway_closure",
  "lane_restriction",
  "congestion",
  "accident",
  "roadworks",
] as const;
export type RoadKind = (typeof roadKinds)[number];
export type RoadConfiguration = {
  template_id: "road-watch";
  template_version: 1;
  name: string;
  corridor_reference_ids: string[];
  materiality: {
    event_kinds: RoadKind[];
    minimum_delay_seconds: number;
    include_planned: boolean;
  };
};
export type RoadMonitor = {
  id: string;
  configuration: RoadConfiguration;
  revision: number;
  version: number;
  status: "draft" | "active" | "paused" | "archived";
  health: string;
  last_check_at?: string | null;
};
export type Corridor = {
  id: string;
  name?: string;
  flow?: string;
  attribution?: string;
  state?: string;
};
export type RoadPreview = {
  corridors: Corridor[];
  start_available: boolean;
  blocking_reasons: string[];
};
export type RoadPayload = {
  state: string;
  corridors: Record<
    string,
    {
      state: string;
      coverage: string;
      facts: {
        kind: string;
        phase: string;
        probability: string;
        valid_from: string | null;
        valid_until: string | null;
        delay_seconds?: number | null;
        lanes_restricted?: number | null;
        lanes_operational?: number | null;
      }[];
    }
  >;
};
export type RoadEvent = {
  id: string;
  monitor_id: string;
  version: number;
  sequence: number;
  reviewed_sequence: number;
  muted: boolean;
  payload: RoadPayload | null;
  availability: string;
  attribution: string | null;
  updated_at: string;
};
export type RoadEventVersion = {
  sequence: number;
  payload: RoadPayload | null;
  availability: string;
  attribution: string | null;
  created_at: string;
};
export type RoadRevision = {
  revision: number;
  configuration: RoadConfiguration;
};
export type RoadDetail = {
  event: RoadEvent;
  snapshot: RoadEventVersion;
  previous: RoadEventVersion | null;
  corridors: Corridor[];
  current_configuration: boolean;
  newer_available: boolean;
};
export type RoadTodayItem = {
  id: string;
  monitor_id: string;
  name: string;
  event_id: string;
  sequence: number;
  detected_at: string;
  event: RoadEvent;
  corridors: Corridor[];
  priority: "urgent" | "normal";
  reason: "unread_road_change";
  href: string;
};
export function roadLink(params: Pick<URLSearchParams, "get">) {
  const monitor = params.get("monitor") || "",
    event = params.get("event") || "",
    raw = params.get("sequence");
  const uuid =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const sequence = raw == null ? undefined : Number(raw);
  const invalid = !!(
    (monitor && !uuid.test(monitor)) ||
    (event && (!uuid.test(event) || !monitor)) ||
    (raw !== null &&
      (!event || !/^[1-9][0-9]*$/.test(raw) || !Number.isSafeInteger(sequence)))
  );
  return {
    monitor: invalid ? "" : monitor,
    event: invalid ? "" : event,
    sequence: invalid ? undefined : sequence,
    invalid,
  };
}
export type RoadPage<T> = { items: T[]; next_cursor: string | number | null };
export function newRoad(): RoadConfiguration {
  return {
    template_id: "road-watch",
    template_version: 1,
    name: "",
    corridor_reference_ids: [],
    materiality: {
      event_kinds: [...roadKinds],
      minimum_delay_seconds: 900,
      include_planned: true,
    },
  };
}
