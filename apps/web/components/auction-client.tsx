"use client";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { auctionCopy } from "@/lib/auction-copy";
import { auctionTrackingCopy } from "@/lib/auction-tracking-copy";
export const Failure = createContext<(error: unknown) => void>(() => {});
const base = "/auction-watch";
export function useData<T>(path: string | null, revision = 0) {
  const deny = useContext(Failure),
    key = `${path}:${revision}`;
  const [value, setValue] = useState<{
    key: string;
    data?: T;
    error?: unknown;
  }>({ key: "" });
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    api<T>(base + path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setValue({ key, data });
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          deny(error);
          setValue({ key, error });
        }
      });
    return () => controller.abort();
  }, [path, key, deny]);
  return value.key === key ? value : { key };
}
export function useMutation() {
  const { locale } = useI18n(),
    c = auctionCopy[locale],
    deny = useContext(Failure);
  const active = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => () => active.current?.abort(), []);
  async function run<T>(
    path: string,
    body: unknown,
    done: (data: T) => void,
    method = "POST",
  ) {
    if (active.current) return;
    const controller = new AbortController();
    active.current = controller;
    setBusy(true);
    setError("");
    try {
      const data = await api<T>(base + path, {
        method,
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!controller.signal.aborted) done(data);
    } catch (problem) {
      if (!controller.signal.aborted) {
        deny(problem);
        setError(
          problem instanceof ApiError &&
            (problem.code.includes("conflict") ||
              problem.code === "auction_item_refresh_required")
            ? c.conflict
            : problem instanceof ApiError &&
                problem.code === "auction_source_not_configured"
              ? auctionTrackingCopy[locale].missing
              : problem instanceof ApiError &&
                  problem.code === "auction_source_use_denied"
                ? auctionTrackingCopy[locale].noDecisionAccess
                : problem instanceof ApiError &&
                    /auction_(source|evidence|permission)/.test(problem.code)
                  ? auctionTrackingCopy[locale].unavailable
                  : c.invalid,
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        active.current = null;
        setBusy(false);
      }
    }
  }
  return { run, busy, error };
}
