export type Domain = "warnings" | "river" | "traffic";
export type Reference = {
  domain: Domain;
  monitor_id: string;
  event_id: string;
  revision: number;
  evidence_hash: string;
};
export type Member = {
  reference?: Reference;
  id?: string;
  domain?: Domain;
  monitor_name?: string;
  availability: "available" | "historical" | "unavailable";
  source_state?: string;
  current_source_state?: string;
  source_at?: string | null;
  source_until?: string | null;
  time_kind?: "instant" | "interval" | "unknown";
  source_identity?: { sender: string; identifier: string; sent: string };
  authority?: { namespace: string; identifier: string };
  reviewed?: boolean;
  href: string | null;
  geography?: {
    id: string;
    place_id: string;
    boundary_version: string;
    valid_until: string;
  } | null;
};
export type Association = {
  state: string;
  reason: string;
  left?: Reference;
  right?: Reference;
};
export type Story = {
  id: string;
  title: string;
  version: number;
  revision: number;
  status: "active" | "archived";
  historical: boolean;
  association_state: "possible" | "unverified" | "separate";
  members: Member[];
  links: Association[];
};
export type Page<T> = { items: T[]; next: string | null };
export type Preview = {
  can_save: boolean;
  members: Member[];
  links: Association[];
};
export const domainLinks: Record<Domain, string> = {
  warnings: "/hazard-watch",
  river: "/river-watch",
  traffic: "/road-watch",
};
export function memberKey(ref: Reference) {
  return `${ref.domain}:${ref.monitor_id}:${ref.event_id}`;
}
export function storyHref(id: string, revision?: number) {
  return `/related-developments?story=${encodeURIComponent(id)}${revision ? `&revision=${revision}` : ""}`;
}
