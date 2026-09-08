import assert from "node:assert/strict";
import test from "node:test";
import { renderLocalizedComponent } from "./analysis-mode-fixtures.mjs";

for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
  const render = (summary) => renderLocalizedComponent("digest-coverage-notice.tsx", "DigestCoverageNotice", locale, { summary });
  test(`${locale}: limited event selection links to the full saved inbox`, () => {
    const html = render({ events: [], truncated: true });
    assert.match(html, /data-digest-coverage="limited"/);
    assert.match(html, /50/);
    assert.match(html, /href="\/"/);
    assert.doesNotMatch(html, /digests\.|\{(?:count|shown|total)\}/);
  });
  test(`${locale}: law-only overflow is visible without claiming 50 event overflow`, () => {
    const html = render({ events: [{ impacts_truncated: true }], truncated: false });
    assert.match(html, /data-digest-coverage="limited"/);
    assert.match(html, /href="\/"/);
    assert.doesNotMatch(html, /50|digests\./);
  });
  test(`${locale}: combined overflow exposes both limits with one clear destination`, () => {
    const html = render({ events: [{ impacts_truncated: true }], truncated: true });
    assert.equal((html.match(/<p /g) || []).length, 3);
    assert.equal((html.match(/<a /g) || []).length, 1);
  });
  test(`${locale}: complete and legacy unknown summaries do not invent omitted laws`, () => {
    for (const summary of [undefined, {}, { events: [], truncated: false }, { events: [{ impacts: [{}, {}, {}, {}, {}] }], truncated: false }]) {
      assert.equal(render(summary), "");
    }
  });
  test(`${locale}: offline source-only preview explains unavailable AI without inventing overflow`, () => {
    const html = render({ events: [], ai_runtime_unverified: true, severity_filter_deferred: false });
    assert.match(html, /data-digest-runtime="unverified"/);
    assert.match(html, /href="\/"/);
    assert.equal((html.match(/<p[ >]/g) || []).length, 1);
    assert.doesNotMatch(html, /50|digests\.|runtime_unavailable|filter_deferred/);
  });
  test(`${locale}: an empty filtered preview explains why the period is retained`, () => {
    const html = render({ events: [], ai_runtime_unverified: true, severity_filter_deferred: true });
    assert.match(html, /data-digest-runtime="unverified"/);
    assert.equal((html.match(/<p[ >]/g) || []).length, 2);
    assert.doesNotMatch(html, /50|digests\.|runtime_unavailable|filter_deferred/);
    assert.ok(html.length > render({ ai_runtime_unverified: true }).length + 50);
  });
}
