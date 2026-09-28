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

const { isAskShortcut, askDraftDecision, askBoundary } = require(
  resolve("apps/web/lib/ask-interaction.ts"),
);
const { searchNativeAsk, nativeSearchHref } = require(
  resolve("apps/web/lib/native-ask-search.ts"),
);
const { NativeAskTrigger } = require(
  resolve("apps/web/components/native-ask-search.tsx"),
);
const { nativeAskCopy } = require(resolve("apps/web/lib/native-ask-copy.ts"));

const key = (extra = {}) => ({
  key: "k",
  ctrlKey: true,
  metaKey: false,
  altKey: false,
  shiftKey: false,
  isComposing: false,
  repeat: false,
  defaultPrevented: false,
  ...extra,
});
test("Cmd/Ctrl K works without swallowing ordinary typing", () => {
  assert.equal(isAskShortcut(key(), null), true);
  assert.equal(
    isAskShortcut(key({ ctrlKey: false, metaKey: true, key: "K" }), null),
    true,
  );
  assert.equal(isAskShortcut(key({ ctrlKey: false }), null), false);
  assert.equal(isAskShortcut(key({ key: "x" }), null), false);
});
test("composition, repeated, modified and already-handled keys keep their owner", () => {
  for (const field of [
    "altKey",
    "shiftKey",
    "isComposing",
    "repeat",
    "defaultPrevented",
  ])
    assert.equal(isAskShortcut(key({ [field]: true }), null), false, field);
});
test("another dialog keeps its shortcut while the global command can refocus", () => {
  assert.equal(isAskShortcut(key(), { getAttribute: () => null }), false);
  assert.equal(isAskShortcut(key(), { getAttribute: () => "true" }), true);
});
test("preparing a question preserves different drafts and does not enable paused context", () => {
  assert.equal(
    askDraftDecision("Existing work", "New question", true),
    "conflict",
  );
  assert.equal(
    askDraftDecision("  Existing work ", "Existing work", true),
    "ready",
  );
  assert.equal(
    askDraftDecision("", "Where is the primary source?", true),
    "ready",
  );
  assert.equal(askDraftDecision("", "Question", false), "unavailable");
  assert.equal(askDraftDecision("", "  ", true), "unavailable");
  assert.equal(askDraftDecision("", "x".repeat(2001), true), "unavailable");
});
test("draft boundaries separate accounts, workspaces, pages, languages and permissions", () => {
  const base = askBoundary("/sources", "org", "person", "en-CH");
  for (const args of [
    ["/sources", "org", "other", "en-CH"],
    ["/sources", "other", "person", "en-CH"],
    ["/laws/1", "org", "person", "en-CH"],
    ["/sources", "org", "person", "fr-CH"],
    ["/sources", "org", "person", "en-CH", "viewer"],
  ])
    assert.notEqual(askBoundary(...args), base);
  assert.notEqual(askBoundary("/a:b", "c"), askBoundary("/a", "b:c"));
});

test("empty, oversized and overlong public queries make no request", async () => {
  let requests = 0;
  const request = () => {
    requests++;
    throw new Error("Must not run");
  };
  for (const [question, mode] of [
    [" ", "sources"],
    ["x".repeat(301), "sources"],
    [Array.from({ length: 13 }, (_, i) => "word" + i).join(" "), "public"],
  ])
    await assert.rejects(
      searchNativeAsk(question, mode, request, new AbortController().signal),
    );
  assert.equal(requests, 0);
});
test("native saved search reuses bounded current-permission readers without a model request", async () => {
  const calls = [];
  const signal = new AbortController().signal;
  const groups = await searchNativeAsk(
    "renal & kidney",
    "sources",
    async (path, init) => {
      calls.push(path);
      assert.equal(init.signal, signal);
      assert.equal(init.method, undefined);
      return {
        items: [
          {
            title: "Saved source",
            authority: "Publisher",
            why: "Matching record",
            evidence_url: "/evidence/version-1",
            comparison_url: "javascript:bad",
          },
        ],
        count: 1,
        next_cursor: "next",
      };
    },
    signal,
  );
  assert.equal(calls.length, 2);
  for (const path of calls) {
    assert.match(path, /^\/registry\?/);
    const url = new URL(path, "https://example.invalid");
    assert.equal(url.searchParams.get("q"), "renal & kidney");
    assert.equal(url.searchParams.get("limit"), "20");
  }
  assert.deepEqual(
    groups.map((g) => g.id),
    ["monitored", "events"],
  );
  assert.equal(groups[0].items[0].href, "/evidence/version-1");
  assert.equal(groups[0].total, null);
  assert.equal(groups[0].more, true);
  assert.match(groups[0].next, /^\/registry\?/);
});
test("published knowledge keeps exact product/source anchors and real collection counts", async () => {
  const calls = [];
  const groups = await searchNativeAsk(
    "evidence",
    "public",
    async (path) => {
      calls.push(path);
      return {
        items: [
          {
            label: "Finding",
            kind: "claim",
            dossier_title: "Public dossier",
            text: "Published excerpt",
            href: "/public-dossiers/dossier-one?research=run-1#claim-c1",
          },
        ],
        total: 21,
      };
    },
    new AbortController().signal,
  );
  assert.equal(calls.length, 2);
  assert.ok(calls.every((p) => p.includes("/public-knowledge?")));
  for (const group of groups) {
    assert.equal(group.total, 21);
    assert.equal(group.more, true);
    assert.equal(
      group.items[0].href,
      `https://${group.id}.helveticlens.ch/public-dossiers/dossier-one?research=run-1#claim-c1`,
    );
    assert.equal(group.items[0].external, true);
    assert.match(group.next, /public-dossiers\?q=evidence/);
  }
});
test("untrusted search links cannot navigate to another origin or another native action", () => {
  for (const value of [
    "https://evil.invalid",
    "//evil.invalid",
    "/\\evil.invalid",
    "javascript:alert(1)",
    "/laws/../admin",
    "/login?next=evil",
    "/api/auth/logout",
    "/laws/a b",
  ])
    assert.equal(nativeSearchHref(value), null, value);
  assert.equal(
    nativeSearchHref("/laws/source-1?tab=history#entry-1"),
    "/laws/source-1?tab=history#entry-1",
  );
  assert.equal(nativeSearchHref("/public-dossiers/../admin", "pharma"), null);
  assert.equal(
    nativeSearchHref("/public-dossiers/a", "legal"),
    "https://legal.helveticlens.ch/public-dossiers/a",
  );
});
test("collection failure remains explicit while another collection can still answer", async () => {
  const groups = await searchNativeAsk(
    "test",
    "public",
    async (path) => {
      if (path.includes("/pharma/")) throw new Error("Unavailable");
      return { items: [], total: 0 };
    },
    new AbortController().signal,
  );
  assert.equal(groups[0].failed, true);
  assert.equal(groups[0].total, null);
  assert.equal(groups[1].failed, false);
  assert.equal(groups[1].total, 0);
});
test("a malformed or oversized response is a failed collection rather than invented coverage", async () => {
  const groups = await searchNativeAsk(
    "test",
    "public",
    async (path) =>
      path.includes("/pharma/")
        ? { items: [{}], total: 1 }
        : { items: Array(21).fill({ label: "x" }), total: 21 },
    new AbortController().signal,
  );
  assert.ok(
    groups.every((g) => g.failed && g.total === null && g.items.length === 0),
  );
});
test("aborted or late searches cannot return a result after the command is dismissed", async () => {
  const controller = new AbortController();
  const pending = [];
  const result = searchNativeAsk(
    "test",
    "public",
    () => new Promise((resolve) => pending.push(resolve)),
    controller.signal,
  );
  controller.abort();
  for (const resolve of pending) resolve({ items: [], total: 0 });
  await assert.rejects(result, { name: "AbortError" });
  let calls = 0;
  await assert.rejects(
    searchNativeAsk(
      "test",
      "sources",
      async () => {
        calls++;
      },
      controller.signal,
    ),
  );
  assert.equal(calls, 0);
});
test("actual native entry is accessible in all five locales and retains all copy contracts", () => {
  const keys = Object.keys(nativeAskCopy["en-CH"]).sort();
  assert.equal(Object.keys(nativeAskCopy).length, 5);
  for (const copy of Object.values(nativeAskCopy)) {
    assert.deepEqual(Object.keys(copy).sort(), keys);
    const html = renderToStaticMarkup(
      React.createElement(NativeAskTrigger, {
        label: copy.trigger,
        open: false,
        controls: "ask-dialog",
        onOpen: () => {},
      }),
    );
    assert.match(html, /type="button"/);
    assert.match(html, /aria-haspopup="dialog"/);
    assert.match(html, /aria-keyshortcuts="Meta\+K Control\+K"/);
    assert.match(html, /aria-expanded="false"/);
  }
});
