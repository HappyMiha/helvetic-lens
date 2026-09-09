import assert from "node:assert/strict";
import test from "node:test";
import { readdir } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import {
  SECTION_GUIDES,
  SHARED_CONTROLS,
  guideForPath,
  permitted,
} from "../apps/web/lib/section-guides.ts";

test("every actual page route has a specific complete guide", async () => {
  const root = resolve(import.meta.dirname, "../apps/web/app");
  async function walk(dir) {
    const files = await readdir(dir, { withFileTypes: true });
    return (
      await Promise.all(
        files.map((entry) =>
          entry.isDirectory()
            ? walk(join(dir, entry.name))
            : entry.name === "page.tsx"
              ? [join(dir, entry.name)]
              : [],
        ),
      )
    ).flat();
  }
  const pages = await walk(root);
  assert.ok(pages.length >= 30);
  const covered = new Set();
  for (const file of pages) {
    const route =
      "/" +
      relative(root, file)
        .replaceAll("\\", "/")
        .replace(/\/?page\.tsx$/, "")
        .replace(/\[[^/]+\]/g, "fixture-id");
    const guide = guideForPath(route);
    assert.ok(guide, `Missing contextual guide for ${route}`);
    covered.add(guide.id);
    for (const key of ["title", "purpose", "wait", "setup"])
      assert.ok(guide[key]?.length > 3, `${guide.id}.${key}`);
    for (const key of ["first", "data", "controls"])
      assert.ok(guide[key].length > 0, `${guide.id}.${key}`);
  }
  assert.equal(
    covered.size,
    SECTION_GUIDES.length,
    "Orphan guide no longer corresponds to a page",
  );
});
test("unknown paths cannot receive unrelated page instructions", () => {
  for (const path of [
    "/missing",
    "/laws",
    "/laws/a/extra",
    "/admin/no-such-tool",
    "/onboarding/basel-stadt/extra",
  ])
    assert.equal(guideForPath(path), undefined);
  assert.equal(guideForPath("/topics/?query=secret#anchor")?.id, "topics");
  assert.equal(guideForPath("/corpus-evidence/id")?.id, "evidence");
});
test("guide and control identities are unique; every action states consequences and prerequisites", () => {
  assert.equal(
    new Set(SECTION_GUIDES.map((g) => g.id)).size,
    SECTION_GUIDES.length,
  );
  for (const [id, controls] of [
    ...SECTION_GUIDES.map((g) => [g.id, g.controls]),
    ["shared", SHARED_CONTROLS],
  ]) {
    assert.equal(new Set(controls.map((c) => c.id)).size, controls.length, id);
    for (const control of controls)
      for (const key of ["label", "does", "when", "effect"])
        assert.ok(control[key]?.length > 3, `${id}/${control.id}/${key}`);
  }
});
test("organization management and platform access are independent", () => {
  assert.equal(permitted("manager", false, true), false);
  assert.equal(permitted("platform", true, false), false);
  assert.equal(permitted("manager", true, false), true);
  assert.equal(permitted("platform", false, true), true);
  assert.equal(permitted(undefined, false, false), true);
});
