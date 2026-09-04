import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");
const shell = read("apps/web/components/shell.tsx");
const organization = read("apps/web/components/organization-page.tsx");
const settings = read("apps/web/components/settings-page.tsx");
const auth = read("apps/web/components/auth-gate.tsx");
const discover = read("apps/web/app/discover/page.tsx");
const registry = read("apps/web/components/registry-page.tsx");
const modelLibrary = read("apps/web/components/model-library.tsx");
const connectorAdmin = read("apps/web/components/connector-admin-page.tsx");
const platformAdmin = read("apps/web/components/platform-admin-page.tsx");
const promptSettings = read("apps/web/components/prompt-settings-page.tsx");
const css = read("apps/web/app/globals.css");

function functionBody(source, signature) {
  const start = source.indexOf(signature);
  assert.notEqual(start, -1, `Missing ${signature}`);
  const open = source.indexOf("{", start + signature.length);
  let depth = 1;
  let cursor = open + 1;
  while (cursor < source.length && depth > 0) {
    if (source[cursor] === "{") depth += 1;
    if (source[cursor] === "}") depth -= 1;
    cursor += 1;
  }
  assert.equal(depth, 0, `Unclosed ${signature}`);
  return source.slice(open + 1, cursor - 1);
}

test("daily work exposes five task destinations", () => {
  for (const destination of [
    "/",
    "/registry",
    "/impact",
    "/discover",
    "/sources",
  ]) {
    assert.match(
      shell,
      new RegExp(`href=["']${destination.replace("/", "\\/")}["']`),
    );
  }
  assert.match(discover, /<RegistryPage defaultView="events" \/>/);
  assert.match(shell, /t\("nav\.today"\)/);
  assert.match(shell, /t\("nav\.monitoring"\)/);
  assert.match(shell, /t\("nav\.discover"\)/);
});

test("company profile has one routed implementation and no modal bridge", () => {
  assert.doesNotMatch(
    shell,
    /\bProfileDialog\b|\bprofileOpen\b|\bsetProfileOpen\b/,
  );
  assert.doesNotMatch(
    settings,
    /\bProfileDialog\b|\bprofileOpen\b|\bsetProfileOpen\b/,
  );
  assert.doesNotMatch(shell, /["']\/model\/test["']/);
  assert.doesNotMatch(
    organization,
    /document\.querySelector[\s\S]{0,180}["']\.workspace["'][\s\S]{0,100}\.click\s*\(/,
  );
  assert.match(shell, /href="\/organization"/);
  assert.doesNotMatch(shell, /href=["']\/(?:profile|company-profile)["']/);
  assert.match(settings, /href="\/organization#company-profile"/);
  assert.match(organization, /id="company-profile"/);
  assert.match(organization, /useResource<Profile>\("\/profile"\)/);
  assert.match(
    organization,
    /api<Profile>\("\/profile",\s*\{[\s\S]{0,80}method: "PATCH"/,
  );
  assert.match(organization, /beforeunload/);
  assert.match(organization, /helvetic:before-navigation/);
  assert.match(organization, /helvetic:navigation-committed/);
  assert.match(organization, /window\.addEventListener\("popstate", continueNavigation, \{ once: true \}\)/);
  assert.match(organization, /useState<string \| null>\(null\)/);
  assert.match(
    organization,
    /if \(hydrated\.current && dirtyRef\.current\) return;/,
  );
  assert.match(organization, /applyProfile\(saved\)/);
  assert.match(organization, /profile\.loading \?/);
  assert.match(organization, /onClick=\{profile\.reload\}/);
  assert.ok(
    organization.match(/readOnly=\{!canManage\}/g)?.length === 3,
    "viewer profile fields must remain readable and keyboard reachable",
  );
});

test("workspace selector performs only an authorized organization switch", () => {
  const switchBody = functionBody(shell, "async function switchWorkspace");
  assert.match(switchBody, /api\("\/auth\/session\/organization"/);
  assert.doesNotMatch(switchBody, /\/profile|\/model\/test|\/settings/);
  assert.match(switchBody, /continueAfterProfileGuard/);
  assert.match(shell, /aria-controls=\{optionsId\}/);
  assert.doesNotMatch(shell, /aria-haspopup="menu"|role="menu(?:item)?"/);
  assert.match(shell, /organizations\.length > 1/);

  const signOutBody = functionBody(shell, "async function signOut");
  assert.match(signOutBody, /helvetic:before-navigation/);
  assert.match(signOutBody, /api\("\/auth\/logout"/);
  assert.match(signOutBody, /continueAfterProfileGuard/);
  assert.match(shell, /helvetic:navigation-committed/);
});

test("Monitoring and Discover use canonical routes and complete tab semantics", () => {
  assert.match(registry, /["']\/registry["']/);
  assert.match(registry, /["']\/discover["']/);
  assert.ok(
    registry.match(/role="tab"/g)?.length === 2,
    "both registry view controls must be tabs",
  );
  assert.ok(
    registry.match(/aria-selected=/g)?.length === 2,
    "both tabs must expose their selected state",
  );
});

test("technical navigation is role-gated and unknown sessions are least privilege", () => {
  assert.match(shell, /const administrationItems = \([\s\S]*\{canManage && \(/);
  assert.match(
    shell,
    /const administrationItems = \([\s\S]*\{isPlatformAdmin && \(/,
  );
  for (const destination of ["/settings", "/prompts", "/logs"]) {
    assert.match(
      shell,
      new RegExp(`href=["']${destination.replaceAll("/", "\\/")}["']`),
    );
  }
  for (const destination of ["/admin", "/connectors", "/models"]) {
    assert.match(
      shell,
      new RegExp(`href=["']${destination.replaceAll("/", "\\/")}["']`),
    );
  }
  assert.match(auth, /session\?\.anonymous_development === true/);
  assert.match(auth, /session\?\.authenticated === true/);
  assert.doesNotMatch(auth, /canManage:\s*!session\?\.authenticated/);
  assert.doesNotMatch(auth, /isPlatformAdmin:\s*!session\?\.authenticated/);
});

test("direct administration routes do not fetch or expose controls before authorization", () => {
  assert.match(modelLibrary, /isPlatformAdmin \? "\/admin\/models" : null/);
  assert.match(
    connectorAdmin,
    /isPlatformAdmin \? "\/admin\/connectors" : null/,
  );
  assert.match(
    platformAdmin,
    /isPlatformAdmin \? "\/admin\/status" : null/,
  );
  assert.match(promptSettings, /useResource<PromptSettings>\(allowed \? endpoint : null\)/);
  for (const source of [modelLibrary, connectorAdmin, platformAdmin]) {
    assert.match(source, /\{isPlatformAdmin && \([\s\S]{0,180}<Button/);
  }
});

test("mobile uses explicit overflow and the same role-filtered route fragments", () => {
  assert.match(shell, /className="mobile-nav-more"/);
  assert.match(shell, /className="mobile-nav-menu"/);
  assert.match(shell, /t\("nav\.more"\)/);
  assert.match(shell, /mobileOverflowLabel/);
  assert.match(shell, /mobile-workspace-switcher/);
  assert.ok(
    shell.match(/\{workspaceItems\}/g)?.length === 2,
    "desktop and mobile must render the same workspace destinations",
  );
  assert.ok(
    shell.match(/\{administrationItems\}/g)?.length === 2,
    "desktop and mobile must render the same authorized administration destinations",
  );
  const mobileRule = [...css.matchAll(/\.mobile-nav\s*\{([^{}]*)\}/g)]
    .map((match) => match[1])
    .find((body) => /display:\s*flex/.test(body));
  assert.ok(mobileRule, "Missing mobile navigation rule");
  assert.doesNotMatch(mobileRule, /overflow-x:\s*auto/);
  assert.match(mobileRule, /overflow:\s*visible/);
});
