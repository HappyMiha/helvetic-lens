import type { MonitoringTopic, MonitoringTopicPreview } from "./types";
import { resourceKey } from "./resource-cache";

export type LegalTopicCard = {
  id: string;
  selected: boolean;
  name: string;
  description: string;
  keywords: string[];
  reference_note: string;
};
export type LegalSourceRequest = {
  id: string;
  label: string;
  url: string;
  kind: "binding" | "pending" | "signals";
  status: "requested";
};
export type LegalProfileConfig = {
  audience: "client" | "organization";
  name: string;
  sector: string;
  goal: string;
  feedback: string;
  requested_jurisdictions: string;
  topics: LegalTopicCard[];
  source_pack_ids: string[];
  source_requests: LegalSourceRequest[];
  delivery: "keep" | "daily" | "weekly" | "off";
  delivery_consent: boolean;
};
export type LegalProfile = {
  id: string;
  revision: number;
  status: "draft" | "active" | "paused";
  step: number;
  config: LegalProfileConfig;
  topic_ids: string[];
  topics?: MonitoringTopic[];
  created_at: string;
  updated_at: string;
  activated_at: string | null;
};
export type LegalProfilePage = {
  items: LegalProfile[];
  total: number;
  offset: number;
  limit: number;
  delivery: {
    enabled: boolean;
    frequency: string;
    next_delivery_at: string | null;
  };
  email_available: boolean;
};
export type LegalPreview = {
  topics: (MonitoringTopicPreview & { id: string; name: string })[];
};
export const emptyLegalProfile = (): LegalProfileConfig => ({
  audience: "client",
  name: "",
  sector: "",
  goal: "",
  feedback: "",
  requested_jurisdictions: "",
  topics: [],
  source_pack_ids: [],
  source_requests: [],
  delivery: "keep",
  delivery_consent: false,
});
// Organization cache scope is reset on membership changes; explicit user identity
// prevents author-private drafts sharing a cache entry across accounts.
export const legalProfileResource = <T>(identity: string, suffix = "") =>
  resourceKey<T>({
    id: `legal-profiles:${identity}:${suffix}`,
    path: `/monitoring-profiles${suffix}`,
    scope: "organization",
    owner: "monitoring",
    tags: ["legal-profiles"],
    staleMs: 0,
    varyByLocale: false,
  });
