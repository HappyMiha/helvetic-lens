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
            r.category_change !== false
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
