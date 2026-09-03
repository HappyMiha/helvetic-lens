"use client";

import { useCallback, useEffect, useState } from "react";

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const method = (init.method || "GET").toUpperCase();
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
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
    throw new Error(
      typeof message === "string"
        ? message
        : "The API could not complete this request. Check that it is running.",
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
              : "Could not load this data.",
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
  if (!value) return "Not checked yet";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
export function dateOnly(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
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
    : "Something went wrong. Please try again.";
}
