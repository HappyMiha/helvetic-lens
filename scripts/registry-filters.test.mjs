import assert from "node:assert/strict";
import test from "node:test";
import { registryDateRange } from "../apps/web/lib/registry-filters.ts";

for (const [instant, today, yesterday, week, month] of [
  [
    "2026-03-29T22:30:00Z",
    "2026-03-30",
    "2026-03-29",
    "2026-03-24",
    "2026-03-01",
  ],
  [
    "2026-10-25T00:30:00Z",
    "2026-10-25",
    "2026-10-24",
    "2026-10-19",
    "2026-09-26",
  ],
  [
    "2026-10-25T01:30:00Z",
    "2026-10-25",
    "2026-10-24",
    "2026-10-19",
    "2026-09-26",
  ],
  [
    "2025-12-31T23:30:00Z",
    "2026-01-01",
    "2025-12-31",
    "2025-12-26",
    "2025-12-03",
  ],
  [
    "2024-03-01T00:01:00Z",
    "2024-03-01",
    "2024-02-29",
    "2024-02-24",
    "2024-02-01",
  ],
]) {
  test(`Zurich calendar presets across midnight/DST/year/leap boundary: ${instant}`, () => {
    const now = new Date(instant);
    assert.deepEqual(registryDateRange("today", now), {
      start: today,
      end: today,
    });
    assert.deepEqual(registryDateRange("yesterday", now), {
      start: yesterday,
      end: yesterday,
    });
    assert.deepEqual(registryDateRange("week", now), {
      start: week,
      end: today,
    });
    assert.deepEqual(registryDateRange("month", now), {
      start: month,
      end: today,
    });
    assert.deepEqual(registryDateRange("all", now), { start: "", end: "" });
  });
}
test("Calendar calculation ignores the browser/runtime local timezone", () => {
  const before = process.env.TZ;
  try {
    for (const timezone of [
      "Pacific/Honolulu",
      "Asia/Tokyo",
      "Europe/Zurich",
    ]) {
      process.env.TZ = timezone;
      assert.deepEqual(
        registryDateRange("today", new Date("2026-09-05T22:30:00Z")),
        { start: "2026-09-06", end: "2026-09-06" },
      );
    }
  } finally {
    if (before === undefined) delete process.env.TZ;
    else process.env.TZ = before;
  }
});
