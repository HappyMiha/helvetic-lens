"use client";

import { useEffect, useMemo } from "react";
import { resourceScopeEpoch } from "./api";
import { storedLocale } from "./i18n";
import { RequestOwner } from "./request-owner";

function authority() {
  return JSON.stringify([
    resourceScopeEpoch("session"),
    resourceScopeEpoch("organization"),
    storedLocale(),
  ]);
}

export function useRequestOwner(identity: string) {
  const owner = useMemo(() => new RequestOwner(), [identity]);
  useEffect(() => {
    owner.activate();
    return () => owner.deactivate();
  }, [owner]);
  return () => owner.capture(authority);
}
