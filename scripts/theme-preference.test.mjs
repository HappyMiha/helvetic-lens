import { runInNewContext } from "node:vm";
import assert from "node:assert/strict";
import { test, after } from "node:test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import Module, { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

// Exercise actual server rendering without a browser or live account. Type
// checking remains the separate full-project gate; this loader only transpiles.
const require = createRequire(import.meta.url);
const originalResolve = Module._resolveFilename;
const originalTs = Module._extensions[".ts"];
const originalTsx = Module._extensions[".tsx"];
const originalCss = Module._extensions[".css"];
Module._extensions[".css"] = () => {}; // Server markup assertions do not load styles.
Module._resolveFilename = function (name, ...args) {
  return originalResolve.call(
    this,
    name.startsWith("@/") ? resolve("apps/web", name.slice(2)) : name,
    ...args,
  );
};
for (const extension of [".ts", ".tsx"])
  Module._extensions[extension] = (module, filename) => {
    const { outputText } = ts.transpileModule(readFileSync(filename, "utf8"), {
      compilerOptions: {
        jsx: ts.JsxEmit.ReactJSX,
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        esModuleInterop: true,
      },
      fileName: filename,
    });
    module._compile(outputText, filename);
  };
after(() => {
  Module._resolveFilename = originalResolve;
  if (originalCss) Module._extensions[".css"] = originalCss;
  else delete Module._extensions[".css"];
  if (originalTs) Module._extensions[".ts"] = originalTs;
  else delete Module._extensions[".ts"];
  if (originalTsx) Module._extensions[".tsx"] = originalTsx;
  else delete Module._extensions[".tsx"];
});

const {
  initializeTheme,
  THEME_BOOTSTRAP,
  THEME_STORAGE_KEY,
  themeCopy,
} = require(resolve("apps/web/lib/theme-preference.ts"));
const { ThemeProvider, ThemeControl } = require(
  resolve("apps/web/components/theme-provider.tsx"),
);

function device(initial = null, systemDark = false) {
  const state = {
    value: initial,
    matches: systemDark,
    blocked: false,
    failWrite: false,
    noMedia: false,
    writes: [],
  };
  const events = new Set();
  const mediaEvents = new Set();
  const classes = new Set();
  const root = {
    dataset: { theme: "dark" },
    style: {},
    classList: {
      toggle(name, enabled) {
        if (enabled) classes.add(name);
        else classes.delete(name);
      },
    },
  };
  const storage = {
    getItem(key) {
      assert.equal(key, THEME_STORAGE_KEY);
      return state.value;
    },
    setItem(key, value) {
      if (state.failWrite) throw new Error("Storage full");
      state.writes.push([key, value]);
      state.value = value;
    },
  };
  const media = {
    get matches() {
      return state.matches;
    },
    addEventListener(name, callback) {
      assert.equal(name, "change");
      mediaEvents.add(callback);
    },
    removeEventListener(name, callback) {
      mediaEvents.delete(callback);
    },
  };
  const host = {
    document: { documentElement: root },
    get localStorage() {
      if (state.blocked) throw new Error("Storage blocked");
      return storage;
    },
    matchMedia() {
      if (state.noMedia) throw new Error("Unsupported");
      return media;
    },
    addEventListener(name, callback) {
      assert.equal(name, "storage");
      events.add(callback);
    },
    removeEventListener(name, callback) {
      events.delete(callback);
    },
  };
  return {
    host,
    state,
    root,
    storage,
    classes,
    events,
    mediaEvents,
    system(value) {
      state.matches = value;
      for (const callback of mediaEvents) callback();
    },
    change(key, newValue, area = storage) {
      for (const callback of events)
        callback({ key, newValue, storageArea: area });
    },
    snapshot() {
      return {
        selected: root.dataset.theme,
        dark: classes.has("dark"),
        scheme: root.style.colorScheme,
      };
    },
    boot() {
      runInNewContext(THEME_BOOTSTRAP, {
        document: host.document,
        matchMedia: () => host.matchMedia(),
        get localStorage() {
          return host.localStorage;
        },
      });
    },
  };
}

test("first paint and hydrated preferences agree for saved, system and invalid values", () => {
  for (const value of [
    null,
    "dark",
    "light",
    "system",
    "untrusted arbitrary text",
  ])
    for (const dark of [false, true]) {
      const d = device(value, dark);
      d.boot();
      const first = d.snapshot();
      const observed = [];
      const controller = initializeTheme(d.host, (t) => observed.push(t));
      assert.deepEqual(d.snapshot(), first);
      assert.equal(
        first.selected,
        ["dark", "light", "system"].includes(value) ? value : "dark",
      );
      assert.equal(
        first.dark,
        first.selected === "dark" || (first.selected === "system" && dark),
      );
      assert.equal(observed.length, 1);
      assert.deepEqual(d.state.writes, []);
      controller.dispose();
    }
});

test("blocked storage keeps the user's current-page choice through device changes", () => {
  const d = device();
  d.state.blocked = true;
  d.boot();
  const c = initializeTheme(d.host, () => {});
  c.select("light");
  d.system(true);
  assert.deepEqual(d.snapshot(), {
    selected: "light",
    dark: false,
    scheme: "light",
  });
  c.select("system");
  d.system(false);
  assert.equal(d.snapshot().dark, false);
  d.system(true);
  assert.equal(d.snapshot().dark, true);
  c.select("dark");
  d.system(false);
  assert.equal(d.snapshot().dark, true);
  assert.deepEqual(d.state.writes, []);
  c.dispose();
});

test("failed persistence never reloads a stale saved choice on a media event", () => {
  const d = device("dark", false);
  d.state.failWrite = true;
  const c = initializeTheme(d.host, () => {});
  c.select("system");
  d.system(true);
  assert.equal(d.snapshot().selected, "system");
  assert.equal(d.snapshot().dark, true);
  d.system(false);
  assert.equal(d.snapshot().dark, false);
  assert.equal(d.state.value, "dark");
  c.dispose();
});

test("same-origin theme events synchronize while unrelated and session storage are ignored", () => {
  const d = device("light");
  const c = initializeTheme(d.host, () => {});
  d.change("research-draft", "dark");
  d.change(THEME_STORAGE_KEY, "dark", {});
  assert.equal(d.snapshot().selected, "light");
  d.change(THEME_STORAGE_KEY, "system");
  d.system(true);
  assert.equal(d.snapshot().dark, true);
  d.change(THEME_STORAGE_KEY, null);
  assert.equal(d.snapshot().selected, "dark");
  d.change(THEME_STORAGE_KEY, "light");
  d.change(null, null);
  assert.equal(d.snapshot().selected, "dark");
  assert.deepEqual(d.state.writes, []);
  c.dispose();
});

test("explicit choices persist only the appearance key and invalid values are ignored", () => {
  const d = device();
  const c = initializeTheme(d.host, () => {});
  c.select("light");
  c.select("untrusted arbitrary text");
  assert.deepEqual(d.state.writes, [[THEME_STORAGE_KEY, "light"]]);
  assert.equal(d.snapshot().selected, "light");
  c.dispose();
});

test("disposal removes subscriptions and late callbacks cannot overwrite the reading choice", () => {
  const d = device("system");
  let changes = 0;
  const c = initializeTheme(d.host, () => changes++);
  const late = [...d.mediaEvents];
  assert.equal(d.events.size, 1);
  assert.equal(d.mediaEvents.size, 1);
  c.dispose();
  assert.equal(d.events.size, 0);
  assert.equal(d.mediaEvents.size, 0);
  d.system(true);
  c.select("dark");
  late[0]();
  assert.equal(changes, 1);
  assert.equal(d.snapshot().selected, "system");
  const again = initializeTheme(d.host, () => {});
  assert.equal(d.events.size, 1);
  again.dispose();
  assert.equal(d.events.size, 0);
});

test("unsupported system media and blocked storage still produce a usable initial page", () => {
  const d = device("system");
  d.state.noMedia = true;
  d.boot();
  assert.equal(d.snapshot().dark, false);
  const c = initializeTheme(d.host, () => {});
  assert.equal(d.snapshot().scheme, "light");
  c.select("dark");
  assert.equal(d.snapshot().dark, true);
  c.dispose();
  const blocked = device();
  blocked.state.blocked = true;
  blocked.state.noMedia = true;
  blocked.boot();
  assert.equal(blocked.snapshot().dark, true);
});

test("server rendering retains the reading child and accessible non-submit controls in all five locales", () => {
  for (const locale of Object.keys(themeCopy)) {
    const html = renderToStaticMarkup(
      React.createElement(
        ThemeProvider,
        null,
        React.createElement(
          "article",
          { "data-reading-context": "retained" },
          "Saved evidence",
        ),
        React.createElement(ThemeControl, { locale }),
      ),
    );
    assert.match(html, /data-reading-context="retained"/);
    assert.match(html, />Saved evidence<\/article>/);
    assert.match(html, /type="button"/);
    assert.ok(
      html.includes(`${themeCopy[locale].label}: ${themeCopy[locale].dark}.`),
    );
    assert.ok(
      html.includes(`${themeCopy[locale].next} ${themeCopy[locale].system}.`),
    );
    assert.doesNotMatch(html, /\b(?:href|action)=/);
  }
});
