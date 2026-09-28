import assert from "node:assert/strict";
import { test, after } from "node:test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import Module, { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

// Exercise actual server rendering without a browser or live account. Type
// checking remains the separate full-project gate; this loader only transpiles.
const require = createRequire(import.meta.url);
const originalResolve = Module._resolveFilename;
const originalTs = Module._extensions[".ts"];
const originalTsx = Module._extensions[".tsx"];
const originalCss = Module._extensions[".css"];
Module._extensions[".css"] = () => {}; // Server markup assertions do not load styles.
Module._resolveFilename = function (name, ...args) {
  return originalResolve.call(
    this,
    name.startsWith("@/") ? resolve("apps/web", name.slice(2)) : name,
    ...args,
  );
};
for (const extension of [".ts", ".tsx"])
  Module._extensions[extension] = (module, filename) => {
    const { outputText } = ts.transpileModule(readFileSync(filename, "utf8"), {
      compilerOptions: {
        jsx: ts.JsxEmit.ReactJSX,
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        esModuleInterop: true,
      },
      fileName: filename,
    });
    module._compile(outputText, filename);
  };
after(() => {
  Module._resolveFilename = originalResolve;
  if (originalCss) Module._extensions[".css"] = originalCss;
  else delete Module._extensions[".css"];
  if (originalTs) Module._extensions[".ts"] = originalTs;
  else delete Module._extensions[".ts"];
  if (originalTsx) Module._extensions[".tsx"] = originalTsx;
  else delete Module._extensions[".tsx"];
});

const {
  chooseBaseline,
  comparisonSelection,
  baselineCommand,
  nativeSnapshotHref,
} = require(resolve("apps/web/lib/comparison-selection.ts"));
const { comparisonReadingCopy } = require(
  resolve("apps/web/lib/comparison-reading-copy.ts"),
);
const { SavedComparisonSummary, ComparisonPassages } = require(
  resolve("apps/web/components/native-comparison-reading.tsx"),
);
const snapshot = (id) => ({
  id,
  version_key: "source-" + id,
  saved_at: "2026-09-28T07:00:00Z",
  evidence_url: "/corpus-evidence/" + encodeURIComponent(id),
});
const before = snapshot("before"),
  afterVersion = snapshot("after"),
  alternate = snapshot("other");
const page = {
  event_id: "event",
  title: "Saved law",
  language: "fr",
  before,
  after: afterVersion,
  revision: 4,
  status: "ready",
  comparison_id: "comparison",
  material_count: 17,
  counts: {},
  items: [],
  pagination: { offset: 0, total: 17 },
};
const render = (component, props) =>
  renderToStaticMarkup(
    React.createElement(component, {
      locale: "en-CH",
      formatDate: (value) => value,
      ...props,
    }),
  );
test("baseline drafts survive same-revision reads and passage/candidate pagination without replacing the saved pair", () => {
  const draft = chooseBaseline(page, alternate);
  const refreshed = {
    ...page,
    before: { ...before },
    pagination: { offset: 20, total: 25 },
  };
  const result = comparisonSelection(refreshed, draft, null);
  assert.equal(result.value, alternate);
  assert.equal(result.dirty, true);
  assert.equal(result.conflict, false);
  assert.equal(refreshed.before.id, "before");
  assert.deepEqual(baselineCommand(refreshed, draft, null, true), {
    before_version_id: "other",
    after_version_id: "after",
    expected_revision: 4,
  });
  assert.equal(chooseBaseline(page, { ...before }), null);
  assert.equal(comparisonSelection(refreshed, null, null).value.id, "before");
});
test("changed event, event version or saved revision blocks both replacement and clear until the saved choice is restored", () => {
  const draft = chooseBaseline(page, alternate);
  for (const current of [
    { ...page, revision: 5 },
    { ...page, after: snapshot("retargeted") },
    { ...page, event_id: "another" },
  ]) {
    assert.equal(comparisonSelection(current, draft, null).conflict, true);
    assert.equal(baselineCommand(current, draft, null, true), null);
    assert.equal(baselineCommand(current, draft, null, true, true), null);
    assert.equal(comparisonSelection(current, null, null).conflict, false);
    assert.ok(
      baselineCommand(current, chooseBaseline(current, alternate), null, true),
    );
  }
});
test("writes need current authorization/read readiness and an explicit valid change", () => {
  assert.equal(baselineCommand(page, null, null, true), null);
  assert.equal(
    baselineCommand(page, chooseBaseline(page, alternate), null, false),
    null,
  );
  assert.equal(
    baselineCommand(null, chooseBaseline(page, alternate), null, true),
    null,
  );
  assert.equal(
    baselineCommand(page, chooseBaseline(page, afterVersion), null, true),
    null,
  );
  assert.equal(
    baselineCommand(page, chooseBaseline(page, null), null, true),
    null,
  );
  assert.deepEqual(baselineCommand(page, null, null, true, true), {
    before_version_id: null,
    after_version_id: "after",
    expected_revision: 4,
  });
  assert.equal(
    baselineCommand(
      { ...page, status: "unselected", before: null },
      null,
      null,
      true,
      true,
    ),
    null,
  );
});
test("server write receipt hides earlier comparisons until acknowledged, including no-op revisions and failed reads", () => {
  const receipt = {
    after: "after",
    revision: 5,
    comparison_id: "new-comparison",
    previous: page,
  };
  for (const current of [null, page, { ...page }, { ...page, revision: 5 }]) {
    assert.equal(comparisonSelection(current, null, receipt).pending, true);
    assert.equal(
      baselineCommand(current, chooseBaseline(page, alternate), receipt, true),
      null,
    );
  }
  for (const current of [
    { ...page, revision: 5, comparison_id: "new-comparison" },
    { ...page, revision: 6 },
    { ...page, after: snapshot("new-event") },
    { ...page, revision: 5, status: "stale", comparison_id: null },
    {
      ...page,
      revision: 5,
      status: "unselected",
      before: null,
      comparison_id: null,
    },
  ])
    assert.equal(comparisonSelection(current, null, receipt).pending, false);
  const unchanged = { ...receipt, revision: 4, comparison_id: "comparison" };
  assert.equal(comparisonSelection(page, null, unchanged).pending, true);
  assert.equal(
    comparisonSelection({ ...page }, null, unchanged).pending,
    false,
  );
  assert.equal(
    comparisonSelection(
      { ...page, status: "stale", comparison_id: null },
      null,
      unchanged,
    ).pending,
    false,
  );
});
test("native references identify the exact version and encode complete passage IDs", () => {
  assert.equal(
    nativeSnapshotHref(snapshot("version/one"), "art/1 ?#"),
    "/corpus-evidence/version%2Fone?passage=art%2F1%20%3F%23",
  );
  for (const evidence_url of [
    "https://example.org/",
    "javascript:alert(1)",
    "/registry",
    "/corpus-evidence/another",
    "/corpus-evidence/before?wrong=1",
  ])
    assert.equal(nativeSnapshotHref({ ...before, evidence_url }), null);
  assert.equal(nativeSnapshotHref(null), null);
});
for (const locale of Object.keys(comparisonReadingCopy))
  test(`native ${locale} saved comparison identifies the persisted pair, actual total and capture times`, () => {
    const html = render(SavedComparisonSummary, { data: page, locale }),
      copy = comparisonReadingCopy[locale];
    assert.ok(html.includes(copy.savedPair));
    assert.ok(html.includes(copy.limits));
    assert.ok(html.includes(copy.details));
    assert.match(html, />17<\/dd>/);
    assert.match(html, /source-before/);
    assert.match(html, /source-after/);
    assert.match(html, /href="\/corpus-evidence\/before"/);
    assert.equal(
      (html.match(/dateTime="2026-09-28T07:00:00Z"/g) || []).length,
      2,
    );
  });
test("unknown native metadata is distinct from zero and invalid capture dates never reach formatting", () => {
  const html = render(SavedComparisonSummary, {
    data: {
      ...page,
      material_count: null,
      before: { ...before, saved_at: "bad", evidence_url: "javascript:bad" },
    },
    formatDate: (value) => {
      assert.notEqual(value, "bad");
      return value;
    },
  });
  assert.match(html, /Not available in this record/);
  assert.doesNotMatch(html, /href="javascript:|>0<\/dd>/);
  assert.match(
    render(SavedComparisonSummary, { data: { ...page, material_count: 0 } }),
    />0<\/dd>/,
  );
});
test("actual paired quotations preserve untrusted text and exact passage links; stale evidence is not rendered", () => {
  const item = {
    id: "change",
    old: { id: "art/1", text: "Earlier <script>alert(1)</script>\nline" },
    new: { id: "art/2", text: "New & exact" },
  };
  const html = render(ComparisonPassages, {
    data: page,
    item,
    evidenceLabel: "Evidence",
  });
  assert.match(html, /Earlier &lt;script&gt;/);
  assert.match(html, /New &amp; exact/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /lang="fr"/);
  assert.match(html, /href="\/corpus-evidence\/before\?passage=art%2F1"/);
  assert.match(html, /href="\/corpus-evidence\/after\?passage=art%2F2"/);
  for (const status of ["stale", "unselected"]) {
    assert.equal(
      render(ComparisonPassages, {
        data: { ...page, status },
        item,
        evidenceLabel: "Evidence",
      }),
      "",
    );
    assert.equal(
      render(SavedComparisonSummary, { data: { ...page, status } }),
      "",
    );
  }
});
