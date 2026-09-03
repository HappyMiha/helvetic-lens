import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const catalogPath = path.join(root, "apps", "web", "lib", "i18n.tsx");
const catalogSource = fs.readFileSync(catalogPath, "utf8");
const keys = new Set(
  [...catalogSource.matchAll(/["']([a-z][a-zA-Z0-9_-]*\.[a-zA-Z0-9_.-]+)["']\s*:/g)].map((match) => match[1]),
);
const sourceFiles = [];
function visit(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) visit(target);
    else if (/\.(ts|tsx)$/.test(entry.name) && target !== catalogPath) sourceFiles.push(target);
  }
}
visit(path.join(root, "apps", "web"));
const productSource = sourceFiles.map((file) => fs.readFileSync(file, "utf8")).join("\n");
const calls = new Set(
  [...productSource.matchAll(/\bt\(\s*["']([^"']+)["']/g)].map((match) => match[1]),
);
const missing = [...calls].filter((key) => !keys.has(key));
const dynamicPrefixes = [
  "count.",
  "error.",
  "connectors.name.",
  "language.",
  "logs.operation.",
  "logs.provider.",
  "status.",
];
const unused = [...keys].filter(
  (key) => !productSource.includes(`"${key}"`) && !productSource.includes(`'${key}'`) &&
    !dynamicPrefixes.some((prefix) => key.startsWith(prefix)),
);
if (missing.length || unused.length) {
  if (missing.length) console.error("Missing catalogue keys:\n" + missing.sort().join("\n"));
  if (unused.length) console.error("Unused catalogue keys:\n" + unused.sort().join("\n"));
  process.exit(1);
}
console.log(`i18n catalogue check passed (${keys.size} production keys, ${calls.size} literal calls).`);
