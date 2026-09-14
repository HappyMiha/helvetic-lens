import assert from "node:assert/strict";
import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, readdir } from "node:fs/promises";
import { resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { trademarkExportCopy } from "../apps/web/lib/trademark-export-copy.ts";

export async function checkExport({
  locale,
  click,
  until,
  evaluate,
  json,
  call,
  record,
}) {
  const c = trademarkExportCopy[locale],
    scope = "[data-trademark-export]";
  if (locale === "de-CH") {
    await click(c.prepare, scope);
    await until(
      "!!document.querySelector('[data-trademark-export-unavailable]')",
    );
    assert.ok(
      !(await evaluate(
        "!!document.querySelector('[data-trademark-export-preview]')",
      )),
    );
    record("export-denied-without-export-rights");
    await json("/__qa/state", { exportAllowed: true });
  }
  await click(c.prepare, scope);
  await until(
    "!!document.querySelector('[data-trademark-export-preview] iframe')",
  );
  const frame = await evaluate(
    "document.querySelector('[data-trademark-export-preview] iframe').getAttribute('srcdoc')",
  );
  assert.ok(
    frame.includes(c.warning) &&
      frame.includes("Changed Owner AG") &&
      frame.includes("Synthetic Owner AG"),
  );
  assert.equal(
    await evaluate(
      "document.querySelector('[data-trademark-export-preview] iframe').getAttribute('sandbox')",
    ),
    "",
  );
  assert.ok(!frame.includes("<script"));
  record("export-localized-sandboxed-exact-change:" + locale);
  if (locale !== "en-CH") return;
  const requests = await json("/__qa/requests");
  assert.ok(!requests.some((r) => r.path.endsWith("/download")));
  record("preview-does-not-download-or-send");
  const dir = resolve(
    import.meta.dirname,
    "../.tmp/trademark-export-download-" + randomUUID(),
  );
  await mkdir(dir, { recursive: true });
  await call("Browser.setDownloadBehavior", {
    behavior: "allow",
    downloadPath: dir,
  });
  await click(c.download, scope);
  let file;
  const end = Date.now() + 10000;
  while (Date.now() < end) {
    file = (await readdir(dir)).find((p) => p.endsWith(".html"));
    if (file) break;
    await delay(100);
  }
  assert.ok(file, "Explicit download did not create an HTML file");
  const bytes = await readFile(resolve(dir, file));
  assert.equal(
    createHash("sha256").update(bytes).digest("hex"),
    createHash("sha256").update(frame).digest("hex"),
  );
  record("explicit-download-matches-inspected-packet-bytes");
  await evaluate(
    "document.querySelector('[data-trademark-export] input[type=checkbox]').click()",
  );
  await until("!document.querySelector('[data-trademark-export-preview]')");
  await click(c.prepare, scope);
  await until(
    "!!document.querySelector('[data-trademark-export-preview] iframe')",
  );
  assert.ok(
    !(await evaluate(
      "document.querySelector('[data-trademark-export-preview] iframe').getAttribute('srcdoc').includes('Synthetic Owner AG')",
    )),
  );
  record("current-only-excludes-selected-historical-evidence");
  await json("/__qa/state", { sourceRevoked: true });
  await click(c.download, scope);
  await until(
    "!!document.querySelector('[data-trademark-export-unavailable]')",
  );
  assert.ok(
    !(await evaluate(
      "!!document.querySelector('[data-trademark-export-preview] iframe')",
    )),
  );
  assert.equal(
    (await readdir(dir)).filter((f) => f.endsWith(".html")).length,
    1,
  );
  record("download-rechecks-rights-and-redacts-rejected-preview");
  await json("/__qa/state", { sourceRevoked: false });
}
