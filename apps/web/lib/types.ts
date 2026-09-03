export type Health = {
  status: string;
  database: string;
  apertus: { configured: boolean; model: string };
  firecrawl: { configured: boolean };
  private_sources_enabled: boolean;
};
export type ApertusSettings = {
  provider: "custom" | "docker" | "infomaniak";
  product_id: string;
  base_url: string;
  model: string;
  timeout_seconds: number;
  request_retries: number;
  batch_concurrency: number;
  context_chars: number;
  max_tokens: number;
  temperature: number;
  top_p: number;
  presence_penalty: number;
  reasoning_effort: "default" | "none" | "low" | "medium" | "high";
  json_mode: boolean;
  configured: boolean;
  api_key_configured: boolean;
  key_source: "environment" | "saved" | "none";
  source: "environment" | "workspace";
  updated_at: string | null;
};
export type ApertusModelOption = {
  id: string;
  owned_by?: string;
  created?: number;
};
export type ApertusModelList = {
  provider: "custom" | "docker" | "infomaniak";
  base_url: string;
  models: ApertusModelOption[];
  count: number;
  saved: boolean;
};
export type Preview = {
  title: string;
  content_type: string;
  characters: number;
  passage_count: number;
  page_count: number;
  excerpt: string;
  url?: string;
  identity?: DocumentIdentity;
};
export type DocumentIdentity = {
  revision: string;
  status: "verified" | "probable" | "unknown" | "mismatch";
  reason: string;
  score?: number;
  tracked_title?: string;
  detected_title?: string;
  tracked_identifier?: string | null;
  detected_identifier?: string | null;
  fingerprint?: string;
  user_confirmed?: boolean;
  artifact?: {
    authority: string;
    canonical_work_id: string | null;
    official_identifiers: { scheme: string; value: string }[];
    document_kind: string;
    title: string;
    language: string;
    version_date: string | null;
    publication_date: string | null;
    source_url: string | null;
    extractor: string;
    content_type: string;
    filename: string;
    evidence: { type: string; source: string; value: string }[];
    fingerprint: string;
  };
};
export type ComparisonIdentity = {
  revision: string;
  status: "verified" | "probable" | "unknown" | "mismatch";
  effective_status: "verified" | "probable" | "unknown" | "mismatch";
  reason: string;
  old: DocumentIdentity;
  new: DocumentIdentity;
  pair_score: number;
  fingerprint: string;
  confirmed_sides: ("old" | "new")[];
};
export type Candidate = {
  title: string;
  url: string;
  format_hint: string;
  verified: boolean;
  tracked?: boolean;
  inspected?: boolean;
  content_type?: string;
  preview?: Preview | null;
  error?: string | null;
  status?: string;
};
export type Discovery = {
  candidates: Candidate[];
  candidate_count: number;
  returned_count: number;
  inspected_count: number;
  verified_count: number;
  error_count: number;
  uninspected_count: number;
  time_limit_reached: boolean;
  time_limit_seconds: number;
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
  identity_json?: DocumentIdentity["artifact"];
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
  complete?: boolean;
  changed_items?: number;
  configured_context_characters?: number;
  exceeds_configured_context?: boolean;
  scope: string;
  provider_calls?: number;
  material_items?: number;
  reviewed_material_items?: number;
  suppressed_non_material_items?: number;
  analysis_call_budget?: number;
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
  prompt_revision: number;
  use_count: number;
  last_used_at: string | null;
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
    declared_date: string | null;
    source_url: string | null;
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
  significance?:
    "substantive" | "structural" | "formatting" | "uncertain" | "unchanged";
  change_type?: string;
  classification?:
    | "substantive"
    | "added"
    | "removed"
    | "moved"
    | "renumbered"
    | "formatting_only"
    | "uncertain"
    | "unchanged";
  match?: {
    reason: string;
    score: number;
    components: Record<string, number>;
    ambiguous: boolean;
  };
  material?: boolean;
  old: Passage | null;
  new: Passage | null;
  old_position?: number | null;
  new_position?: number | null;
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
  diff: {
    schema_version?: number;
    algorithm?: string;
    granularity?: string;
    complete?: boolean;
    old_passage_count?: number;
    new_passage_count?: number;
    items: Change[];
    counts: Counts;
    classification_counts?: {
      substantive: number;
      structural: number;
      formatting: number;
      uncertain: number;
    };
    semantic_counts?: Record<string, number>;
    semantic_changes?: {
      id: string;
      kind: Change["kind"];
      classification: NonNullable<Change["classification"]>;
      significance?: Change["significance"];
      change_type?: string;
      material: boolean;
      match?: Change["match"];
      old_unit_id?: string | null;
      new_unit_id?: string | null;
      old_position?: number | null;
      new_position?: number | null;
    }[];
    change_clusters?: {
      id: string;
      classifications: string[];
      change_ids: string[];
      old_unit_ids: string[];
      new_unit_ids: string[];
      context_before_unit_id?: string | null;
      context_after_unit_id?: string | null;
      ambiguous: boolean;
    }[];
    material_count?: number;
    material_changed?: boolean;
    changed: boolean;
  };
  identity?: ComparisonIdentity;
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
  job?: Job | null;
};
export type Job = {
  id: string;
  type: string;
  target_type: string;
  target_id: string;
  queue: string;
  priority: number;
  state: string;
  progress: { current: number; total: number };
  attempts: number;
  max_attempts: number;
  queue_position: number | null;
  cancel_requested: boolean;
  error: { code: string; detail: string } | null;
  result: {
    type: string | null;
    id: string | null;
    url: string | null;
    data: unknown;
  } | null;
  steps: {
    id: string;
    position: number;
    name: string;
    state: string;
    progress: { current: number; total: number };
    details: Record<string, unknown>;
    error: string | null;
    started_at: string | null;
    finished_at: string | null;
  }[];
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
};
export type LocalModel = {
  id: string;
  display_name: string;
  family: string;
  upstream_repository: string;
  base_repository: string;
  immutable_revision: string;
  quantization: string;
  sha256: string;
  size_bytes: number;
  license: string;
  license_url: string;
  served_model_id: string;
  state:
    | "available"
    | "downloading"
    | "paused"
    | "verifying"
    | "starting"
    | "ready"
    | "stopped"
    | "degraded"
    | "incompatible"
    | "error";
  installed: boolean;
  active: boolean;
  license_accepted: boolean;
  error: string | null;
  compatibility: {
    status: "compatible" | "unverified" | "incompatible";
    reason: string;
  };
  download: {
    downloaded_bytes: number;
    total_bytes: number;
    resumable: boolean;
    cached_copy_available: boolean;
  };
  artifact: { sha256: string; verified_at: string } | null;
  requirements: {
    min_ram_bytes: number;
    min_disk_bytes: number;
    min_vram_bytes: number;
    recommended_context: number;
    gpu_layers: number;
    slots: number;
  };
};
export type LocalModelInventory = {
  catalog_version: number;
  runtime_image: string;
  hardware: {
    probed_at: string;
    ram_bytes: number;
    disk_total_bytes: number;
    disk_free_bytes: number;
    cuda_devices: {
      index: number;
      name: string;
      vram_bytes: number;
      compute_capability: string;
    }[];
    cuda_error: string | null;
    runtime_supported: boolean;
  };
  deployment: {
    model_id: string;
    state: string;
    started_at?: string;
    ready_at?: string;
  } | null;
  models: LocalModel[];
};
export type IntegrationLogSummary = {
  id: string;
  provider: string;
  operation: string;
  method: string;
  url: string;
  status: "success" | "error";
  response_status: number | null;
  duration_ms: number;
  request_size: number;
  response_size: number;
  error: string | null;
  created_at: string;
};
export type IntegrationLogDetail = IntegrationLogSummary & {
  request_headers: Record<string, unknown>;
  request_body: unknown;
  response_headers: Record<string, unknown>;
  response_body: unknown;
};
export type IntegrationLogPage = {
  items: IntegrationLogSummary[];
  total: number;
  limit: number;
  offset: number;
  providers: string[];
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
  context_mode:
    | "deterministic_diff"
    | "full_saved_versions"
    | "targeted_passages"
    | "clarification";
  suggestions?: string[];
  record_id: string;
  cached: boolean;
  created_at: string;
  last_used_at: string | null;
  use_count: number;
  prompt_revision: number;
};

export type PromptSettings = {
  impact_instructions: string;
  impact_synthesis_instructions: string;
  ask_instructions: string;
  answer_synthesis_instructions: string;
  repair_instructions: string;
  ask_context_mode: "automatic" | "changes_only";
  source: "defaults" | "workspace";
  revision: number;
  fingerprint: string;
  updated_at: string | null;
};

export type AIHistoryComparison = {
  id: string;
  mode: string;
  created_at: string;
  before: Pick<
    Version,
    "id" | "title" | "declared_date" | "origin" | "created_at"
  > & {
    artifact_url: string;
  };
  after: Pick<
    Version,
    "id" | "title" | "declared_date" | "origin" | "created_at"
  > & {
    artifact_url: string;
  };
  counts: Partial<Counts>;
};

export type AIHistoryItem = {
  id: string;
  type: "impact" | "question";
  comparison_id: string;
  comparison: AIHistoryComparison;
  status: "pending" | "succeeded" | "failed";
  model: string;
  prompt_revision: number;
  use_count: number;
  last_used_at: string | null;
  created_at: string;
  error: string | null;
  coverage: Partial<Coverage>;
  result:
    | Impact
    | (Omit<Answer, "coverage" | "model"> & { context_mode?: string })
    | null;
  question?: string;
  history?: { question: string }[];
  context_mode?: string;
};

export type AIHistoryPage = {
  items: AIHistoryItem[];
  total: number;
};
