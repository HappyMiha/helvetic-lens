export type RiverMetric = "W" | "Q" | "WT";
export const RIVER_RISE_UNIT = "cm";
export type RiverRule = {
  metric: RiverMetric;
  kind: "absolute" | "rise";
  threshold: string;
  unit: "m" | "cm" | "m3/s" | "°C";
  window_minutes: number | null;
};
export type RiverConfiguration = {
  template_id?: "river-lake-watch";
  template_version?: 1;
  name: string;
  station_id: string;
  metrics: RiverMetric[];
  official_danger: boolean;
  rules: RiverRule[];
};
export type RiverSample = {
  metric: string;
  value: string;
  unit: string;
  timestamp: string;
  quality: string;
  datum: string | null;
  aggregation: string;
  source: string;
  source_url: string;
};
export type RiverCoverage = Record<
  string,
  { status: string; sample: RiverSample | null }
>;
export type RiverMonitor = {
  id: string;
  configuration: RiverConfiguration;
  revision: number;
  version: number;
  status: "draft" | "active" | "paused" | "archived";
  health: string;
  state: { coverage?: RiverCoverage; last_gap?: { from: string; to: string } };
  last_poll_at: string | null;
};
export type RiverChange = {
  id: string;
  development_id: string;
  sequence: number;
  revision: number;
  kind: string;
  priority: number;
  review_version: number;
  decision: string | null;
  evidence: {
    sample: RiverSample;
    baseline: RiverSample | null;
    rule: RiverRule | null;
    evaluated_value: string;
    recovered: boolean;
  };
};
export type RiverStation = {
  id: string;
  name: string;
  waterbody: string;
  source_url: string;
};
export type RiverPreview = {
  station: RiverStation;
  coverage: RiverCoverage;
  start_available: boolean;
};

export const riverUnit = (metric: RiverMetric) =>
  ({ W: "m", Q: "m3/s", WT: "°C" })[metric] as RiverRule["unit"];
export function configurationError(config: RiverConfiguration): boolean {
  return (
    !config.name.trim() ||
    !/^2\d{3}$/.test(config.station_id) ||
    !config.metrics.length ||
    config.rules.some(
      (rule) =>
        !rule.threshold.trim() ||
        !Number.isFinite(Number(rule.threshold)) ||
        (rule.kind === "rise" &&
          (Number(rule.threshold) <= 0 ||
            !rule.window_minutes ||
            rule.window_minutes % 10 !== 0)),
    )
  );
}
