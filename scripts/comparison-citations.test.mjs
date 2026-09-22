import assert from "node:assert/strict";
import test from "node:test";
import { citationChange } from "../apps/web/lib/comparison-citations.ts";

const versions = { old_version: { id: "before" }, new_version: { id: "after" } };
const passage = (id, text) => ({ id, text, page: null });
const rows = [
  { id: "article-63", old: passage("p00545", "Art. 63"), new: passage("p00574", "Art. 63") },
  { id: "article-66", old: passage("p00574", "Temporary protection"), new: passage("p00603", "Temporary protection") },
  { id: "later", old: passage("p00603", "Later provision"), new: passage("p00632", "Later provision") },
];
const cite = (version_id, passage_id) => ({ version_id, passage_id, url: `/evidence/${version_id}#${passage_id}` });

test("old and new citations with colliding passage numbers reach their own version", () => {
  assert.equal(citationChange(rows, cite("before", "p00574"), versions)?.id, "article-66");
  assert.equal(citationChange(rows, cite("after", "p00574"), versions)?.id, "article-63");
  assert.equal(citationChange(rows, cite("before", "p00603"), versions)?.id, "later");
  assert.equal(citationChange(rows, cite("after", "p00603"), versions)?.id, "article-66");
});

test("unrelated history versions and missing passages do not substitute another target", () => {
  for (const citation of [cite("unrelated", "p00574"), cite("before", "p00632"), cite("after", "p00545")]) {
    assert.equal(citationChange(rows, citation, versions), undefined);
  }
  assert.equal(citationChange(rows, cite("before", "p00574"), null), undefined);
});

test("one-sided added and removed passages remain reachable", () => {
  const changes = [
    { id: "removed", old: passage("p1", "Old"), new: null },
    { id: "added", old: null, new: passage("p1", "New") },
  ];
  assert.equal(citationChange(changes, cite("before", "p1"), versions)?.id, "removed");
  assert.equal(citationChange(changes, cite("after", "p1"), versions)?.id, "added");
});

test("ambiguous input retains the evidence link; identical-version comparison has one target", () => {
  assert.equal(citationChange([...rows, {...rows[1], id: "duplicate"}], cite("before", "p00574"), versions), undefined);
  const same = { old_version: { id: "same" }, new_version: { id: "same" } };
  const changes = [{ id: "unchanged", old: passage("p1", "Same"), new: passage("p1", "Same") }];
  assert.equal(citationChange(changes, cite("same", "p1"), same)?.id, "unchanged");
  assert.equal(citationChange([], cite("same", "p1"), same), undefined);
});
