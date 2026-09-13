import assert from "node:assert/strict";
import test from "node:test";
import { hazardTarget, hazardHref, officialLink } from "../apps/web/lib/hazard-events.ts";

const monitor = "00000000-0000-4000-8000-000000000011", event = "00000000-0000-4000-8000-000000000022";
test("exact warning links preserve monitor, development and historical revision", () => {
  const url = new URL(hazardHref(monitor, event, 3), "https://example.invalid");
  assert.deepEqual(hazardTarget(url.searchParams), { event, revision: 3, invalid: false });
  assert.deepEqual(hazardTarget(new URLSearchParams(`monitor=${monitor}&event=${event}`)), { event, revision: null, invalid: false });
});
test("ambiguous or malformed warning routes cannot silently become current instructions", () => {
  for (const suffix of ["revision=0", "revision=-1", "revision=1e2", "revision=1&revision=2", "revision=9007199254740992", `event=${event}`]) {
    assert.ok(hazardTarget(new URLSearchParams(`monitor=${monitor}&event=${event}&${suffix}`)).invalid, suffix);
  }
  for (const query of [`event=${event}`, `monitor=${monitor}&revision=1`, `monitor=${monitor}&event=bad`, `monitor=${monitor}&monitor=${monitor}&event=${event}`]) {
    assert.ok(hazardTarget(new URLSearchParams(query)).invalid, query);
  }
});
test("official links cannot execute script, reveal embedded credentials or use a local protocol", () => {
  for (const link of ["javascript:alert(1)", "data:text/html,secret", "file:///private", "http://example.invalid", "https://secret:password@example.invalid"]) {
    assert.equal(officialLink(link), null);
  }
  assert.equal(officialLink("https://example.invalid/official"), "https://example.invalid/official");
});
