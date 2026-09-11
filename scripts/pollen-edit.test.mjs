import assert from "node:assert/strict";
import { test } from "node:test";
import { editablePollenConfiguration } from "../apps/web/lib/pollen-edit.ts";

const fixture = () => ({ contract_version: 1, template_id: "pollen-watch", template_version: 1,
  station_id: "PBS", timezone: "Europe/Zurich", selections: [{ allergen: "birch", rules: [{
    period: "observation_hourly", unit: "number/m3", category_change: false,
    threshold: { trigger_at_or_above: "12.500001", reset_at_or_below: "5" },
    rapid_increase: { minimum_increase: "3.000001", window_hours: 2 },
  }] }], delivery: { email: "daily_digest", digest_at: "08:30", quiet_hours: { start: "22:00", end: "07:00" } } });

test("supported v1 settings and delivery preferences remain representable without mutation", () => {
  const value = fixture(), before = structuredClone(value);
  assert.equal(editablePollenConfiguration(value), true);
  assert.deepEqual(value, before);
});
for (const [name, change] of [
  ["future contract", c => c.contract_version = 2],
  ["future template", c => c.template_version = 2],
  ["different template", c => c.template_id = "other"],
  ["unknown root setting", c => c.future = true],
  ["unknown selection setting", c => c.selections[0].future = true],
  ["unknown rule setting", c => c.selections[0].rules[0].future = true],
  ["category rules", c => c.selections[0].rules[0].category_change = true],
  ["different units", c => c.selections[0].rules[0].unit = "category"],
  ["unknown period", c => c.selections[0].rules[0].period = "forecast_daily"],
  ["unknown allergen", c => c.selections[0].allergen = "unknown"],
  ["future threshold field", c => c.selections[0].rules[0].threshold.future = true],
  ["future increase field", c => c.selections[0].rules[0].rapid_increase.future = true],
  ["future delivery field", c => c.delivery.future = true],
  ["future quiet hours field", c => c.delivery.quiet_hours.future = true],
]) test(`${name} stays read-only instead of being silently discarded`, () => {
  const value = fixture(); change(value);
  assert.equal(editablePollenConfiguration(value), false);
});
