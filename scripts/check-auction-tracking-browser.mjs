import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { resolve, join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { Cdp } from "./browser-cdp.mjs";
import { auctionCopy } from "../apps/web/lib/auction-copy.ts";
import { auctionTrackingCopy } from "../apps/web/lib/auction-tracking-copy.ts";
const w = auctionTrackingCopy["en-CH"];
const origin = new URL(process.argv[2]);
assert.equal(origin.hostname, "127.0.0.1");
assert.equal(origin.protocol, "http:");
const base = origin.origin,
  root = resolve(import.meta.dirname, ".."),
  output = join(root, "test-results/accessibility"),
  c = auctionCopy["en-CH"];
const chrome = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
].find(existsSync);
assert.ok(chrome);
await mkdir(output, { recursive: true });
const profile = await mkdtemp(join(root, ".tmp/auction-tracking-chrome-"));
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
const checks = [];
async function bounded(p, ms = 10000) {
  let t;
  try {
    return await Promise.race([
      p,
      new Promise((_, reject) => {
        t = setTimeout(() => reject(Error("Browser operation timed out")), ms);
      }),
    ]);
  } finally {
    clearTimeout(t);
  }
}
const call = (method, params = {}) => bounded(cdp.send(method, params));
async function evaluate(expression) {
  const value = await call("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: false,
  });
  if (value.exceptionDetails) throw Error(value.exceptionDetails.text);
  return value.result.value;
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
  assert.ok(response.ok);
  return response.json();
}
async function click(label, scope = "[data-auction-watch]") {
  const found = `[...document.querySelectorAll(${JSON.stringify(scope + " button")})].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled&&b.getClientRects().length)`;
  await until(`!!(${found})`);
  await evaluate(`(${found}).click()`);
}
async function fill(selector, value) {
  await evaluate(
    `(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('field missing');const p=e.tagName==='SELECT'?HTMLSelectElement.prototype:e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));})()`,
  );
}
async function navigate(locale = "en-CH") {
  await json("/__qa/state", { locale });
  await call("Page.navigate", { url: base + "/auction-watch" });
  await until(
    `document.querySelector('[data-auction-watch] h1')?.textContent===${JSON.stringify(auctionCopy[locale].title)}`,
  );
  await until("!document.querySelector('[data-auction-watch] [role=status]')");
}
function record(name) {
  checks.push(name);
  console.log(name);
}
async function audit(name) {
  await evaluate(
    "(()=>{const s=document.createElement('script');s.src='/__qa/axe.js';document.head.append(s);})()",
  );
  await until("typeof window.axe==='object'");
  await evaluate(
    "(()=>{window.__ipAudit=null;window.axe.run(document).then(v=>window.__ipAudit={violations:v.violations,incomplete:v.incomplete.map(i=>({id:i.id,nodes:i.nodes.map(n=>n.target)}))},e=>window.__ipAudit={error:String(e)});})()",
  );
  await until("window.__ipAudit!==null");
  const result = await evaluate("window.__ipAudit");
  assert.ok(!result.error, result.error);
  assert.deepEqual(
    result.violations.map((v) => v.id),
    [],
  );
  await json("/__qa/audit", { name, ...result });
  const shot = await call("Page.captureScreenshot", { format: "png" });
  await writeFile(
    join(output, `auction-tracking-${name}.png`),
    Buffer.from(shot.data, "base64"),
  );
  record(`axe:${name}:0-violations`);
}
async function openProfile(locale = "en-CH") {
  await navigate(locale);
  await until("!!document.querySelector('[data-auction-watch] aside button')");
  await evaluate(
    "[...document.querySelectorAll('[data-auction-watch] aside button')].find(b=>b.textContent.includes('Tracking profile')).click()",
  );
  await until("!!document.querySelector('[data-auction-tracking]')");
}
try {
  const end = Date.now() + 15000;
  let port;
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
  await bounded(cdp.ready);
  await call("Page.enable");
  await call("Runtime.enable");
  await call("Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await navigate();
  await click(c.create);
  await fill(
    "[data-auction-form] > fieldset > label input",
    "Tracking profile",
  );
  await fill("[data-auction-form] input[inputmode=decimal]", "12000.50");
  await click(c.save);
  await until("!!document.querySelector('[data-auction-tracking]')");
  await click(w.check);
  await until(
    `document.querySelector('[data-auction-tracking]')?.textContent.includes(${JSON.stringify(w.missing)})`,
  );
  assert.ok(
    !(await evaluate(
      `[...document.querySelectorAll('[data-auction-tracking] button')].some(b=>b.textContent.trim()===${JSON.stringify(w.start)})`,
    )),
  );
  assert.ok(
    !(await json("/__qa/requests")).some((r) => r.path.endsWith("/start")),
  );
  record("missing-source-preserves-profile-without-starting");
  await json("/__qa/state", { sourceReady: true });
  await click(w.check);
  await click(w.start);
  await until(
    `document.querySelector('[data-auction-detail]')?.textContent.includes(${JSON.stringify(c.active)})`,
  );
  await click(w.refreshItems);
  await until(
    "!!document.querySelector('[data-auction-item] [data-auction-evidence]')",
  );
  assert.equal(
    await evaluate(
      "document.querySelector('[data-auction-item] [data-auction-evidence] li').textContent.replace(/[^0-9]/g,'')",
    ),
    "850000",
  );
  assert.ok(
    await evaluate(
      `document.querySelector('[data-auction-item]')?.textContent.includes(${JSON.stringify(w.match)})`,
    ),
  );
  record("start-and-discover-explained-priced-lot");
  await click(w.follow);
  await until(
    `[...document.querySelectorAll('[data-auction-item] button')].some(b=>b.textContent.trim()===${JSON.stringify(w.unfollow)})`,
  );
  await click(w.bid);
  await until(
    `document.querySelector('[data-auction-item] strong')?.textContent===${JSON.stringify(w.reviewed)}`,
  );
  record("follow-and-record-internal-considering-bid");
  await json("/__qa/source", {
    prices: [{ kind: "current_bid", currency: "CHF", amount_minor: 1270000 }],
  });
  await click(w.inspect);
  await until(
    `document.querySelector('[data-auction-item] [role=alert]')?.textContent===${JSON.stringify(c.conflict)}`,
  );
  record("new-source-state-rejects-stale-review");
  await click(w.refreshItems);
  await until(
    `document.querySelector('[data-auction-item] strong')?.textContent===${JSON.stringify(w.needsReview)}`,
  );
  assert.equal(
    await evaluate(
      "document.querySelector('[data-auction-item] [data-auction-evidence] li').textContent.replace(/[^0-9]/g,'')",
    ),
    "1270000",
  );
  await click(w.history);
  await until(
    "document.querySelectorAll('[data-auction-source-history] > details').length===2",
  );
  await evaluate(
    "document.querySelector('[data-auction-source-history] > details').open=true",
  );
  assert.ok(
    await evaluate(
      "document.body.textContent.includes('PRIVATE-AUCTION-DESCRIPTION')",
    ),
  );
  record("material-price-change-reopens-review-and-retains-history");
  await evaluate(
    "document.querySelector('[data-auction-item]').scrollIntoView({block:'start'})",
  );
  await audit("desktop");
  await json("/__qa/state", { revoked: true });
  await click(c.refresh, "[data-auction-tracking]");
  await until(
    "!document.querySelector('[data-auction-item] [data-auction-evidence]')",
  );
  assert.ok(
    !(await evaluate(
      "document.body.textContent.includes('PRIVATE-AUCTION-DESCRIPTION')",
    )),
  );
  assert.ok(
    !(await evaluate(
      "!!document.querySelector('[data-auction-source-history]')",
    )),
  );
  await click(w.unfollow);
  await until(
    `![...document.querySelectorAll('[data-auction-item] button')].some(b=>b.textContent.trim()===${JSON.stringify(w.unfollow)})`,
  );
  record("source-revocation-redacts-open-history-and-still-allows-unfollow");
  await click(w.pause);
  await until(
    `document.querySelector('[data-auction-detail]')?.textContent.includes(${JSON.stringify(c.paused)})`,
  );
  record("pause-remains-available-with-source-access-lost");
  await json("/__qa/state", { revoked: false, manager: false });
  await call("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  });
  for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    await openProfile(locale);
    await until("!!document.querySelector('[data-auction-item]')");
    const copy = auctionTrackingCopy[locale];
    assert.ok(
      await evaluate(
        `document.querySelector('[data-auction-tracking]').textContent.includes(${JSON.stringify(copy.internal)})`,
      ),
    );
    assert.ok(
      !(await evaluate(
        `[...document.querySelectorAll('[data-auction-item] button')].some(b=>b.textContent.trim()===${JSON.stringify(copy.bid)})`,
      )),
    );
    assert.ok(
      await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),
    );
    record(`private-lot-viewer-mobile:${locale}`);
  }
  await evaluate(
    "document.querySelector('[data-auction-item]').scrollIntoView({block:'start'})",
  );
  await audit("mobile");
  await click(w.history);
  await until("!!document.querySelector('[data-auction-source-history]')");
  await json("/__qa/state", { denied: true });
  await click(c.refresh, "[data-auction-tracking]");
  await until("!document.querySelector('[data-auction-item]')");
  assert.ok(
    !(await evaluate(
      "document.body.textContent.includes('PRIVATE-AUCTION-DESCRIPTION')",
    )),
  );
  record("membership-loss-redacts-private-lots-and-history");
  const requests = await json("/__qa/requests");
  assert.ok(!requests.some((r) => /\/bid$|\/send|\/email/.test(r.path)));
  record("no-external-bid-message-or-email");
} finally {
  await writeFile(
    join(output, "auction-tracking-browser-checks.json"),
    JSON.stringify(checks, null, 2),
  );
  cdp?.close();
  child.kill();
  await json("/__qa/finish", {});
}
