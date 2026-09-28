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
  sourceReference,
  sourceCount,
  sourceTimestamp,
  sourceFingerprint,
} = require(resolve("apps/web/lib/source-reading.ts"));
const { SourceReadingMetadata } = require(
  resolve("apps/web/components/source-reading.tsx"),
);
const { sourceReadingCopy } = require(
  resolve("apps/web/lib/source-reading-copy.ts"),
);

test("source references preserve exact context and reject unsafe or credential-bearing links", () => {
  assert.deepEqual(
    sourceReference("https://example.org:8443/law?q=one#art_1"),
    {
      href: "https://example.org:8443/law?q=one#art_1",
      origin: "example.org:8443",
    },
  );
  for (const value of [
    "javascript:alert(1)",
    "//example.org",
    "https://user:secret@example.org/",
    "https://example.org\\bad",
    "https://example.org/\npath",
    "",
    null,
  ])
    assert.equal(sourceReference(value, true), null);
  assert.equal(sourceReference("http://example.org/law"), null);
  assert.equal(
    sourceReference("http://example.org/law", true).href,
    "http://example.org/law",
  );
});
test("unknown counts cannot become measured zero or fabricated totals", () => {
  assert.equal(sourceCount(0), 0);
  assert.equal(sourceCount(10001), 10001);
  for (const value of [
    null,
    undefined,
    "",
    "7",
    -1,
    1.5,
    NaN,
    Infinity,
    Number.MAX_SAFE_INTEGER + 1,
  ])
    assert.equal(sourceCount(value), null);
});
test("only complete recorded SHA-256 values are fingerprint labels", () => {
  assert.equal(sourceFingerprint("AB".repeat(32)), "ab".repeat(32));
  for (const value of [
    null,
    undefined,
    "",
    "a".repeat(63),
    "x".repeat(64),
    "<script>not-a-fingerprint</script>",
  ])
    assert.equal(sourceFingerprint(value), null);
});
test("capture dates require an explicit parseable timestamp", () => {
  for (const value of [
    "2026-09-28T07:00:00Z",
    "2026-09-28T09:00:00.123456+02:00",
  ])
    assert.equal(sourceTimestamp(value), value);
  for (const value of [
    undefined,
    null,
    "",
    "yesterday",
    "2026-09-28",
    "2026-09-28T07:00:00",
    "2026-13-28T07:00:00Z",
    "<script>",
  ])
    assert.equal(sourceTimestamp(value), null);
});

const source = {
  id: "version-one",
  source_url: "https://example.org/law",
  created_at: "2026-09-28T07:00:00Z",
  declared_date: "2025-01-01",
  filename: "law.pdf",
  content_type: "application/pdf",
  content_hash: "ab".repeat(32),
  characters: 123456,
  passage_count: 10001,
  identity_json: { language: "fr" },
};
const render = (value, locale = "en-CH") =>
  renderToStaticMarkup(
    React.createElement(SourceReadingMetadata, {
      source: value,
      locale,
      savedAt: "28 September 2026",
      statedLabel: sourceReadingCopy[locale].stated,
    }),
  );
for (const locale of Object.keys(sourceReadingCopy))
  test(`native ${locale} source metadata distinguishes document dates, capture identity and real saved totals`, () => {
    const html = render(source, locale),
      copy = sourceReadingCopy[locale];
    assert.match(html, /data-source-reading/);
    assert.ok(html.includes(copy.captured));
    assert.ok(html.includes(copy.stated));
    assert.ok(
      html.includes(
        renderToStaticMarkup(
          React.createElement(
            React.Fragment,
            null,
            new Intl.NumberFormat(locale).format(10001),
          ),
        ),
      ),
    );
    assert.ok(
      html.includes(
        renderToStaticMarkup(
          React.createElement(
            React.Fragment,
            null,
            new Intl.NumberFormat(locale).format(123456),
          ),
        ),
      ),
    );
    assert.match(html, /dateTime="2026-09-28T07:00:00Z"/);
    assert.match(html, /2025-01-01/);
    assert.match(html, /example.org/);
    assert.match(html, /version-one/);
    assert.match(html, /law.pdf/);
    assert.match(html, /application\/pdf/);
    assert.ok(html.includes(copy.unknownClassification));
    assert.ok(html.includes(source.content_hash));
  });
test("native empty and unavailable metadata remain different from actual zero", () => {
  const html = render({
    ...source,
    source_url: "javascript:alert(1)",
    created_at: "bad",
    declared_date: null,
    content_hash: "bad",
    passage_count: 0,
    characters: undefined,
    filename: "",
    identity_json: null,
    content_type: "unknown",
  });
  assert.match(html, /Origin not established/);
  assert.match(html, /Not available in this record/);
  assert.match(html, />0<\/dd>/);
  assert.doesNotMatch(html, /<time|data-source-fingerprint|javascript:|>bad</);
});
test("native untrusted file names, declared dates and identifiers remain escaped text", () => {
  const html = render({
    ...source,
    filename: "<img src=x onerror=alert(1)>",
    id: "<script>id</script>",
    declared_date: "<script>date</script>",
  });
  assert.match(html, /&lt;img/);
  assert.match(html, /&lt;script&gt;id/);
  assert.doesNotMatch(html, /<img|<script>/);
});
