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

const { VersionContext, ReportVersionReferences } = require(
  resolve("apps/web/components/version-context.tsx"),
);
const { sourceReadingCopy } = require(
  resolve("apps/web/lib/source-reading-copy.ts"),
);
const { savedEvidenceHref } = require(
  resolve("apps/web/lib/saved-evidence-link.ts"),
);
const version = {
  id: "old-version-0123456789",
  declared_date: "2025-01-01",
  created_at: "2026-09-28T07:00:00Z",
  source_url: "https://example.org/law",
  content_type: "application/pdf",
  filename: "saved-law.pdf",
  characters: 12000,
  passage_count: 21,
  content_hash: "ab".repeat(32),
  identity_json: { language: "fr" },
  synthetic: false,
};
const render = (value = version, locale = "en-CH", extra = {}) =>
  renderToStaticMarkup(
    React.createElement(VersionContext, {
      version: value,
      side: "Baseline",
      locale,
      formatDate: (date) => date,
      originLabel: "Retained upload",
      dateLabel: "User-supplied document date",
      syntheticLabel: "Synthetic saved version",
      ...extra,
    }),
  );
const escaped = (value) =>
  renderToStaticMarkup(React.createElement(React.Fragment, null, value));
for (const locale of Object.keys(sourceReadingCopy))
  test(`${locale} version context keeps capture date, declared date, full file identity and actual retained totals separate`, () => {
    const html = render(version, locale),
      copy = sourceReadingCopy[locale];
    for (const value of [
      copy.provenance,
      copy.identifier,
      copy.digest,
      copy.captured,
      copy.classification,
      copy.unknownClassification,
      version.id,
      version.filename,
      version.content_type,
      version.content_hash,
      "2025-01-01",
      "User-supplied document date",
      "Retained upload",
    ])
      assert.ok(html.includes(escaped(value)), value);
    assert.match(html, /dateTime="2026-09-28T07:00:00Z"/);
    assert.ok(
      html.includes(escaped(new Intl.NumberFormat(locale).format(12000))),
    );
    assert.match(html, />21<\/dd>/);
    assert.match(html, /href="\/evidence\/old-version-0123456789"/);
  });
test("unknown capture, count and fingerprint cannot become a plausible date, zero or verified digest", () => {
  const html = render(
    {
      ...version,
      created_at: "bad",
      characters: undefined,
      passage_count: 0,
      content_hash: "bad",
      source_url: "https://user:secret@example.org",
    },
    "en-CH",
    {
      formatDate: () => {
        throw new Error("Malformed date formatted");
      },
    },
  );
  assert.match(html, /Not established|Not available in this record/);
  assert.match(html, />0<\/dd>/);
  assert.match(html, /Origin not established/);
  assert.doesNotMatch(html, /<time|data-version-fingerprint|secret|>bad</);
});
test("source labels remain escaped while synthetic captures stay explicitly identified", () => {
  const html = render({
    ...version,
    synthetic: true,
    filename: "<img src=x onerror=alert(1)>",
    declared_date: "<script>date</script>",
  });
  assert.match(html, /Synthetic saved version/);
  assert.match(html, /&lt;img/);
  assert.match(html, /&lt;script&gt;date/);
  assert.doesNotMatch(html, /<img|<script>/);
});
test("exact evidence links round-trip passage query and fragment characters without changing the version path", () => {
  const href = savedEvidenceHref(
      "version/one?x",
      "Art. 1 / ?section=x&other=y#end",
    ),
    url = new URL(href, "https://native.test");
  assert.equal(url.pathname, "/evidence/version%2Fone%3Fx");
  assert.equal(
    url.searchParams.get("passage"),
    "Art. 1 / ?section=x&other=y#end",
  );
  assert.equal(url.searchParams.size, 1);
  assert.equal(url.hash, "");
  for (const id of [undefined, null, "", "x".repeat(201), "\ud800"])
    assert.equal(savedEvidenceHref(id), null);
  for (const passage of [null, "", 17, "\ud800"])
    assert.equal(savedEvidenceHref("version", passage), null);
  assert.equal(savedEvidenceHref("version"), "/evidence/version");
});
test("saved report provenance shows complete old/new identities and opens those exact retained sources", () => {
  const html = renderToStaticMarkup(
    React.createElement(ReportVersionReferences, {
      before: "before/full?x",
      after: "after/full#x",
      beforeLabel: "Earlier source",
      afterLabel: "Later source",
      unknown: "Not recorded",
    }),
  );
  assert.match(html, /data-report-version-references/);
  assert.match(html, /before\/full\?x/);
  assert.match(html, /after\/full#x/);
  assert.match(html, /href="\/evidence\/before%2Ffull%3Fx"/);
  assert.match(html, /href="\/evidence\/after%2Ffull%23x"/);
  const absent = renderToStaticMarkup(
    React.createElement(ReportVersionReferences, {
      before: "",
      after: "",
      beforeLabel: "Earlier",
      afterLabel: "Later",
      unknown: "Not recorded",
    }),
  );
  assert.doesNotMatch(absent, /<a /);
  assert.match(absent, /Not recorded/);
});
