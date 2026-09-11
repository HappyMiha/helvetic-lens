import type { PollenDraft, PollenRule } from "./pollen-drafts";

export type PollenSample = {
  series: {
    station_id: string;
    allergen: string;
    period: string;
    unit: string;
    source_id: string;
    method_version: string;
    forecast: { issue_at: string; model: string } | null;
  };
  valid_at: string;
  fetched_at: string;
  fresh_until: string;
  value: string | null;
  quality: string;
  source_revision: number;
  artifact_hashes: string[];
  policy_version: string;
};
export type PollenRuntime = {
  version: number;
  run_id: string | null;
  health: string;
  email_consent: boolean;
  muted: boolean;
  configuration_revision?: number;
};
export type PollenState = PollenDraft & {
  delivery_counts?: Record<string, number>;
  runtime: PollenRuntime;
  start_available: boolean;
  blocking_reasons: string[];
  coverage: { allergen: string; period: string; status: string }[];
  current: {
    stream_id: string;
    entry_id: string;
    sample: PollenSample;
    availability: string;
    category: { category: string | null; scale_version: string } | null;
  }[];
};
export type PollenActivity = {
  id: string;
  sequence: number;
  kind: string;
  material_id: string | null;
  created_at: string;
  current: PollenSample;
  previous: PollenSample | null;
  baseline: PollenSample | null;
  reasons: string[];
  binding: { rule: PollenRule | null };
  configuration_revision: number;
  raw_export_available?: boolean;
  review: {
    version: number;
    decision: "reviewed" | "not_relevant" | "continue" | "action_required";
  } | null;
};
export type ActivityPage = {
  items: PollenActivity[];
  next_cursor: string | null;
};
export type RuntimeAction =
  | "start"
  | "pause"
  | "resume"
  | "archive"
  | "mute"
  | "unmute"
  | "unsubscribe"
  | "consent_email";
export type RuntimeCommand = {
  action: RuntimeAction;
  expected_revision: number;
  expected_version: number;
  request_key: string;
  email_consent: boolean;
};
