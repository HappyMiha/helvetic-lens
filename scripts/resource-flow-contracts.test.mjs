import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  ResourceStore,
  resourceKey,
  resourceTag,
} from "../apps/web/lib/resource-cache.ts";

const LOCALE = "en-CH";
const COMPONENTS_DIRECTORY = fileURLToPath(
  new URL("../apps/web/components/", import.meta.url),
);

function flowKey(
  id,
  { tags = [], scope = "organization", owner = "monitoring" } = {},
) {
  return resourceKey({
    id,
    path: `/contract/${id}`,
    scope,
    owner,
    tags,
    varyByLocale: false,
    staleMs: Number.POSITIVE_INFINITY,
  });
}

function observe(store, resource, requests, initial) {
  store.prime(resource, LOCALE, initial);
  requests[resource.id] = 0;
  return store.subscribe(
    resource,
    LOCALE,
    () => undefined,
    async () => {
      requests[resource.id] += 1;
      return { refreshed: resource.id, sequence: requests[resource.id] };
    },
    { staleMs: Number.POSITIVE_INFINITY },
  );
}

function assertOnlyRequests(requests, expected) {
  for (const [id, count] of Object.entries(requests)) {
    assert.equal(
      count,
      expected[id] || 0,
      `${id} received an unexpected request`,
    );
  }
}

function cleanup(store, subscriptions) {
  for (const unsubscribe of subscriptions) unsubscribe();
  store.destroy();
}

test("Ask completion refreshes history only and preserves comparison evidence", async () => {
  const store = new ResourceStore();
  const comparison = flowKey("comparison:cmp-1", { tags: ["comparison"] });
  const history = flowKey("comparison:history:cmp-1", {
    tags: ["ai-history"],
    owner: "comparison",
  });
  const job = flowKey("monitoring:job:ask-1", { tags: ["job", "jobs"] });
  const health = flowKey("runtime:health", {
    tags: ["health"],
    owner: "runtime",
  });
  const models = flowKey("platform:models", {
    tags: ["models"],
    scope: "platform",
    owner: "administration",
  });
  const navigation = flowKey("organization:status", {
    tags: ["organization-status"],
    owner: "organization",
  });
  const diff = { items: [{ id: "article-1", kind: "modified" }] };
  const comparisonValue = { id: "cmp-1", diff, analysis: null };
  const interactionState = {
    scrollTop: 840,
    selectedTab: "ask",
    expandedEvidence: ["article-1"],
    typedInput: "Does this change our filing deadline?",
  };
  const requests = {};
  const subscriptions = [
    observe(store, comparison, requests, comparisonValue),
    observe(store, history, requests, { items: [] }),
    observe(store, job, requests, { id: "ask-1", state: "running" }),
    observe(store, health, requests, { status: "ok" }),
    observe(store, models, requests, { models: [] }),
    observe(store, navigation, requests, { law_count: 1 }),
  ];

  store.prime(job, LOCALE, { id: "ask-1", state: "succeeded" });
  await store.invalidate(history);

  assertOnlyRequests(requests, { [history.id]: 1 });
  assert.strictEqual(
    store.getSnapshot(comparison, LOCALE).data,
    comparisonValue,
  );
  assert.strictEqual(store.getSnapshot(comparison, LOCALE).data.diff, diff);
  assert.deepEqual(interactionState, {
    scrollTop: 840,
    selectedTab: "ask",
    expandedEvidence: ["article-1"],
    typedInput: "Does this change our filing deadline?",
  });
  cleanup(store, subscriptions);
});

test("impact completion patches its report without refetching the saved diff", async () => {
  const store = new ResourceStore();
  const comparison = flowKey("comparison:cmp-2", { tags: ["comparison"] });
  const history = flowKey("comparison:history:cmp-2", {
    tags: ["ai-history"],
    owner: "comparison",
  });
  const job = flowKey("monitoring:job:impact-1", {
    tags: ["job", "jobs"],
  });
  const health = flowKey("runtime:health", {
    tags: ["health"],
    owner: "runtime",
  });
  const settings = flowKey("organization:settings", {
    tags: ["settings"],
    owner: "organization",
  });
  const diff = { items: [{ id: "article-7", kind: "added" }] };
  const comparisonValue = {
    id: "cmp-2",
    diff,
    analysis: null,
    analysis_job: null,
  };
  const completedJob = { id: "impact-1", state: "succeeded" };
  const analysis = { id: "analysis-1", summary: "Material amendment" };
  const requests = {};
  const subscriptions = [
    observe(store, comparison, requests, comparisonValue),
    observe(store, history, requests, { items: [] }),
    observe(store, job, requests, { id: "impact-1", state: "running" }),
    observe(store, health, requests, { status: "ok" }),
    observe(store, settings, requests, { provider: "local" }),
  ];

  store.prime(job, LOCALE, completedJob);
  store.mutate(comparison, LOCALE, (current) => ({
    ...current,
    analysis,
    analysis_job: completedJob,
  }));
  await store.invalidate(history);

  const updated = store.getSnapshot(comparison, LOCALE).data;
  assertOnlyRequests(requests, { [history.id]: 1 });
  assert.strictEqual(updated.diff, diff);
  assert.strictEqual(updated.analysis, analysis);
  assert.strictEqual(updated.analysis_job, completedJob);
  cleanup(store, subscriptions);
});

test("relation review refreshes its history and every inbox query, but no analysis or law", async () => {
  const store = new ResourceStore();
  const reviews = flowKey("monitoring:relation-reviews:relation-1", {
    tags: ["relation-reviews", "relation:relation-1"],
  });
  const analyses = flowKey("monitoring:relation-analyses:relation-1", {
    tags: ["relation-analyses", "relation:relation-1"],
  });
  const inboxAll = flowKey("monitoring:/impact-inbox", {
    tags: ["impact-inbox"],
  });
  const inboxUnread = flowKey("monitoring:/impact-inbox?state=unread", {
    tags: ["impact-inbox"],
  });
  const laws = flowKey("monitoring:laws", { tags: ["laws"] });
  const health = flowKey("runtime:health", {
    tags: ["health"],
    owner: "runtime",
  });
  const analysisValue = { items: [{ id: "analysis-before-review" }] };
  const requests = {};
  const subscriptions = [
    observe(store, reviews, requests, { items: [] }),
    observe(store, analyses, requests, analysisValue),
    observe(store, inboxAll, requests, { items: [] }),
    observe(store, inboxUnread, requests, { items: [] }),
    observe(store, laws, requests, [{ id: "law-1" }]),
    observe(store, health, requests, { status: "ok" }),
  ];

  await store.invalidate(reviews);
  await store.invalidate(resourceTag("impact-inbox", "organization"));

  assertOnlyRequests(requests, {
    [reviews.id]: 1,
    [inboxAll.id]: 1,
    [inboxUnread.id]: 1,
  });
  assert.strictEqual(store.getSnapshot(analyses, LOCALE).data, analysisValue);
  cleanup(store, subscriptions);
});

test("watch creation updates the law list and refreshes discovery/status only", async () => {
  const store = new ResourceStore();
  const laws = flowKey("monitoring:laws", { tags: ["laws"] });
  const registryAll = flowKey("monitoring:/registry", { tags: ["registry"] });
  const registryFiltered = flowKey("monitoring:/registry?period=today", {
    tags: ["registry"],
  });
  const organizationStatus = flowKey("organization:status", {
    tags: ["organization-status"],
    owner: "organization",
  });
  const sources = flowKey("monitoring:sources", { tags: ["sources"] });
  const health = flowKey("runtime:health", {
    tags: ["health"],
    owner: "runtime",
  });
  const requests = {};
  const initialLaw = { id: "law-1", title: "Existing law" };
  const newLaw = { id: "law-2", title: "New watch" };
  const subscriptions = [
    observe(store, laws, requests, [initialLaw]),
    observe(store, registryAll, requests, { items: [] }),
    observe(store, registryFiltered, requests, { items: [] }),
    observe(store, organizationStatus, requests, { law_count: 1 }),
    observe(store, sources, requests, [{ id: "source-1" }]),
    observe(store, health, requests, { status: "ok" }),
  ];

  store.mutate(laws, LOCALE, (current) => [
    newLaw,
    ...current.filter((item) => item.id !== newLaw.id),
  ]);
  await store.invalidate(
    resourceTag("registry", "organization"),
    organizationStatus,
  );

  assertOnlyRequests(requests, {
    [registryAll.id]: 1,
    [registryFiltered.id]: 1,
    [organizationStatus.id]: 1,
  });
  assert.deepEqual(store.getSnapshot(laws, LOCALE).data, [newLaw, initialLaw]);
  cleanup(store, subscriptions);
});

test("organization switch clears session and organization data without touching platform state", () => {
  const store = new ResourceStore();
  const session = flowKey("auth:session", {
    tags: ["auth-session"],
    scope: "session",
    owner: "auth",
  });
  const laws = flowKey("monitoring:laws", { tags: ["laws"] });
  const platform = flowKey("platform:status", {
    tags: ["platform-status"],
    scope: "platform",
    owner: "administration",
  });
  const requests = {};
  const platformValue = { organizations: 12 };
  const subscriptions = [
    observe(store, session, requests, { organization_id: "old-org" }),
    observe(store, laws, requests, [{ id: "old-org-law" }]),
    observe(store, platform, requests, platformValue),
  ];

  store.resetScope("organization");
  store.resetScope("session");

  assert.equal(store.getSnapshot(session, LOCALE).data, null);
  assert.equal(store.getSnapshot(laws, LOCALE).data, null);
  assert.strictEqual(store.getSnapshot(platform, LOCALE).data, platformValue);
  assertOnlyRequests(requests, {});
  cleanup(store, subscriptions);
});

test("sign-out clears every scoped snapshot without issuing background requests", () => {
  const store = new ResourceStore();
  const session = flowKey("auth:session", {
    scope: "session",
    owner: "auth",
  });
  const organization = flowKey("organization:profile", {
    owner: "organization",
  });
  const platform = flowKey("platform:status", {
    scope: "platform",
    owner: "administration",
  });
  const requests = {};
  const subscriptions = [
    observe(store, session, requests, { authenticated: true }),
    observe(store, organization, requests, { name: "Acme" }),
    observe(store, platform, requests, { workers: 1 }),
  ];

  store.resetScope("all");

  assert.equal(store.getSnapshot(session, LOCALE).data, null);
  assert.equal(store.getSnapshot(organization, LOCALE).data, null);
  assert.equal(store.getSnapshot(platform, LOCALE).data, null);
  assertOnlyRequests(requests, {});
  cleanup(store, subscriptions);
});

function componentFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = `${directory}/${entry.name}`;
    if (entry.isDirectory()) return componentFiles(path);
    return /\.(?:ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}

function source(relativePath) {
  return readFileSync(new URL(`../${relativePath}`, import.meta.url), "utf8");
}

function compact(value) {
  return value.replace(/\s+/g, " ");
}

test("flow call sites use targeted cache contracts instead of global refresh broadcasts", () => {
  const comparison = compact(source("apps/web/components/comparison-view.tsx"));
  const impactInbox = compact(
    source("apps/web/components/impact-inbox-page.tsx"),
  );
  const documentForms = compact(
    source("apps/web/components/document-forms.tsx"),
  );
  const shell = compact(source("apps/web/components/shell.tsx"));
  const organization = compact(
    source("apps/web/components/organization-page.tsx"),
  );
  const api = source("apps/web/lib/api.ts");
  const resourceKeys = compact(source("apps/web/lib/resource-keys.ts"));
  const everyComponent = componentFiles(COMPONENTS_DIRECTORY)
    .map((path) => readFileSync(path, "utf8"))
    .join("\n");

  assert.doesNotMatch(everyComponent, /\brefreshWorkspace\b/);
  assert.doesNotMatch(api, /helvetic-lens:refresh/);
  assert.doesNotMatch(
    everyComponent,
    /useResource(?:<[^>]+>)?\s*\(\s*["'`]/,
    "components must declare ownership through typed resource keys",
  );
  for (const name of ["profile", "settings", "prompts"]) {
    const start = resourceKeys.indexOf(`${name}:`);
    assert.notEqual(start, -1, `missing ${name} resource factory`);
    assert.ok(
      resourceKeys.slice(start, start + 650).includes("varyByLocale: false"),
      `${name} configuration must be shared across UI locales`,
    );
  }

  assert.ok(comparison.includes("resources.comparisonAskJobs(comparisonId)"));
  assert.ok(
    comparison.includes(
      "primeResourceForLocale(resources.job(next.id), locale, next)",
    ),
  );
  assert.ok(comparison.includes("askJobs.setData"));
  assert.ok(
    comparison.includes(
      "analysisJobActive && effectiveAnalysisJob ? resources.job(effectiveAnalysisJob.id) : null",
    ),
  );
  assert.doesNotMatch(
    comparison,
    /(?:current|next)\s*=\s*await\s+api<Job>\(["'`]\/jobs\//,
  );
  assert.doesNotMatch(comparison, /setInterval\(async/);
  assert.ok(
    comparison.includes(
      "mutateResourceForLocale<Comparison>( resources.comparison(id), effectiveAnalysisJobLocale,",
    ),
  );
  assert.ok(
    comparison.includes(
      "setAnalysisJobs((current) => ({ ...current, [requestLocale]: queued })); mutateResourceForLocale<Comparison>( resources.comparison(id), requestLocale,",
    ),
    "an enqueued Impact job must be recorded before the component can navigate away",
  );
  assert.ok(
    comparison.includes(
      "primeResourceForLocale(resources.job(queued.id), requestLocale, queued)",
    ),
    "long-running Impact work must remain bound to the locale that queued it",
  );
  assert.ok(
    comparison.includes(
      "invalidateResources(resources.comparisonHistory(comparisonId))",
    ),
  );
  assert.doesNotMatch(comparison, /window\.location\.(?:reload|assign)/);

  assert.ok(
    impactInbox.includes(
      "invalidateResources(resources.relationReviews(item.organization_candidate_id))",
    ),
  );
  assert.ok(
    impactInbox.includes('resourceTag("impact-inbox", "organization")'),
  );

  assert.ok(documentForms.includes("mutateResource<Law[]>( resources.laws(),"));
  assert.ok(documentForms.includes('resourceTag("registry", "organization")'));
  assert.ok(documentForms.includes("resources.organizationStatus()"));

  assert.ok(organization.includes("if (invitationsResource.data)"));
  assert.ok(
    organization.includes(
      "await invalidateResources( resources.organizationInvitations<Invitation[]>(), )",
    ),
    "a cold invitation cache must be loaded instead of replaced by one new item",
  );

  assert.ok(
    shell.includes(
      'resetResourceScope("organization"); resetResourceScope("session");',
    ),
  );
  assert.ok(shell.includes('resetResourceScope("all")'));
});
