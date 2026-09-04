import type {
  AIHistoryPage,
  ApertusSettings,
  Comparison,
  ConnectorSchedulePage,
  DigestOverview,
  Health,
  ImpactMatrix,
  IntegrationLogDetail,
  Job,
  Law,
  LawDetail,
  LocalModelInventory,
  OrganizationStatus,
  Profile,
  PromptSettings,
  ProductionDeploymentStatus,
  Scan,
  Source,
  Version,
} from "@/lib/types";
import {
  resourceKey,
  type ResourceKey,
  type ResourceOwner,
  type ResourceScope,
} from "@/lib/resource-cache";

type KeyOptions = {
  scope?: ResourceScope;
  owner?: ResourceOwner;
  tags?: readonly string[];
  varyByLocale?: boolean;
  staleMs?: number;
  pollMs?: number;
  priority?: "background" | "interactive";
};

function key<T>(id: string, path: string, options: KeyOptions): ResourceKey<T> {
  return resourceKey<T>({
    id,
    path,
    scope: options.scope || "organization",
    owner: options.owner || "monitoring",
    tags: options.tags || [],
    varyByLocale: options.varyByLocale,
    staleMs: options.staleMs,
    pollMs: options.pollMs,
    priority: options.priority,
  });
}

function withQuery(base: string, query = ""): string {
  const value = query.trim();
  if (!value) return base;
  if (value === base || value.startsWith(`${base}?`)) return value;
  return `${base}${value.startsWith("?") ? value : `?${value}`}`;
}

export function legacyResourceKey<T>(path: string): ResourceKey<T> {
  const scope: ResourceScope = path.startsWith("/auth/")
    ? "session"
    : path.startsWith("/admin/")
      ? "platform"
      : "organization";
  const owner: ResourceOwner =
    scope === "session"
      ? "auth"
      : scope === "platform"
        ? "administration"
        : "monitoring";
  return key<T>(`legacy:${path}`, path, {
    scope,
    owner,
    tags: ["legacy"],
  });
}

export const resources = {
  authSession: <T = unknown>() =>
    key<T>("auth:session", "/auth/session", {
      scope: "session",
      owner: "auth",
      tags: ["auth-session"],
      varyByLocale: false,
      staleMs: 60_000,
    }),

  health: () =>
    key<Health>("runtime:health", "/health", {
      owner: "runtime",
      tags: ["health", "runtime"],
      varyByLocale: false,
      staleMs: 15_000,
      pollMs: 15_000,
    }),

  laws: () =>
    key<Law[]>("monitoring:laws", "/laws", {
      tags: ["laws", "monitoring"],
      staleMs: 5_000,
      pollMs: 5_000,
    }),

  law: (id: string) =>
    key<LawDetail>(`monitoring:law:${id}`, `/laws/${id}`, {
      tags: ["law", `law:${id}`, "monitoring"],
      staleMs: 4_000,
      pollMs: 4_000,
    }),

  lawHistory: (id: string) =>
    key<AIHistoryPage>(
      `comparison:law-history:${id}`,
      `/laws/${id}/ai-history`,
      {
        owner: "comparison",
        tags: ["ai-history", `law:${id}`],
        staleMs: 5_000,
        pollMs: 5_000,
      },
    ),

  sources: () =>
    key<Source[]>("monitoring:sources", "/sources", {
      tags: ["sources", "monitoring"],
      staleMs: 8_000,
      pollMs: 8_000,
    }),

  scans: () =>
    key<Scan[]>("monitoring:scans", "/scans", {
      tags: ["scans", "jobs", "monitoring"],
      staleMs: 2_000,
      pollMs: 2_000,
      priority: "interactive",
    }),

  jobs: () =>
    key<Job[]>("monitoring:jobs", "/jobs", {
      tags: ["jobs", "monitoring"],
      staleMs: 2_000,
      pollMs: 2_000,
      priority: "interactive",
    }),

  job: (id: string) =>
    key<Job>(`monitoring:job:${id}`, `/jobs/${id}`, {
      tags: ["job", "jobs", `job:${id}`],
      staleMs: 1_000,
      pollMs: 1_000,
      priority: "interactive",
    }),

  version: <T = Version>(id: string) =>
    key<T>(`comparison:version:${id}`, `/versions/${id}`, {
      owner: "comparison",
      tags: ["version", `version:${id}`, "evidence"],
      varyByLocale: false,
      staleMs: Number.POSITIVE_INFINITY,
    }),

  comparison: (id: string) =>
    key<Comparison>(`comparison:${id}`, `/comparisons/${id}`, {
      owner: "comparison",
      tags: ["comparison", `comparison:${id}`, "evidence"],
      staleMs: Number.POSITIVE_INFINITY,
    }),

  comparisonHistory: (id: string) =>
    key<AIHistoryPage>(
      `comparison:history:${id}`,
      `/comparisons/${id}/ai-history`,
      {
        owner: "comparison",
        tags: ["ai-history", `comparison:${id}`],
        staleMs: 5_000,
        pollMs: 5_000,
      },
    ),

  registry: <T = unknown>(query = "") => {
    const path = withQuery("/registry", query);
    return key<T>(`monitoring:${path}`, path, {
      tags: ["registry", "monitoring"],
      staleMs: 15_000,
      pollMs: 15_000,
    });
  },

  impactInbox: <T = unknown>(query = "") => {
    const path = withQuery("/impact-inbox", query);
    return key<T>(`monitoring:${path}`, path, {
      tags: ["impact-inbox", "monitoring"],
      staleMs: 15_000,
      pollMs: 15_000,
    });
  },

  impactMatrix: (query = "") => {
    const path = withQuery("/impact-matrix", query);
    return key<ImpactMatrix>(`monitoring:${path}`, path, {
      tags: ["impact-matrix", "monitoring"],
      staleMs: 30_000,
      pollMs: 30_000,
    });
  },

  relationReviews: <T = unknown>(id: string) =>
    key<T>(
      `monitoring:relation-reviews:${id}`,
      `/relation-candidates/${id}/reviews`,
      {
        tags: ["relation-reviews", `relation:${id}`],
      },
    ),

  relationAnalyses: <T = unknown>(id: string) =>
    key<T>(
      `monitoring:relation-analyses:${id}`,
      `/relation-candidates/${id}/analyses`,
      {
        tags: ["relation-analyses", `relation:${id}`],
      },
    ),

  profile: () =>
    key<Profile>("organization:profile", "/profile", {
      owner: "organization",
      tags: ["profile", "organization"],
      varyByLocale: false,
    }),

  organizationStatus: () =>
    key<OrganizationStatus>("organization:status", "/organization/status", {
      owner: "organization",
      tags: ["organization-status", "organization"],
    }),

  organizationMembers: <T = unknown>() =>
    key<T>("organization:members", "/organization/members", {
      owner: "organization",
      tags: ["organization-members", "organization"],
      varyByLocale: false,
    }),

  organizationInvitations: <T = unknown>() =>
    key<T>("organization:invitations", "/organization/invitations", {
      owner: "organization",
      tags: ["organization-invitations", "organization"],
      varyByLocale: false,
    }),

  settings: () =>
    key<ApertusSettings>("organization:settings", "/settings/apertus", {
      owner: "organization",
      tags: ["settings", "runtime", "organization"],
      varyByLocale: false,
    }),

  prompts: (scope: "organization" | "platform" = "organization") =>
    key<PromptSettings>(
      `${scope}:prompts`,
      scope === "platform" ? "/admin/prompts" : "/settings/prompts",
      {
        scope: scope === "platform" ? "platform" : "organization",
        owner: scope === "platform" ? "administration" : "organization",
        tags: ["prompts", scope],
        varyByLocale: false,
      },
    ),

  models: () =>
    key<LocalModelInventory>("platform:models", "/admin/models", {
      scope: "platform",
      owner: "administration",
      tags: ["models", "runtime", "administration"],
      staleMs: 2_000,
      pollMs: 2_000,
    }),

  connectors: () =>
    key<ConnectorSchedulePage>("platform:connectors", "/admin/connectors", {
      scope: "platform",
      owner: "administration",
      tags: ["connectors", "jobs", "administration"],
      staleMs: 5_000,
      pollMs: 5_000,
    }),

  platformStatus: <T = unknown>() =>
    key<T>("platform:status", "/admin/status", {
      scope: "platform",
      owner: "administration",
      tags: ["platform-status", "runtime", "administration"],
      staleMs: 10_000,
      pollMs: 10_000,
    }),

  deployments: () =>
    key<ProductionDeploymentStatus>("platform:deployments", "/admin/deployments", {
      scope: "platform",
      owner: "administration",
      tags: ["deployments", "runtime", "administration"],
      staleMs: 10_000,
      pollMs: 10_000,
    }),

  integrationLogs: <T = unknown>(query = "") => {
    const path = withQuery("/integration-logs", query);
    return key<T>(`organization:${path}`, path, {
      owner: "administration",
      tags: ["integration-logs", "administration"],
      staleMs: 5_000,
      pollMs: 5_000,
    });
  },

  integrationLog: (id: string) =>
    key<IntegrationLogDetail>(
      `organization:integration-log:${id}`,
      `/integration-logs/${id}`,
      {
        owner: "administration",
        tags: ["integration-log", "integration-logs", `integration-log:${id}`],
      },
    ),

  digests: () =>
    key<DigestOverview>("organization:digests", "/digests", {
      owner: "organization",
      tags: ["digests", "organization"],
    }),
};
