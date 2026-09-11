import type { PollenConfiguration } from "./pollen-drafts";

// Fail closed for settings that the current numeric form cannot safely represent.
export function editablePollenConfiguration(value: unknown): boolean {
  const object = (v: unknown): v is Record<string, unknown> =>
    !!v && typeof v === "object" && !Array.isArray(v);
  const keys = (v: Record<string, unknown>, allowed: string[]) =>
    Object.keys(v).every((k) => allowed.includes(k));
  const decimal = (v: unknown) =>
    typeof v === "string" || (typeof v === "number" && Number.isFinite(v));
  if (
    !object(value) ||
    !keys(value, [
      "contract_version",
      "template_id",
      "template_version",
      "station_id",
      "selections",
      "timezone",
      "delivery",
    ])
  )
    return false;
  if (
    (value.contract_version !== undefined && value.contract_version !== 1) ||
    (value.template_version !== undefined && value.template_version !== 1) ||
    (value.template_id !== undefined && value.template_id !== "pollen-watch")
  )
    return false;
  if (
    typeof value.station_id !== "string" ||
    typeof value.timezone !== "string" ||
    !Array.isArray(value.selections)
  )
    return false;
  const allergens = [
    "alder",
    "birch",
    "hazel",
    "beech",
    "ash",
    "oak",
    "grasses",
    "ragweed",
  ];
  const periods = [
    "observation_hourly",
    "observation_daily_00_24_utc",
    "observation_daily_06_06_utc",
    "forecast_instant",
  ];
  if (
    !value.selections.every(
      (s) =>
        object(s) &&
        keys(s, ["allergen", "rules"]) &&
        allergens.includes(String(s.allergen)) &&
        Array.isArray(s.rules) &&
        s.rules.every((r) => {
          if (
            !object(r) ||
            !keys(r, [
              "period",
              "unit",
              "threshold",
              "rapid_increase",
              "category_change",
            ]) ||
            !periods.includes(String(r.period)) ||
            r.unit !== "number/m3" ||
            typeof r.category_change !== "boolean"
          )
            return false;
          if (
            r.threshold !== null &&
            (!object(r.threshold) ||
              !keys(r.threshold, [
                "trigger_at_or_above",
                "reset_at_or_below",
              ]) ||
              !decimal(r.threshold.trigger_at_or_above) ||
              !decimal(r.threshold.reset_at_or_below))
          )
            return false;
          if (
            r.rapid_increase !== null &&
            (!object(r.rapid_increase) ||
              !keys(r.rapid_increase, ["minimum_increase", "window_hours"]) ||
              !decimal(r.rapid_increase.minimum_increase) ||
              !Number.isInteger(r.rapid_increase.window_hours))
          )
            return false;
          return true;
        }),
    )
  )
    return false;
  const delivery = value.delivery;
  return (
    object(delivery) &&
    keys(delivery, ["email", "digest_at", "quiet_hours"]) &&
    ["off", "immediate", "daily_digest"].includes(String(delivery.email)) &&
    (delivery.digest_at === null || typeof delivery.digest_at === "string") &&
    (delivery.quiet_hours === null ||
      (object(delivery.quiet_hours) &&
        keys(delivery.quiet_hours, ["start", "end"]) &&
        typeof delivery.quiet_hours.start === "string" &&
        typeof delivery.quiet_hours.end === "string"))
  );
}

export const POLLEN_BACKUP_MAX_BYTES = 65_536;
export class PollenBackupError extends Error {
  readonly code: "invalid_backup" | "unsupported_backup";
  constructor(code: "invalid_backup" | "unsupported_backup") {
    super(code);
    this.code = code;
  }
}
const backupFormat = "helvetic-lens.pollen-draft";

// A portable file is an untrusted configuration proposal, never an identity,
// revision, permission, source admission or instruction to send notifications.
function portableConfiguration(value: unknown): value is PollenConfiguration {
  if (!editablePollenConfiguration(value)) return false;
  const config = value as PollenConfiguration;
  const decimal = (v: unknown) =>
    typeof v === "string" && /^\d{1,6}(?:\.\d{1,6})?$/.test(v);
  const clock = (v: unknown) =>
    typeof v === "string" && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(v);
  return (
    /^[A-Z]{3}$/.test(config.station_id) &&
    config.timezone.length > 0 &&
    config.timezone.length <= 64 &&
    config.selections.length > 0 &&
    config.selections.length <= 8 &&
    new Set(config.selections.map((s) => s.allergen)).size ===
      config.selections.length &&
    config.selections.every(
      (s) =>
        s.rules.length <= 4 &&
        new Set(s.rules.map((r) => r.period)).size === s.rules.length &&
        s.rules.every(
          (r) =>
            (!r.threshold ||
              (decimal(r.threshold.trigger_at_or_above) &&
                decimal(r.threshold.reset_at_or_below))) &&
            (!r.rapid_increase ||
              (decimal(r.rapid_increase.minimum_increase) &&
                r.rapid_increase.window_hours >= 1 &&
                r.rapid_increase.window_hours <= 24)),
        ),
    ) &&
    (config.delivery.digest_at === null || clock(config.delivery.digest_at)) &&
    (config.delivery.quiet_hours === null ||
      (clock(config.delivery.quiet_hours.start) &&
        clock(config.delivery.quiet_hours.end)))
  );
}

export function encodePollenBackup(configuration: unknown): string {
  if (!portableConfiguration(configuration))
    throw new PollenBackupError("unsupported_backup");
  const text =
    JSON.stringify(
      { format: backupFormat, version: 1, configuration },
      null,
      2,
    ) + "\n";
  if (new TextEncoder().encode(text).byteLength > POLLEN_BACKUP_MAX_BYTES)
    throw new PollenBackupError("invalid_backup");
  return text;
}

export function decodePollenBackup(text: string): PollenConfiguration {
  if (new TextEncoder().encode(text).byteLength > POLLEN_BACKUP_MAX_BYTES)
    throw new PollenBackupError("invalid_backup");
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new PollenBackupError("invalid_backup");
  }
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new PollenBackupError("invalid_backup");
  const file = value as Record<string, unknown>;
  if (
    file.format !== backupFormat ||
    file.version !== 1 ||
    Object.keys(file).length !== 3 ||
    !Object.hasOwn(file, "configuration") ||
    !portableConfiguration(file.configuration)
  )
    throw new PollenBackupError("unsupported_backup");
  // Preview on the server still validates semantics (timezone, rule boundaries,
  // period compatibility and schedules). Reading this file performs no request.
  return file.configuration;
}
