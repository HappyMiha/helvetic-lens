export const cantons =
  "AG AI AR BE BL BS FR GE GL GR JU LU NE NW OW SG SH SO SZ TG TI UR VD VS ZG ZH".split(
    " ",
  );
export const hazardKinds = [
  "flood",
  "storm",
  "forest_fire",
  "heavy_snow",
  "power_outage",
  "civil_protection_warning",
] as const;
export type HazardKind = (typeof hazardKinds)[number];
export type HazardCapabilities = {
  drafts_available: boolean;
  source?: {
    state: "current" | "unavailable";
    supported_hazards: HazardKind[];
    attribution?: string;
    last_poll_at?: string;
  };
};
export type Location = { country: "CH"; canton: string } & (
  | { kind: "point"; latitude: number; longitude: number; radius_km: number }
  | { kind: "municipality"; municipality_code: string }
);
export type HazardConfiguration = {
  template_id: "hazard-watch";
  template_version: 1;
  name: string;
  location: Location;
  hazards: HazardKind[];
  minimum_importance: "information" | "warning" | "alarm";
};
export type HazardMonitor = {
  id: string;
  configuration: HazardConfiguration;
  version: number;
  revision: number;
  status: string;
  health?: string;
  last_poll_at?: string | null;
  next_poll_at?: string | null;
};
export type Page<T> = { items: T[]; next_cursor: string | number | null };
export type Revision = { revision: number; configuration: HazardConfiguration };
export type HazardPreview = {
  configuration: HazardConfiguration;
  start_available: boolean;
  geography?: {
    state: "verified" | "no_match" | "unavailable";
    reason: string;
    version?: string;
    attribution?: string;
    municipality_code?: string | null;
    municipality_name?: string | null;
  };
};
