import assert from "node:assert/strict";
import { test } from "node:test";
import { decodePollenBackup, encodePollenBackup, POLLEN_BACKUP_MAX_BYTES } from "../apps/web/lib/pollen-edit.ts";

const settings = () => ({ contract_version: 1, template_id: "pollen-watch", template_version: 1,
  station_id: "PBS", timezone: "Europe/Zurich", selections: [{ allergen: "birch", rules: [{
    period: "observation_hourly", unit: "number/m3", category_change: false,
    threshold: { trigger_at_or_above: "999999.999999", reset_at_or_below: "0.000001" },
    rapid_increase: { minimum_increase: "3.000001", window_hours: 2 },
  }] }, { allergen: "grasses", rules: [] }], delivery: { email: "daily_digest", digest_at: "08:30", quiet_hours: { start: "22:00", end: "07:00" } } });
const file = configuration => ({ format: "helvetic-lens.pollen-draft", version: 1, configuration });
test("portable backup preserves exact numeric text, schedules and version metadata without identity or mutation", () => {
  const original = settings(), before = structuredClone(original);
  const encoded = encodePollenBackup(original), restored = decodePollenBackup(encoded);
  assert.deepEqual(restored, before);
  assert.deepEqual(original, before);
  assert.deepEqual(Object.keys(JSON.parse(encoded)), ["format", "version", "configuration"]);
  restored.station_id = "PZH";
  assert.equal(original.station_id, "PBS");
  assert.ok(new TextEncoder().encode(encoded).byteLength < POLLEN_BACKUP_MAX_BYTES);
});
for (const [name, mutate] of [
  ["another product", f => f.format = "other"],
  ["future version", f => f.version = 2],
  ["subject identity", f => f.id = "private-subject"],
  ["retry identity", f => f.request_key = "old-save"],
  ["owner identity", f => f.configuration.owner_user_id = "another-owner"],
  ["unknown rule", f => f.configuration.selections[0].rules[0].future = true],
  ["category not supported by form", f => f.configuration.selections[0].rules[0].category_change = true],
  ["JSON number precision", f => f.configuration.selections[0].rules[0].threshold.trigger_at_or_above = 12.500001],
  ["excess decimals", f => f.configuration.selections[0].rules[0].threshold.trigger_at_or_above = "1.1234567"],
  ["duplicate selection", f => f.configuration.selections.push(f.configuration.selections[0])],
  ["duplicate period", f => f.configuration.selections[0].rules.push(f.configuration.selections[0].rules[0])],
  ["missing selections", f => f.configuration.selections = []],
  ["invalid schedule structure", f => f.configuration.delivery.quiet_hours.end = "25:00"],
  ["script in station", f => f.configuration.station_id = "<script>alert(1)</script>"],
]) test(`reject ${name} before review or network activity`, () => {
  const value = file(settings()); mutate(value);
  assert.throws(() => decodePollenBackup(JSON.stringify(value)), /unsupported_backup/);
});
for (const value of ["null", "[]", "false", "{bad", "", "x".repeat(POLLEN_BACKUP_MAX_BYTES + 1), "é".repeat(POLLEN_BACKUP_MAX_BYTES / 2 + 1)]) {
  test(`reject invalid or oversized input (${value.length} characters)`, () => assert.throws(() => decodePollenBackup(value), /invalid_backup/));
}
test("configuration semantics still require explicit server preview, without silently correcting a backup", () => {
  const original = settings();
  original.selections[0].rules[0].threshold.reset_at_or_below = "999999.999999";
  assert.deepEqual(decodePollenBackup(JSON.stringify(file(original))), original);
});
test("export does not silently discard future saved fields", () => {
  const original = settings(); original.future = { private: "value" };
  assert.throws(() => encodePollenBackup(original), /unsupported_backup/);
});
