import assert from "node:assert/strict";
import test from "node:test";
import { influenceDossier } from "../apps/web/lib/influence-dossier.ts";
import { influenceCopy } from "../apps/web/lib/influence-copy.ts";
import {
  influenceEdgeGeometry,
  nextInfluenceEntityPosition,
  isConfirmedMoneyFlow,
  visibleInfluenceEdges,
  validateInfluenceDossier,
} from "../apps/web/lib/influence-graph.ts";

test("reference dossier retains resolvable provenance and dispute boundaries", () => {
  assert.deepEqual(validateInfluenceDossier(influenceDossier), []);
  const disputed = influenceDossier.edges.find(
    (edge) => edge.status === "disputed",
  );
  assert.ok(disputed.supporting.length && disputed.disputing.length);
  assert.equal(
    influenceDossier.edges.find((edge) => edge.kind === "potential_impact")
      .status,
    "not_established",
  );
});

test("confirmed money excludes ownership, estimates, disputes and secondary reporting", () => {
  const edges = visibleInfluenceEdges(influenceDossier, "money");
  assert.equal(edges.length, 1);
  assert.equal(edges[0].money.amount, 403461000);
  assert.equal(edges[0].to, "shareholders");
  assert.deepEqual(
    visibleInfluenceEdges(influenceDossier, "money", "blocher"),
    [],
  );
  for (const alter of [
    (edge) => {
      edge.kind = "ownership";
    },
    (edge) => {
      edge.status = "reported";
    },
    (edge) => {
      edge.money.basis = "proposed";
    },
    (edge) => {
      edge.money.amount = NaN;
    },
    (edge) => {
      edge.money.amount = -1;
    },
    (edge) => {
      edge.money.periodEnd = "2026-02-31";
    },
    (edge) => {
      edge.money.evidenceSourceId = "republik-investigation";
    },
    (edge) => {
      edge.disputing.push({
        sourceId: "ems-response",
        locator: "reply",
        summary: "Denial",
      });
    },
  ]) {
    const edge = structuredClone(edges[0]);
    alter(edge);
    assert.equal(isConfirmedMoneyFlow(edge, influenceDossier.sources), false);
  }
});

test("entity and perspective filters intersect without completing imaginary paths", () => {
  const rows = visibleInfluenceEdges(influenceDossier, "documented", "blocher");
  assert.deepEqual(
    rows.map((row) => row.id),
    ["E01", "E02"],
  );
  assert.equal(visibleInfluenceEdges(influenceDossier, "policy").length, 3);
  assert.deepEqual(
    visibleInfluenceEdges(influenceDossier, "all", "unknown"),
    [],
  );
});

test("parallel claims and opposite directions keep distinct selectable labels", () => {
  const from = { id: "a", x: 30, y: 30 };
  const to = { id: "b", x: 430, y: 30 };
  const edges = [
    { id: "ownership", from: "a", to: "b" },
    { id: "role", from: "a", to: "b" },
    { id: "payment", from: "b", to: "a" },
  ];
  const positions = edges.map((edge) =>
    influenceEdgeGeometry(
      edge.from === "a" ? from : to,
      edge.to === "b" ? to : from,
      edge,
      edges,
    ),
  );
  assert.equal(new Set(positions.map((position) => position.y)).size, 3);
  assert.ok(
    positions.every(
      (position) => Number.isFinite(position.x) && Number.isFinite(position.y),
    ),
  );
  assert.ok(Math.abs(positions[0].y - positions[1].y) >= 30);
});

test("adding after deletion or copying a dossier selects unoccupied node positions", () => {
  const retained = [
    { id: "b", x: 360, y: 30 },
    { id: "c", x: 690, y: 30 },
  ];
  assert.deepEqual(
    nextInfluenceEntityPosition(retained, influenceCopy["en-CH"].graphFull),
    { x: 30, y: 30 },
  );
  const nodes = structuredClone(influenceDossier.entities);
  while (nodes.length < 100) {
    const position = nextInfluenceEntityPosition(nodes, influenceCopy["en-CH"].graphFull);
    assert.ok(position.x <= 12000 && position.y <= 12000);
    assert.ok(
      nodes.every(
        (node) =>
          position.x + 230 <= node.x ||
          node.x + 230 <= position.x ||
          position.y + 112 <= node.y ||
          node.y + 112 <= position.y,
      ),
    );
    nodes.push({ id: `new-${nodes.length}`, ...position });
  }
});

test("each supported locale supplies the full interface and evidence vocabulary", () => {
  const keys = (object) => Object.keys(object).sort();
  for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    assert.deepEqual(keys(influenceCopy[locale]), keys(influenceCopy["en-CH"]));
    for (const group of [
      "statuses",
      "entityKinds",
      "sourceKinds",
      "relationKinds",
    ]) {
      assert.deepEqual(
        keys(influenceCopy[locale][group]),
        keys(influenceCopy["en-CH"][group]),
      );
    }
  }
});
