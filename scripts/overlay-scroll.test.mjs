import assert from "node:assert/strict";
import test from "node:test";
import { lockOverlayScroll } from "../apps/web/lib/overlay-scroll.ts";

function page(mainOverflow = "auto") {
  const root = { style: { overflow: "scroll" } };
  const main = { style: { overflow: mainOverflow } };
  const document = { documentElement: root, querySelector: () => main };
  return { root, main, document };
}

for (const order of [[0, 1], [1, 0]]) test(`overlapping overlays preserve original styles, release order ${order}`, () => {
  const previous = globalThis.document;
  const { root, main, document } = page();
  globalThis.document = document;
  const releases = [];
  try {
    releases.push(lockOverlayScroll(), lockOverlayScroll());
    assert.equal(root.style.overflow, "hidden");
    assert.equal(main.style.overflow, "hidden");
    releases[order[0]]();
    releases[order[0]](); // A duplicate cleanup must not release the other owner.
    assert.equal(root.style.overflow, "hidden");
    assert.equal(main.style.overflow, "hidden");
    releases[order[1]]();
    assert.equal(root.style.overflow, "scroll");
    assert.equal(main.style.overflow, "auto");
  } finally {
    releases.forEach(release => release());
    globalThis.document = previous;
  }
});

test("route replacement releases detached main separately while keeping shared root locked", () => {
  const previous = globalThis.document;
  const first = page("clip"), second = page("");
  globalThis.document = first.document;
  const releases = [];
  try {
    releases.push(lockOverlayScroll());
    globalThis.document = { documentElement: first.root, querySelector: () => second.main };
    releases.push(lockOverlayScroll());
    releases[0]();
    assert.equal(first.main.style.overflow, "clip");
    assert.equal(first.root.style.overflow, "hidden");
    assert.equal(second.main.style.overflow, "hidden");
    releases[1]();
    assert.equal(second.main.style.overflow, "");
    assert.equal(first.root.style.overflow, "scroll");
  } finally {
    releases.forEach(release => release());
    globalThis.document = previous;
  }
});

test("a missing main and an existing external scroll lock retain their original state", () => {
  const previous = globalThis.document;
  const root = { style: { overflow: "hidden" } };
  globalThis.document = { documentElement: root, querySelector: () => null };
  try {
    const release = lockOverlayScroll();
    release();
    assert.equal(root.style.overflow, "hidden");
  } finally { globalThis.document = previous; }
});
