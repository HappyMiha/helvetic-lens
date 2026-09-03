"use client";

import { useCallback, useEffect, useState } from "react";
import { storedLocale, translate } from "@/lib/i18n";

export class ApiError extends Error {
  constructor(message: string, public code = "request_failed", public params: Record<string, unknown> = {}) {
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
    const localized = typeof data?.code === "string" ? translate(locale, `error.${data.code}`, data?.params || {}) : null;
    throw new ApiError(
      localized || (typeof message === "string" ? message : translate(locale, "error.fallback") || "Request failed."),
      typeof data?.code === "string" ? data.code : "request_failed",
      data?.params || {},
    );
  }
  return data as T;
}

export function refreshWorkspace() {
  window.dispatchEvent(new Event("helvetic-lens:refresh"));
}

export function useResource<T>(path: string | null, interval = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    setData(null);
    setError("");
  }, [path]);
  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    let live = true;
    const controller = new AbortController();
    const load = async () => {
      try {
        const value = await api<T>(path, { signal: controller.signal });
        if (live) {
          setData(value);
          setError("");
        }
      } catch (cause) {
        if (live && !controller.signal.aborted)
          setError(
            cause instanceof Error
              ? cause.message
              : translate(storedLocale(), "error.fallback") || "Request failed.",
          );
      } finally {
        if (live) setLoading(false);
      }
    };
    setLoading(true);
    void load();
    const timer = interval ? window.setInterval(load, interval) : null;
    window.addEventListener("helvetic-lens:refresh", reload);
    return () => {
      live = false;
      controller.abort();
      if (timer) window.clearInterval(timer);
      window.removeEventListener("helvetic-lens:refresh", reload);
    };
  }, [path, interval, revision, reload]);
  return { data, error, loading, reload, setData };
}

export function dateTime(value: string | null | undefined) {
  const locale = storedLocale();
  if (!value) return translate(locale, "format.notChecked") || "Not checked yet";
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
