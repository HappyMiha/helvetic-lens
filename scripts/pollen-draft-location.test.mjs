import assert from "node:assert/strict";
import { test } from "node:test";
import { pollenDraftIdFromHash, replacePollenDraftLocation } from "../apps/web/lib/pollen-draft-location.ts";

test("only a bounded opaque draft locator can be restored", () => {
  const id = "1c498cd1-7894-434a-9fdd-4e0a53d6b8e3";
  assert.equal(pollenDraftIdFromHash(`#draft=${id}`), id);
  for (const value of ["", "#draft=", "#other=id", "#draft=../../private", "#draft=%2f", "#draft=a&configuration=private", `#draft=${"a".repeat(129)}`])
    assert.equal(pollenDraftIdFromHash(value), null);
});
test("fragment replacement preserves route/query and existing Next history state", () => {
  const original = globalThis.window, state = { __NA: true, tree: ["retained"] }, calls = [];
  globalThis.window = { location: { href: "https://example.invalid/pollen-watch?mode=read#old" }, history: { state, replaceState: (...args) => calls.push(args) } };
  try {
    replacePollenDraftLocation("draft-123");
    assert.equal(calls[0][0], state);
    assert.equal(String(calls[0][2]), "https://example.invalid/pollen-watch?mode=read#draft=draft-123");
    replacePollenDraftLocation(null);
    assert.equal(String(calls[1][2]), "https://example.invalid/pollen-watch?mode=read");
  } finally { globalThis.window = original; }
});
