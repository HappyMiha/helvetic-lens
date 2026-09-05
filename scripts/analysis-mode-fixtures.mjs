// Render the actual notice component and catalogue without a running API/model.
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { createRequire } from "node:module";
import ts from "typescript";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

const require = createRequire(import.meta.url);
const root = path.resolve(import.meta.dirname, "..");
const source = fs.readFileSync(path.join(root, "apps/web/lib/i18n.tsx"), "utf8");
const start = source.indexOf("export const locales");
const end = source.indexOf("const localeCookie");
if (start < 0 || end < 0) throw new Error("Catalogue bounds missing");
const compile = (code) => ts.transpileModule(code, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const scope = { globalThis: {} };
vm.runInNewContext(compile(`${source.slice(start, end).replaceAll("export ", "")}\nglobalThis.catalog = catalog;`), scope);
const catalog = scope.globalThis.catalog;
const component = compile(fs.readFileSync(path.join(root, "apps/web/components/analysis-mode-notice.tsx"), "utf8"));

export function analysisModeFixtures() {
  return Object.keys(catalog).flatMap((locale) => {
    const exports = {};
    vm.runInNewContext(component, {
      exports,
      require: (name) => name === "@/lib/i18n"
        ? { useI18n: () => ({ t: (key) => {
          if (!catalog[locale][key]) throw new Error(`Missing ${locale}: ${key}`);
          return catalog[locale][key];
        } }) }
        : require(name),
    });
    return ["selected_evidence", "generated_explanation", "deterministic", undefined].map((mode) => ({
      locale,
      mode: mode || "legacy",
      html: renderToStaticMarkup(createElement(exports.AnalysisModeNotice, { mode })),
    }));
  });
}
