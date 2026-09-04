import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const css = readFileSync(resolve(root, "apps/web/app/globals.css"), "utf8");
const shellSource = readFileSync(
  resolve(root, "apps/web/components/shell.tsx"),
  "utf8",
);

function ruleBodies(source, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const matches = [];
  const expression = new RegExp(`(?:^|\\n)\\s*${escaped}\\s*\\{`, "g");
  let match;
  while ((match = expression.exec(source))) {
    const open = source.indexOf("{", match.index);
    let depth = 1;
    let cursor = open + 1;
    while (cursor < source.length && depth > 0) {
      if (source[cursor] === "{") depth += 1;
      if (source[cursor] === "}") depth -= 1;
      cursor += 1;
    }
    assert.equal(depth, 0, `Unclosed CSS rule for ${selector}`);
    matches.push(source.slice(open + 1, cursor - 1));
    expression.lastIndex = cursor;
  }
  return matches;
}

function compact(value) {
  return value.replace(/\s+/g, " ").trim();
}

function expectDeclaration(rule, pattern, message) {
  assert.match(compact(rule), pattern, message);
}

test("desktop shell owns the viewport and main content scrolls independently", () => {
  const desktopShell = ruleBodies(css, ".shell")[0];
  const desktopMain = ruleBodies(css, ".main")[0];
  const desktopTopbar = ruleBodies(css, ".topbar")[0];

  expectDeclaration(
    desktopShell,
    /height:\s*100vh/,
    "100vh fallback is required",
  );
  expectDeclaration(
    desktopShell,
    /height:\s*100dvh/,
    "dynamic viewport height is required",
  );
  expectDeclaration(
    desktopShell,
    /position:\s*fixed/,
    "desktop shell must be removed from document scrolling",
  );
  expectDeclaration(
    desktopShell,
    /inset:\s*0/,
    "desktop shell must be pinned to the viewport",
  );
  expectDeclaration(
    desktopShell,
    /overflow:\s*hidden/,
    "the document must not become the desktop scroller",
  );
  expectDeclaration(desktopMain, /height:\s*100%/, "main must fill the shell");
  expectDeclaration(
    desktopMain,
    /min-height:\s*0/,
    "main must be allowed to shrink inside the grid",
  );
  expectDeclaration(
    desktopMain,
    /overflow-y:\s*auto/,
    "main must own desktop page scrolling",
  );
  expectDeclaration(
    desktopTopbar,
    /position:\s*sticky/,
    "account and route context must stay reachable",
  );
  expectDeclaration(
    desktopTopbar,
    /top:\s*0/,
    "the sticky topbar must anchor to the main scroller",
  );
});

test("long desktop navigation has a bounded keyboard-reachable scroll region", () => {
  const sidebar = ruleBodies(css, ".sidebar")[0];
  const navigation = ruleBodies(css, ".nav-group")[0];
  const item = ruleBodies(css, ".nav-item")[0];

  expectDeclaration(
    sidebar,
    /height:\s*100%/,
    "sidebar must fill but not exceed the shell",
  );
  expectDeclaration(
    sidebar,
    /min-height:\s*0/,
    "sidebar must permit its navigation child to shrink",
  );
  expectDeclaration(
    sidebar,
    /overflow:\s*hidden/,
    "sidebar chrome must remain stable",
  );
  expectDeclaration(
    navigation,
    /flex:\s*1 1 auto/,
    "navigation must receive the remaining height",
  );
  expectDeclaration(
    navigation,
    /min-height:\s*0/,
    "navigation must shrink on short viewports",
  );
  expectDeclaration(
    navigation,
    /overflow-y:\s*auto/,
    "every role-gated route must remain scroll-reachable",
  );
  expectDeclaration(
    navigation,
    /overflow-x:\s*hidden/,
    "long localized labels must not create a second navigation axis",
  );
  expectDeclaration(
    navigation,
    /scroll-padding-block:\s*8px/,
    "focused links need visible scroll padding",
  );
  expectDeclaration(
    navigation,
    /padding-block:\s*6px/,
    "focus outlines need space inside the scrolling viewport",
  );
  expectDeclaration(
    item,
    /scroll-margin-block:\s*8px/,
    "focused links need visible scroll margin",
  );
  expectDeclaration(
    item,
    /min-width:\s*0/,
    "localized navigation labels must be allowed to wrap",
  );
  expectDeclaration(
    item,
    /max-width:\s*100%/,
    "navigation items must stay inside their scroll viewport",
  );

  const brand = shellSource.indexOf('className="brand"');
  const workspace = shellSource.indexOf('className="workspace text-left"');
  const nav = shellSource.indexOf('className="nav-group"');
  const bottom = shellSource.indexOf('className="sidebar-bottom"');
  assert.ok(
    brand >= 0 && brand < workspace,
    "brand must precede the workspace control",
  );
  assert.ok(
    workspace < nav,
    "workspace control must remain outside the scrolling route list",
  );
  assert.ok(
    nav < bottom,
    "support/model links must remain outside the scrolling route list",
  );
});

test("mobile restores one document scroll and removes the nested chat scroller", () => {
  const shellRules = ruleBodies(css, ".shell");
  const mainRules = ruleBodies(css, ".main");
  const chatRules = ruleBodies(css, ".chat-history");
  const mobileShell = shellRules.at(-1);
  const mobileMain = mainRules.at(-1);
  const mobileChat = chatRules.at(-1);

  assert.ok(shellRules.length > 1, "a mobile shell override is required");
  assert.ok(mainRules.length > 1, "a mobile main override is required");
  assert.ok(chatRules.length > 1, "a mobile chat-history override is required");
  expectDeclaration(
    mobileShell,
    /height:\s*auto/,
    "mobile shell must grow with its content",
  );
  expectDeclaration(
    mobileShell,
    /position:\s*static/,
    "mobile shell must return to normal document flow",
  );
  expectDeclaration(
    mobileShell,
    /inset:\s*auto/,
    "mobile must clear desktop viewport pinning",
  );
  expectDeclaration(
    mobileShell,
    /min-height:\s*100dvh/,
    "mobile shell must follow dynamic viewport changes",
  );
  expectDeclaration(
    mobileShell,
    /overflow:\s*visible/,
    "mobile must use the document scroller",
  );
  expectDeclaration(
    mobileMain,
    /height:\s*auto/,
    "mobile main must grow with its content",
  );
  expectDeclaration(
    mobileMain,
    /overflow:\s*visible/,
    "mobile main must not create a nested vertical scroller",
  );
  expectDeclaration(
    mobileChat,
    /max-height:\s*none/,
    "chat history must not trap touch scrolling",
  );
  expectDeclaration(
    mobileChat,
    /overflow-y:\s*visible/,
    "chat history must share the mobile document scroll",
  );
});

test("viewport chrome reserves device safe areas", () => {
  const sidebar = compact(ruleBodies(css, ".sidebar")[0]);
  const topbar = compact(ruleBodies(css, ".topbar")[0]);
  const content = compact(ruleBodies(css, ".content")[0]);
  const mobileNav = compact(ruleBodies(css, ".mobile-nav").at(-1));

  assert.match(sidebar, /safe-area-inset-(top|bottom)/);
  assert.match(sidebar, /safe-area-inset-(left|right)/);
  assert.match(topbar, /safe-area-inset-top/);
  assert.match(topbar, /safe-area-inset-(left|right)/);
  assert.match(content, /safe-area-inset-bottom/);
  assert.match(content, /safe-area-inset-(left|right)/);
  assert.match(mobileNav, /safe-area-inset-(left|right)/);
});
