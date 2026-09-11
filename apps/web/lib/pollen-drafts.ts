export type PollenRule = {
  period: string;
  unit: "number/m3";
  threshold: { trigger_at_or_above: string; reset_at_or_below: string } | null;
  rapid_increase: { minimum_increase: string; window_hours: number } | null;
  category_change: boolean;
};
export type PollenConfiguration = {
  station_id: string;
  selections: { allergen: string; rules: PollenRule[] }[];
  timezone: string;
  delivery: {
    email: "off" | "immediate" | "daily_digest";
    digest_at: string | null;
    quiet_hours: { start: string; end: string } | null;
  };
};
export type PollenRevision = {
  revision: number;
  configuration: PollenConfiguration;
  configuration_hash: string;
};
export type PollenDraft = PollenRevision & {
  id: string;
  status: string;
  runtime_version?: number;
};
export type DraftPage = { items: PollenDraft[]; next_cursor: string | null };
export type RevisionPage = {
  items: PollenRevision[];
  next_before_revision: number | null;
};

export function privatePollenScope(
  user?: string,
  organization?: string,
  role?: string,
): string | null {
  return user && organization
    ? JSON.stringify([user, organization, role || ""])
    : null;
}

export function draftFailure(
  code: string,
): "disabled" | "access" | "missing" | "failed" {
  if (code === "monitoring_not_enabled") return "disabled";
  if (
    [
      "authentication_required",
      "membership_required",
      "subject_role_denied",
      "forbidden",
    ].includes(code)
  )
    return "access";
  return code === "subject_not_found" ? "missing" : "failed";
}
