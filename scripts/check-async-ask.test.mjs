import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");
const comparison = read("apps/web/components/comparison-view.tsx");
const resources = read("apps/web/lib/resource-keys.ts");
const css = read("apps/web/app/globals.css");

test("Ask returns control after enqueue and observes persisted jobs", () => {
  assert.doesNotMatch(comparison, /waitForJob/);
  assert.match(comparison, /resources\.comparisonAskJobs\(comparisonId\)/);
  assert.match(comparison, /askJobs\.setData/);
  assert.match(
    resources,
    /comparisonAskJobs:[\s\S]*?\/comparisons\/\$\{id\}\/ask-jobs/,
  );
  assert.match(resources, /comparisonAskJobs:[\s\S]*?pollMs:\s*1_000/);
});

test("Ask exposes real durable stages and recovery controls", () => {
  for (const stage of [
    "queued",
    "startingModel",
    "selectingEvidence",
    "generating",
    "validating",
    "completed",
    "limited",
    "failed",
    "cancelled",
  ]) {
    assert.match(comparison, new RegExp(`askStage\\.${stage}`));
  }
  assert.match(comparison, /aria-live=\{active \? "polite" : "assertive"\}/);
  assert.match(comparison, /\/jobs\/\$\{job\.id\}\/cancel/);
  assert.match(comparison, /\/jobs\/\$\{job\.id\}\/retry/);
  assert.match(comparison, /answerFromCache/);
  assert.match(comparison, /answerFromInference/);
});

test("Ask progress respects reduced motion", () => {
  assert.match(
    css,
    /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.ask-job-card \.animate-spin/,
  );
  assert.match(
    css,
    /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.analysis-job-track span/,
  );
});
