import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

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
  "GB",
  "HL",
  "Infomaniak AI",
  "Infomaniak API docs",
  "Apertus",
  "Helvetic Lens",
  "Local Docker Apertus",
  "Public AI setup",
  "Hugging Face setup",
  "SHA-256:",
  "ms",
  "Runtime:",
  "YYYY-MM-DD",
  "https://…",
  "http://localhost:8080/v1",
]);
const hardcoded = [];
function recordLiteral(file, sourceFile, node, rawValue) {
  const value = rawValue.replace(/\s+/g, " ").trim();
  if (!/[A-Za-zÀ-ÿ]/.test(value) || approvedUiLiterals.has(value)) return;
  const line = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1;
  hardcoded.push(`${path.relative(root, file)}:${line}: ${value}`);
}
function inspectRenderedExpression(file, sourceFile, node) {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
    recordLiteral(file, sourceFile, node, node.text);
  } else if (ts.isConditionalExpression(node)) {
    inspectRenderedExpression(file, sourceFile, node.whenTrue);
    inspectRenderedExpression(file, sourceFile, node.whenFalse);
  } else if (ts.isParenthesizedExpression(node)) {
    inspectRenderedExpression(file, sourceFile, node.expression);
  } else if (
    ts.isBinaryExpression(node) &&
    [ts.SyntaxKind.AmpersandAmpersandToken, ts.SyntaxKind.QuestionQuestionToken].includes(node.operatorToken.kind)
  ) {
    inspectRenderedExpression(file, sourceFile, node.right);
  }
}
for (const file of sourceFiles) {
  const source = fs.readFileSync(file, "utf8");
  const sourceFile = ts.createSourceFile(
    file,
    source,
    ts.ScriptTarget.Latest,
    true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  function visit(node) {
    if (ts.isJsxText(node)) {
      recordLiteral(file, sourceFile, node, node.getText(sourceFile));
    } else if (
      ts.isJsxExpression(node) &&
      node.expression &&
      (ts.isJsxElement(node.parent) || ts.isJsxFragment(node.parent))
    ) {
      inspectRenderedExpression(file, sourceFile, node.expression);
    } else if (
      ts.isJsxAttribute(node) &&
      ["aria-label", "placeholder", "title"].includes(node.name.getText(sourceFile)) &&
      node.initializer && ts.isStringLiteral(node.initializer)
    ) {
      recordLiteral(file, sourceFile, node, node.initializer.text);
    } else if (ts.isCallExpression(node) && node.arguments.length) {
      const callee = node.expression.getText(sourceFile);
      const argument = node.arguments[0];
      if (["window.confirm", "window.prompt"].includes(callee) && ts.isStringLiteral(argument)) {
        recordLiteral(file, sourceFile, argument, argument.text);
      }
    } else if (ts.isNewExpression(node) && node.expression.getText(sourceFile) === "Error") {
      const argument = node.arguments?.[0];
      if (argument && ts.isStringLiteral(argument)) recordLiteral(file, sourceFile, argument, argument.text);
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
}
if (missing.length || unused.length || hardcoded.length) {
  if (missing.length) console.error("Missing catalogue keys:\n" + missing.sort().join("\n"));
  if (unused.length) console.error("Unused catalogue keys:\n" + unused.sort().join("\n"));
  if (hardcoded.length) console.error("Unapproved hard-coded UI text:\n" + hardcoded.sort().join("\n"));
  process.exit(1);
}
console.log(`i18n catalogue check passed (${keys.size} production keys, ${calls.size} literal calls).`);
