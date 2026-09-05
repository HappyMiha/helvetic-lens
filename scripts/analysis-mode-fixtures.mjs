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
const end = source.indexOf("type I18nValue");
if (start < 0 || end < 0) throw new Error("Catalogue bounds missing");
const compile = (code) => ts.transpileModule(code, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const scope = { globalThis: {}, exports: {} };
vm.runInNewContext(compile(`${source.slice(start, end)}\nglobalThis.catalog = catalog; globalThis.translate = translate;`), scope);
const catalog = scope.globalThis.catalog;

export function renderLocalizedComponent(file, name, locale, props) {
  const component = compile(fs.readFileSync(path.join(root, "apps/web/components", file), "utf8"));
  const exports = {};
  vm.runInNewContext(component, {
    exports,
    require: (module) => module === "@/lib/i18n"
      ? { useI18n: () => ({ t: (key, values) => {
        const text = scope.globalThis.translate(locale, key, values);
        if (!text) throw new Error(`Missing ${locale}: ${key}`);
        return text;
      } }) }
      : require(module),
  });
  return renderToStaticMarkup(createElement(exports[name], props));
}

export function analysisModeFixtures() {
  return Object.keys(catalog).flatMap((locale) => {
    return ["selected_evidence", "generated_explanation", "deterministic", undefined].map((mode) => ({
      locale,
      mode: mode || "legacy",
      html: renderLocalizedComponent("analysis-mode-notice.tsx", "AnalysisModeNotice", locale, { mode }),
    }));
  });
}
