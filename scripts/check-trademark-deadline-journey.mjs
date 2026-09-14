import assert from "node:assert/strict";
import { trademarkDeadlineCopy } from "../apps/web/lib/trademark-deadline-copy.ts";

export async function checkDeadlineChoice({
  click,
  fill,
  until,
  evaluate,
  json,
  record,
  copy,
}) {
  const c = trademarkDeadlineCopy["en-CH"];
  await until(
    "!!document.querySelector('[data-trademark-deadline-choice] [role=status]')",
  );
  assert.ok(
    await evaluate(
      `document.querySelector('[data-trademark-deadline-choice]').textContent.includes(${JSON.stringify(c.empty)})`,
    ),
  );
  record("no-reviewed-calendars-explained-form-remains-visible");
  await click(copy.cancel);
  await json("/__qa/state", { deadlineCalendars: true });
  await click(copy.create);
  await until(
    "document.querySelectorAll('[data-deadline-calendar] option').length===2",
  );
  await fill("[data-deadline-calendar]", "synthetic-basel");
  assert.equal(
    await evaluate("document.querySelector('[data-deadline-domicile]').value"),
    "",
  );
  assert.equal(
    await evaluate(
      "document.querySelector('[data-deadline-domicile]').checkValidity()",
    ),
    false,
  );
  await fill("[data-deadline-domicile]", "representative");
  assert.equal(
    await evaluate(
      "document.querySelector('[data-deadline-domicile]').checkValidity()",
    ),
    true,
  );
  record("explicit-calendar-and-domicile-required-without-geolocation");
}

export async function checkDeadlineView({ locale, evaluate, until, record }) {
  const c = trademarkDeadlineCopy[locale];
  await until(
    "!!document.querySelector('[data-trademark-candidate-detail] [data-trademark-deadline]')",
  );
  const text = await evaluate(
    "document.querySelector('[data-trademark-candidate-detail] [data-trademark-deadline]').textContent",
  );
  assert.ok(
    text.includes(c.title) && text.includes(c.warning) && text.includes(c.days),
  );
  assert.ok(text.includes("2026-09-15") && text.includes("Europe/Zurich"));
  assert.ok(text.includes(c.representative));
  assert.equal(
    await evaluate(
      "document.querySelector('[data-trademark-deadline] a')?.getAttribute('href')",
    ),
    "https://example.invalid/rule",
  );
  assert.ok(
    await evaluate(
      "document.querySelector('[data-trademark-change] [data-trademark-deadline]')?.textContent.includes('2026-09-15')",
    ),
  );
  record("deadline-current-history-and-references:" + locale);
}
