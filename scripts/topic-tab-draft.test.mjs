import assert from "node:assert/strict";
import test from "node:test";
import {
  parseTopicDraft,
  readTopicDraft,
  writeTopicDraft,
  removeTopicDraft,
  topicDraftKey,
  topicDraftLifetime,
} from "../apps/web/lib/topic-tab-draft.ts";

const scope = topicDraftKey("user-a", "org-a");
const plan = {
  name: "Unfinished plan",
  goal: "Follow this subject",
  concepts: "privacy, data",
  synonyms: "",
  exclusions: "sport",
  jurisdictions: "CH",
  languages: ["de"],
  source_pack_ids: ["federal"],
  document_kinds: ["act"],
  event_kinds: ["amended"],
  importance_floor: "low",
};
const draft = {
  version: 1,
  scope,
  savedAt: 1000,
  form: plan,
  baseline: { ...plan, goal: "Original" },
  editing: { id: "topic-1", current_revision: 3 },
  aiDraft: { id: "draft-1", provider: "docker", model: "local-test" },
  idempotencyKey: "same-activation",
};
function storage() {
  const values = new Map();
  return {
    getItem: (k) => values.get(k) ?? null,
    setItem: (k, v) => values.set(k, v),
    removeItem: (k) => values.delete(k),
  };
}

test("tab draft retains raw fields, original revision and retry key without restoring a preview", () => {
  const store = storage();
  assert.ok(writeTopicDraft(store, draft));
  assert.deepEqual(readTopicDraft(store, scope, 1100), {
    draft,
    failed: false,
  });
  assert.ok(removeTopicDraft(store, scope));
  assert.equal(store.getItem(scope), null);
});
test("user and organization scopes never collide or borrow another draft", () => {
  assert.notEqual(scope, topicDraftKey("user-a", "org-b"));
  assert.notEqual(scope, topicDraftKey("user-b", "org-a"));
  assert.notEqual(topicDraftKey("a:b", "c"), topicDraftKey("a", "b:c"));
  assert.equal(topicDraftKey(undefined, "org-a"), null);
  assert.equal(
    parseTopicDraft(
      JSON.stringify(draft),
      topicDraftKey("user-b", "org-a"),
      1100,
    ),
    null,
  );
});
for (const [name, update] of [
  ["schema", { version: 2 }],
  ["array severity", { form: { ...plan, importance_floor: ["low"] } }],
  ["expiry", { savedAt: 1000 - topicDraftLifetime }],
  ["future", { savedAt: 1002 }],
  ["revision", { editing: { id: "topic-1", current_revision: 0 } }],
  ["form", { form: { ...plan, languages: "de" } }],
  ["size", { form: { ...plan, goal: "x".repeat(70000) } }],
  ["missing identity", { editing: { current_revision: 3 } }],
]) {
  test(`invalid ${name} is discarded without restoring arbitrary state`, () => {
    const store = storage();
    store.setItem(scope, JSON.stringify({ ...draft, ...update }));
    assert.deepEqual(readTopicDraft(store, scope, 1001), {
      draft: null,
      failed: false,
    });
    assert.equal(store.getItem(scope), null);
  });
}
test("unknown metadata, preview data and credentials are never persisted", () => {
  const store = storage();
  assert.ok(
    writeTopicDraft(store, {
      ...draft,
      preview: { secret: "not stored" },
      form: { ...plan, token: "not stored" },
    }),
  );
  assert.ok(!store.getItem(scope).includes("not stored"));
  assert.deepEqual(readTopicDraft(store, scope, 1001).draft, draft);
});
test("denied storage and quota exhaustion are surfaced without throwing", () => {
  const denied = {
    getItem() {
      throw Error("denied");
    },
    setItem() {
      throw Error("quota");
    },
    removeItem() {
      throw Error("denied");
    },
  };
  assert.deepEqual(readTopicDraft(denied, scope, 1001), {
    draft: null,
    failed: true,
  });
  assert.equal(writeTopicDraft(denied, draft), false);
  assert.equal(removeTopicDraft(denied, scope), false);
});
test("malformed JSON and exact expiry boundary are rejected", () => {
  assert.equal(parseTopicDraft("{", scope, 1001), null);
  assert.equal(
    parseTopicDraft(JSON.stringify(draft), scope, 1000 + topicDraftLifetime),
    null,
  );
});
