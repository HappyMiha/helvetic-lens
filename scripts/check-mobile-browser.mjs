import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const baseUrl = process.env.HELVETIC_LENS_WEB_URL || "http://127.0.0.1:3000";
const comparisonId = process.env.HELVETIC_LENS_QA_COMPARISON_ID || "";
const chromeCandidates = [
  process.env.CHROME_BIN,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
].filter(Boolean);
const chrome = chromeCandidates.find(existsSync);
assert.ok(chrome, "Set CHROME_BIN to a Chrome or Chromium executable.");

const sleep = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

class Cdp {
  constructor(url) {
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
    this.socket = new WebSocket(url);
    this.ready = new Promise((resolve, reject) => {
      this.socket.addEventListener("open", resolve, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const pending = this.pending.get(message.id);
        if (!pending) return;
        this.pending.delete(message.id);
        if (message.error) pending.reject(new Error(message.error.message));
        else pending.resolve(message.result);
        return;
      }
      for (const listener of this.listeners.get(message.method) || []) {
        void listener(message.params || {});
      }
    });
    const rejectPending = (reason) => {
      for (const pending of this.pending.values()) pending.reject(reason);
      this.pending.clear();
    };
    this.socket.addEventListener("close", () =>
      rejectPending(new Error("Chrome closed the DevTools connection.")),
    );
    this.socket.addEventListener("error", () =>
      rejectPending(new Error("Chrome DevTools connection failed.")),
    );
  }

  on(method, listener) {
    const listeners = this.listeners.get(method) || [];
    listeners.push(listener);
    this.listeners.set(method, listeners);
  }

  async send(method, params = {}) {
    await this.ready;
    const id = this.nextId++;
    const result = new Promise((resolve, reject) =>
      this.pending.set(id, { resolve, reject }),
    );
    this.socket.send(JSON.stringify({ id, method, params }));
    return result;
  }

  close() {
    this.socket.close();
  }
}

async function pollJson(url, timeout = 10_000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.json();
    } catch {}
    await sleep(100);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function evaluate(cdp, expression) {
  const response = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (response.exceptionDetails) {
    throw new Error(
      response.exceptionDetails.exception?.description ||
        response.exceptionDetails.text ||
        "Browser evaluation failed",
    );
  }
  return response.result.value;
}

async function waitFor(cdp, expression, message, timeout = 10_000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await evaluate(cdp, expression).catch(() => false)) return;
    await sleep(100);
  }
  throw new Error(message);
}

async function navigate(cdp, path) {
  const targetUrl = new URL(path, baseUrl);
  await cdp.send("Page.navigate", { url: targetUrl.href });
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    const ready = await evaluate(
      cdp,
      `location.pathname === ${JSON.stringify(targetUrl.pathname)} && document.readyState === "complete" && !!document.querySelector(".shell, main")`,
    ).catch(() => false);
    if (ready) {
      await sleep(350);
      return;
    }
    await sleep(100);
  }
  throw new Error(`Timed out loading ${path}`);
}

const auditExpression = `(() => {
  const visible = (element) => {
    if (!element) return false;
    const style = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
  };
  const critical = Array.from(document.querySelectorAll(
    '[data-slot="button"], [data-slot="input"], select, .mobile-nav a, .mobile-nav summary, .comparison-task-tabs [role="tab"], .companion-close, [data-slot="dialog-close"]'
  )).filter(visible);
  const undersized = critical
    .map((element) => {
      const box = element.getBoundingClientRect();
      return { label: element.getAttribute("aria-label") || element.textContent.trim().slice(0, 60), width: box.width, height: box.height };
    })
    .filter((item) => item.width < 43.5 || item.height < 43.5);
  return {
    path: location.pathname,
    title: document.title,
    text: document.body.innerText.trim().slice(0, 240),
    width: innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
    horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1 || document.body.scrollWidth > innerWidth + 1,
    mobileNavVisible: visible(document.querySelector(".mobile-nav")),
    primaryDestinations: Array.from(document.querySelectorAll(".mobile-nav > a")).map((item) => item.getAttribute("href")),
    undersized,
  };
})()`;

async function auditRoute(
  cdp,
  width,
  height,
  path,
  role,
  expectNavigation = true,
  shouldNavigate = true,
) {
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: true,
  });
  if (shouldNavigate) await navigate(cdp, path);
  else await sleep(150);
  let audit = await evaluate(cdp, auditExpression);
  if (expectNavigation && !audit.mobileNavVisible) {
    const deadline = Date.now() + 10_000;
    while (Date.now() < deadline && !audit.mobileNavVisible) {
      await sleep(100);
      audit = await evaluate(cdp, auditExpression);
    }
  }
  assert.equal(audit.horizontalOverflow, false, `${role} ${path} overflows at ${width}px: ${JSON.stringify(audit)}`);
  if (expectNavigation) {
    assert.equal(audit.mobileNavVisible, true, `${role} ${path} has no mobile navigation at ${width}px: ${JSON.stringify(audit)}`);
    assert.deepEqual(audit.primaryDestinations, ["/", "/registry", "/impact", "/discover"]);
  }
  assert.deepEqual(audit.undersized, [], `${role} ${path} has undersized controls: ${JSON.stringify(audit.undersized)}`);
}

async function installViewerSession(cdp) {
  cdp.on("Fetch.requestPaused", async (event) => {
    try {
      if (!event.responseStatusCode || !event.request.url.includes("/api/auth/session")) {
        await cdp.send("Fetch.continueRequest", { requestId: event.requestId });
        return;
      }
      const response = await cdp.send("Fetch.getResponseBody", {
        requestId: event.requestId,
      });
      const session = JSON.parse(
        response.base64Encoded
          ? Buffer.from(response.body, "base64").toString("utf8")
          : response.body,
      );
      const viewer = {
        ...session,
        authenticated: true,
        anonymous_development: false,
        authentication_required: false,
        onboarding_required: false,
        role: "viewer",
        platform_admin: false,
        user: { id: "qa-viewer", email: "viewer@example.test", name: "QA Viewer", locale: "en-CH" },
        organization: session.organization || { id: "qa-organization", name: "QA Organization" },
        organizations: [],
      };
      const headers = (event.responseHeaders || []).filter(
        (header) => !["content-length", "content-encoding"].includes(header.name.toLowerCase()),
      );
      await cdp.send("Fetch.fulfillRequest", {
        requestId: event.requestId,
        responseCode: event.responseStatusCode,
        responseHeaders: headers,
        body: Buffer.from(JSON.stringify(viewer)).toString("base64"),
      });
    } catch (error) {
      console.error("Viewer response interception failed:", error.message);
      await cdp.send("Fetch.continueRequest", { requestId: event.requestId }).catch(() => {});
    }
  });
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: "*api/auth/session*", requestStage: "Response" }],
  });
}

const profile = await mkdtemp(join(tmpdir(), "helvetic-lens-mobile-"));
const port = 9300 + Math.floor(Math.random() * 400);
const browser = spawn(
  chrome,
  [
    "--headless=new",
    // Chrome's Windows sandbox can make its GPU process exit before CDP is
    // available in CI and restricted desktop sessions. This disposable local
    // profile never loads an external URL.
    "--no-sandbox",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: "ignore" },
);

let admin;
let viewer;
let states;
try {
  await pollJson(`http://127.0.0.1:${port}/json/version`);
  const adminTarget = await fetch(
    `http://127.0.0.1:${port}/json/new?${encodeURIComponent("about:blank")}`,
    { method: "PUT" },
  ).then((response) => response.json());
  admin = new Cdp(adminTarget.webSocketDebuggerUrl);
  await Promise.all([admin.send("Page.enable"), admin.send("Runtime.enable"), admin.send("Network.enable")]);

  for (const path of ["/", "/registry", "/impact", "/discover", "/digests", "/sources", "/organization"]) {
    for (const [index, width] of [360, 390, 430].entries()) {
      await auditRoute(admin, width, 844, path, "admin", true, index === 0);
    }
  }
  // First-run onboarding intentionally has its own focused shell.
  for (const [index, width] of [360, 390, 430].entries()) {
    await auditRoute(admin, width, 844, "/onboarding", "admin", false, index === 0);
  }
  await auditRoute(admin, 768, 1024, "/registry", "admin");

  await navigate(admin, "/organization");
  const localeOptions = await evaluate(
    admin,
    `Array.from(document.querySelector('.language-selector select')?.options || []).map((option) => option.value)`,
  );
  assert.deepEqual(localeOptions, ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]);
  for (const locale of localeOptions) {
    await evaluate(
      admin,
      `(() => {
        const select = document.querySelector('.language-selector select');
        select.value = ${JSON.stringify(locale)};
        select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`,
    );
    await sleep(100);
    assert.equal(await evaluate(admin, "document.documentElement.lang"), locale);
    await auditRoute(admin, 390, 844, "/organization", `admin ${locale}`, true, false);
  }

  await navigate(admin, "/sources");
  await waitFor(admin, `document.querySelectorAll('.source-pack-card').length === 5`, "Swiss Federal Starter subpacks did not render");
  await waitFor(admin, `document.querySelectorAll('.official-coverage-card').length === 6`, "Official source capability families did not render");
  await auditRoute(admin, 390, 844, "/sources", "source capability catalogue", true, false);
  await navigate(admin, "/connectors");
  await waitFor(admin, `document.querySelectorAll('.capability-contract').length === 23`, "Operator source capability contracts did not render");
  await auditRoute(admin, 390, 844, "/connectors", "operator capability catalogue", true, false);

  if (comparisonId) {
    await auditRoute(admin, 390, 844, `/compare/${comparisonId}`, "admin");
    const tabsDeadline = Date.now() + 15_000;
    let labels = [];
    while (Date.now() < tabsDeadline && labels.length !== 5) {
      labels = await evaluate(
        admin,
        `Array.from(document.querySelectorAll('.comparison-task-tabs [role="tab"]')).map((item) => item.getAttribute('aria-label'))`,
      );
      if (labels.length !== 5) await sleep(100);
    }
    await evaluate(
      admin,
      `document.querySelector('.comparison-task-tabs [aria-controls="companion-ask"]')?.click()`,
    );
    await sleep(150);
    const comparison = {
      labels,
      openedAsk: await evaluate(
        admin,
        `!!document.querySelector('.comparison-layout[data-mobile-surface="companion"]')`,
      ),
    };
    assert.equal(comparison.labels.length, 5);
    assert.equal(comparison.openedAsk, true);
  }

  await admin.send("Network.emulateNetworkConditions", {
    offline: true,
    latency: 0,
    downloadThroughput: 0,
    uploadThroughput: 0,
  });
  const offlineShell = await evaluate(admin, `(() => { window.dispatchEvent(new Event('offline')); return !!document.querySelector('.shell'); })()`);
  assert.equal(offlineShell, true, "Cached mobile workspace disappeared while offline");
  await admin.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 0,
    downloadThroughput: -1,
    uploadThroughput: -1,
  });
  await evaluate(admin, `window.dispatchEvent(new Event('online'))`);

  const stateTarget = await fetch(
    `http://127.0.0.1:${port}/json/new?${encodeURIComponent("about:blank")}`,
    { method: "PUT" },
  ).then((response) => response.json());
  states = new Cdp(stateTarget.webSocketDebuggerUrl);
  await Promise.all([states.send("Page.enable"), states.send("Runtime.enable")]);
  let registryState = "loading";
  let pendingRegistryRequest = "";
  states.on("Fetch.requestPaused", async (event) => {
    if (registryState === "loading") {
      pendingRegistryRequest = event.requestId;
      return;
    }
    const error = registryState === "error";
    await states.send("Fetch.fulfillRequest", {
      requestId: event.requestId,
      responseCode: error ? 503 : 200,
      responseHeaders: [{ name: "Content-Type", value: "application/json" }],
      body: Buffer.from(
        JSON.stringify(
          error
            ? { detail: "Mobile error-state probe", code: "qa_probe" }
            : { view: "monitored", groups: [], count: 0 },
        ),
      ).toString("base64"),
    });
  });
  await states.send("Fetch.enable", {
    patterns: [{ urlPattern: "*api/registry?*", requestStage: "Request" }],
  });
  await auditRoute(states, 390, 844, "/registry?q=mobile-loading-probe", "loading state");
  await waitFor(
    states,
    `!!document.querySelector('.animate-spin')`,
    "Registry loading state did not render",
  );
  assert.ok(pendingRegistryRequest, "Registry request was not paused for loading-state QA");
  registryState = "empty";
  await states.send("Fetch.fulfillRequest", {
    requestId: pendingRegistryRequest,
    responseCode: 200,
    responseHeaders: [{ name: "Content-Type", value: "application/json" }],
    body: Buffer.from(JSON.stringify({ view: "monitored", groups: [], count: 0 })).toString("base64"),
  });
  await waitFor(states, `!!document.querySelector('.empty-state')`, "Registry empty state did not render");
  await auditRoute(states, 390, 844, "/registry", "empty state", true, false);
  registryState = "error";
  await auditRoute(states, 390, 844, "/registry?q=mobile-error-probe", "error state");
  await waitFor(states, `!!document.querySelector('.error-note')`, "Registry error state did not render");
  await auditRoute(states, 390, 844, "/registry", "error state", true, false);

  const viewerTarget = await fetch(
    `http://127.0.0.1:${port}/json/new?${encodeURIComponent("about:blank")}`,
    { method: "PUT" },
  ).then((response) => response.json());
  viewer = new Cdp(viewerTarget.webSocketDebuggerUrl);
  await Promise.all([viewer.send("Page.enable"), viewer.send("Runtime.enable")]);
  await installViewerSession(viewer);
  await auditRoute(viewer, 390, 844, "/organization", "viewer");
  await evaluate(viewer, `document.querySelector('.mobile-nav-more summary')?.click()`);
  await sleep(100);
  const viewerLinks = await evaluate(
    viewer,
    `Array.from(document.querySelectorAll('.mobile-nav-menu a')).map((item) => item.getAttribute('href'))`,
  );
  for (const hidden of ["/settings", "/prompts", "/logs", "/admin", "/deployments", "/connectors", "/models"]) {
    assert.equal(viewerLinks.includes(hidden), false, `Viewer mobile menu exposed ${hidden}`);
  }
  await auditRoute(viewer, 768, 1024, "/registry", "viewer");

  console.log("Mobile browser journeys passed for 360/390/430 px, 768×1024, five locales, admin, viewer, and offline recovery.");
} finally {
  admin?.close();
  viewer?.close();
  states?.close();
  browser.kill();
  await sleep(100);
  await rm(profile, { recursive: true, force: true });
}
