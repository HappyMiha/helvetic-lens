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
    if (entry.isDirectory() && [".next", "node_modules"].includes(entry.name)) continue;
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
const approvedUiLiterals = new Set([
  "GPU",
  "HL",
  "Infomaniak AI",
  "Infomaniak API docs",
  "Apertus",
  "Helvetic Lens",
  "Local Docker Apertus",
  "Public AI setup",
  "Hugging Face setup",
  "SHA-256:",
  "Runtime:",
  "YYYY-MM-DD",
  "https://…",
  "http://localhost:8080/v1",
]);
const hardcoded = [];
const uiPatterns = [
  />\s*([A-Z][A-Za-z0-9][^<>{}\r\n]{1,120}?)\s*</g,
  /(?:aria-label|placeholder|title)=["']([A-Z][^"']{1,160})["']/g,
  /(?:window\.(?:confirm|prompt)|new Error)\(\s*["']([A-Z][^"']{2,200})["']/g,
];
for (const file of sourceFiles) {
  const source = fs.readFileSync(file, "utf8");
  for (const pattern of uiPatterns) {
    for (const match of source.matchAll(pattern)) {
      const value = match[1].replace(/\s+/g, " ").trim();
      if (!approvedUiLiterals.has(value) && !/^(?:React\.|Promise\b)/.test(value)) {
        const line = source.slice(0, match.index).split("\n").length;
        hardcoded.push(`${path.relative(root, file)}:${line}: ${value}`);
      }
    }
  }
}
if (missing.length || unused.length || hardcoded.length) {
  if (missing.length) console.error("Missing catalogue keys:\n" + missing.sort().join("\n"));
  if (unused.length) console.error("Unused catalogue keys:\n" + unused.sort().join("\n"));
  if (hardcoded.length) console.error("Unapproved hard-coded UI text:\n" + hardcoded.sort().join("\n"));
  process.exit(1);
}
console.log(`i18n catalogue check passed (${keys.size} production keys, ${calls.size} literal calls).`);
