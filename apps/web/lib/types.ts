export type Health = {
  status: string;
  database: string;
  apertus: { configured: boolean; model: string };
  firecrawl: { configured: boolean };
  private_sources_enabled: boolean;
};
export type Preview = {
  title: string;
  content_type: string;
  characters: number;
  passage_count: number;
  page_count: number;
  excerpt: string;
  url?: string;
};
export type Candidate = {
  title: string;
  url: string;
  format_hint: string;
  verified: boolean;
  tracked?: boolean;
};
export type Discovery = {
  candidates: Candidate[];
  candidate_count: number;
  returned_count: number;
  limit: number;
  limit_reached: boolean;
  note: string;
};
export type Source = {
  id: string;
  name: string;
  url: string;
  section: string;
  provider: string;
  last_checked: string | null;
  error: string | null;
  discovery: Partial<Discovery>;
};
export type Passage = { id: string; text: string; page: number | null };
export type Version = {
  id: string;
  law_id: string;
  title: string;
  origin: string;
  content_type: string;
  created_at: string;
  declared_date: string | null;
  date_provenance: string | null;
  filename: string;
  synthetic: boolean;
  source_url: string | null;
  characters: number;
  passage_count: number;
  page_count: number;
  content_hash: string;
  artifact_url: string;
};
export type Citation = {
  version_id: string;
  passage_id: string;
  quote: string;
  url: string;
  page: number | null;
};
export type Coverage = {
  included_passages: number;
  available_passages: number;
  included_characters: number;
  limited: boolean;
  scope: string;
};
export type Impact = {
  summary: string;
  impact: "high" | "medium" | "low";
  reason: string;
  business_areas: string[];
  actions: { text: string; citations: Citation[] }[];
  citations: Citation[];
};
export type Analysis = {
  id: string;
  status: string;
  stale: boolean;
  error: string | null;
  result: Impact | null;
  coverage: Coverage;
  model: string;
  created_at: string;
};
export type Counts = {
  added: number;
  removed: number;
  modified: number;
  unchanged: number;
};
export type Law = {
  id: string;
  name: string;
  url: string;
  source_id: string | null;
  active: boolean;
  current_version_id: string | null;
  current_version: Version | null;
  created_at: string;
  last_checked: string | null;
  last_result: string;
  last_error: string | null;
  comparison_id: string | null;
  comparison_mode: string | null;
  change_counts: Counts | null;
  analysis: Analysis | null;
};
export type LawDetail = Law & {
  versions: Version[];
  observations: {
    id: string;
    version_id: string;
    origin: string;
    created_at: string;
    synthetic: boolean;
    filename: string;
  }[];
  comparisons: {
    id: string;
    mode: string;
    old_version_id: string;
    new_version_id: string;
    created_at: string;
    counts: Counts;
  }[];
};
export type Change = {
  id: string;
  kind: "added" | "removed" | "modified" | "unchanged";
  old: Passage | null;
  new: Passage | null;
  old_parts: { text: string; kind: string }[];
  new_parts: { text: string; kind: string }[];
};
export type Comparison = {
  id: string;
  law_id: string;
  law: Law;
  mode: string;
  created_at: string;
  old_version: Version;
  new_version: Version;
  diff: { items: Change[]; counts: Counts; changed: boolean };
  analysis: Analysis | null;
};
export type ScanItem = {
  id: string;
  law_id: string;
  law_name: string;
  stage: string;
  result: string | null;
  live_result: string | null;
  mode: string;
  error: string | null;
  comparison_id: string | null;
  analysis_status: string;
  events: { stage: string; at: string }[];
};
export type Scan = {
  id: string;
  status: string;
  total: number;
  completed: number;
  created_at: string;
  finished_at: string | null;
  items: ScanItem[];
};
export type Profile = {
  name: string;
  description: string;
  business_areas: string[];
  revision: number;
};
export type Answer = {
  supported: boolean;
  answer: string;
  citations: Citation[];
  coverage: Coverage;
  model: string;
};
