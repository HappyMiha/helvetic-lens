import assert from "node:assert/strict";
import { test } from "node:test";
import { auctionCopy } from "../apps/web/lib/auction-copy.ts";
import { newAuctionProfile, parseAuctionBudget } from "../apps/web/lib/auction-watch.ts";

test("budget entry preserves cents, distinguishes no limit and refuses ambiguous values", () => {
  assert.equal(parseAuctionBudget("12000,50"), 1200050);
  assert.equal(parseAuctionBudget("12000.50"), 1200050);
  assert.equal(parseAuctionBudget("0"), 0);
  assert.equal(parseAuctionBudget(""), null);
  assert.equal(parseAuctionBudget("  "), null);
  for (const value of ["1e3", "-1", "12'000", "12,000", "0.001", "NaN", "Infinity", "10000000000000.01"])
    assert.equal(parseAuctionBudget(value), undefined, value);
  assert.equal(parseAuctionBudget("10000000000000"), 10 ** 15);
});

test("fresh profiles do not share mutable interests or opt into every bid", () => {
  const first = newAuctionProfile(), second = newAuctionProfile();
  first.locations.push("Lugano"); first.notify.every_bid_change = true;
  assert.deepEqual(second.locations, []);
  assert.equal(second.notify.every_bid_change, false);
  assert.equal(second.notify.ending_soon_hours, null);
});

test("every product language describes source, budget and stored preference limits", () => {
  const keys = Object.keys(auctionCopy["en-CH"]).sort();
  assert.equal(Object.keys(auctionCopy).length, 5);
  for (const copy of Object.values(auctionCopy)) {
    assert.deepEqual(Object.keys(copy).sort(), keys);
    assert.ok(Object.values(copy).every(value => typeof value === "string" && value.trim()));
    assert.ok(new Set([copy.current_bid, copy.starting_price, copy.minimum_price, copy.estimate]).size === 4);
  }
});
