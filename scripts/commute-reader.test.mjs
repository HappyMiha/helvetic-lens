import test from "node:test";
import assert from "node:assert/strict";
import {
  savedConditions,
  savedLabels,
  sourceEdition,
  zurichDate,
} from "../apps/web/lib/commute-watch.ts";

test("journey dates use Zurich midnight rather than UTC or host timezone", () => {
  assert.equal(zurichDate(new Date("2026-01-12T23:30:00Z")), "2026-01-13");
  assert.equal(zurichDate(new Date("2026-07-12T22:30:00Z")), "2026-07-13");
  assert.equal(zurichDate(new Date("2026-03-29T21:59:00Z")), "2026-03-29");
  assert.equal(zurichDate(new Date("2026-03-29T22:00:00Z")), "2026-03-30");
});
test("official source language editions stay literal with explicit fallback language", () => {
  const editions = [
    ["de", "Gleis gesperrt"],
    ["fr-CH", "Voie fermée"],
    ["en", "Track closed"],
  ];
  assert.deepEqual(sourceEdition(editions, "fr-CH"), editions[1]);
  assert.deepEqual(sourceEdition(editions, "rm-CH"), editions[2]);
  assert.deepEqual(
    sourceEdition([[null, "<script>source text</script>"]], "it-CH"),
    [null, "<script>source text</script>"],
  );
  assert.equal(sourceEdition([], "de-CH"), undefined);
});

test("linked evidence keeps its own observed delay and labels without changing the immutable snapshot", () => {
  const snapshot = {
    evidence: {
      current: {
        states: {
          leg: { condition: "delay_material", availability: "present" },
        },
        editions: {},
      },
      observations: {
        leg: { delay_seconds: 600, observed_at: "2026-09-14T05:40:00Z" },
      },
      legs: {
        leg: {
          route_name: "Tram 8",
          boarding_name: "Basel SBB",
          alighting_name: "Claraplatz",
        },
      },
    },
  };
  const original = structuredClone(snapshot);
  const current = savedConditions(snapshot);
  assert.equal(current.states.leg.delay_seconds, 600);
  assert.equal(current.states.leg.observed_at, "2026-09-14T05:40:00Z");
  current.states.leg.availability = "stale";
  assert.deepEqual(snapshot, original);
  assert.deepEqual(savedLabels(snapshot), [
    { id: "leg", label: "Tram 8: Basel SBB → Claraplatz" },
  ]);
});
