"use client";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { hazardCopy } from "@/lib/hazard-copy";
import { roadCopy } from "@/lib/road-copy";
const base = "/hazard-watch";
export const AccessFailure = createContext<(error: unknown) => void>(() => {});
export function useData<T>(path: string | null, revision = 0) {
  const deny = useContext(AccessFailure),
    key = `${path}:${revision}`;
  const [result, setResult] = useState<{
    key: string;
    data?: T;
    error?: unknown;
  }>({ key: "" });
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    api<T>(base + path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ key, data });
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          deny(error);
          setResult({ key, error });
        }
      });
    return () => controller.abort();
  }, [path, key, deny]);
  return result.key === key ? result : { key };
}
export function useMutation() {
  const { locale } = useI18n(),
    c = hazardCopy[locale],
    r = roadCopy[locale],
    deny = useContext(AccessFailure);
  const pending = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => () => pending.current?.abort(), []);
  async function run<T>(
    path: string,
    body: unknown,
    done: (value: T) => void,
    method = "POST",
  ) {
    if (pending.current) return;
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    setError("");
    try {
      const value = await api<T>(base + path, {
        method,
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!controller.signal.aborted) done(value);
    } catch (problem) {
      if (!controller.signal.aborted) {
        deny(problem);
        setError(
          problem instanceof ApiError && problem.code.includes("conflict")
            ? c.changed
            : r.failed,
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        pending.current = null;
        setBusy(false);
      }
    }
  }
  return { run, busy, error };
}
