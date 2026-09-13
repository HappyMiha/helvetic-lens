import assert from "node:assert/strict";
import test from "node:test";
import { sourceExcerpts, sourceTitle } from "../apps/web/lib/tender-watch.ts";

test("publication language fallback preserves original source words", () => {
  const source = { de: "Vergabe", fr: "Marché", en: "Tender" };
  assert.equal(sourceTitle(source, "fr-CH"), "Marché");
  assert.equal(sourceTitle(source, "rm-CH"), "Vergabe");
  assert.equal(sourceTitle(null, "en-CH"), "");
});

test("large source text is explicitly shortened without altering the original", () => {
  const source = { terms: [{ description: { en: "x".repeat(10000) } }] };
  const before = JSON.stringify(source);
  const result = sourceExcerpts(source, "en-CH");
  assert.equal(result.truncated, true);
  assert.equal(result.paragraphs[0].length, 2000);
  assert.equal(JSON.stringify(source), before);
});

test("large and deeply nested fields cannot create an unbounded reader", () => {
  const result = sourceExcerpts(
    Array.from({ length: 50000 }, (_, number) => String(number)),
    "en-CH",
  );
  assert.equal(result.paragraphs.length, 100);
  assert.equal(result.truncated, true);
  let deep = "inaccessible";
  for (let index = 0; index < 50; index++) deep = { child: deep };
  assert.deepEqual(sourceExcerpts(deep, "en-CH"), {
    paragraphs: [],
    truncated: true,
  });
});

test("source markup is retained as inert display text, not interpreted HTML", () => {
  const source = { en: '<script>alert("source")</script>' };
  assert.deepEqual(sourceExcerpts(source, "en-CH"), {
    paragraphs: [source.en],
    truncated: false,
  });
});
