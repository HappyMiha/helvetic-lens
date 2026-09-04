"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";
import { storedLocale, translate } from "@/lib/i18n";
import {
  disabledResourceSnapshot,
  resourceKey,
  resourceTag,
  ResourceStore,
  type ResourceInvalidation,
  type ResourceKey,
  type ResourceScope,
  type ResourceSnapshot,
  type ResourceSubscriptionOptions,
  type ResourceTagTarget,
  type ResourceUpdater,
} from "@/lib/resource-cache";
import { legacyResourceKey, resources } from "@/lib/resource-keys";

export { resourceKey, resources, resourceTag };
export type {
  ResourceInvalidation,
  ResourceKey,
  ResourceScope,
  ResourceSnapshot,
  ResourceTagTarget,
  ResourceUpdater,
};

export type ResourceOptions = ResourceSubscriptionOptions;

const resourceStore = new ResourceStore();

export class ApiError extends Error {
  constructor(
    message: string,
    public code = "request_failed",
    public params: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const method = (init.method || "GET").toUpperCase();
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  headers.set("Accept-Language", storedLocale());
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith("helvetic_lens_csrf="))
      ?.split("=", 2)[1];
    if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  }
  const response = await fetch("/api" + path, {
    ...init,
    headers,
    cache: "no-store",
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    let message = data?.detail;
    if (Array.isArray(message))
      message = message.map((item: { msg: string }) => item.msg).join("; ");
    const locale = storedLocale();
    const localized =
      typeof data?.code === "string"
        ? translate(locale, `error.${data.code}`, data?.params || {})
        : null;
    throw new ApiError(
      localized ||
        (typeof message === "string"
          ? message
          : translate(locale, "error.fallback") || "Request failed."),
      typeof data?.code === "string" ? data.code : "request_failed",
      data?.params || {},
    );
  }
  return data as T;
}

export function invalidateResources(
  ...targets: ResourceInvalidation[]
): Promise<void> {
  return resourceStore.invalidate(...targets);
}

export function mutateResource<T>(
  key: ResourceKey<T>,
  updater: ResourceUpdater<T>,
): T | null {
  return resourceStore.mutate(key, storedLocale(), updater);
}

/**
 * Updates a locale-specific cache entry captured by an earlier interaction.
 * Long-running requests must not write their result into a different locale
 * merely because the user changed language while the request was running.
 */
export function mutateResourceForLocale<T>(
  key: ResourceKey<T>,
  locale: string,
  updater: ResourceUpdater<T>,
): T | null {
  return resourceStore.mutate(key, locale, updater);
}

export function primeResource<T>(key: ResourceKey<T>, value: T): T {
  return resourceStore.prime(key, storedLocale(), value);
}

export function primeResourceForLocale<T>(
  key: ResourceKey<T>,
  locale: string,
  value: T,
): T {
  return resourceStore.prime(key, locale, value);
}

/**
 * Loads a typed resource through the same store used by useResource.
 * Imperative workflows such as durable-job polling therefore share in-flight
 * requests and the latest snapshot with mounted subscribers.
 */
export async function fetchResource<T>(key: ResourceKey<T>): Promise<T> {
  const locale = storedLocale();
  const value = await resourceStore.revalidate(
    key,
    locale,
    (signal) => api<T>(key.path, { signal }),
    true,
  );
  if (value !== undefined) return value;
  const snapshot = resourceStore.getSnapshot(key, locale);
  throw new Error(
    snapshot.error || translate(locale, "error.fallback") || "Request failed.",
  );
}

export function resetResourceScope(scope: ResourceScope | "all"): void {
  resourceStore.resetScope(scope);
}

export function useResource<T>(
  input: ResourceKey<T> | string | null,
  intervalOrOptions?: number | ResourceOptions,
) {
  const candidate =
    typeof input === "string" ? legacyResourceKey<T>(input) : input;
  const locale = storedLocale();
  const candidateCacheId = candidate
    ? resourceStore.cacheId(candidate, locale)
    : "disabled";
  const key = useMemo(
    () => candidate,
    // Resource factories intentionally return immutable value objects. Their
    // cache identity and path, rather than object identity, own a subscription.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [candidateCacheId, candidate?.path],
  );
  const pollMs =
    typeof intervalOrOptions === "number"
      ? intervalOrOptions
      : intervalOrOptions?.pollMs;
  const staleMs =
    typeof intervalOrOptions === "number"
      ? intervalOrOptions || undefined
      : intervalOrOptions?.staleMs;
  const priority =
    typeof intervalOrOptions === "number"
      ? undefined
      : intervalOrOptions?.priority;
  const cacheId = candidateCacheId;
  const path = key?.path || "";
  const loader = useCallback(
    (signal: AbortSignal) => api<T>(path, { signal }),
    [path],
  );
  const subscribe = useCallback(
    (listener: () => void) =>
      key
        ? resourceStore.subscribe(key, locale, listener, loader, {
            pollMs,
            staleMs,
            priority,
          })
        : () => undefined,
    [cacheId, key, loader, locale, pollMs, priority, staleMs],
  );
  const getSnapshot = useCallback(
    () =>
      key
        ? resourceStore.getSnapshot(key, locale)
        : (disabledResourceSnapshot as ResourceSnapshot<T>),
    [cacheId, key, locale],
  );
  const getServerSnapshot = useCallback(
    () => disabledResourceSnapshot as ResourceSnapshot<T>,
    [],
  );
  const snapshot = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot,
  );
  const reload = useCallback(
    () =>
      key
        ? resourceStore.revalidate(key, locale, loader, true)
        : Promise.resolve(undefined),
    [cacheId, key, loader, locale],
  );
  const setData = useCallback(
    (updater: ResourceUpdater<T>) =>
      key ? resourceStore.mutate(key, locale, updater) : null,
    [cacheId, key, locale],
  );
  return { ...snapshot, reload, setData };
}

export function dateTime(value: string | null | undefined) {
  const locale = storedLocale();
  if (!value)
    return translate(locale, "format.notChecked") || "Not checked yet";
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Zurich",
  }).format(new Date(value));
}
export function dateOnly(value: string) {
  return new Intl.DateTimeFormat(storedLocale(), {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "Europe/Zurich",
  }).format(new Date(value));
}
export function host(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
export function label(value: string | null) {
  return (value || "pending").replaceAll("_", " ");
}
export function errorText(cause: unknown) {
  return cause instanceof Error
    ? cause.message
    : translate(storedLocale(), "error.fallback") || "Request failed.";
}
