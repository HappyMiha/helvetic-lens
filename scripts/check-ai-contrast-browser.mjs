// Focused HL-097 regression, not a full WCAG or user-journey audit.
// Renders the real PostCSS output without a database, API or model call.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import postcss from "postcss";
import tailwindcss from "@tailwindcss/postcss";
import { Cdp, evaluate, pollJson, sleep } from "./browser-cdp.mjs";
import { analysisModeFixtures } from "./analysis-mode-fixtures.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const cssPath = join(root, "apps/web/app/globals.css");
const css = await postcss([tailwindcss()]).process(
  await readFile(cssPath, "utf8"),
  { from: cssPath },
);
const chrome = [
  process.env.CHROME_BIN,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
]
  .filter(Boolean)
  .find(existsSync);
assert.ok(chrome, "Set CHROME_BIN; a missing browser cannot pass this gate.");

const sample = (tag, label, attributes = "") =>
  `<${tag} data-contrast="${label}" ${attributes}>${label}</${tag}>`;
const tabs = (className) => `<div class="${className}">
  ${sample("button", "Summary", 'role="tab" aria-selected="true"')}
  ${sample("button", "Actions", 'role="tab" aria-selected="false"')}
  ${sample("button", "Ask", 'role="tab" aria-selected="false"')}
  ${sample("button", "History", 'role="tab" aria-selected="false"')}
  <button disabled>Unavailable</button></div>`;
const markup = `<div class="comparison-layout" data-mobile-surface="companion">
  <div>${tabs("comparison-task-tabs")}</div>
  <aside class="analysis-column"><div class="companion-nav-wrap">${tabs("companion-tabs")}
    ${sample("button", "Close", 'class="companion-close"')}
  </div><section class="panel companion-tab-panel"><div class="panel-body">
    <div class="triage-summary"><div>${sample("span", "Material")}${sample("small", "Count")}</div></div>
    <div class="semantic-cluster-heading">${sample("span", "Legal unit")}</div>
    <div class="analysis-job"><div class="analysis-job-title">${sample("span", "Queued")}</div>${sample("p", "Waiting for model")}</div>
    <div class="impact-change-list"><article><div class="impact-change-title">${sample("span", "Change")}</div></article></div>
    <div class="impact-applicability">${sample("span", "Applicability")}</div>
    <div class="impact-date-list"><div>${sample("span", "Effective date")}</div></div>
    <details class="action-decision-history" open>${sample("summary", "Decisions")}</details>
    <dl class="report-provenance">${sample("dt", "Model")}</dl>
    ${sample("p", "Owner", 'class="action-meta"')}${sample("p", "Condition", 'class="action-condition"')}
    <div class="action-empty">${sample("p", "No action established")}</div>
    <div class="ask-job-heading">${sample("span", "Preparing evidence")}</div>
    ${sample("p", "Retry available", 'class="ask-job-recovery"')}
    ${sample("p", "Saved result", 'class="ask-job-result-kind"')}
    <div class="prompt-context-option">${sample("span", "Saved evidence only")}</div>
    ${sample("p", "Requested yesterday", 'class="ai-history-meta"')}
    ${sample("p", "Comparison versions", 'class="ai-history-facts"')}
    ${sample("span", "Citations", 'class="history-citations"')}
    ${sample("p", "Provider unavailable", 'class="error-note"')}
    ${analysisModeFixtures().map(({ html, locale, mode }) => html
      .replace("<strong>", `<strong data-contrast="Mode ${locale} ${mode}">`)
      .replace("<p ", `<p data-contrast="Mode body ${locale} ${mode}" `)).join("\n")}
  </div></section></aside></div>`;

// Composite transparent ancestor surfaces before WCAG relative luminance.
const contrastExpression = `(() => {
  const rgba = value => value.match(/[\\d.]+/g).map(Number);
  const blend = (front, back) => front.slice(0, 3).map((c, i) => c * (front[3] ?? 1) + back[i] * (1 - (front[3] ?? 1)));
  const luminance = rgb => rgb.map(c => c / 255).map(c => c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4).reduce((s, c, i) => s + c * [.2126, .7152, .0722][i], 0);
  const ratio = (a, b) => { const x = luminance(a), y = luminance(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  return Array.from(document.querySelectorAll('[data-contrast]')).filter(el => el.getClientRects().length).map(el => {
    const chain = []; for (let p = el; p; p = p.parentElement) chain.unshift(p);
    const background = chain.reduce((bg, p) => blend(rgba(getComputedStyle(p).backgroundColor), bg), [255, 255, 255]);
    const style = getComputedStyle(el);
    const foreground = blend(rgba(style.color), background);
    const outline = blend(rgba(style.outlineColor), background);
    return { label: el.dataset.contrast, ratio: ratio(foreground, background), color: style.color, background,
      focused: el === document.activeElement, outline: style.outlineStyle, outlineRatio: ratio(outline, background) };
  });
})()`;

const profile = await mkdtemp(join(tmpdir(), "helvetic-lens-contrast-"));
const port = 9700 + Math.floor(Math.random() * 200);
const browser = spawn(
  chrome,
  [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: "ignore" },
);
let cdp;
let samples = 0;
let minimum = Infinity;
try {
  await pollJson(`http://127.0.0.1:${port}/json/version`);
  const target = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, {
    method: "PUT",
  }).then((r) => r.json());
  cdp = new Cdp(target.webSocketDebuggerUrl);
  await Promise.all([
    cdp.send("Page.enable"),
    cdp.send("Runtime.enable"),
    cdp.send("DOM.enable"),
  ]);
  await cdp.send("CSS.enable");
  const { frameTree } = await cdp.send("Page.getFrameTree");
  for (const [width, height] of [
    [390, 844],
    [768, 1024],
    [1024, 768],
    [1440, 900],
  ]) {
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await cdp.send("Page.setDocumentContent", {
      frameId: frameTree.frame.id,
      html: `<!doctype html><html lang="en"><head><style>${css.css}</style></head><body>${markup}</body></html>`,
    });
    const audit = async (state) => {
      const rows = await evaluate(cdp, contrastExpression);
      assert.ok(
        rows.length >= (width <= 1350 ? 26 : 25),
        `Required contrast fixtures missing at ${width}px (${state})`,
      );
      for (const row of rows) {
        assert.ok(
          row.ratio >= 4.5,
          `${width}px ${state} ${row.label}: ${row.ratio.toFixed(2)}:1 (${row.color})`,
        );
        minimum = Math.min(minimum, row.ratio);
      }
      samples += rows.length;
      return rows;
    };
    await audit("default");
    const { root: documentNode } = await cdp.send("DOM.getDocument");
    const { nodeIds } = await cdp.send("DOM.querySelectorAll", {
      nodeId: documentNode.nodeId,
      selector: '[role="tab"]',
    });
    for (const nodeId of nodeIds)
      await cdp.send("CSS.forcePseudoState", {
        nodeId,
        forcedPseudoClasses: ["hover"],
      });
    await audit("hover");
    for (const nodeId of nodeIds)
      await cdp.send("CSS.forcePseudoState", {
        nodeId,
        forcedPseudoClasses: [],
      });
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "Tab",
      code: "Tab",
      windowsVirtualKeyCode: 9,
    });
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "Tab",
      code: "Tab",
      windowsVirtualKeyCode: 9,
    });
    const focused = (await audit("keyboard focus")).filter((r) => r.focused);
    assert.equal(focused.length, 1, "Keyboard must reach an enabled control");
    assert.notEqual(focused[0].outline, "none");
    assert.ok(
      focused[0].outlineRatio >= 3,
      "Focus outline must contrast with its surface",
    );
    assert.equal(await evaluate(cdp, `document.activeElement.disabled`), false);
  }
  console.log(
    `AI contrast: ${samples} rendered samples passed; minimum ${minimum.toFixed(2)}:1. Default, selected, hover, keyboard focus and error; 390/768/1024/1440px. Disabled controls excluded from text contrast.`,
  );
} finally {
  cdp?.close();
  const closed = new Promise((resolve) => browser.once("exit", resolve));
  browser.kill();
  await Promise.race([closed, sleep(5000)]);
  // Only delete the exact disposable directory created above.
  assert.equal(dirname(resolve(profile)), resolve(tmpdir()));
  assert.ok(basename(profile).startsWith("helvetic-lens-contrast-"));
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}
