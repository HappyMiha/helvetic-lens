import assert from "node:assert/strict";
import { ipiSourceCopy } from "../apps/web/lib/ipi-source-copy.ts";

export async function checkIPI({ click, until, evaluate, json, record }) {
  const copy = ipiSourceCopy["en-CH"];
  const content =
    "document.querySelector('[data-ipi-source-status]')?.textContent";
  await until(
    `${content}?.includes(${JSON.stringify(copy.permission_required)})`,
  );
  record("ipi-permission-required-visible-without-hiding-portfolios");
  for (const state of ["credentials_required", "permission_unavailable"]) {
    await json("/__qa/state", { ipiStatus: { state, traversal: null } });
    await click(copy.refresh);
    await until(`${content}?.includes(${JSON.stringify(copy[state])})`);
    record("ipi-" + state);
  }
  for (const state of ["running", "completed", "abandoned"]) {
    await json("/__qa/state", {
      ipiStatus: {
        state: "configured",
        coverage_verified: false,
        traversal: {
          state,
          page_count: 7,
          unique_count: 430,
          duplicate_count: 18,
          next_attempt_at: "2026-09-15T12:30:00Z",
          completed_at: state === "completed" ? "2026-09-14T12:30:00Z" : null,
          last_error: state === "abandoned" ? "ipi_continuation_expired" : null,
        },
      },
    });
    await click(copy.refresh);
    await until(`${content}?.includes(${JSON.stringify(copy[state])})`);
    assert.ok(
      await evaluate(`${content}?.includes(${JSON.stringify(copy.limit)})`),
    );
    assert.ok(
      await evaluate(
        `${content}?.includes("430") && ${content}?.includes("18")`,
      ),
    );
    record("ipi-" + state + "-counts-without-coverage-claim");
  }
  const before = (await json("/__qa/requests")).filter(
    (r) => r.method !== "GET",
  ).length;
  await click(copy.refresh);
  await until("!!document.querySelector('[data-ipi-source-status] dl')");
  assert.equal(
    (await json("/__qa/requests")).filter((r) => r.method !== "GET").length,
    before,
  );
  record("ipi-status-refresh-never-starts-source-collection");
  await json("/__qa/state", { ipiStatus: null });
  await click(copy.refresh);
  await until(
    `${content}?.includes(${JSON.stringify(copy.permission_required)})`,
  );
}
