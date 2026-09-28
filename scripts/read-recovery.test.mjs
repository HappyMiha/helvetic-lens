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
const originalLoad = Module._load;
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
  Module._load = originalLoad;
  if (originalCss) Module._extensions[".css"] = originalCss;
  else delete Module._extensions[".css"];
  if (originalTs) Module._extensions[".ts"] = originalTs;
  else delete Module._extensions[".ts"];
  if (originalTsx) Module._extensions[".tsx"] = originalTsx;
  else delete Module._extensions[".tsx"];
});

let selectedLocale = "en-CH";
let selectedRead = { data: null, error: "", validating: false, stale: false };
let epoch = 0;
const apiMock = {
  resourceScopeEpoch: () => epoch,
  useResource: (key) =>
    key?.id === "comparison:cmp-one"
      ? { ...selectedRead, reload: () => Promise.resolve(undefined) }
      : {
          data: null,
          error: "",
          loading: false,
          validating: false,
          reload: () => Promise.resolve(undefined),
        },
};
Module._load = function (name, parent, ...rest) {
  const native = parent?.filename?.includes("/apps/web/");
  if (name === "@/lib/api" || (native && name === "./api")) return apiMock;
  if (name === "@/lib/i18n" || (native && name === "./i18n"))
    return {
      storedLocale: () => selectedLocale,
      useI18n: () => ({
        locale: selectedLocale,
        t: (key) => key,
        dateTime: (x) => x,
        number: (x) => String(x),
      }),
      translate: (_locale, key) => key,
    };
  if (native && name === "./auth-gate")
    return {
      useAuth: () => ({
        canManage: false,
        session: { user: { id: "reader" }, organization: { id: "workspace" } },
      }),
    };
  if (native && name === "./shell")
    return {
      Shell: ({ children }) => React.createElement("main", null, children),
    };
  if (name === "next/navigation")
    return {
      useSearchParams: () => new URLSearchParams(),
      usePathname: () => "/comparisons/cmp-one",
      useRouter: () => ({}),
    };
  return originalLoad.call(this, name, parent, ...rest);
};
const { RequestOwner } = require(resolve("apps/web/lib/request-owner.ts"));
const { readableComparison, comparisonJob } = require(
  resolve("apps/web/lib/comparison-read.ts"),
);
const { ResourceStore, resourceKey } = require(
  resolve("apps/web/lib/resource-cache.ts"),
);
const { ReadRecovery, readRecoveryCopy } = require(
  resolve("apps/web/components/read-recovery.tsx"),
);
const { ComparisonView } = require(
  resolve("apps/web/components/comparison-view.tsx"),
);
const render = (component, props) =>
  renderToStaticMarkup(React.createElement(component, props));
const comparison = {
  id: "cmp-one",
  mode: "saved_versions",
  law: { name: "PRIVATE EVIDENCE TITLE" },
};
for (const locale of Object.keys(readRecoveryCopy)) {
  test(`${locale} retry is accessible, escaped and disabled only while the read is pending`, () => {
    const pending = render(ReadRecovery, {
      error: "<source unavailable>",
      busy: true,
      retry: () => {},
      locale,
    });
    assert.match(pending, /role="alert"/);
    assert.match(pending, /aria-busy="true"/);
    assert.match(pending, /disabled=""/);
    assert.match(pending, /&lt;source unavailable&gt;/);
    assert.ok(pending.includes(readRecoveryCopy[locale].retrying));
    const settled = render(ReadRecovery, {
      error: "Unavailable",
      busy: false,
      retry: () => {},
      locale,
    });
    assert.doesNotMatch(settled, /disabled=""/);
    assert.ok(settled.includes(readRecoveryCopy[locale].retry));
  });
  test(`${locale} actual comparison and snapshot render no retained source or Ask after a failed read`, () => {
    selectedLocale = locale;
    for (const mode of ["snapshot", "saved_versions"]) {
      selectedRead = {
        data: { ...comparison, mode },
        error: "Access withdrawn",
        validating: true,
        stale: true,
      };
      const html = render(ComparisonView, { id: "cmp-one" });
      assert.match(html, /data-read-recovery/);
      assert.match(html, /Access withdrawn/);
      assert.doesNotMatch(
        html,
        /PRIVATE EVIDENCE TITLE|companion-ask|\/evidence\/|MonitorThis|compare\.readyToAnalyse/,
      );
    }
  });
}
test("read ownership rejects another comparison even if a transport returned a successful payload", () => {
  assert.equal(readableComparison(comparison, "", "cmp-two"), null);
  assert.equal(readableComparison(comparison, "Denied", "cmp-one"), null);
  assert.strictEqual(readableComparison(comparison, "", "cmp-one"), comparison);
});
test("analysis polling follows only the matching comparison, job kind and output locale", () => {
  const job = {
    id: "impact",
    target_id: "cmp-one",
    target_type: "comparison",
    type: "impact_analysis",
    request: { output_locale: "fr-CH" },
  };
  assert.strictEqual(comparisonJob(job, "cmp-one", "fr-CH"), job);
  for (const changed of [
    { target_id: "cmp-two" },
    { target_type: "product_investigation" },
    { type: "ask" },
    { request: { output_locale: "de-CH" } },
  ])
    assert.equal(
      comparisonJob({ ...job, ...changed }, "cmp-one", "fr-CH"),
      null,
    );
  assert.ok(comparisonJob({ ...job, request: null }, "cmp-one", "fr-CH"));
});
test("analysis, Ask and action callbacks lose authority on unmount, locale or workspace changes", () => {
  let scope = "user-one:workspace-one:en";
  const owner = new RequestOwner();
  owner.activate();
  const first = owner.capture(() => scope);
  assert.equal(first(), true);
  scope = "user-one:workspace-two:en";
  assert.equal(first(), false);
  const second = owner.capture(() => scope);
  scope = "user-two:workspace-two:en";
  assert.equal(second(), false);
  const third = owner.capture(() => scope);
  scope = "user-two:workspace-two:fr";
  assert.equal(third(), false);
  const fourth = owner.capture(() => scope);
  owner.deactivate();
  owner.activate();
  assert.equal(fourth(), false);
  assert.equal(owner.capture(() => scope)(), true);
});
test("deferred retry preserves a denial until a current successful read; job completion cannot restore evidence", async () => {
  const store = new ResourceStore();
  const key = resourceKey({
    id: "comparison:cmp-one",
    path: "/comparison",
    scope: "organization",
    owner: "comparison",
  });
  const jobKey = resourceKey({
    id: "job:one",
    path: "/job",
    scope: "organization",
    owner: "comparison",
  });
  store.prime(key, "en-CH", comparison);
  await store.revalidate(
    key,
    "en-CH",
    async () => {
      throw new Error("Access withdrawn");
    },
    true,
  );
  store.prime(jobKey, "en-CH", {
    state: "succeeded",
    result: { data: comparison },
  });
  let snapshot = store.getSnapshot(key, "en-CH");
  assert.equal(
    readableComparison(snapshot.data, snapshot.error, "cmp-one"),
    null,
  );
  let resolveRead;
  const retry = store.revalidate(
    key,
    "en-CH",
    () =>
      new Promise((resolve) => {
        resolveRead = resolve;
      }),
    true,
  );
  await Promise.resolve();
  snapshot = store.getSnapshot(key, "en-CH");
  assert.equal(snapshot.validating, true);
  assert.equal(
    readableComparison(snapshot.data, snapshot.error, "cmp-one"),
    null,
  );
  const current = {
    ...comparison,
    analysis: null,
    analysis_job: null,
    profile_revision: "current",
  };
  resolveRead(current);
  await retry;
  snapshot = store.getSnapshot(key, "en-CH");
  assert.strictEqual(
    readableComparison(snapshot.data, snapshot.error, "cmp-one"),
    current,
  );
  assert.equal(
    snapshot.data.analysis,
    null,
    "obsolete job output cannot replace the current profile/runtime projection",
  );
  store.destroy();
});
