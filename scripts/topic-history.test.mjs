import assert from "node:assert/strict";
import { createElement } from "react";
import test from "node:test";
import { renderLocalizedComponent } from "./analysis-mode-fixtures.mjs";

const scan = { job_id: "scan", revision: 1, captured_at: "2026-09-05T10:00:00Z", processed: 500, remaining: 1, matched: 490, excluded: 10 };
for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
  function render(state, options = {}) {
    return renderLocalizedComponent("topic-history-status.tsx", "TopicHistoryStatus", locale, {
      topic: { status: options.inactive ? "paused" : "active", history_scan: { ...scan, status: state, ...options.scan } },
      capturedAtLabel: "5 September 2026 12:00",
      renderResume: options.viewer ? undefined : () => createElement("button", null, "continue"),
    });
  }
  test(`${locale}: ongoing history shows real remaining work and no duplicate start`, () => {
    const html = render("queued");
    assert.match(html, /max="501" value="500"/);
    assert.match(html, /dateTime="2026-09-05T10:00:00Z"/);
    assert.match(html, /490/);
    assert.doesNotMatch(html, /topicHistory\.|status\.|\{(?:processed|remaining|matched|excluded)\}|<button/);
  });
  test(`${locale}: incomplete legacy history offers recovery without invented totals`, () => {
    const html = render("legacy_limited", { scan: { processed: 500, remaining: null } });
    assert.match(html, /<button/);
    assert.doesNotMatch(html, /<progress/);
  });
  test(`${locale}: failed history preserves progress and limits recovery to active administrators`, () => {
    assert.match(render("failed"), /<button/);
    assert.match(render("failed"), /max="501" value="500"/);
    assert.doesNotMatch(render("failed", { viewer: true }), /<button/);
    assert.doesNotMatch(render("failed", { inactive: true }), /<button/);
  });
  test(`${locale}: zero saved events is a bounded empty result`, () => {
    const html = render("complete", { scan: { processed: 0, remaining: 0, matched: 0, excluded: 0 } });
    assert.doesNotMatch(html, /<progress|<button|topicHistory\./);
    assert.match(html, /data-topic-history="complete"/);
  });
  test(`${locale}: an obsolete evaluator exposes refresh without certifying its old result`, () => {
    const html = render("superseded", { scan: { processed: 500, remaining: 0 } });
    assert.match(html, /data-topic-history="superseded"/);
    assert.match(html, /<button/);
    assert.doesNotMatch(html, /topicHistory\.|data-topic-history="complete"/);
    assert.doesNotMatch(render("superseded", { viewer: true }), /<button/);
  });
}
