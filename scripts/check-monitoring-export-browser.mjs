// Actual compiled settings page and browser downloads; synthetic API data only.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import {
  mkdtemp,
  readFile,
  readdir,
  rm,
  unlink,
  writeFile,
} from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { monitoringExportCopy as copy } from "../apps/web/lib/monitoring-export-copy.ts";

const root = resolve(import.meta.dirname, ".."),
  panel = "[data-configuration-export]";
const configs = JSON.parse(
  await readFile(
    join(root, "scripts/fixtures/monitoring-configurations.json"),
    "utf8",
  ),
);
const domains = Object.keys(configs),
  endpoint = "/api/monitoring-centre/configuration/export";
const chrome = [
  process.env.CHROME_BIN,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/google-chrome",
]
  .filter(Boolean)
  .find(existsSync);
assert.ok(chrome);
const reserve = createServer();
await new Promise((r) => reserve.listen(0, "127.0.0.1", r));
const port = reserve.address().port;
await new Promise((r) => reserve.close(r));
const base = `http://127.0.0.1:${port}`;
const server = spawn(
  process.execPath,
  [
    join(root, "node_modules/next/dist/bin/next"),
    "start",
    "-H",
    "127.0.0.1",
    "-p",
    String(port),
  ],
  { cwd: join(root, "apps/web"), stdio: "ignore", windowsHide: true },
);
const profile = await mkdtemp(join(tmpdir(), "helvetic-export-browser-"));
const downloadDir = await mkdtemp(
  join(root, ".tmp/settings-export-downloads-"),
);
const browser = spawn(
  chrome,
  [
    "--headless=new",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: "ignore", windowsHide: true },
);
let cdp,
  locale = "en-CH",
  domain = "river",
  mode = "ready",
  held,
  checks = 0;
const errors = [],
  calls = [],
  audit = new AccessibilityAudit("monitoring-configuration-export");
async function wait(fn, label) {
  for (let n = 0; n < 200; n++) {
    if (
      await Promise.resolve()
        .then(fn)
        .catch(() => false)
    )
      return;
    await sleep(100);
  }
  throw new Error(label);
}
async function reply(requestId, data, code = 200) {
  await cdp
    .send("Fetch.fulfillRequest", {
      requestId,
      responseCode: code,
      responseHeaders: [{ name: "Content-Type", value: "application/json" }],
      body: Buffer.from(JSON.stringify(data)).toString("base64"),
    })
    .catch(() => {});
}
async function button(label) {
  await wait(
    () =>
      evaluate(
        cdp,
        `(()=>{const b=[...document.querySelectorAll('${panel} button')].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled);if(!b)return false;b.focus();b.click();return true;})()`,
      ),
    "Missing button " + label,
  );
}
async function navigate() {
  await evaluate(cdp, "window.__oldExportDocument=true");
  await cdp.send("Page.navigate", {
    url: `${base}/monitoring/settings?category=${domain}&qa=${Date.now()}`,
  });
  await wait(
    () =>
      evaluate(
        cdp,
        `!window.__oldExportDocument&&document.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector('${panel}')`,
      ),
    "Settings unavailable",
  );
}
async function check(name) {
  assert.ok(
    await evaluate(cdp, "document.documentElement.scrollWidth<=innerWidth+1"),
    "Overflow",
  );
  await audit.check(cdp, name, panel);
  checks++;
}
function item(kind, index) {
  const payload = {
    domain: kind,
    id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    configuration: configs[kind],
    configuration_revision: 2,
    status: "archived",
    email_preferences: { revision: 0, configuration: null },
  };
  const canonical_json = JSON.stringify(payload);
  return {
    ...payload,
    canonical_json,
    sha256: createHash("sha256").update(canonical_json).digest("hex"),
  };
}
async function downloaded(expected) {
  await wait(
    async () =>
      (await readdir(downloadDir)).some((file) => file.endsWith(".json")),
    "Download missing",
  );
  const files = (await readdir(downloadDir)).filter((file) =>
    file.endsWith(".json"),
  );
  assert.equal(files.length, 1);
  const file = join(downloadDir, files[0]);
  let archive;
  await wait(async () => {
    archive = JSON.parse(await readFile(file, "utf8"));
    return true;
  }, "Download not completely written");
  assert.equal(archive.count, expected.length);
  assert.deepEqual(
    archive.items.map((row) => row.domain).sort(),
    [...expected].sort(),
  );
  assert.equal(archive.owner_user_id, "owner");
  assert.equal(archive.organization_id, "org-a");
  for (const row of archive.items)
    assert.equal(
      createHash("sha256").update(row.canonical_json).digest("hex"),
      row.sha256,
    );
  assert.ok(archive.excludes.includes("connector_credentials"));
  await unlink(file);
}
try {
  await wait(async () => (await fetch(base)).ok, "Next unavailable");
  let debug;
  await wait(async () => {
    debug = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split(
      "\n",
    )[0];
    return !!debug;
  }, "Chrome unavailable");
  const target = await fetch(`http://127.0.0.1:${debug}/json/new?about:blank`, {
    method: "PUT",
  }).then((r) => r.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Browser.setDownloadBehavior", {
    behavior: "allow",
    downloadPath: downloadDir,
  });
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    errors.push(
      exceptionDetails.exception?.description || exceptionDetails.text,
    ),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    try {
      const url = new URL(request.url),
        path = url.pathname;
      calls.push({ path, method: request.method, mode });
      let data = {},
        code = 200;
      if (path === "/api/auth/session")
        data = {
          authenticated: true,
          user: {
            id: "owner",
            name: "Export QA",
            email: "export@example.invalid",
            locale,
          },
          organization: { id: "org-a", name: "Synthetic workspace" },
          role: "viewer",
          platform_admin: false,
          onboarding_required: false,
        };
      else if (path === "/api/health")
        data = {
          status: "ok",
          database: "synthetic",
          apertus: { configured: false },
          firecrawl: { configured: false },
        };
      else if (path === "/api/jobs") data = [];
      else if (path === "/api/monitoring-settings")
        data = { can_configure_connectors: false, items: [] };
      else if (path === endpoint) {
        const selected = url.searchParams.get("domain"),
          kinds = mode === "empty" ? [] : selected ? [selected] : domains;
        const offset = url.searchParams.has("cursor") ? 2 : 0;
        const items = kinds
          .slice(offset, offset + 2)
          .map((kind) => item(kind, domains.indexOf(kind)));
        // A second page contains the rest, proving the client does not stop early.
        if (offset)
          items.splice(
            0,
            items.length,
            ...kinds
              .slice(offset)
              .map((kind) => item(kind, domains.indexOf(kind))),
          );
        data = {
          format: "helvetic-lens-monitoring-configuration-v1",
          scope: [mode === "scope" ? "org-other" : "org-a", "owner", selected],
          started_at: "2026-09-14T12:00:00Z",
          read_at: "2026-09-14T12:01:00Z",
          items,
          next_cursor: offset || kinds.length <= 2 ? null : "second-page",
        };
        if (mode === "corrupt" && items.length)
          items[0].sha256 = "0".repeat(64);
        if (mode === "page-failure" && offset) {
          code = 503;
          data = { code: "unavailable" };
        }
        if (mode === "held") {
          held = { requestId, data };
          return;
        }
      } else if (path === endpoint + "/verify") {
        const body = JSON.parse(request.postData);
        assert.ok(
          body.items.every(
            (row) => Object.keys(row).sort().join() === "domain,id,sha256",
          ),
        );
        data = { verified: body.items.length, scope: ["org-a", "owner"] };
        if (mode === "revoked") {
          code = 403;
          data = { code: "membership_required" };
        }
      } else if (path.endsWith("/capabilities"))
        data = {
          drafts_available: true,
          public_source_available: false,
          start_available: false,
        };
      else if (
        path.endsWith("/monitors") ||
        path === "/api/monitoring-subjects"
      )
        data = { items: [], next_cursor: null };
      else if (path.endsWith("/stations")) data = { stations: [] };
      else {
        code = 503;
        data = { code: "unavailable" };
      }
      await reply(requestId, data, code);
    } catch (error) {
      errors.push(String(error));
      await reply(requestId, { code: "fixture_failed" }, 500);
    }
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: `${base}/api/*`, requestStage: "Request" }],
  });
  await cdp.send("Network.setCookie", {
    name: "helvetic_lens_csrf",
    value: "synthetic",
    url: base,
  });
  for (const language of Object.keys(copy))
    for (const width of [390, 1440]) {
      locale = language;
      domain = "river";
      mode = "ready";
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: false,
      });
      await navigate();
      await button(copy[locale].all);
      await downloaded(domains);
      await wait(
        () =>
          evaluate(
            cdp,
            `document.querySelector('${panel}').innerText.includes(${JSON.stringify(copy[locale].complete)})`,
          ),
        "Completion missing",
      );
      await check(`${locale}-${width}-all`);
      if (locale === "en-CH")
        await writeFile(
          join(root, `test-results/settings-export-${width}.png`),
          Buffer.from(
            (await cdp.send("Page.captureScreenshot", { format: "png" })).data,
            "base64",
          ),
        );
    }
  locale = "en-CH";
  for (const kind of domains) {
    domain = kind;
    mode = "ready";
    await navigate();
    await button(copy[locale].category);
    await downloaded([kind]);
    await check(`category-${kind}`);
  }
  domain = "river";
  for (const failure of ["scope", "corrupt", "page-failure", "revoked"]) {
    mode = failure;
    await navigate();
    await button(copy[locale].all);
    await wait(
      () => evaluate(cdp, `!!document.querySelector('${panel} [role=alert]')`),
      "Failure not shown",
    );
    assert.deepEqual(await readdir(downloadDir), []);
    await check(failure);
  }
  mode = "held";
  held = null;
  await navigate();
  await button(copy[locale].all);
  await wait(() => !!held, "Request not held");
  await button(copy[locale].cancel);
  await reply(held.requestId, held.data);
  await sleep(200);
  assert.deepEqual(await readdir(downloadDir), []);
  await check("cancel-late");
  mode = "empty";
  await navigate();
  await button(copy[locale].all);
  await downloaded([]);
  await check("empty");
  assert.deepEqual(errors, []);
  assert.ok(
    calls
      .filter((row) => row.method !== "GET" && !["/api/assistant/context", "/api/assistant/conversations"].includes(row.path))
      .every((row) => row.path === endpoint + "/verify"),
  );
  audit.finish(25);
  console.log(
    "Owned settings downloads, nine category selection, pagination and failure handling passed.",
  );
} catch (error) {
  console.error({
    locale,
    domain,
    mode,
    errors,
    recent: calls.slice(-8),
    text: cdp
      ? await evaluate(cdp, "document.body.innerText").catch(() => "")
      : "",
  });
  throw error;
} finally {
  cdp?.close();
  for (const child of [browser, server]) {
    const done = new Promise((r) => child.once("exit", r));
    child.kill();
    await Promise.race([done, sleep(2000)]);
  }
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-export-browser-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
  assert.equal(dirname(resolve(downloadDir)), join(root, ".tmp"));
  assert.ok(basename(downloadDir).startsWith("settings-export-downloads-"));
  await rm(downloadDir, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
