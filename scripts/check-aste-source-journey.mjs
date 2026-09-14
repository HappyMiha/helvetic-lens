import assert from "node:assert/strict";
import { asteSourceCopy } from "../apps/web/lib/aste-source-copy.ts";

export async function checkAste({ click, until, evaluate, json, record, call, navigate, audit }) {
  const scope = "[data-aste-source-status]";
  const content = "document.querySelector('[data-aste-source-status]')?.textContent";
  const c = asteSourceCopy["en-CH"];
  await until(`${content}?.includes(${JSON.stringify(c.permission_required)})`);
  record("aste-access-gap-visible-with-profile-creation");
  for (const state of ["waiting", "permission_unavailable", "disabled"]) {
    await json("/__qa/state", { asteStatus: { state, collection: null } });
    await click(c.refresh, scope);
    await until(`${content}?.includes(${JSON.stringify(c[state])})`);
    assert.ok(await evaluate("!!document.querySelector('[data-auction-watch] aside')"));
    record("aste-" + state + "-keeps-section-visible");
  }
  const collection = {
    known_items: 119, failed_items: 2, pending_listing_pages: 8,
    last_record_at: "2026-09-14T02:30:00Z",
    last_completed_at: "2026-09-14T01:30:00Z",
    next_request_at: "2026-09-14T03:00:00Z",
    last_error: "aste_http_429",
    source_categories: ["Biciclette", "E-Bike", "Scultura in bronzo"],
  };
  await json("/__qa/state", { asteStatus: { state: "configured", collection } });
  await click(c.refresh, scope);
  await until(`${content}?.includes(${JSON.stringify(c.interruption)})`);
  assert.ok(await evaluate(`${content}?.includes("119") && ${content}?.includes("Biciclette")`));
  assert.ok(await evaluate(`${content}?.includes(${JSON.stringify(c.limit)})`));
  assert.equal(await evaluate("document.querySelectorAll('[data-aste-source-status] time').length"), 3);
  assert.ok(!(await evaluate(`${content}?.includes("aste_http_429")`)));
  await audit("aste-source-desktop");
  record("aste-partial-collection-and-backoff-visible-without-coverage-claim");
  await json("/__qa/state", { sourceStatusError: true });
  await click(c.refresh, scope);
  await until(`${content}?.includes(${JSON.stringify(c.failed)})`);
  assert.equal(await evaluate("document.querySelectorAll('[data-aste-source-status] time').length"), 0);
  record("aste-fetch-failure-clears-stale-collection-details");
  await json("/__qa/state", { sourceStatusError: false, asteStatus: null });
  await click(c.refresh, scope);
  await until(`${content}?.includes(${JSON.stringify(c.permission_required)})`);
  await call("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    await navigate(locale);
    const copy = asteSourceCopy[locale];
    await until(`${content}?.includes(${JSON.stringify(copy.permission_required)})`);
    const before = (await json("/__qa/requests")).filter(r => r.method !== "GET").length;
    await click(copy.refresh, scope);
    await until(`${content}?.includes(${JSON.stringify(copy.permission_required)})`);
    assert.equal((await json("/__qa/requests")).filter(r => r.method !== "GET").length, before);
    assert.ok(await evaluate("document.documentElement.scrollWidth <= innerWidth"));
    record("aste-mobile-read-only-status:" + locale);
  }
  await audit("aste-source-mobile");
  await call("Emulation.setDeviceMetricsOverride", { width: 1280, height: 1000, deviceScaleFactor: 1, mobile: false });
}
