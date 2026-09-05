import assert from "node:assert/strict";
import test from "node:test";
import { reportDateFixtures } from "./report-date-fixtures.mjs";

for (const { locale, state, html } of reportDateFixtures()) {
  test(`date evidence renders ${locale} ${state} with honest state and provenance`, () => {
    assert.doesNotMatch(html, /\{(?:count|shown|passages)\}|dateReview\./);
    assert.match(html, /<h3/);
    if (state === "legacy") {
      assert.match(html, /data-date-review="legacy"/);
      assert.match(html, /Original historical label/);
      assert.doesNotMatch(html, /<details/);
    } else {
      assert.match(html, /data-date-review="date-mentions-v1"/);
      if (state === "empty") {
        assert.doesNotMatch(html, /<details|<blockquote|href=/);
        assert.match(html, /historical-note/);
      } else {
        assert.equal((html.match(/<summary>/g) || []).length, 2);
        assert.match(html, /href="\/evidence\/old\?passage=p1"/);
        assert.match(html, /href="\/evidence\/new\?passage=p1"/);
        assert.match(html, /Proposed date: 1 January 2026/);
        assert.match(html, /Proposed date: 1 January 2027/);
        assert.doesNotMatch(html, /<details open/); // Quotes do not expand the initial summary.
        if (state === "limited") assert.match(html, /12/);
      }
    }
  });
}
