import assert from "node:assert/strict";
import { checkExport } from "./check-trademark-export-journey.mjs";
import { checkDeadlineView } from "./check-trademark-deadline-journey.mjs";
import { trademarkDeadlineCopy } from "../apps/web/lib/trademark-deadline-copy.ts";
import { trademarkReviewCopy } from "../apps/web/lib/trademark-review-copy.ts";
import { trademarkCopy } from "../apps/web/lib/trademark-copy.ts";

export async function checkReview({
  click,
  until,
  evaluate,
  json,
  call,
  record,
  audit,
  base,
}) {
  const f = trademarkReviewCopy["en-CH"],
    c = trademarkCopy["en-CH"];
  await click(f.check);
  await until("!!document.querySelector('[data-trademark-readiness]')");
  assert.ok(
    await evaluate(
      `[...document.querySelectorAll('[data-trademark-tracking] button')].find(b=>b.textContent===${JSON.stringify(f.start)}).disabled`,
    ),
  );
  record("missing-source-explained-start-gated-section-visible");
  await json("/__qa/state", { sourceReady: true });
  await click(f.check);
  await click(f.start);
  await click(f.scan);
  await until("!!document.querySelector('[data-trademark-candidate]')");
  await click(f.open);
  await until(
    "!!document.querySelector('[data-trademark-candidate-detail] [data-trademark-register-facts]')",
  );
  assert.ok(
    await evaluate(
      `document.querySelector('[data-trademark-explanation]').textContent.includes(${JSON.stringify(f.exact)})`,
    ),
  );
  record("start-scan-explained-private-candidate");
  await json("/__qa/state", { conflict: true });
  await click(f.relevant);
  await until(
    "!!document.querySelector('[data-trademark-candidate-detail] [role=alert]')",
  );
  await json("/__qa/state", { conflict: false });
  await click(f.counsel);
  await until(
    `document.querySelector('[data-trademark-reviews]')?.textContent.includes(${JSON.stringify(f.counsel)})`,
  );
  record("review-version-conflict-and-private-counsel-marker");
  await json("/__qa/state", { registerOwner: "Changed Owner AG" });
  await click(f.scan);
  await until("!document.querySelector('[data-trademark-candidate-detail]')");
  await click(f.open);
  await until(
    "document.querySelector('[data-trademark-candidate-detail]')?.textContent.includes('Changed Owner AG')",
  );
  assert.ok(
    await evaluate(
      `document.querySelector('[data-trademark-candidate-detail]').textContent.includes(${JSON.stringify(f.needsReview)})`,
    ),
  );
  record("register-owner-change-reopens-review-keeps-decision");
  const page = await json("/api/trademark-watch/inbox"),
    exact = page.items[0].href;
  await call("Page.navigate", { url: base + "/impact" });
  await until("!!document.querySelector('[data-trademark-inbox] li a')");
  assert.equal(
    await evaluate(
      "document.querySelector('[data-trademark-inbox] li a').getAttribute('href')",
    ),
    exact,
  );
  record("inbox-links-exact-private-change");
  assert.ok(
    await evaluate(
      "document.querySelector('[data-trademark-inbox] [data-trademark-deadline]')?.textContent.includes('2026-09-15')",
    ),
  );
  record("deadline-shown-in-inbox");
  await evaluate(
    "document.querySelector('[data-trademark-inbox] li a').click()",
  );
  await until(
    "!!document.querySelector('[data-trademark-change] [data-trademark-register-facts]')",
  );
  assert.ok(
    await evaluate(
      "document.querySelector('[data-trademark-change]').textContent.includes('Synthetic Owner AG') && document.querySelector('[data-trademark-change]').textContent.includes('Changed Owner AG')",
    ),
  );
  record("exact-change-displays-before-and-at-detection");
  await call("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  });
  for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    await json("/__qa/state", { locale });
    await call("Page.navigate", { url: base + exact });
    await until(
      "!!document.querySelector('[data-trademark-candidate-detail] [data-trademark-register-facts]')",
    );
    assert.ok(
      await evaluate(
        `document.querySelector('[data-trademark-tracking]').textContent.includes(${JSON.stringify(trademarkReviewCopy[locale].internal)})`,
      ),
    );
    assert.ok(
      await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),
      locale,
    );
    record("mobile-review:" + locale);
    await checkDeadlineView({ locale, evaluate, until, record });
    await checkExport({ locale, click, until, evaluate, json, call, record });
  }
  await evaluate(
    "document.querySelector('[data-trademark-candidate-detail] [data-trademark-deadline]').scrollIntoView({block:'center'})",
  );
  await audit("review-mobile");
  await json("/__qa/state", { deadlineMissing: true });
  await evaluate("window.dispatchEvent(new Event('focus'))");
  await until(
    `document.querySelector('[data-trademark-candidate-detail] [data-trademark-deadline]')?.textContent.includes(${JSON.stringify(trademarkDeadlineCopy["en-CH"].calendarMissing)})`,
  );
  assert.ok(
    !(await evaluate(
      "document.querySelector('[data-trademark-candidate-detail] [data-trademark-deadline]').textContent.includes('2026-09-15')",
    )),
  );
  record("missing-calendar-redacts-date-with-visible-explanation");
  await json("/__qa/state", { deadlineMissing: false });
  await json("/__qa/state", { sourceRevoked: true });
  await evaluate("window.dispatchEvent(new Event('focus'))");
  await until(
    `document.querySelector('[data-trademark-candidate-detail]')?.textContent.includes(${JSON.stringify(f.unavailable)})`,
  );
  await until("!!document.querySelector('[data-trademark-change]')");
  assert.ok(
    !(await evaluate(
      "document.querySelector('[data-trademark-tracking]').textContent.includes('Changed Owner AG')",
    )),
  );
  assert.ok(
    await evaluate(
      "[...document.querySelectorAll('[data-trademark-decision]')].every(b=>b.disabled)",
    ),
  );
  record("focus-refresh-redacts-current-and-historical-source-facts");
  assert.ok(
    !(await evaluate(
      "document.querySelector('[data-trademark-tracking]').textContent.includes('SYNTHETIC-PUBLICATION')",
    )),
  );
  record("source-revocation-redacts-deadline-source-evidence");
  await json("/__qa/state", { sourceRevoked: false });
  await call("Page.navigate", { url: base + exact });
  await until(
    "!!document.querySelector('[data-trademark-candidate-detail] [data-trademark-register-facts]')",
  );
  await click(f.reviewed, "[data-trademark-candidate-detail]");
  await until(
    `document.querySelector('[data-trademark-reviews]')?.textContent.includes(${JSON.stringify(f.reviewed)})`,
  );
  await call("Page.navigate", { url: base + "/" });
  await until(
    `document.querySelector('[data-trademark-today]')?.textContent.includes(${JSON.stringify(f.empty)})`,
  );
  record("review-clears-today-pending-item");
  await call("Page.navigate", { url: base + exact });
  await until("!!document.querySelector('[data-trademark-tracking]')");
  await click(f.pause);
  await until(
    `document.querySelector('[data-trademark-detail]')?.textContent.includes(${JSON.stringify(c.paused)})`,
  );
  record("pause-restores-portfolio-editing");
}
