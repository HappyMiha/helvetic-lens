import type { BusinessScope } from "./business-monitor-copy";
export const auctionCategories = [
  "real_estate",
  "vehicles",
  "equipment",
  "furniture",
  "bicycles",
  "jewellery",
  "precious_metals",
  "other",
] as const;
export const auctionPriceKinds = [
  "current_bid",
  "starting_price",
  "minimum_price",
  "estimate",
] as const;
export const auctionNotices = [
  "new_match",
  "price_above_limit",
  "every_bid_change",
  "deadline_change",
  "documents_change",
  "conditions_change",
  "cancellation",
] as const;
export type AuctionProfile = {
  schema_version: 1;
  name: string;
  categories: (typeof auctionCategories)[number][];
  cantons: string[];
  locations: string[];
  keywords: string[];
  brands: string[];
  maximum_price_chf_cents: number | null;
  budget_price_kind: (typeof auctionPriceKinds)[number];
  notify: Record<(typeof auctionNotices)[number], boolean> & {
    ending_soon_hours: number | null;
  };
};
export type AuctionMonitor = BusinessScope & {
  id: string;
  configuration: AuctionProfile;
  status: "draft" | "active" | "paused" | "archived";
  version: number;
  revision: number;
  runtime?: {
    health: string;
    last_check_at: string | null;
    next_check_at: string | null;
  };
};
export type AuctionPage<T> = {
  items: T[];
  next_cursor: string | number | null;
};
export function newAuctionProfile(): AuctionProfile {
  return {
    schema_version: 1,
    name: "",
    categories: ["vehicles"],
    cantons: ["TI"],
    locations: [],
    keywords: [],
    brands: [],
    maximum_price_chf_cents: null,
    budget_price_kind: "current_bid",
    notify: {
      new_match: true,
      price_above_limit: true,
      every_bid_change: false,
      deadline_change: true,
      documents_change: true,
      conditions_change: true,
      cancellation: true,
      ending_soon_hours: null,
    },
  };
}
export function parseAuctionBudget(value: string): number | null | undefined {
  if (!value.trim()) return null;
  if (!/^\d+(?:[.,]\d{1,2})?$/.test(value.trim())) return undefined;
  const [whole, fraction = ""] = value.trim().split(/[.,]/);
  const cents = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return Number.isSafeInteger(cents) && cents <= 10 ** 15 ? cents : undefined;
}
