"use client";
import { useEffect, useRef, useState } from "react";
import { errorText, fetchResource, resourceScopeEpoch, useResource } from "./api";
import type { ResourceKey } from "./resource-cache";
export type InterestPage<T> = {items: T[]; next_cursor: string | null};
export function useFeedInterestPage<T>(items: T[], nextCursor: string | null,
  resource: (cursor: string) => ResourceKey<InterestPage<T>>) {
  const [cursors, setCursors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const generation = useRef(0);
  useEffect(() => () => { generation.current++; }, []);
  const cursor = cursors.at(-1);
  const page = useResource(cursor === undefined ? null : resource(cursor));
  const shown = cursor === undefined ? items : page.data?.items || [];
  const next = cursor === undefined ? nextCursor : page.data?.next_cursor;
  async function move(stack: string[]) {
    if (busy) return;
    const current = generation.current, epoch = resourceScopeEpoch("session");
    setBusy(true); setFailure("");
    try {
      if (stack.length) await fetchResource(resource(stack.at(-1)!));
      if (current === generation.current && epoch === resourceScopeEpoch("session")) setCursors(stack);
    } catch (cause) {
      if (current === generation.current && epoch === resourceScopeEpoch("session")) setFailure(errorText(cause));
    } finally {
      if (current === generation.current && epoch === resourceScopeEpoch("session")) setBusy(false);
    }
  }
  return {shown, next, cursors, busy, error: failure || page.error, move};
}
