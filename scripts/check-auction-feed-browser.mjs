// Built local frontend and synthetic API only. No source access, email or bids.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { resolve, join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { Cdp } from "./browser-cdp.mjs";
import { newAuctionProfile } from "../apps/web/lib/auction-watch.ts";
import { auctionCopy } from "../apps/web/lib/auction-copy.ts";
import { auctionFeedCopy } from "../apps/web/lib/auction-feed-copy.ts";
import { auctionTrackingCopy } from "../apps/web/lib/auction-tracking-copy.ts";

const url = new URL(process.argv[2]);
assert.equal(url.hostname, "127.0.0.1");
assert.equal(url.protocol, "http:");
const base = url.origin,
  root = resolve(import.meta.dirname, ".."),
  output = join(root, "test-results/accessibility");
const chrome = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
].find(existsSync);
assert.ok(chrome);
await mkdir(output, { recursive: true });
const profile = await mkdtemp(join(root, ".tmp/auction-feed-chrome-"));
const child = spawn(
  chrome,
  [
    "--headless=new",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { windowsHide: true, stdio: "ignore" },
);
let cdp;
const checks = [],
  exceptions = [];
async function bounded(promise, ms = 10000) {
  let timer;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(
          () => reject(Error("Browser operation timed out")),
          ms,
        );
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}
const call = (method, params = {}) => bounded(cdp.send(method, params));
async function evaluate(expression) {
  const response = await call("Runtime.evaluate", {
    expression,
    returnByValue: true,
  });
  if (response.exceptionDetails) throw Error(response.exceptionDetails.text);
  return response.result.value;
}
async function until(expression) {
  const end = Date.now() + 15000;
  while (Date.now() < end) {
    if (await evaluate(expression)) return;
    await delay(100);
  }
  throw Error("Condition timed out: " + expression);
}
async function json(path, body) {
  const response = await fetch(base + path, {
    ...(body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {}),
    signal: AbortSignal.timeout(3000),
  });
  assert.ok(response.ok, `${path}: ${response.status}`);
  return response.json();
}
async function click(label, scope) {
  const expression = `[...document.querySelectorAll(${JSON.stringify(scope + " button")})].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled)`;
  await until(`!!(${expression})`);
  await evaluate(`(${expression}).click()`);
}
async function navigate(path, locale = "en-CH") {
  await json("/__qa/state", { locale });
  await call("Page.navigate", { url: base + path });
}
function record(label) {
  checks.push(label);
  console.log(label);
}
async function audit(name, selector) {
  await evaluate(
    `document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'start'})`,
  );
  await evaluate(
    "(()=>{const script=document.createElement('script');script.src='/__qa/axe.js';document.head.append(script);})()",
  );
  await until("typeof window.axe==='object'");
  await evaluate(
    "(()=>{window.__auctionAudit=null;window.axe.run(document).then(v=>window.__auctionAudit={violations:v.violations,incomplete:v.incomplete.map(i=>i.id)});})()",
  );
  await until("window.__auctionAudit!==null");
  const result = await evaluate("window.__auctionAudit");
  assert.deepEqual(
    result.violations.map((v) => v.id),
    [],
  );
  await writeFile(
    join(output, `auction-feed-${name}-axe.json`),
    JSON.stringify(result, null, 2),
  );
  const shot = await call("Page.captureScreenshot", { format: "png" });
  await writeFile(
    join(output, `auction-feed-${name}.png`),
    Buffer.from(shot.data, "base64"),
  );
  record(`axe:${name}:0-violations`);
}

try {
  let port;
  const end = Date.now() + 15000;
  while (Date.now() < end) {
    try {
      port = Number(
        (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split(
          "\n",
        )[0],
      );
      break;
    } catch {
      await delay(100);
    }
  }
  assert.ok(port);
  const tabs = await fetch(`http://127.0.0.1:${port}/json/list`, {
    signal: AbortSignal.timeout(3000),
  }).then((r) => r.json());
  cdp = new Cdp(tabs.find((t) => t.type === "page").webSocketDebuggerUrl);
  cdp.on("Runtime.exceptionThrown", (value) =>
    exceptions.push(value.exceptionDetails?.text || "runtime exception"),
  );
  await bounded(cdp.ready);
  await call("Page.enable");
  await call("Runtime.enable");
  await call("Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });
  const config = newAuctionProfile();
  config.name = "Private Auction Feed";
  config.maximum_price_chf_cents = 1200000;
  await json("/__qa/state", { sourceReady: true });
  const monitor = await json("/api/auction-watch/monitors", {
    configuration: config,
    request_key: "synthetic-feed",
  });
  const path = `/api/auction-watch/monitors/${monitor.id}`;
  await json(path + "/start", { expected_version: 1 });
  await json(path + "/refresh", {});
  let item = (await json(path + "/items")).items[0];
  await json(path + `/items/${item.id}/follow`, {
    expected_version: item.version,
    following: true,
  });
  await json("/__qa/source", {
    prices: [{ kind: "current_bid", currency: "CHF", amount_minor: 1270000 }],
  });
  await json(path + "/refresh", {});
  await navigate("/");
  await until("!!document.querySelector('[data-auction-today] li a')");
  assert.ok(
    await evaluate(
      `document.querySelector('[data-auction-today]').textContent.includes(${JSON.stringify(auctionFeedCopy["en-CH"].price_above_limit)})`,
    ),
  );
  record("today-shows-private-budget-crossing");
  const link = await evaluate(
    "document.querySelector('[data-auction-today] li a').getAttribute('href')",
  );
  await evaluate("document.querySelector('[data-auction-today] li a').click()");
  await until(
    "!!document.querySelector('[data-auction-change] [data-auction-item]')",
  );
  await evaluate(
    "document.querySelector('[data-auction-change] > details').open=true",
  );
  const prices = await evaluate(
    "[...document.querySelectorAll('[data-auction-change] [data-auction-evidence] dl li')].map(e=>e.textContent.replace(/[^0-9]/g,''))",
  );
  assert.deepEqual(prices, ["850000", "1270000", "1270000"]);
  record("exact-change-link-shows-before-after-and-current-lot");
  await audit("desktop-change", "[data-auction-change]");
  await click(auctionTrackingCopy["en-CH"].inspect, "[data-auction-change]");
  await until(
    `document.querySelector('[data-auction-change] [data-auction-item] strong')?.textContent===${JSON.stringify(auctionTrackingCopy["en-CH"].reviewed)}`,
  );
  await navigate("/impact");
  await until(
    `document.querySelector('[data-auction-inbox]')?.textContent.includes(${JSON.stringify(auctionFeedCopy["en-CH"].empty)})`,
  );
  assert.equal(
    await evaluate(
      "document.querySelectorAll('[data-auction-inbox] li').length",
    ),
    0,
  );
  record("internal-review-removes-inbox-signal-without-external-action");
  await json("/__qa/source", { status: "cancelled" });
  await json(path + "/refresh", {});
  await json("/__qa/state", { manager: false });
  await call("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  });
  for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    await navigate("/impact", locale);
    await until("!!document.querySelector('[data-auction-inbox] li a')");
    assert.equal(
      await evaluate(
        "document.querySelector('[data-auction-inbox] h2').textContent",
      ),
      auctionFeedCopy[locale].inbox,
    );
    assert.ok(
      await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),
    );
    record(`mobile-viewer-inbox:${locale}`);
  }
  await audit("mobile-inbox", "[data-auction-inbox]");
  await navigate(link);
  await until(
    "!!document.querySelector('[data-auction-change] [data-auction-item]')",
  );
  assert.ok(
    !(await evaluate(
      `[...document.querySelectorAll('[data-auction-change] button')].some(b=>b.textContent.trim()===${JSON.stringify(auctionTrackingCopy["en-CH"].bid)})`,
    )),
  );
  await json("/__qa/state", { revoked: true });
  await click(auctionCopy["en-CH"].refresh, "[data-auction-detail] > div");
  await until(
    "!document.querySelector('[data-auction-change] [data-auction-evidence]')",
  );
  assert.ok(
    !(await evaluate(
      "document.body.textContent.includes('PRIVATE-AUCTION-DESCRIPTION')",
    )),
  );
  record("source-revocation-redacts-current-and-both-snapshots");
  await json("/__qa/state", { revoked: false });
  await navigate("/impact");
  await until("!!document.querySelector('[data-auction-inbox] li a')");
  await json("/__qa/state", { denied: true });
  await click(auctionCopy["en-CH"].refresh, "[data-auction-inbox]");
  await until("!document.querySelector('[data-auction-inbox]')");
  record("membership-denial-removes-private-feed");
  const requests = await json("/__qa/requests");
  assert.ok(!requests.some((r) => /\/(email|send|bid)$/.test(r.path)));
  record("no-email-source-activation-or-external-bid");
  assert.deepEqual(exceptions, []);
  await writeFile(
    join(output, "auction-feed-browser-checks.json"),
    JSON.stringify({ checks, exceptions }, null, 2),
  );
} finally {
  cdp?.close();
  child.kill();
  await json("/__qa/finish", {}).catch(() => {});
}
