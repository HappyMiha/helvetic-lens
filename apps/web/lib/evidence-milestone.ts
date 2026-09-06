"use client";
import { useEffect, useRef, type RefObject } from "react";
import { useAuth } from "@/components/auth-gate";
import { api, invalidateResources, resourceScopeEpoch } from "./api";
import { resources } from "./resource-keys";

/** Record displayed text, not route prefetch or proof that a person understood it. */
export function useEvidenceMilestone(root: RefObject<HTMLElement | null>, id: string, native: boolean, enabled: boolean, page: number) {
  const { session } = useAuth();
  const user = session?.user?.id;
  const organization = session?.organization?.id;
  const allowed = Boolean(session?.authenticated || session?.anonymous_development);
  const recordedScope = useRef<string | null>(null);
  useEffect(() => {
    if (!enabled || !allowed || !root.current || !window.IntersectionObserver) return;
    const epoch = resourceScopeEpoch("session");
    const scope = JSON.stringify([epoch, user, organization, id, native]);
    if (recordedScope.current === scope) return;
    const visible = new Set<Element>();
    let disposed = false, done = false, busy = false, attempts = 0;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const abort = new AbortController();
    async function record() {
      if (disposed || done || busy || attempts >= 2 || !visible.size || document.visibilityState !== "visible" || epoch !== resourceScopeEpoch("session")) return;
      busy = true; attempts++;
      try {
        await api("/onboarding/evidence-displayed", {method:"POST", signal:abort.signal,
          body:JSON.stringify({kind:native ? "native_version" : "version", id})});
        done = true;
        if (!disposed && epoch === resourceScopeEpoch("session")) recordedScope.current = scope;
        if (!disposed && epoch === resourceScopeEpoch("session")) void invalidateResources(resources.onboarding());
      } catch {
        // A personal progress write must never hide the evidence or block reading.
        if (!disposed && attempts < 2) retry = setTimeout(() => void record(), 1500);
      } finally { busy = false; }
    }
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) entry.isIntersecting ? visible.add(entry.target) : visible.delete(entry.target);
      void record();
    });
    for (const element of root.current.querySelectorAll("[data-evidence-display-text]")) observer.observe(element);
    document.addEventListener("visibilitychange", record);
    return () => { disposed = true; observer.disconnect(); abort.abort(); clearTimeout(retry); document.removeEventListener("visibilitychange", record); };
  }, [root, id, native, enabled, page, user, organization, allowed]);
}
