import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");
const comparison = read("apps/web/components/comparison-view.tsx");
const history = read("apps/web/components/ai-history.tsx");
const css = read("apps/web/app/globals.css");

test("comparison exposes four companion tasks with complete tab semantics", () => {
  for (const tab of ["summary", "actions", "ask", "history"]) {
    assert.match(comparison, new RegExp(`id: ["']${tab}["']`));
    assert.match(comparison, new RegExp(`companion-\\$\\{tab\\.id\\}`));
  }
  assert.match(comparison, /role="tablist"/);
  assert.match(comparison, /role="tab"/);
  assert.match(comparison, /aria-selected=\{selected\}/);
  assert.match(comparison, /aria-controls=/);
  assert.match(comparison, /ArrowLeft/);
  assert.match(comparison, /ArrowRight/);
  assert.match(comparison, /Home/);
  assert.match(comparison, /End/);
  assert.match(comparison, /role="tabpanel"/);
  assert.match(history, /id=\{comparisonId \? "companion-history"/);
});

test("wide comparison keeps evidence primary and companion content viewport-stable", () => {
  assert.match(
    css,
    /\.comparison-layout\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0, 1fr\) clamp\(420px, 30vw, 480px\)/,
  );
  assert.match(
    css,
    /\.analysis-column\s*\{[\s\S]*?position:\s*sticky[\s\S]*?height:\s*calc\(100dvh - 112px\)/,
  );
  assert.match(
    css,
    /\.analysis-column > \.companion-tab-panel\s*\{[\s\S]*?overflow-y:\s*auto[\s\S]*?overscroll-behavior:\s*contain/,
  );
  assert.match(comparison, /id="comparison-evidence"/);
  assert.match(
    read("apps/web/components/comparison-panel.tsx"),
    /className="analysis-column"/,
  );
});

test("tablet uses a drawer and mobile uses a full-screen task surface", () => {
  assert.match(
    css,
    /@media \(min-width: 901px\) and \(max-width: 1350px\)[\s\S]*?\.analysis-column\s*\{[\s\S]*?position:\s*fixed[\s\S]*?width:\s*min\(480px, calc\(100vw - 48px\)\)/,
  );
  assert.match(
    css,
    /@media \(max-width: 900px\)[\s\S]*?\.analysis-column\s*\{[\s\S]*?inset:\s*0[\s\S]*?position:\s*fixed/,
  );
  assert.match(css, /\.comparison-task-tabs\s*\{[\s\S]*?display:\s*flex/);
  assert.match(comparison, /data-mobile-surface=\{mobileSurface\}/);
  assert.match(comparison, /<ComparisonPanel/);
});

test("compact summary limits action preview and discloses detail", () => {
  assert.match(comparison, /actions\.slice\(0, 3\)/);
  assert.match(comparison, /<details className="impact-details">/);
  assert.match(
    comparison,
    /<details className="impact-details provenance-disclosure">/,
  );
  assert.match(comparison, /onHistory=\{\(\) => openCompanion\("history"\)\}/);
});

test("saved citations jump in place while companion tab state is retained", () => {
  assert.match(comparison, /function ComparisonCitations/);
  assert.match(comparison, /onClick=\{\(\) => onEvidence\(change\.id\)\}/);
  assert.match(history, /onClick=\{\(\) => onEvidence\(change\.id\)\}/);
  assert.match(comparison, /setMobileSurface\("evidence"\)/);
  assert.match(comparison, /target\?\.focus\(\{ preventScroll: true \}\)/);
  assert.match(comparison, /tabIndex=\{-1\}/);
  const jumpStart = comparison.indexOf("function jump(value: string)");
  const jumpEnd = comparison.indexOf("function openCompanion", jumpStart);
  assert.ok(jumpStart >= 0 && jumpEnd > jumpStart, "Missing jump function");
  assert.doesNotMatch(
    comparison.slice(jumpStart, jumpEnd),
    /setCompanionTab/,
    "Evidence jumps must retain the selected companion tab",
  );
});

test("durable AI result links open the matching comparison task", () => {
  assert.match(comparison, /HASH_COMPANION_TAB\.get\(/);
  assert.match(
    comparison,
    /linkedTask \? `#\$\{linkedTask\}` : window\.location\.hash/,
  );
  assert.match(comparison, /searchParams\.get\("task"\)/);
  assert.match(comparison, /target\.searchParams\.set\("task"/);
  assert.match(comparison, /window\.addEventListener\("hashchange"/);
  assert.match(comparison, /COMPANION_TAB_HASH\[tab\]/);
  assert.match(comparison, /target\.hash = ""/);
});
