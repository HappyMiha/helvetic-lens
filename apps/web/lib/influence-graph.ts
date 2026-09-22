/** Shared evidence contract. Private dossiers remain in authenticated workspace responses. */
export const evidenceStatuses = [
  "documented",
  "reported",
  "disputed",
  "not_established",
] as const;
export type EvidenceStatus = (typeof evidenceStatuses)[number];
export type Perspective = "all" | "documented" | "money" | "policy";
export type EntityKind =
  "person" | "company" | "initiative" | "policy" | "group";
export type RelationKind =
  | "family"
  | "role"
  | "campaign"
  | "ownership"
  | "business"
  | "policy_proposal"
  | "potential_impact"
  | "dividend";
export type SourceKind =
  "primary_corporate" | "primary_government" | "primary_campaign" | "reporting";

export type InfluenceSource = {
  id: string;
  title: string;
  publisher: string;
  url: string;
  kind: SourceKind;
  language: "en" | "de" | "fr" | "it" | "rm" | "uk";
  publishedOn: string | null;
  checkedOn: string;
  snapshotText?: string | null;
};
export type InfluenceEntity = {
  id: string;
  name: string;
  kind: EntityKind;
  country: string | null;
  x: number;
  y: number;
};
export type InfluenceEvidence = {
  sourceId: string;
  locator: string;
  summary: string;
  quote?: string | null;
};
export type MoneyFlow = {
  amount: number;
  currency: string;
  periodStart: string;
  periodEnd: string;
  basis: "paid" | "proposed";
  evidenceSourceId: string;
};
export type InfluenceEdge = {
  id: string;
  from: string;
  to: string;
  kind: RelationKind;
  status: EvidenceStatus;
  label: string;
  statement: string;
  asOf: string | null;
  supporting: InfluenceEvidence[];
  disputing: InfluenceEvidence[];
  limits: string[];
  money?: MoneyFlow | null;
};
export type InfluenceDossier = {
  id: string;
  title: string;
  checkedOn: string;
  summaryLanguage: "en" | "de" | "fr" | "it" | "rm" | "uk";
  sources: InfluenceSource[];
  entities: InfluenceEntity[];
  edges: InfluenceEdge[];
  gaps: string[];
};

export const INFLUENCE_NODE_WIDTH = 230;
export const INFLUENCE_NODE_HEIGHT = 112;

/** Reusing an array index after deletion must not stack two graph nodes. */
export function nextInfluenceEntityPosition(
  entities: InfluenceEntity[],
  unavailableMessage: string,
) {
  for (const columnOffset of [0, 3]) {
    for (let row = 0; row < 67; row++) {
      for (let column = 0; column < 3; column++) {
        const x = 30 + (column + columnOffset) * 330;
        const y = 30 + row * 180;
        const overlaps = entities.some(
          (entity) =>
            x < entity.x + INFLUENCE_NODE_WIDTH + 20 &&
            x + INFLUENCE_NODE_WIDTH + 20 > entity.x &&
            y < entity.y + INFLUENCE_NODE_HEIGHT + 20 &&
            y + INFLUENCE_NODE_HEIGHT + 20 > entity.y,
        );
        if (!overlaps) return { x, y };
      }
    }
  }
  // The server caps a dossier at 100 entities; the grid has 402 candidates,
  // and one existing node can intersect at most four candidates.
  throw new Error(unavailableMessage);
}

/** Keep parallel and reverse-direction claims separately selectable. */
export function influenceEdgeGeometry(
  from: InfluenceEntity,
  to: InfluenceEntity,
  edge: InfluenceEdge,
  edges: InfluenceEdge[],
) {
  const x1 = from.x + INFLUENCE_NODE_WIDTH / 2;
  const y1 = from.y + INFLUENCE_NODE_HEIGHT / 2;
  const x2 = to.x + INFLUENCE_NODE_WIDTH / 2;
  const y2 = to.y + INFLUENCE_NODE_HEIGHT / 2;
  const dx = x2 - x1,
    dy = y2 - y1;
  const ratio = Math.min(
    INFLUENCE_NODE_WIDTH / 2 / Math.max(Math.abs(dx), 0.001),
    INFLUENCE_NODE_HEIGHT / 2 / Math.max(Math.abs(dy), 0.001),
    0.45,
  );
  const sx = x1 + dx * ratio,
    sy = y1 + dy * ratio;
  const ex = x2 - dx * ratio,
    ey = y2 - dy * ratio;
  const siblings = edges.filter(
    (item) =>
      (item.from === from.id && item.to === to.id) ||
      (item.from === to.id && item.to === from.id),
  );
  const index = siblings.findIndex((item) => item.id === edge.id);
  const lane = index - (siblings.length - 1) / 2;
  const direction = from.id < to.id ? 1 : -1;
  const length = Math.max(Math.hypot(dx, dy), 1);
  const offset = lane * 76 * direction;
  const cx = (sx + ex) / 2 - (dy / length) * offset;
  const cy = (sy + ey) / 2 + (dx / length) * offset;
  return {
    path: `M ${sx} ${sy} Q ${cx} ${cy} ${ex} ${ey}`,
    x: (sx + 2 * cx + ex) / 4,
    y: (sy + 2 * cy + ey) / 4,
    minX: Math.min(sx, cx, ex) - 30,
    minY: Math.min(sy, cy, ey) - 30,
    maxX: Math.max(sx, cx, ex) + 30,
    maxY: Math.max(sy, cy, ey) + 30,
  };
}

function validDate(value: string): boolean {
  return (
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    !Number.isNaN(Date.parse(value)) &&
    new Date(value).toISOString().slice(0, 10) === value
  );
}

export function safeSourceUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return (
      url.protocol === "https:" &&
      Boolean(url.hostname) &&
      !url.username &&
      !url.password
    );
  } catch {
    return false;
  }
}

/** A source-backed ownership edge is never promoted to a payment by traversal. */
export function isConfirmedMoneyFlow(
  edge: InfluenceEdge,
  sources: InfluenceSource[],
): boolean {
  const money = edge.money;
  if (
    edge.kind !== "dividend" ||
    edge.status !== "documented" ||
    edge.disputing.length ||
    !money
  )
    return false;
  const source = sources.find((item) => item.id === money.evidenceSourceId);
  return Boolean(
    source &&
    source.kind !== "reporting" &&
    safeSourceUrl(source.url) &&
    validDate(source.checkedOn) &&
    edge.supporting.some(
      (item) =>
        item.sourceId === source.id &&
        item.locator.trim() &&
        item.summary.trim(),
    ) &&
    money.basis === "paid" &&
    Number.isFinite(money.amount) &&
    money.amount > 0 &&
    /^[A-Z]{3}$/.test(money.currency) &&
    validDate(money.periodStart) &&
    validDate(money.periodEnd) &&
    money.periodStart <= money.periodEnd &&
    money.periodEnd <= source.checkedOn,
  );
}

export function visibleInfluenceEdges(
  dossier: InfluenceDossier,
  perspective: Perspective,
  entityId: string | null = null,
): InfluenceEdge[] {
  return dossier.edges.filter((edge) => {
    if (entityId && edge.from !== entityId && edge.to !== entityId)
      return false;
    switch (perspective) {
      case "documented":
        return edge.status === "documented";
      case "money":
        return isConfirmedMoneyFlow(edge, dossier.sources);
      case "policy":
        return ["campaign", "policy_proposal", "potential_impact"].includes(
          edge.kind,
        );
      default:
        return true;
    }
  });
}

/** Fail the checked-in dossier gate on broken provenance, dates or disputed facts. */
export function validateInfluenceDossier(dossier: InfluenceDossier): string[] {
  const errors: string[] = [];
  const unique = (items: { id: string }[], kind: string) => {
    const ids = new Set<string>();
    for (const item of items) {
      if (!item.id.trim() || ids.has(item.id))
        errors.push(`${kind}: duplicate or empty id ${item.id}`);
      ids.add(item.id);
    }
    return ids;
  };
  const entityIds = unique(dossier.entities, "entity");
  const sourceIds = unique(dossier.sources, "source");
  unique(dossier.edges, "edge");
  if (!validDate(dossier.checkedOn)) errors.push("Invalid dossier date");
  for (const source of dossier.sources) {
    if (!safeSourceUrl(source.url))
      errors.push(`${source.id}: invalid source URL`);
    if (
      !validDate(source.checkedOn) ||
      source.checkedOn > dossier.checkedOn ||
      (source.publishedOn !== null &&
        (!validDate(source.publishedOn) ||
          source.publishedOn > source.checkedOn))
    ) {
      errors.push(`${source.id}: invalid source chronology`);
    }
  }
  for (const edge of dossier.edges) {
    if (
      !entityIds.has(edge.from) ||
      !entityIds.has(edge.to) ||
      edge.from === edge.to
    )
      errors.push(`${edge.id}: invalid endpoints`);
    if (!evidenceStatuses.includes(edge.status))
      errors.push(`${edge.id}: unknown status`);
    if (!edge.statement.trim() || !edge.limits.length)
      errors.push(`${edge.id}: statement or limits missing`);
    if (
      edge.asOf !== null &&
      (!validDate(edge.asOf) || edge.asOf > dossier.checkedOn)
    )
      errors.push(`${edge.id}: invalid effective date`);
    if (!edge.supporting.length)
      errors.push(`${edge.id}: supporting evidence missing`);
    for (const evidence of [...edge.supporting, ...edge.disputing]) {
      if (
        !sourceIds.has(evidence.sourceId) ||
        !evidence.locator.trim() ||
        !evidence.summary.trim()
      )
        errors.push(`${edge.id}: incomplete evidence`);
    }
    if (edge.status === "disputed" && !edge.disputing.length)
      errors.push(`${edge.id}: counter-statement missing`);
    if (
      edge.status === "documented" &&
      (edge.disputing.length ||
        !edge.supporting.some((ref) =>
          dossier.sources.some(
            (source) =>
              source.id === ref.sourceId && source.kind !== "reporting",
          ),
        ))
    ) {
      errors.push(
        `${edge.id}: documented status requires primary evidence without unresolved dispute`,
      );
    }
    if (edge.kind === "potential_impact" && edge.status === "documented")
      errors.push(`${edge.id}: potential impact is not a documented outcome`);
    if (
      edge.money &&
      edge.status === "documented" &&
      !isConfirmedMoneyFlow(edge, dossier.sources)
    )
      errors.push(`${edge.id}: invalid documented money flow`);
  }
  return errors;
}
