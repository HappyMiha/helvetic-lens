export type ResourceScope = "session" | "organization" | "platform";

export type ResourceOwner =
  | "auth"
  | "runtime"
  | "monitoring"
  | "comparison"
  | "organization"
  | "administration";

export type ResourcePriority = "background" | "interactive";

export type ResourceKey<T> = Readonly<{
  id: string;
  path: string;
  scope: ResourceScope;
  owner: ResourceOwner;
  tags: readonly string[];
  varyByLocale: boolean;
  staleMs?: number;
  pollMs?: number;
  priority?: ResourcePriority;
  /** Type-only marker. */
  __result?: T;
}>;

export type ResourceTagTarget = Readonly<{
  kind: "tag";
  tag: string;
  scope?: ResourceScope;
}>;

export type ResourceInvalidation = ResourceKey<unknown> | ResourceTagTarget;

export type ResourceSnapshot<T> = Readonly<{
  data: T | null;
  error: string;
  loading: boolean;
  validating: boolean;
  stale: boolean;
  updatedAt: number | null;
}>;

export type ResourceUpdater<T> = T | null | ((current: T | null) => T | null);

export type ResourceSubscriptionOptions = {
  pollMs?: number;
  staleMs?: number;
  priority?: ResourcePriority;
};

type ResourceLoader<T> = (signal: AbortSignal) => Promise<T>;

type Subscription = {
  listener: () => void;
  loader: ResourceLoader<unknown>;
  pollMs: number;
  staleMs: number;
  priority: ResourcePriority;
};

type ResourceEntry = {
  cacheId: string;
  key: ResourceKey<unknown>;
  locale: string;
  lastAccess: number;
  snapshot: ResourceSnapshot<unknown>;
  hasData: boolean;
  subscriptions: Map<number, Subscription>;
  loader: ResourceLoader<unknown> | null;
  inFlight: Promise<unknown | undefined> | null;
  controller: AbortController | null;
  requestGeneration: number;
  timer: ReturnType<typeof setInterval> | null;
};

type ResourceStoreOptions = {
  now?: () => number;
  setInterval?: (
    callback: () => void,
    milliseconds: number,
  ) => ReturnType<typeof setInterval>;
  clearInterval?: (timer: ReturnType<typeof setInterval>) => void;
  maxEntries?: number;
};

const DEFAULT_STALE_MS = 30_000;
const DEFAULT_MAX_ENTRIES = 250;

const initialSnapshot = <T>(): ResourceSnapshot<T> => ({
  data: null,
  error: "",
  loading: true,
  validating: false,
  stale: true,
  updatedAt: null,
});

export const disabledResourceSnapshot: ResourceSnapshot<never> = Object.freeze({
  data: null,
  error: "",
  loading: false,
  validating: false,
  stale: false,
  updatedAt: null,
});

export function resourceKey<T>(
  definition: Omit<ResourceKey<T>, "tags" | "varyByLocale"> & {
    tags?: readonly string[];
    varyByLocale?: boolean;
  },
): ResourceKey<T> {
  return Object.freeze({
    ...definition,
    tags: Object.freeze([
      ...new Set(["all-resources", ...(definition.tags || [])]),
    ]),
    varyByLocale: definition.varyByLocale ?? true,
  });
}

export function resourceTag(
  tag: string,
  scope?: ResourceScope,
): ResourceTagTarget {
  return Object.freeze({ kind: "tag", tag, ...(scope ? { scope } : {}) });
}

function isTagTarget(
  target: ResourceInvalidation,
): target is ResourceTagTarget {
  return "kind" in target && target.kind === "tag";
}

function errorMessage(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Request failed.";
}

/**
 * A small external resource store used by the React adapter in api.ts.
 * It deliberately knows nothing about React or HTTP, which keeps request
 * ownership, deduplication and polling deterministic and directly testable.
 */
export class ResourceStore {
  private readonly entries = new Map<string, ResourceEntry>();
  private readonly scopeEpochs: Record<ResourceScope, number> = {
    session: 0,
    organization: 0,
    platform: 0,
  };
  private readonly now: () => number;
  private readonly startInterval: ResourceStoreOptions["setInterval"];
  private readonly stopInterval: ResourceStoreOptions["clearInterval"];
  private readonly maxEntries: number;
  private nextSubscriptionId = 0;
  private accessSequence = 0;
  private hidden = false;
  private online = true;
  private lifecycleAttached = false;

  constructor(options: ResourceStoreOptions = {}) {
    this.now = options.now || Date.now;
    this.startInterval =
      options.setInterval ||
      ((callback, milliseconds) => setInterval(callback, milliseconds));
    this.stopInterval =
      options.clearInterval || ((timer) => clearInterval(timer));
    this.maxEntries = Math.max(1, options.maxEntries ?? DEFAULT_MAX_ENTRIES);
  }

  cacheId<T>(key: ResourceKey<T>, locale = ""): string {
    return [
      key.scope,
      key.varyByLocale ? locale || "default" : "*",
      key.id,
    ].join(":");
  }

  private entry<T>(key: ResourceKey<T>, locale = ""): ResourceEntry {
    const cacheId = this.cacheId(key, locale);
    const existing = this.entries.get(cacheId);
    if (existing) {
      existing.key = key as ResourceKey<unknown>;
      existing.locale = locale;
      existing.lastAccess = ++this.accessSequence;
      return existing;
    }
    const created: ResourceEntry = {
      cacheId,
      key: key as ResourceKey<unknown>,
      locale,
      lastAccess: ++this.accessSequence,
      snapshot: initialSnapshot(),
      hasData: false,
      subscriptions: new Map(),
      loader: null,
      inFlight: null,
      controller: null,
      requestGeneration: 0,
      timer: null,
    };
    this.entries.set(cacheId, created);
    this.pruneEntries(cacheId);
    return created;
  }

  private pruneEntries(preserveCacheId?: string): void {
    if (this.entries.size <= this.maxEntries) return;
    const removable = [...this.entries.values()]
      .filter(
        (entry) =>
          entry.cacheId !== preserveCacheId &&
          entry.subscriptions.size === 0 &&
          !entry.inFlight,
      )
      .sort((left, right) => left.lastAccess - right.lastAccess);
    for (const entry of removable) {
      if (this.entries.size <= this.maxEntries) break;
      this.clearTimer(entry);
      entry.controller?.abort();
      this.entries.delete(entry.cacheId);
    }
  }

  entryCount(): number {
    return this.entries.size;
  }

  getSnapshot<T>(key: ResourceKey<T>, locale = ""): ResourceSnapshot<T> {
    return this.entry(key, locale).snapshot as ResourceSnapshot<T>;
  }

  private publish(
    entry: ResourceEntry,
    patch: Partial<ResourceSnapshot<unknown>>,
  ): void {
    entry.snapshot = Object.freeze({ ...entry.snapshot, ...patch });
    for (const subscription of entry.subscriptions.values()) {
      subscription.listener();
    }
  }

  private staleMs(entry: ResourceEntry): number {
    const configured = [...entry.subscriptions.values()].map(
      (subscription) => subscription.staleMs,
    );
    return configured.length
      ? Math.min(...configured)
      : (entry.key.staleMs ?? DEFAULT_STALE_MS);
  }

  private isStale(entry: ResourceEntry): boolean {
    if (!entry.hasData || entry.snapshot.stale) return true;
    const staleMs = this.staleMs(entry);
    return (
      Number.isFinite(staleMs) &&
      entry.snapshot.updatedAt !== null &&
      this.now() - entry.snapshot.updatedAt >= staleMs
    );
  }

  private autoFetchPaused(entry: ResourceEntry): boolean {
    if (!this.online) return true;
    if (!this.hidden) return false;
    return ![...entry.subscriptions.values()].some(
      (subscription) => subscription.priority === "interactive",
    );
  }

  private clearTimer(entry: ResourceEntry): void {
    if (entry.timer === null) return;
    this.stopInterval?.(entry.timer);
    entry.timer = null;
  }

  private schedule(entry: ResourceEntry): void {
    this.clearTimer(entry);
    if (!entry.subscriptions.size || this.autoFetchPaused(entry)) return;
    const intervals = [...entry.subscriptions.values()]
      .map((subscription) => subscription.pollMs)
      .filter((milliseconds) => milliseconds > 0);
    if (!intervals.length) return;
    const milliseconds = Math.min(...intervals);
    entry.timer =
      this.startInterval?.(() => {
        if (!entry.loader || this.autoFetchPaused(entry)) return;
        void this.revalidateEntry(entry, entry.loader, true);
      }, milliseconds) || null;
  }

  subscribe<T>(
    key: ResourceKey<T>,
    locale: string,
    listener: () => void,
    loader: ResourceLoader<T>,
    options: ResourceSubscriptionOptions = {},
  ): () => void {
    this.attachBrowserLifecycle();
    const entry = this.entry(key, locale);
    const id = ++this.nextSubscriptionId;
    const pollMs = Math.max(0, options.pollMs ?? key.pollMs ?? 0);
    const staleMs = Math.max(
      0,
      options.staleMs ?? key.staleMs ?? (pollMs || DEFAULT_STALE_MS),
    );
    const subscription: Subscription = {
      listener,
      loader: loader as ResourceLoader<unknown>,
      pollMs,
      staleMs,
      priority: options.priority ?? key.priority ?? "background",
    };
    entry.subscriptions.set(id, subscription);
    entry.loader = subscription.loader;
    this.schedule(entry);
    if (this.isStale(entry) && !this.autoFetchPaused(entry)) {
      void this.revalidateEntry(entry, entry.loader, false);
    }
    return () => {
      entry.subscriptions.delete(id);
      if (entry.loader === subscription.loader) {
        entry.loader = [...entry.subscriptions.values()].at(-1)?.loader || null;
      }
      this.schedule(entry);
      this.pruneEntries();
    };
  }

  async revalidate<T>(
    key: ResourceKey<T>,
    locale: string,
    loader: ResourceLoader<T>,
    force = true,
  ): Promise<T | undefined> {
    const entry = this.entry(key, locale);
    entry.loader = loader as ResourceLoader<unknown>;
    return (await this.revalidateEntry(entry, entry.loader, force)) as
      T | undefined;
  }

  private revalidateEntry(
    entry: ResourceEntry,
    loader: ResourceLoader<unknown>,
    force: boolean,
  ): Promise<unknown | undefined> {
    if (entry.inFlight) return entry.inFlight;
    if (!this.online) return Promise.resolve(undefined);
    if (!force && !this.isStale(entry)) {
      return Promise.resolve(entry.snapshot.data);
    }

    const requestGeneration = ++entry.requestGeneration;
    const scopeEpoch = this.scopeEpochs[entry.key.scope];
    const controller = new AbortController();
    entry.controller = controller;
    this.publish(entry, {
      loading: !entry.hasData,
      validating: true,
      stale: this.isStale(entry),
    });

    const request = Promise.resolve()
      .then(() => loader(controller.signal))
      .then((value) => {
        if (
          entry.requestGeneration !== requestGeneration ||
          this.scopeEpochs[entry.key.scope] !== scopeEpoch
        ) {
          return undefined;
        }
        entry.hasData = true;
        this.publish(entry, {
          data: value,
          error: "",
          loading: false,
          validating: false,
          stale: false,
          updatedAt: this.now(),
        });
        return value;
      })
      .catch((cause: unknown) => {
        if (
          entry.requestGeneration === requestGeneration &&
          this.scopeEpochs[entry.key.scope] === scopeEpoch &&
          !controller.signal.aborted
        ) {
          this.publish(entry, {
            error: errorMessage(cause),
            loading: false,
            validating: false,
            stale: true,
          });
        }
        return undefined;
      })
      .finally(() => {
        if (entry.requestGeneration === requestGeneration) {
          entry.inFlight = null;
          if (entry.controller === controller) entry.controller = null;
        }
      });
    entry.inFlight = request;
    return request;
  }

  mutate<T>(
    key: ResourceKey<T>,
    locale: string,
    updater: ResourceUpdater<T>,
  ): T | null {
    const entry = this.entry(key, locale);
    const next =
      typeof updater === "function"
        ? (updater as (current: T | null) => T | null)(
            entry.snapshot.data as T | null,
          )
        : updater;
    entry.requestGeneration += 1;
    entry.controller?.abort();
    entry.controller = null;
    entry.inFlight = null;
    entry.hasData = true;
    this.publish(entry, {
      data: next,
      error: "",
      loading: false,
      validating: false,
      stale: false,
      updatedAt: this.now(),
    });
    return next;
  }

  prime<T>(key: ResourceKey<T>, locale: string, value: T): T {
    return this.mutate(key, locale, value) as T;
  }

  async invalidate(...targets: ResourceInvalidation[]): Promise<void> {
    const matched = new Set<ResourceEntry>();
    for (const entry of this.entries.values()) {
      if (
        targets.some((target) =>
          isTagTarget(target)
            ? (!target.scope || target.scope === entry.key.scope) &&
              entry.key.tags.includes(target.tag)
            : target.scope === entry.key.scope && target.id === entry.key.id,
        )
      ) {
        matched.add(entry);
      }
    }

    const requests: Promise<unknown>[] = [];
    for (const entry of matched) {
      // A request that began before the mutation which triggered this
      // invalidation can contain obsolete data. Supersede it before loading
      // the newly authoritative representation, even if abort is ignored.
      if (entry.inFlight) {
        entry.requestGeneration += 1;
        entry.controller?.abort();
        entry.controller = null;
        entry.inFlight = null;
      }
      this.publish(entry, { stale: true });
      if (
        entry.subscriptions.size &&
        entry.loader &&
        !this.autoFetchPaused(entry)
      ) {
        requests.push(this.revalidateEntry(entry, entry.loader, true));
      }
    }
    await Promise.all(requests);
  }

  resetScope(scope: ResourceScope | "all"): void {
    const scopes: ResourceScope[] =
      scope === "all" ? ["session", "organization", "platform"] : [scope];
    for (const value of scopes) this.scopeEpochs[value] += 1;
    for (const entry of this.entries.values()) {
      if (!scopes.includes(entry.key.scope)) continue;
      entry.requestGeneration += 1;
      entry.controller?.abort();
      entry.controller = null;
      entry.inFlight = null;
      entry.hasData = false;
      this.publish(entry, initialSnapshot());
    }
  }

  scopeEpoch(scope: ResourceScope): number {
    return this.scopeEpochs[scope];
  }

  async refreshStale(): Promise<void> {
    if (!this.online) return;
    const requests: Promise<unknown>[] = [];
    for (const entry of this.entries.values()) {
      if (
        entry.subscriptions.size &&
        entry.loader &&
        this.isStale(entry) &&
        !this.autoFetchPaused(entry)
      ) {
        requests.push(this.revalidateEntry(entry, entry.loader, false));
      }
    }
    await Promise.all(requests);
  }

  setActivity(state: { hidden?: boolean; online?: boolean }): void {
    const wasPaused = this.hidden || !this.online;
    if (typeof state.hidden === "boolean") this.hidden = state.hidden;
    if (typeof state.online === "boolean") this.online = state.online;
    const paused = this.hidden || !this.online;
    for (const entry of this.entries.values()) this.schedule(entry);
    if (wasPaused && !paused) void this.refreshStale();
  }

  attachBrowserLifecycle(): void {
    if (
      this.lifecycleAttached ||
      typeof window === "undefined" ||
      typeof document === "undefined"
    ) {
      return;
    }
    this.lifecycleAttached = true;
    this.hidden = document.hidden;
    this.online = typeof navigator === "undefined" ? true : navigator.onLine;
    document.addEventListener("visibilitychange", () => {
      this.setActivity({ hidden: document.hidden });
    });
    window.addEventListener("online", () => this.setActivity({ online: true }));
    window.addEventListener("offline", () =>
      this.setActivity({ online: false }),
    );
    window.addEventListener("focus", () => void this.refreshStale());
  }

  destroy(): void {
    for (const entry of this.entries.values()) {
      this.clearTimer(entry);
      entry.controller?.abort();
      entry.subscriptions.clear();
    }
    this.entries.clear();
  }
}
