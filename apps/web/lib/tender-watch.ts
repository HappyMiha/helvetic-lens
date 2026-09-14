import type { BusinessScope } from "./business-monitor-copy";
export type TenderProfile = {
  template_id: "tender-watch";
  template_version: 1;
  name: string;
  company_name: string;
  capabilities: { name: string; phrases: string[] }[];
  cpv_codes: string[];
  cpv_include_descendants: boolean;
  contract_cantons: string[];
  offer_languages: string[];
  authority_levels: string[];
  excluded_phrases: string[];
  excluded_cpv_codes: string[];
  excluded_contract_types: string[];
  minimum_contract_chf: string | null;
  maximum_contract_chf: string | null;
  available_reference_count: number | null;
  certificates: string[] | null;
  minimum_semantic_score: number | null;
};
export type TenderMonitor = BusinessScope & {
  id: string;
  configuration: TenderProfile;
  revision: number;
  version: number;
  status: "draft" | "active" | "paused" | "archived";
  health: string;
  last_poll_at: string | null;
  next_poll_at: string | null;
};
export type TenderCapabilities = {
  public_source_available: boolean;
  lookback_days: number;
  cycle_hours: number;
};
export type TenderPlan = {
  queries: { query?: string; cpv_codes?: string[] }[];
  start_available: boolean;
  live_results_checked: false;
};
export type TenderReason = {
  code: string;
  phrase?: string;
  capability?: string;
  value?: string;
  values?: string[];
  selected_code?: string;
  locator?: string;
  language?: string;
  required?: number;
  declared?: number;
};
export type TenderSummary = {
  title: Record<string, string>;
  title_truncated: boolean;
  phase: string;
  deadline: { utc: string | null; status: string };
  verdict: string;
  match_scope: string;
};
export type TenderCard = {
  id: string;
  monitor_id: string;
  project_id: string;
  lot_id: string | null;
  version: number;
  sequence: number;
  following: boolean;
  review_state: string;
  decision: string | null;
  reviewed_sequence: number | null;
  summary: TenderSummary;
  evidence_version_id: string;
  profile_revision: number;
  current_profile_revision: number;
};
export type TenderMaterial = {
  value: unknown;
  locator: string;
  coverage: string;
};
export type TenderDossier = Omit<TenderCard, "summary"> & {
  document_observation_id?: string | null;
  material: Record<string, TenderMaterial>;
  match: {
    verdict: string;
    matches: TenderReason[];
    exclusions: TenderReason[];
    unknowns: TenderReason[];
    qualification_gaps: TenderReason[];
    project_context: TenderReason[];
  };
  changes: { field: string; kind: string }[];
  source_hash: string;
  publication_id: string;
  kind: string;
};
export type TenderVersion = {
  document_observation_id?: string | null;
  id: string;
  sequence: number;
  publication_id: string;
  kind: string;
  summary: TenderSummary;
  changes: { field: string; kind: string }[];
  profile_revision: number;
};
export type TenderPage<T> = { items: T[]; next_cursor: string | number | null };
export const tenderCantons =
  "AG AI AR BE BL BS FR GE GL GR JU LU NE NW OW SG SH SO SZ TG TI UR VD VS ZG ZH".split(
    " ",
  );
export const tenderLanguages = {
  de: "Deutsch",
  fr: "Français",
  it: "Italiano",
  en: "English",
};
export function newTenderProfile(): TenderProfile {
  return {
    template_id: "tender-watch",
    template_version: 1,
    name: "",
    company_name: "",
    capabilities: [],
    cpv_codes: [],
    cpv_include_descendants: true,
    contract_cantons: [],
    offer_languages: [],
    authority_levels: [],
    excluded_phrases: [],
    excluded_cpv_codes: [],
    excluded_contract_types: [],
    minimum_contract_chf: null,
    maximum_contract_chf: null,
    available_reference_count: null,
    certificates: null,
    minimum_semantic_score: null,
  };
}
export function sourceTitle(value: unknown, locale: string): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) return "";
  const text = value as Record<string, unknown>;
  const languages = [...new Set([locale.slice(0, 2), "de", "fr", "it", "en"])];
  for (const language of languages)
    if (typeof text[language] === "string" && text[language])
      return text[language] as string;
  return "";
}

export function sourceExcerpts(value: unknown, locale: string) {
  const paragraphs: string[] = [];
  let visited = 0,
    truncated = false;
  function visit(item: unknown, depth: number) {
    if (++visited > 2000 || depth > 20 || paragraphs.length >= 100) {
      truncated = true;
      return;
    }
    const translated = sourceTitle(item, locale);
    if (translated || typeof item === "string" || typeof item === "number") {
      const text = translated || String(item);
      paragraphs.push(text.slice(0, 2000));
      truncated ||= text.length > 2000;
    } else if (item && typeof item === "object") {
      for (const key in item) {
        if (visited >= 2000 || paragraphs.length >= 100) {
          truncated = true;
          break;
        }
        if (key !== "id" && key !== "code")
          visit((item as Record<string, unknown>)[key], depth + 1);
      }
    }
  }
  visit(value, 0);
  return { paragraphs, truncated };
}
