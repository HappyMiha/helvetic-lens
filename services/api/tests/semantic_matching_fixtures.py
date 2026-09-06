"""Synthetic reviewer attestations exercise code, never establish human quality."""

import json
from pathlib import Path

from helvetic_lens.semantic_matching_eval import FEATURES, LOCALES, digest


def write_json(path, value):
    path = Path(path)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    path.write_bytes(raw)
    return {"path": path.name, "sha256": digest(raw)}


def matching_input(index=0, positive=True, locale="en-CH"):
    title = (
        f"Synthetic record retention change {index}"
        if positive
        else f"Synthetic unrelated football event {index}"
    )
    return {
        "schema_version": "hl093.matching-input.v1",
        "plan": {
            "name": "Synthetic monitoring",
            "goal": "Follow retention rules for our records.",
            "concepts": ["retention"],
            "synonyms": [],
            "exclusions": [],
            "jurisdictions": ["CH"],
            "languages": ["de", "fr", "it", "rm", "en"],
            "source_pack_ids": ["test-law-pack"],
            "document_kinds": ["act"],
            "event_kinds": ["amended"],
            "importance_floor": "low",
        },
        "work": {"title": title, "kind": "act", "authority": "fedlex", "metadata": {"jurisdiction": "CH"}},
        "event": {
            "event_type": "amended",
            "connector": "fedlex",
            "impact": "medium",
            "evidence": {"stream": "rss", "language": locale[:2]},
        },
        "identifiers": [],
        "packs": [{"id": "test-law-pack", "revision": "synthetic-v1", "streams": [["fedlex", "rss"]]}],
    }


def package(root, count=6, provenance="synthetic_fixture"):
    root.mkdir(parents=True, exist_ok=True)
    cases, labels, predictions = [], [], []
    for index in range(count):
        case_id = f"case-{index:04d}"
        locale = LOCALES[index % 5]
        positive = index % 2 == 0
        value = matching_input(index, positive, locale)
        input_ref = write_json(root / f"input-{index}.json", value)
        source = value["work"]["title"] + ". Exact saved synthetic source wording."
        source_path = root / f"source-{index}.txt"
        source_path.write_text(source, encoding="utf-8")
        cases.append(
            {
                "id": case_id,
                "family": case_id,
                "split": "held_out",
                "locale": locale,
                "source_type": ("fedlex", "parliament", "court")[index % 3],
                "features": list(FEATURES),
                "input": input_ref,
                "sources": [
                    {
                        "id": "event",
                        "public_url": "https://example.invalid/synthetic/" + case_id,
                        "artifact": {"path": source_path.name, "sha256": digest(source.encode())},
                    }
                ],
            }
        )
        vote = {
            "reviewer_id": "reviewer-a",
            "relevant": positive,
            "rationale": "Synthetic relevance label, not an independently reviewed legal judgment.",
            "citations": [{"source_id": "event", "quote": source}],
        }
        labels.append({"case_id": case_id, "votes": [vote, {**vote, "reviewer_id": "reviewer-b"}]})
        predictions.append(
            {
                "case_id": case_id,
                "input_sha256": input_ref["sha256"],
                "status": "ok",
                "relevant": positive,
                "reason_codes": ["synthetic_prediction"],
                "latency_ms": 1.0,
            }
        )
    dataset = {
        "schema_version": "hl093.matching-dataset.v1",
        "id": "synthetic-matching",
        "revision": "test-v1",
        "provenance": provenance,
        "authors": ["fixture-author"],
        "cases": cases,
    }
    dataset_ref = write_json(root / "dataset.json", dataset)
    gold = {
        "schema_version": "hl093.matching-labels.v1",
        "dataset_sha256": dataset_ref["sha256"],
        "frozen_at": "2026-09-01T10:00:00Z",
        "review_reference": "Synthetic declarations for automated regression only.",
        "reviewers": [
            {
                "id": name,
                "independent_of_system": True,
                "fluent_locales": list(LOCALES),
                "domain_review_reference": "Synthetic person, not actual independent evidence.",
            }
            for name in ("reviewer-a", "reviewer-b", "reviewer-c")
        ],
        "labels": labels,
    }
    run = {
        "schema_version": "hl093.matching-predictions.v1",
        "dataset_sha256": dataset_ref["sha256"],
        "split": "held_out",
        "run_id": "synthetic-run",
        "created_at": "2026-09-02T10:00:00Z",
        "system": "synthetic-system",
        "system_revision": "a" * 40,
        "implementation_sha256": "b" * 64,
        "configuration_sha256": "c" * 64,
        "working_tree_dirty": False,
        "rows": predictions,
    }
    write_json(root / "labels.json", gold)
    write_json(root / "predictions.json", run)
    return dataset, gold, run
