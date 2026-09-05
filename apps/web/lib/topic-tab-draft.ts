import type {
  MonitoringTopic,
  MonitoringTopicDraft,
  MonitoringTopicPlan,
} from "./types";

export type TopicForm = Omit<
  MonitoringTopicPlan,
  "concepts" | "synonyms" | "exclusions" | "jurisdictions"
> & {
  concepts: string;
  synonyms: string;
  exclusions: string;
  jurisdictions: string;
};
export type TopicEditIdentity = Pick<
  MonitoringTopic,
  "id" | "current_revision"
>;
export type TopicAiIdentity = Pick<
  MonitoringTopicDraft,
  "id" | "provider" | "model"
>;
export type TopicTabDraft = {
  version: 1;
  scope: string;
  savedAt: number;
  form: TopicForm;
  baseline: TopicForm;
  editing: TopicEditIdentity | null;
  aiDraft: TopicAiIdentity | null;
  idempotencyKey: string;
};
export const topicDraftLifetime = 24 * 60 * 60 * 1000;
const maxCharacters = 65536;
type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;
const object = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown, max = 12000): value is string =>
  typeof value === "string" && value.length <= max;
const strings = (value: unknown): value is string[] =>
  Array.isArray(value) &&
  value.length <= 100 &&
  value.every((item) => text(item, 1000));

export function topicDraftKey(
  user: string | undefined,
  organization: string | undefined,
): string | null {
  return user && organization
    ? `helvetic-topic-tab-v1:${JSON.stringify([user, organization])}`
    : null;
}

function form(value: unknown): TopicForm | null {
  if (!object(value)) return null;
  const {
    name,
    goal,
    concepts,
    synonyms,
    exclusions,
    jurisdictions,
    languages,
    source_pack_ids,
    document_kinds,
    event_kinds,
    importance_floor,
  } = value;
  if (
    !text(name) ||
    !text(goal) ||
    !text(concepts) ||
    !text(synonyms) ||
    !text(exclusions) ||
    !text(jurisdictions) ||
    !strings(languages) ||
    !strings(source_pack_ids) ||
    !strings(document_kinds) ||
    !strings(event_kinds) ||
    typeof importance_floor !== "string" ||
    !["high", "medium", "low", "none"].includes(importance_floor)
  )
    return null;
  return {
    name,
    goal,
    concepts,
    synonyms,
    exclusions,
    jurisdictions,
    languages,
    source_pack_ids,
    document_kinds,
    event_kinds,
    importance_floor: importance_floor as TopicForm["importance_floor"],
  };
}

export function parseTopicDraft(
  raw: string | null,
  scope: string,
  now = Date.now(),
): TopicTabDraft | null {
  if (!raw || raw.length > maxCharacters) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (
      !object(value) ||
      value.version !== 1 ||
      value.scope !== scope ||
      typeof value.savedAt !== "number" ||
      !Number.isFinite(value.savedAt) ||
      value.savedAt > now ||
      now - value.savedAt >= topicDraftLifetime ||
      !text(value.idempotencyKey, 200)
    )
      return null;
    const current = form(value.form),
      baseline = form(value.baseline);
    if (!current || !baseline) return null;
    const editing = value.editing,
      ai = value.aiDraft;
    if (
      editing !== null &&
      (!object(editing) ||
        !text(editing.id, 200) ||
        !editing.id ||
        !Number.isSafeInteger(editing.current_revision) ||
        Number(editing.current_revision) < 1)
    )
      return null;
    if (
      ai !== null &&
      (!object(ai) ||
        !text(ai.id, 200) ||
        !ai.id ||
        !text(ai.provider, 200) ||
        !text(ai.model, 1000))
    )
      return null;
    return {
      version: 1,
      scope,
      savedAt: value.savedAt,
      form: current,
      baseline,
      editing:
        editing === null
          ? null
          : {
              id: editing.id as string,
              current_revision: editing.current_revision as number,
            },
      aiDraft:
        ai === null
          ? null
          : {
              id: ai.id as string,
              provider: ai.provider as string,
              model: ai.model as string,
            },
      idempotencyKey: value.idempotencyKey,
    };
  } catch {
    return null;
  }
}

export function readTopicDraft(
  storage: StorageLike,
  scope: string,
  now = Date.now(),
): { draft: TopicTabDraft | null; failed: boolean } {
  try {
    const raw = storage.getItem(scope),
      draft = parseTopicDraft(raw, scope, now);
    if (raw && !draft) storage.removeItem(scope);
    return { draft, failed: false };
  } catch {
    return { draft: null, failed: true };
  }
}
export function writeTopicDraft(
  storage: StorageLike,
  draft: TopicTabDraft,
): boolean {
  try {
    const raw = JSON.stringify(draft);
    const clean = parseTopicDraft(raw, draft.scope, draft.savedAt);
    if (!clean) return false;
    storage.setItem(draft.scope, JSON.stringify(clean));
    return true;
  } catch {
    return false;
  }
}
export function removeTopicDraft(storage: StorageLike, scope: string): boolean {
  try {
    storage.removeItem(scope);
    return true;
  } catch {
    return false;
  }
}
