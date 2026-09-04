import assert from "node:assert/strict";
import test from "node:test";
import {
  ResourceStore,
  resourceKey,
  resourceTag,
} from "../apps/web/lib/resource-cache.ts";

function key(id, tags = [], options = {}) {
  return resourceKey({
    id,
    path: `/test/${id}`,
    scope: "organization",
    owner: "monitoring",
    tags,
    varyByLocale: true,
    ...options,
  });
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function flush() {
  await Promise.resolve();
  await Promise.resolve();
}

class FakeIntervals {
  nextId = 0;
  callbacks = new Map();

  set = (callback) => {
    const id = ++this.nextId;
    this.callbacks.set(id, callback);
    return id;
  };

  clear = (id) => {
    this.callbacks.delete(id);
  };

  fire() {
    for (const callback of [...this.callbacks.values()]) callback();
  }
}

test("deduplicates concurrent requests for one scoped key", async () => {
  const store = new ResourceStore();
  const resource = key("dedupe");
  const pending = deferred();
  let requests = 0;
  const loader = async () => {
    requests += 1;
    return pending.promise;
  };

  const first = store.revalidate(resource, "en-CH", loader);
  const second = store.revalidate(resource, "en-CH", loader);
  await flush();
  assert.equal(requests, 1);

  pending.resolve({ value: "ready" });
  assert.deepEqual(await first, { value: "ready" });
  assert.deepEqual(await second, { value: "ready" });
  assert.deepEqual(store.getSnapshot(resource, "en-CH").data, {
    value: "ready",
  });
  store.destroy();
});

test("keeps stale data visible while one background revalidation runs", async () => {
  let now = 0;
  const store = new ResourceStore({ now: () => now });
  const resource = key("swr");
  store.prime(resource, "en-CH", { value: "saved" });
  now = 50;
  const pending = deferred();
  let requests = 0;
  const unsubscribe = store.subscribe(
    resource,
    "en-CH",
    () => undefined,
    async () => {
      requests += 1;
      return pending.promise;
    },
    { staleMs: 10 },
  );
  await flush();

  const during = store.getSnapshot(resource, "en-CH");
  assert.equal(requests, 1);
  assert.deepEqual(during.data, { value: "saved" });
  assert.equal(during.loading, false);
  assert.equal(during.validating, true);
  assert.equal(during.stale, true);

  pending.resolve({ value: "fresh" });
  await flush();
  const after = store.getSnapshot(resource, "en-CH");
  assert.deepEqual(after.data, { value: "fresh" });
  assert.equal(after.validating, false);
  assert.equal(after.stale, false);
  unsubscribe();
  store.destroy();
});

test("invalidates exact keys and query-family tags without unrelated requests", async () => {
  const store = new ResourceStore();
  const first = key("registry:first", ["registry"]);
  const second = key("registry:second", ["registry"]);
  const health = key("health", ["health"]);
  const counts = { first: 0, second: 0, health: 0 };

  for (const [resource, name] of [
    [first, "first"],
    [second, "second"],
    [health, "health"],
  ]) {
    store.prime(resource, "en-CH", { name });
    store.subscribe(
      resource,
      "en-CH",
      () => undefined,
      async () => {
        counts[name] += 1;
        return { name, refreshed: counts[name] };
      },
      { staleMs: Number.POSITIVE_INFINITY },
    );
  }

  await store.invalidate(first);
  assert.deepEqual(counts, { first: 1, second: 0, health: 0 });

  await store.invalidate(resourceTag("registry", "organization"));
  assert.deepEqual(counts, { first: 2, second: 1, health: 0 });
  store.destroy();
});

test("one central poller serves duplicate subscribers and pauses while hidden", async () => {
  const timers = new FakeIntervals();
  const store = new ResourceStore({
    setInterval: timers.set,
    clearInterval: timers.clear,
  });
  const resource = key("polling");
  let requests = 0;
  const loader = async () => ({ request: ++requests });
  store.prime(resource, "en-CH", { request: 0 });

  const first = store.subscribe(resource, "en-CH", () => undefined, loader, {
    pollMs: 100,
    staleMs: Number.POSITIVE_INFINITY,
  });
  const second = store.subscribe(resource, "en-CH", () => undefined, loader, {
    pollMs: 100,
    staleMs: Number.POSITIVE_INFINITY,
  });
  assert.equal(timers.callbacks.size, 1);

  timers.fire();
  await flush();
  assert.equal(requests, 1);

  store.setActivity({ hidden: true });
  assert.equal(timers.callbacks.size, 0);
  timers.fire();
  await flush();
  assert.equal(requests, 1);

  store.setActivity({ hidden: false });
  assert.equal(timers.callbacks.size, 1);
  timers.fire();
  await flush();
  assert.equal(requests, 2);
  first();
  second();
  assert.equal(timers.callbacks.size, 0);
  store.destroy();
});

test("online recovery and focus-style refresh coalesce stale work", async () => {
  let now = 0;
  const store = new ResourceStore({ now: () => now });
  const resource = key("reconnect");
  store.prime(resource, "en-CH", { request: 0 });
  store.setActivity({ online: false });
  const pending = deferred();
  let requests = 0;
  const unsubscribe = store.subscribe(
    resource,
    "en-CH",
    () => undefined,
    async () => {
      requests += 1;
      return pending.promise;
    },
    { staleMs: 10 },
  );
  now = 20;

  store.setActivity({ online: true });
  const focusRefresh = store.refreshStale();
  await flush();
  assert.equal(requests, 1);
  pending.resolve({ request: 1 });
  await focusRefresh;
  await flush();
  assert.deepEqual(store.getSnapshot(resource, "en-CH").data, {
    request: 1,
  });
  unsubscribe();
  store.destroy();
});

test("a local mutation wins over an older request that ignores abort", async () => {
  const store = new ResourceStore();
  const resource = key("mutation-race");
  const pending = deferred();
  const request = store.revalidate(
    resource,
    "en-CH",
    async () => pending.promise,
  );
  await flush();

  store.mutate(resource, "en-CH", { value: "optimistic" });
  pending.resolve({ value: "obsolete" });
  await request;
  assert.deepEqual(store.getSnapshot(resource, "en-CH").data, {
    value: "optimistic",
  });
  store.destroy();
});

test("invalidation supersedes a request started before the mutation", async () => {
  const store = new ResourceStore();
  const resource = key("invalidate-race");
  const first = deferred();
  const second = deferred();
  let requests = 0;
  const unsubscribe = store.subscribe(
    resource,
    "en-CH",
    () => undefined,
    async () => {
      requests += 1;
      return requests === 1 ? first.promise : second.promise;
    },
  );
  await flush();
  assert.equal(requests, 1);

  const invalidation = store.invalidate(resource);
  await flush();
  assert.equal(requests, 2);
  second.resolve({ value: "after-mutation" });
  await invalidation;

  first.resolve({ value: "before-mutation" });
  await flush();
  assert.deepEqual(store.getSnapshot(resource, "en-CH").data, {
    value: "after-mutation",
  });
  unsubscribe();
  store.destroy();
});

test("scope reset clears data and rejects late responses from the old epoch", async () => {
  const store = new ResourceStore();
  const organization = key("organization-data");
  const platform = resourceKey({
    id: "platform-data",
    path: "/admin/test",
    scope: "platform",
    owner: "administration",
    varyByLocale: false,
  });
  store.prime(platform, "en-CH", { retained: true });
  const pending = deferred();
  const request = store.revalidate(
    organization,
    "en-CH",
    async () => pending.promise,
  );
  await flush();
  const previousEpoch = store.scopeEpoch("organization");

  store.resetScope("organization");
  assert.equal(store.scopeEpoch("organization"), previousEpoch + 1);
  pending.resolve({ leaked: true });
  await request;

  const reset = store.getSnapshot(organization, "en-CH");
  assert.equal(reset.data, null);
  assert.equal(reset.loading, true);
  assert.deepEqual(store.getSnapshot(platform, "en-CH").data, {
    retained: true,
  });
  store.destroy();
});

test("evicts least-recently-used inactive query entries", () => {
  const store = new ResourceStore({ maxEntries: 3 });
  const first = key("query:first");
  const second = key("query:second");
  const retained = key("query:retained");
  const latest = key("query:latest");

  store.prime(first, "en-CH", { value: 1 });
  store.prime(second, "en-CH", { value: 2 });
  store.prime(retained, "en-CH", { value: 3 });
  const unsubscribe = store.subscribe(
    retained,
    "en-CH",
    () => undefined,
    async () => ({ value: 3 }),
    { staleMs: Number.POSITIVE_INFINITY },
  );
  store.prime(latest, "en-CH", { value: 4 });

  assert.equal(store.entryCount(), 3);
  assert.deepEqual(store.getSnapshot(retained, "en-CH").data, { value: 3 });
  assert.deepEqual(store.getSnapshot(latest, "en-CH").data, { value: 4 });
  unsubscribe();
  store.destroy();
});
