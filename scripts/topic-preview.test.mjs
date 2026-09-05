import assert from "node:assert/strict";
import test from "node:test";
import { renderLocalizedComponent } from "./analysis-mode-fixtures.mjs";

for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
  function render(overrides = {}) {
    return renderLocalizedComponent("topic-preview-coverage.tsx", "TopicPreviewCoverage", locale, {
      preview: { count_is_complete: false, scanned_event_count: 500, scanned_event_limit: 500,
        candidate_count: 120, items: Array(10).fill({}), display_truncated: true,
        sample_captured_at: "2026-09-05T10:00:00Z", ...overrides },
      capturedAtLabel: "5 September 2026 12:00",
    });
  }
  test(`${locale}: preview distinguishes checked sample from displayed matches`, () => {
    const html = render();
    assert.match(html, /data-topic-preview-coverage="limited-sample"/);
    for (const number of [500, 10, 120]) assert.match(html, new RegExp(String(number)));
    assert.match(html, /dateTime="2026-09-05T10:00:00Z"/);
    assert.doesNotMatch(html, /topicPreview\.|topics\.|\{(?:count|limit|shown|total)\}/);
  });
  test(`${locale}: complete saved sample does not claim complete source coverage`, () => {
    const html = render({ count_is_complete: true, scanned_event_count: 4, candidate_count: 1,
      items: [{}], display_truncated: false });
    assert.match(html, /data-topic-preview-coverage="saved-sample"/);
    assert.doesNotMatch(html, /font-medium/); // No unprocessed-sample warning.
    assert.match(html, /<p class="m-0 mt-2">/); // Scope disclaimer remains.
  });
  test(`${locale}: an empty saved corpus shows the actual zero inspected`, () => {
    const html = render({ count_is_complete: true, scanned_event_count: 0, candidate_count: 0,
      items: [], display_truncated: false });
    assert.match(html, />[^<]*0[^<]*500[^<]*</);
    assert.doesNotMatch(html, /font-medium/);
  });
  test(`${locale}: an older API response never invents a checked count`, () => {
    const html = render({ scanned_event_count: undefined, sample_captured_at: undefined,
      display_truncated: undefined });
    assert.doesNotMatch(html, /<time|>[^<]*0[^<]*500[^<]*</);
    assert.match(html, /500/);
  });
}
