import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import ts from "typescript";

const root = process.cwd();
const source = fs.readFileSync(path.join(root, "apps", "web", "lib", "i18n.tsx"), "utf8");
const start = source.indexOf("export const locales");
const end = source.indexOf("const localeCookie");
if (start < 0 || end < 0) throw new Error("Could not locate the i18n catalogue");

const catalogueSource = `${source.slice(start, end).replaceAll("export ", "")}\nglobalThis.__catalog = catalog;`;
const compiled = ts.transpileModule(catalogueSource, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const sandbox = { globalThis: {} };
vm.runInNewContext(compiled, sandbox);
const catalog = sandbox.globalThis.__catalog;

const sourceLocale = catalog["en-CH"];
const approvedIdentical = {
  "de-CH": new Set(["common.optional", "scan.apertus", "settings.infomaniak", "settings.topP", "prompts.ask", "models.revision", "logs.integration", "logs.provider.website", "logs.provider.fedlex", "logs.provider.firecrawl", "logs.provider.infomaniak", "org.team", "org.prompts", "org.revision", "status.live", "companion.name", "companion.toneNeutral", "companion.route.settings"]),
  "fr-CH": new Set(["nav.sources", "filter.impact", "filter.type", "history.impact", "history.question", "monitor.document", "sources.section", "scan.position", "scan.apertus", "form.pages", "settings.infomaniak", "settings.topP", "logs.provider.fedlex", "logs.provider.firecrawl", "logs.provider.infomaniak", "org.prompts", "org.quotas", "admin.services", "connectors.active", "connectors.pause", "evidence.contentMeta", "law.passages", "law.pages", "law.version", "law.source", "status.probable", "compare.page", "compare.versions", "companion.name", "companion.route.sources", "companion.route.settings"]),
  "it-CH": new Set(["login.password", "sources.section", "scan.apertus", "settings.database", "settings.infomaniak", "settings.topP", "logs.provider.fedlex", "logs.provider.firecrawl", "logs.provider.infomaniak", "admin.backup", "law.file", "compare.area", "companion.name"]),
  "rm-CH": new Set(["history.context", "monitor.document", "scan.apertus", "settings.infomaniak", "settings.model", "settings.topP", "logs.success", "logs.provider.website", "logs.provider.fedlex", "logs.provider.firecrawl", "logs.provider.infomaniak", "org.local", "org.prompts", "org.quotas", "companion.name", "companion.toneNeutral"]),
};
let failed = false;
for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH"]) {
  const identical = Object.keys(sourceLocale).filter((key) => catalog[locale][key] === sourceLocale[key]);
  const unexpected = identical.filter((key) => !approvedIdentical[locale].has(key));
  if (unexpected.length) {
    failed = true;
    console.error(`Untranslated ${locale} catalogue values:\n${unexpected.map((key) => `${key}=${JSON.stringify(sourceLocale[key])}`).join("\n")}`);
  }
}

for (const [key, value] of Object.entries(sourceLocale)) {
  let braceDepth = 0;
  const expanded = `⟦${[...value].map((character) => {
    if (character === "{") { braceDepth += 1; return character; }
    if (character === "}") { braceDepth = Math.max(0, braceDepth - 1); return character; }
    return braceDepth === 0 && /[aeiouy]/i.test(character) ? `${character}${character.toLowerCase()}` : character;
  }).join("")}⟧`;
  const sourceParameters = [...value.matchAll(/\{(\w+)(?:,|\})/g)].map((match) => match[1]).sort().join("|");
  const expandedParameters = [...expanded.matchAll(/\{(\w+)(?:,|\})/g)].map((match) => match[1]).sort().join("|");
  if (expanded.length <= value.length || sourceParameters !== expandedParameters) {
    failed = true;
    console.error(`Pseudo-locale stress value is invalid: ${key}`);
  }
}

if (failed) process.exit(1);
console.log("i18n value audit passed (no unapproved English inheritance; pseudo-locale placeholders preserved).\n");
