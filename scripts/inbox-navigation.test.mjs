import assert from "node:assert/strict";
import test from "node:test";
import { inboxQuery } from "../apps/web/lib/inbox-navigation.ts";
import { renderLocalizedComponent } from "./analysis-mode-fixtures.mjs";

for (const filter of ["source", "severity", "item_type", "watched_law", "state"]) {
  test(`changing ${filter} starts fresh and exits a pinned notification`, () => {
    const params = new URLSearchParams(inboxQuery("cursor=old&candidate=linked&limit=20&severity=high&extra=ignored", { [filter]: "new value" }));
    assert.equal(params.get(filter), "new value");
    assert.equal(params.has("cursor"), false);
    assert.equal(params.has("candidate"), false);
    assert.equal(params.has("extra"), false);
    assert.equal(params.get("limit"), "20");
  });
}

test("next/newest links preserve filters and a candidate without treating values as URLs", () => {
  const query = "severity=high&candidate=linked&state=unread";
  const next = inboxQuery(query, { cursor: "opaque+/= &value" });
  assert.equal(new URLSearchParams(next).get("cursor"), "opaque+/= &value");
  assert.deepEqual(Object.fromEntries(new URLSearchParams(inboxQuery(next, { cursor: "" }))), Object.fromEntries(new URLSearchParams(query)));
  assert.equal(new URLSearchParams(inboxQuery(next, { candidate: "" })).has("cursor"), false);
});

for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
  const render = props => renderLocalizedComponent("inbox-page-navigation.tsx", "InboxPageNavigation", locale, props);
  test(`${locale}: sparse page still offers next with honest shown/checked numbers`, () => {
    const html = render({ page: { total_events: 0, scanned_event_count: 50, has_more: true }, nextHref: "/impact?cursor=test", newestHref: "/impact" });
    assert.match(html, /href="\/impact\?cursor=test"/);
    assert.match(html, /role="status"/);
    assert.match(html, /50/);
    assert.match(html, /min-h-11/);
    assert.doesNotMatch(html, /inboxPaging\.|\{(?:shown|scanned)\}/);
  });
  test(`${locale}: exhausted page has no invented next destination`, () => {
    const html = render({ page: { total_events: 21, scanned_event_count: 21, has_more: false }, newestHref: "/impact?severity=high" });
    assert.match(html, /21/);
    assert.equal((html.match(/<a /g) || []).length, 1);
  });
  test(`${locale}: rejected cursor can recover without any response data`, () => {
    const html = render({ newestHref: "/impact?state=unread" });
    assert.match(html, /href="\/impact\?state=unread"/);
    assert.doesNotMatch(html, /role="status"/);
  });
  test(`${locale}: pending navigation does not expose a stale next link`, () => {
    assert.doesNotMatch(render({ busy: true, nextHref: "/impact?cursor=stale" }), /cursor=stale/);
  });
}
