"use client";

import { createContext } from "react";
import type { ComparisonCitationVersions } from "@/lib/comparison-citations";

export const ComparisonCitationContext =
  createContext<ComparisonCitationVersions | null>(null);
