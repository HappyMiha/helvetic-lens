import type { BusinessScope } from "./business-monitor-copy";
export const trademarkLanguages = ["de", "fr", "it", "rm", "en"] as const;
export type TrademarkLanguage = (typeof trademarkLanguages)[number];
export type GoodsInterest = {
  name: string;
  phrases: { language: TrademarkLanguage; text: string }[];
};
export type Brand = {
  key: string;
  name: string;
  language: TrademarkLanguage;
  exact_name: boolean;
  similar_names: boolean;
  word_variants: string[];
  owners_of_interest: string[];
  relevant_classes: number[];
  goods_services: GoodsInterest[];
};
export type TrademarkPortfolio = {
  template_id: "trademark-watch";
  template_version: 1;
  jurisdiction: "CH";
  name: string;
  brands: Brand[];
  deadline_context?: {
    calendar_key: string;
    domicile_basis: "party" | "representative";
  };
};
export type TrademarkMonitor = BusinessScope & {
  runtime?: {
    health: string;
    last_check_at: string | null;
    next_check_at: string | null;
    unavailable_count: number;
  };
  id: string;
  configuration: TrademarkPortfolio;
  status: "draft" | "active" | "paused" | "archived";
  version: number;
  revision: number;
};
export type TrademarkPage<T> = {
  items: T[];
  next_cursor: string | number | null;
};
export function newBrand(): Brand {
  return {
    key: crypto.randomUUID(),
    name: "",
    language: "de",
    exact_name: true,
    similar_names: true,
    word_variants: [],
    owners_of_interest: [],
    relevant_classes: [],
    goods_services: [],
  };
}
