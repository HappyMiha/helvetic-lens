// Compiled UI with synthetic identities only; never deletes a real account.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { Cdp, evaluate, sleep } from "./browser-cdp.mjs";
import { AccessibilityAudit } from "./browser-accessibility.mjs";
import { accountCopy } from "../apps/web/lib/account-copy.ts";

const root = resolve(import.meta.dirname, ".."),
  panel = "[data-account-deletion]";
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
const profile = await mkdtemp(join(tmpdir(), "helvetic-account-browser-"));
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
const audit = new AccessibilityAudit("account-deletion"),
  errors = [],
  calls = [];
let cdp,
  locale = "en-CH",
  mode = "ready",
  held,
  deleted = false,
  checkpoints = 0;
const domains = [
  "pollen",
  "air",
  "river",
  "warnings",
  "traffic",
  "commute",
  "tenders",
  "ip",
  "auctions",
];
async function wait(fn, label) {
  for (let i = 0; i < 200; i++) {
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
async function click(selector) {
  await wait(
    () =>
      evaluate(
        cdp,
        `(()=>{const b=document.querySelector(${JSON.stringify(selector)});if(!b||b.disabled)return false;b.focus();b.click();return true;})()`,
      ),
    "Missing enabled control " + selector,
  );
}
async function navigate() {
  deleted = false;
  await evaluate(cdp, "window.__oldAccountDocument=true");
  await cdp.send("Page.navigate", { url: `${base}/account?qa=${Date.now()}` });
  await wait(
    () =>
      evaluate(
        cdp,
        `!window.__oldAccountDocument&&document.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector('${panel}')`,
      ),
    "Account unavailable",
  );
}
async function preview() {
  await click("[data-account-preview]");
  await wait(
    () =>
      evaluate(
        cdp,
        `document.querySelectorAll('${panel} dl:first-of-type dt').length===9`,
      ),
    "Nine categories missing",
  );
}
async function password() {
  await evaluate(
    cdp,
    `(()=>{const e=document.querySelector('input[type=password]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'Synthetic-pass-only-123!');e.dispatchEvent(new Event('input',{bubbles:true}));})()`,
  );
}
async function confirm() {
  await password();
  await click(`${panel} input[type=checkbox]`);
  await click(`${panel} input[type=checkbox]:not(:checked)`);
}
async function check(name) {
  assert.ok(
    await evaluate(cdp, "document.documentElement.scrollWidth<=innerWidth+1"),
    "Horizontal overflow",
  );
  await audit.check(cdp, name, panel);
  checkpoints++;
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
  cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    errors.push(
      exceptionDetails.exception?.description || exceptionDetails.text,
    ),
  );
  cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
    try {
      const path = new URL(request.url).pathname;
      calls.push({ path, method: request.method, mode });
      let data = {},
        code = 200;
      if (path === "/api/auth/session")
        data = deleted
          ? { authenticated: false }
          : {
              authenticated: true,
              user: {
                id: "owner",
                name: "Privacy QA",
                email: "privacy@example.invalid",
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
      else if (path === "/api/account/deletion" && request.method === "GET") {
        data = {
          can_delete: mode !== "blocked",
          confirmation_token: mode === "blocked" ? null : "synthetic-proof",
          categories: domains.map((domain) => ({
            domain,
            owned: 2,
            handover_required: 0,
          })),
          workspaces: [
            {
              id: "org-a",
              name: "Private workspace",
              disposition: "erase_private_workspace",
            },
          ],
          blockers:
            mode === "blocked"
              ? [
                  { kind: "workspace_administrator", organization_id: "org-a" },
                  {
                    kind: "monitor_owner",
                    organization_id: "org-b",
                    domain: "tenders",
                    monitor_id: "monitor-a",
                  },
                ]
              : [],
          personal_counts: { sessions: 3, conversations: 4, preferences: 2 },
          private_document_versions: 5,
          artifact_retention_hours: 168,
        };
        if (mode === "held") {
          held = { requestId, data };
          return;
        }
      } else if (
        path === "/api/account/deletion" &&
        request.method === "POST"
      ) {
        assert.deepEqual(JSON.parse(request.postData), {
          password: "Synthetic-pass-only-123!",
          confirmed: true,
          confirmation_token: "synthetic-proof",
          erase_workspaces: ["org-a"],
        });
        if (mode === "password") {
          code = 401;
          data = { code: "invalid_credentials" };
        } else if (mode === "changed") {
          code = 409;
          data = { code: "account_deletion_changed" };
        } else if (mode === "revoked") {
          code = 403;
          data = { code: "membership_required" };
        } else {
          deleted = true;
          data = { deleted: true, authenticated: false };
        }
      } else {
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
  for (const language of Object.keys(accountCopy))
    for (const width of [390, 1440]) {
      locale = language;
      mode = "ready";
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: width < 500,
      });
      await navigate();
      const before = calls.filter(
        (x) => x.path === "/api/account/deletion",
      ).length;
      assert.equal(
        await evaluate(
          cdp,
          `document.querySelectorAll('${panel} input').length`,
        ),
        0,
      );
      await preview();
      assert.equal(
        calls.filter((x) => x.path === "/api/account/deletion").length,
        before + 1,
      );
      assert.equal(
        await evaluate(
          cdp,
          "document.querySelectorAll('input[type=checkbox]:checked').length",
        ),
        0,
      );
      assert.ok(
        await evaluate(
          cdp,
          "document.querySelector('[data-account-erase]').disabled",
        ),
      );
      await password();
      await click(`${panel} input[type=checkbox]`);
      assert.ok(
        await evaluate(
          cdp,
          "document.querySelector('[data-account-erase]').disabled",
        ),
      );
      await click(`${panel} input[type=checkbox]:not(:checked)`);
      assert.ok(
        await evaluate(
          cdp,
          "!document.querySelector('[data-account-erase]').disabled",
        ),
      );
      await check(`${language}-${width}`);
      if (language === "en-CH") {
        const shot = await cdp.send("Page.captureScreenshot", {
          format: "png",
          captureBeyondViewport: true,
        });
        await writeFile(
          join(root, `.tmp/account-deletion-${width}.png`),
          Buffer.from(shot.data, "base64"),
        );
      }
      assert.ok(
        await evaluate(
          cdp,
          "!JSON.stringify({...localStorage,...sessionStorage}).includes('Synthetic-pass-only')",
        ),
      );
      await click("[data-account-erase]");
      await wait(
        () =>
          evaluate(
            cdp,
            `location.pathname==='/login'&&document.body.innerText.includes(${JSON.stringify(accountCopy[locale].deleted)})`,
          ),
        "Deletion success navigation missing",
      );
    }
  locale = "en-CH";
  for (const failure of ["password", "changed", "revoked"]) {
    mode = failure;
    await navigate();
    await preview();
    await confirm();
    await click("[data-account-erase]");
    await wait(
      () => evaluate(cdp, `!!document.querySelector('${panel} [role=alert]')`),
      "Failure missing",
    );
    assert.equal(
      await evaluate(
        cdp,
        "document.querySelector('input[type=password]')?.value||''",
      ),
      "",
    );
    assert.equal(
      await evaluate(cdp, "!!document.querySelector('[data-account-erase]')"),
      false,
    );
    await check(failure);
  }
  mode = "blocked";
  await navigate();
  await preview();
  assert.equal(
    await evaluate(cdp, "!!document.querySelector('[data-account-erase]')"),
    false,
  );
  await check("blocked");
  mode = "held";
  held = null;
  await navigate();
  await click("[data-account-preview]");
  await wait(() => !!held, "Preview not held");
  await evaluate(
    cdp,
    `[...document.querySelectorAll('${panel} button')].find(x=>x.textContent.trim()===${JSON.stringify(accountCopy[locale].cancel)}).click()`,
  );
  await reply(held.requestId, held.data);
  await sleep(200);
  assert.equal(
    await evaluate(cdp, "!!document.querySelector('[data-account-erase]')"),
    false,
  );
  await check("cancel-late-preview");
  assert.deepEqual(errors, []);
  audit.finish(checkpoints);
  assert.equal(checkpoints, 15);
  console.log(
    "Five-locale account deletion confirmations, nine categories, failures and cancellation passed.",
  );
} catch (error) {
  console.error({
    locale,
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
  assert.ok(basename(profile).startsWith("helvetic-account-browser-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
