/** Shareable calendar-date presets; day arithmetic never uses the browser timezone. */
export const registryPeriods = [
  "all",
  "today",
  "yesterday",
  "week",
  "month",
] as const;
export type RegistryPeriod = (typeof registryPeriods)[number];
export function registryDateRange(
  period: RegistryPeriod,
  now = new Date(),
): { start: string; end: string } {
  if (period === "all") return { start: "", end: "" };
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Zurich",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const part = (type: string) =>
    Number(parts.find((item) => item.type === type)!.value);
  const today = Date.UTC(part("year"), part("month") - 1, part("day"));
  const day = (offset: number) =>
    new Date(today - offset * 86_400_000).toISOString().slice(0, 10);
  return {
    start: day(
      period === "yesterday"
        ? 1
        : period === "week"
          ? 6
          : period === "month"
            ? 29
            : 0,
    ),
    end: day(period === "yesterday" ? 1 : 0),
  };
}
