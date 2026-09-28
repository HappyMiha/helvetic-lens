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

const { ProductDestinations } = require(
  resolve("apps/web/components/product-destinations.tsx"),
);
const { productNavigationCopy } = require(
  resolve("apps/web/lib/product-navigation.ts"),
);
test("product navigation preserves the current tab and never carries private context to another origin", () => {
  const destinations = {
    pharma: "https://pharma.helveticlens.ch/",
    loyer: "https://loyer.helveticlens.ch/",
    platform: "https://helveticlens.ch/",
  };
  for (const current of Object.keys(destinations)) {
    const html = renderToStaticMarkup(
      React.createElement(ProductDestinations, {
        current,
        question: "CONFIDENTIAL_QUESTION",
        dossierId: "PRIVATE_ID",
        credential: "SECRET_VALUE",
      }),
    );
    const links = [...html.matchAll(/<a ([^>]+)>/g)].map(
      ([_, attributes]) => attributes,
    );
    assert.equal(links.length, 2);
    assert.match(html, /aria-current="true"/);
    assert.doesNotMatch(html, /CONFIDENTIAL_QUESTION|PRIVATE_ID|SECRET_VALUE/);
    for (const attributes of links) {
      const href = attributes.match(/href="([^"]+)"/)[1];
      assert.ok(
        Object.entries(destinations).some(
          ([id, url]) => id !== current && url === href,
        ),
      );
      assert.equal(new URL(href).search, "");
      assert.equal(new URL(href).hash, "");
      assert.match(attributes, /target="_blank"/);
      assert.match(attributes, /rel="noopener noreferrer"/);
      assert.match(attributes.toLowerCase(), /referrerpolicy="no-referrer"/);
      assert.match(attributes, /aria-label="[^"]+Opens in a new tab"/);
    }
  }
});
test("all native product navigation locales expose current location and external-link meaning", () => {
  assert.deepEqual(Object.keys(productNavigationCopy), [
    "en-CH",
    "de-CH",
    "fr-CH",
    "it-CH",
    "rm-CH",
  ]);
  for (const copy of Object.values(productNavigationCopy)) {
    const html = renderToStaticMarkup(
      React.createElement(ProductDestinations, { current: "platform", copy }),
    );
    assert.ok(html.includes(copy.title));
    assert.ok(html.includes(copy.current));
    assert.ok(html.includes(copy.opens));
    assert.ok(html.includes(copy.note));
  }
});
