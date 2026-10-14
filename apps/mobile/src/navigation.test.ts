import { test } from "node:test";
import assert from "node:assert/strict";
import { classifyNavigation, deepLinkToSiteUrl, SITE_ORIGIN } from "./navigation.ts";

test("site pages stay inside the app", () => {
  assert.equal(classifyNavigation(`${SITE_ORIGIN}/registry?x=1`), "app");
  assert.equal(classifyNavigation("https://www.helveticlens.ch/"), "app");
  assert.equal(classifyNavigation("about:blank"), "app");
  assert.equal(classifyNavigation("blob:https://helveticlens.ch/abc"), "app");
});

test("other sites, including look-alike hosts, open in the browser", () => {
  assert.equal(classifyNavigation("https://www.fedlex.admin.ch/eli/cc/1"), "browser");
  assert.equal(classifyNavigation("https://helveticlens.ch.evil.example/"), "browser");
  assert.equal(classifyNavigation("https://pharma.helveticlens.ch/"), "browser");
  assert.equal(classifyNavigation("http://helveticlens.ch/"), "browser");
});

test("mail and phone links go to the system, unknown schemes are dropped", () => {
  assert.equal(classifyNavigation("mailto:hello@example.ch"), "system");
  assert.equal(classifyNavigation("tel:+41000000000"), "system");
  assert.equal(classifyNavigation("javascript:alert(1)"), "ignore");
  assert.equal(classifyNavigation("intent://x#Intent;end"), "ignore");
  assert.equal(classifyNavigation("not a url"), "ignore");
});

test("deep links map onto site paths only", () => {
  assert.equal(deepLinkToSiteUrl("helveticlens://registry"), `${SITE_ORIGIN}/registry`);
  assert.equal(
    deepLinkToSiteUrl("helveticlens://laws/42?tab=history#v2"),
    `${SITE_ORIGIN}/laws/42?tab=history#v2`,
  );
  assert.equal(deepLinkToSiteUrl("helveticlens:///"), `${SITE_ORIGIN}/`);
  assert.equal(
    deepLinkToSiteUrl("https://helveticlens.ch/login?next=%2Finbox"),
    `${SITE_ORIGIN}/login?next=%2Finbox`,
  );
});

test("deep links cannot redirect the app to another origin", () => {
  assert.equal(deepLinkToSiteUrl("https://evil.example/registry"), null);
  assert.equal(deepLinkToSiteUrl("exp://127.0.0.1:8081"), null);
  assert.equal(deepLinkToSiteUrl("helveticlens:////evil.example/x"), `${SITE_ORIGIN}/evil.example/x`);
  assert.equal(deepLinkToSiteUrl(""), null);
  assert.equal(deepLinkToSiteUrl(null), null);
});
