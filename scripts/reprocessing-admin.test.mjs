import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

function load(name) {
  const scope = { exports: {} };
  vm.runInNewContext(
    ts.transpileModule(
      fs.readFileSync(
        new URL(`../apps/web/lib/${name}.ts`, import.meta.url),
        "utf8",
      ),
      {
        compilerOptions: {
          module: ts.ModuleKind.CommonJS,
          target: ts.ScriptTarget.ES2022,
        },
      },
    ).outputText,
    scope,
  );
  return scope.exports;
}
const { canApplyReprocessing, reprocessingResult, readReprocessingIntent } =
  load("reprocessing");
const { jobResultHref } = load("job-links");
function preview() {
  return {
    id: "saved-job",
    type: "relation_candidate_reprocess",
    state: "succeeded",
    maintenance: { dry_run: true, rule_revision: "rule-2" },
    result: {
      data: {
        status: "complete",
        has_more: false,
        dry_run: true,
        rule_revision: "rule-2",
        processed: 25,
        eligible: 25,
        changed: 3,
        retained: 20,
        rejected: 3,
        skipped: 2,
        batches: 1,
        examples: [],
      },
    },
  };
}
test("only a completed current-rule preview with actual changes admits apply", () => {
  assert.equal(canApplyReprocessing(preview(), "rule-2"), true);
  for (const mutate of [
    (j) => (j.state = "running"),
    (j) => (j.state = "cancelled"),
    (j) => (j.maintenance.dry_run = false),
    (j) => (j.maintenance.rule_revision = "rule-1"),
    (j) => (j.result.data.rule_revision = "rule-1"),
    (j) => (j.result.data.status = "superseded"),
    (j) => (j.result.data.has_more = true),
    (j) => (j.result.data.changed = 0),
    (j) => (j.result.data.changed = NaN),
    (j) => (j.result.data.changed = 26),
    (j) => (j.result.data.dry_run = undefined),
    (j) => (j.result.data.retained = 0),
    (j) => (j.result.data.examples = [{ reason: "unsafe shape" }]),
    (j) => (j.type = "scan"),
  ]) {
    const job = preview();
    mutate(job);
    assert.equal(canApplyReprocessing(job, "rule-2"), false);
  }
  assert.equal(canApplyReprocessing(preview(), undefined), false);
});
test("supersession before a first batch still has a readable zero-count result", () => {
  const job = preview();
  Object.assign(job.result.data, {
    status: "superseded",
    eligible: null,
    processed: 0,
    changed: 0,
    retained: 0,
    rejected: 0,
    skipped: 0,
    batches: 0,
  });
  assert.equal(reprocessingResult(job).eligible, 0);
  assert.equal(canApplyReprocessing(job, "rule-2"), false);
});
test("request recovery retains a validated UUID, mode and the original rule", () => {
  const intent = {
    request_id: "11111111-2222-4333-8444-555555555555",
    dry_run: false,
    rule_revision: "rule-2",
  };
  assert.equal(
    JSON.stringify(readReprocessingIntent(JSON.stringify(intent))),
    JSON.stringify(intent),
  );
  for (const invalid of [
    null,
    "invalid",
    JSON.stringify({ ...intent, dry_run: "false" }),
    JSON.stringify({ ...intent, request_id: "bad" }),
    JSON.stringify({ ...intent, rule_revision: null }),
  ])
    assert.equal(readReprocessingIntent(invalid), null);
});
test("maintenance jobs open their persisted result instead of looping to activity", () => {
  const job = preview();
  job.result.url = "/activity";
  assert.equal(
    jobResultHref(job),
    "/admin/relation-reprocessing?job=saved-job",
  );
});
test("all five locales contain the complete maintenance interface copy", () => {
  const { reprocessingCopy } = load("reprocessing-copy");
  const keys = Object.keys(reprocessingCopy["en-CH"]).sort();
  for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    assert.deepEqual(Object.keys(reprocessingCopy[locale]).sort(), keys);
    assert.ok(
      Object.values(reprocessingCopy[locale]).every(
        (value) =>
          typeof value === "string" &&
          value.length > 2 &&
          !value.includes("undefined"),
      ),
    );
  }
});
