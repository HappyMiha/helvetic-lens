export const AIR_UNIT = "µg/m³";
export const AIR_STATION_NAME = "Basel-Binningen";
export type AirMetric = "O3" | "NO2" | "PM10" | "PM25";
export type AirPeriod = "hourly_mean" | "rolling_24h_mean";
export type AirRule = {
  metric: AirMetric;
  period: AirPeriod;
  threshold: string;
  hysteresis: string;
  cooldown_hours: number;
};
export type AirConfiguration = {
  name: string;
  station_id: string;
  metrics: AirMetric[];
  muted_metrics: AirMetric[];
  rules: AirRule[];
};
export type AirSample = {
  metric: AirMetric;
  timestamp: string;
  value: string | null;
  unit: string;
  period: AirPeriod;
  quality: string;
  source_url: string;
  license_url: string;
  corrected?: boolean;
  derived?: boolean;
  revision: number;
};
export type AirCoverage = Record<
  string,
  { status: string; sample: AirSample | null }
>;
export type AirMonitor = {
  id: string;
  configuration: AirConfiguration;
  revision: number;
  version: number;
  status: "draft" | "active" | "paused" | "archived";
  health: string;
  state: { coverage?: AirCoverage; last_gap?: unknown };
};
export type AirChange = {
  id: string;
  development_id: string;
  sequence: number;
  revision: number;
  kind: string;
  decision: string | null;
  review_version: number;
  evidence: {
    sample: AirSample;
    baseline: AirSample | null;
    rule: AirRule;
    corrected: boolean;
    recovered: boolean;
  };
};
export type AirPreview = { coverage: AirCoverage; start_available: boolean };
export type AirStation = { id: string; name: string; area: string };
export type AirTodayEntry = AirChange & {
  monitor_id: string;
  monitor_name: string;
  monitor_status: string;
  health: string;
  muted: boolean;
};
export const AIR_METRICS: AirMetric[] = ["O3", "NO2", "PM10", "PM25"];
export function invalidAir(c: AirConfiguration) {
  return (
    !c.name.trim() ||
    c.station_id !== "BAS" ||
    !c.metrics.length ||
    c.rules.some(
      (r) =>
        !r.threshold.trim() ||
        !Number.isFinite(Number(r.threshold)) ||
        Number(r.threshold) <= 0 ||
        Number(r.threshold) > 10000 ||
        !r.hysteresis.trim() ||
        !Number.isFinite(Number(r.hysteresis)) ||
        Number(r.hysteresis) < 0 ||
        Number(r.hysteresis) >= Number(r.threshold) ||
        !Number.isInteger(r.cooldown_hours) ||
        r.cooldown_hours < 1 ||
        r.cooldown_hours > 48,
    ) ||
    new Set(c.rules.map((r) => `${r.metric}:${r.period}`)).size !==
      c.rules.length
  );
}
