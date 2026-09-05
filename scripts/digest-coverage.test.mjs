import assert from "node:assert/strict";
import test from "node:test";
import { renderLocalizedComponent } from "./analysis-mode-fixtures.mjs";

for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
  const render = (summary) => renderLocalizedComponent("digest-coverage-notice.tsx", "DigestCoverageNotice", locale, { summary });
  test(`${locale}: limited event selection links to the full saved inbox`, () => {
    const html = render({ events: [], truncated: true });
    assert.match(html, /data-digest-coverage="limited"/);
    assert.match(html, /50/);
    assert.match(html, /href="\/impact"/);
    assert.doesNotMatch(html, /digests\.|\{(?:count|shown|total)\}/);
  });
  test(`${locale}: law-only overflow is visible without claiming 50 event overflow`, () => {
    const html = render({ events: [{ impacts_truncated: true }], truncated: false });
    assert.match(html, /data-digest-coverage="limited"/);
    assert.match(html, /href="\/impact"/);
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
}
