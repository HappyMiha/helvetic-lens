import assert from "node:assert/strict";
import test from "node:test";
import {roadLink} from "../apps/web/lib/road-watch.ts";
import {roadCopy, roadLabel} from "../apps/web/lib/road-copy.ts";

const monitor = "af8bb580-6742-48e8-a6c1-a6946f603aca";
const event = "d9a719c0-59d4-453d-95d9-2e95d9d6eb9a";
test("exact road links do not silently substitute a newer or unrelated event", () => {
  assert.deepEqual(roadLink(new URLSearchParams({monitor, event, sequence:"7"})), {monitor, event, sequence:7, invalid:false});
  assert.deepEqual(roadLink(new URLSearchParams({monitor})), {monitor, event:"", sequence:undefined, invalid:false});
  for (const values of [
    {monitor, event, sequence:"0"}, {monitor, event, sequence:""}, {monitor, event, sequence:"1.5"},
    {monitor, event, sequence:"-1"}, {monitor, event, sequence:"1e3"}, {monitor, event, sequence:"9007199254740993"},
    {monitor, event:"private-name"}, {event}, {monitor:"------------------------------------"}, {monitor, sequence:"2"},
  ]) assert.deepEqual(roadLink(new URLSearchParams(values)), {monitor:"", event:"", sequence:undefined, invalid:true});
});
test("all five locales distinguish source clearance, expiry and unavailable evidence", () => {
  assert.equal(Object.keys(roadCopy).length, 5);
  for (const locale of Object.keys(roadCopy)) {
    const statuses = ["cleared", "possible_clearance", "withdrawn", "expired", "stale", "unavailable"];
    assert.equal(new Set(statuses.map(key => roadLabel(locale, key))).size, statuses.length);
    for (const text of Object.values(roadCopy[locale])) assert.ok(typeof text === "string" && text.trim());
    assert.equal(roadLabel(locale, "secret-provider-code"), roadCopy[locale].unavailable);
    assert.equal(roadLabel(locale, "toString"), roadCopy[locale].unavailable);
  }
});
