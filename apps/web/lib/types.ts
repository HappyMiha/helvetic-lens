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
export type AnalysisPlan = {
  schema_version: string;
  state: "planned" | "completed" | "failed";
  task: "impact_report" | "ask" | "relation_impact";
  output_locale?: string;
  intent: string;
  selected_change_ids?: string[];
  selected_evidence_ids?: string[];
  context_fingerprint: string;
  limits: {
    provider_call_budget: number;
    configured_context_characters: number;
    reserved_output_tokens_per_call: number;
  };
  estimates: {
    input_characters: number;
    input_tokens: number;
    output_tokens: number;
    planned_generation_calls: number;
  };
  execution: {
    strategy: string;
    provider: string;
    model: string;
    batch_count: number;
    local_first: boolean;
    profile_revision?: number | null;
  };
  shared_general_change?: {
    source: string;
    summary: string;
    fingerprint: string;
  };
  coverage: Partial<Coverage>;
  actual?: {
    provider_calls: number;
    queue_wait_ms: number;
    inference_duration_ms: number;
    token_counts: Record<string, number>;
    validation: Record<string, unknown>;
    coverage_limited: boolean;
    result_url: string;
  };
};
export type Impact = {
  summary: string;
  impact: "high" | "medium" | "low";
  reason: string;
  business_areas: string[];
  schema_version?: "impact-report-v2";
  output_locale?: string;
  headline?: string;
  materiality?: "high" | "medium" | "low";
  evidence_grade?: "confirmed" | "supported" | "possible" | "needs_review";
  material_changes?: {
    change_id: string;
    change_type: "added" | "removed" | "modified";
    title: string;
    explanation: string;
    old_unit: {
      unit_id: string | null;
      passage_id: string | null;
      page: number | null;
      label: string;
    } | null;
    new_unit: {
      unit_id: string | null;
      passage_id: string | null;
      page: number | null;
      label: string;
    } | null;
    evidence_grade: "confirmed" | "supported" | "possible" | "needs_review";
    citations: Citation[];
  }[];
  organization_applicability?: {
    status: "applies" | "may_apply" | "unlikely" | "unknown";
    explanation: string;
    evidence_grade: "confirmed" | "supported" | "possible" | "needs_review";
    citations: Citation[];
  };
  important_dates?: {
    kind: "effective_date" | "deadline" | "transition" | "other";
    label: string;
    date: string | null;
    status: "found" | "not_found" | "uncertain";
    evidence_grade: "confirmed" | "supported" | "possible" | "needs_review";
    citations: Citation[];
  }[];
  uncertainties?: string[];
  evidence_coverage?: {
    reviewed_material_items: number;
    material_items: number;
    limited: boolean;
    scope: string;
  };
  actions: {
    text: string;
    citations: Citation[];
    action_key?: string;
    action_type?: string;
    title?: string;
    rationale?: string;
    owner_role?: string;
    affected_area?: string;
    priority?: "high" | "medium" | "low";
    due_basis?: string;
    due_date?: string | null;
    applicability_condition?: string;
    related_change_ids?: string[];
    evidence_grade?: "confirmed" | "supported" | "possible" | "needs_review";
    review_suggestion?: true;
  }[];
  citations: Citation[];
};
export type Analysis = {
  id: string;
  status: string;
  stale: boolean;
  error: string | null;
  result: Impact | null;
  coverage: Coverage;
  analysis_plan: AnalysisPlan;
  provenance: Record<string, unknown>;
  model: string;
  prompt_revision: number;
  use_count: number;
  last_used_at: string | null;
  created_at: string;
  latest_attempt?: {
    id: string;
    status: string;
    error: string | null;
    created_at: string;
  };
  action_decisions?: ActionDecisionPage;
};
export type ActionDecision = {
  id: string;
  organization_id: string;
  comparison_id: string;
  analysis_id: string;
  action_key: string;
  decision: "accepted" | "assigned" | "scheduled" | "dismissed" | "not_applicable";
  assigned_to: string | null;
  scheduled_for: string | null;
  rationale: string | null;
  actor_user_id: string | null;
  actor_label: string;
  created_at: string;
};
export type ActionDecisionPage = {
  current: Record<string, ActionDecision>;
  history: ActionDecision[];
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
  regulatory_timeline: {
    monitoring: {
      active: boolean;
      last_checked: string | null;
      last_result: string;
    };
    work: {
      id: string | null;
      kind: string;
      authority: string;
      lifecycle: string;
      stable_official_url: string | null;
    };
    identifiers: { scheme: string; value: string; source_url: string | null }[];
    expressions: {
      id: string;
      language: string;
      title: string;
      url: string | null;
    }[];
    normalized_versions: number;
    relations: {
      id: string;
      direction: "incoming" | "outgoing";
      type: string;
      state: string;
      other_work_id: string;
      provenance: string;
    }[];
    source_provenance: {
      origin: string;
      source_url: string | null;
      observed_at: string;
    }[];
    timeline: {
      id: string;
      type: "event" | "version" | "comparison";
      at: string;
      label: string;
      detail: string;
      url: string | null;
    }[];
  };
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
  analysis_job?: Job | null;
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
    served_model_id?: string;
    state: string;
    hardware_profile?: string;
    accepted_slots?: number;
    available_slots?: number;
    context_size?: number;
    started_at?: string;
    ready_at?: string;
  } | null;
  models: LocalModel[];
};
export type PlatformStatus = {
  scope: "platform";
  generated_at: string;
  services: Record<string, string>;
  resources: {
    organizations: number;
    users: number;
    memberships: number;
    active_watches: number;
    custom_sources: number;
  };
  jobs: {
    states: Record<string, number>;
    queues: Record<string, number>;
    oldest_active_age_seconds: number | null;
    dead_letters: number;
    recent_failures: Array<{
      id: string;
      type: string;
      queue: string;
      error: string | null;
      finished_at: string | null;
    }>;
  };
  connectors: Array<{
    connector: string;
    stream: string;
    health: string;
    message: string | null;
    last_success_at: string | null;
    freshness_seconds: number | null;
  }>;
  model: {
    available: boolean;
    state: string;
    model_id?: string | null;
    available_slots?: number;
    accepted_slots?: number;
    cuda_devices?: Array<{ index: number; name: string; vram_bytes: number }>;
    ram_bytes?: number;
    disk_free_bytes?: number;
    benchmark?: { status: string; message?: string };
    error?: string;
  };
  storage: {
    total_bytes: number;
    free_bytes: number;
    used_bytes: number;
    retention: Record<string, string | number>;
  };
  backup: {
    configured: boolean;
    latest_at: string | null;
    age_seconds: number | null;
    file_count: number;
    status: string;
  };
  recent_audit: Array<{
    id: string;
    scope: string;
    action: string;
    result: string;
    response_status: number;
    actor_kind: string;
    created_at: string;
  }>;
};
export type OrganizationStatus = {
  scope: "organization";
  generated_at: string;
  workspace: {
    members: number;
    pending_invitations: number;
    active_watches: number;
    custom_sources: number;
  };
  profile: { name: string; revision: number; complete: boolean };
  prompts: { source: string; revision: number };
  ai: {
    provider: string;
    execution: "local" | "cloud";
    cloud_opt_in: boolean;
    credential_configured: boolean;
    analyses: number;
    questions: number;
    token_counts: Record<string, number>;
  };
  quotas: Record<string, unknown>;
  recent_audit: Array<{
    action: string;
    result: string;
    response_status: number;
    created_at: string;
  }>;
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
export type ConnectorRun = {
  id: string;
  job_id: string | null;
  trigger: string;
  status: string;
  input_cursor: Record<string, unknown> | null;
  output_cursor: Record<string, unknown> | null;
  new: number;
  changed: number;
  failed: number;
  fanout: number;
  duration_ms: number | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
};
export type ConnectorSchedule = {
  id: string;
  connector: string;
  stream: string;
  enabled: boolean;
  interval_seconds: number;
  jitter_seconds: number;
  window_start: string | null;
  window_end: string | null;
  timezone: string;
  policy: {
    overlap?: string;
    minimum_request_interval_seconds?: number;
    timezone?: string;
  };
  next_run_at: string;
  last_enqueued_at: string | null;
  health: string;
  health_message: string | null;
  cursor: Record<string, unknown> | null;
  checkpoint: Record<string, unknown>;
  last_success_at: string | null;
  freshness_lag_seconds: number | null;
  partial_coverage: boolean;
  last_run: ConnectorRun | null;
};
export type ConnectorSchedulePage = {
  items: ConnectorSchedule[];
  pressure: {
    blocked: boolean;
    reasons: string[];
    active: number;
    active_limit: number;
    pending: number;
    pending_limit: number;
    free_megabytes: number;
    minimum_free_megabytes: number;
  };
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
    | "clarification"
    | "impact_report"
    | "off_topic";
  intent:
    | "explain_changes"
    | "organization_impact"
    | "actions"
    | "specific_unit"
    | "whole_document"
    | "vague"
    | "off_topic";
  scope: string;
  selected_change_ids: string[];
  selected_evidence_ids: string[];
  output_locale: string;
  reused_impact_report_id?: string | null;
  suggestions?: string[];
  record_id: string;
  cached: boolean;
  created_at: string;
  last_used_at: string | null;
  use_count: number;
  prompt_revision: number;
  analysis_plan?: AnalysisPlan;
};

export type PromptSettings = {
  impact_instructions: string;
  impact_synthesis_instructions: string;
  ask_instructions: string;
  answer_synthesis_instructions: string;
  repair_instructions: string;
  ask_context_mode: "automatic" | "changes_only";
  source: "defaults" | "workspace" | "platform_default";
  scope?: "platform_default" | "built_in_default";
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
  analysis_plan?: AnalysisPlan;
  result:
    | Impact
    | (Omit<Answer, "coverage" | "model"> & { context_mode?: string })
    | null;
  question?: string;
  history?: { question: string; answer?: string; citations?: Citation[] }[];
  context_mode?: string;
};

export type AIHistoryPage = {
  items: AIHistoryItem[];
  total: number;
};
