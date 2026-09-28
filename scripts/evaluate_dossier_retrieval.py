#!/usr/bin/env python3
"""Reproducible public NoMIRACL evaluation; no private records or paid calls.

prepare downloads pinned public data, encode uses a separately isolated local
torch environment, decisions uses the native API environment and configured
local Laya, report publishes IDs/metrics only. Keep data/model caches outside Git.
"""
import argparse
import asyncio
import gzip
import hashlib
import json
import math
import re
import statistics
import time
import urllib.request
from pathlib import Path

DATA_REVISION = "ecd08778d0426a5ca28ac99763b0c9ddc2c78e68"
MODEL = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
LANGUAGES = ("english", "german", "french")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def prepare(directory, test_offset=0):
    directory.mkdir(parents=True, exist_ok=True)
    samples, corpus, manifest = [], {}, []
    for language in LANGUAGES:
        def download(relative, language=language):
            url = f"https://huggingface.co/datasets/miracl/nomiracl/resolve/{DATA_REVISION}/data/{language}/{relative}"
            path = directory / (language + "-" + relative.replace("/", "-"))
            if not path.exists():
                with urllib.request.urlopen(url, timeout=90) as response:
                    path.write_bytes(response.read())
            body = path.read_bytes()
            manifest.append({"url": url, "sha256": digest(body), "bytes": len(body)})
            return body
        wanted = set()
        language_samples = []
        for split, count in (("dev", 12), ("test", 20)):
            for subset in ("relevant", "non_relevant"):
                name = f"{split}.{subset}.tsv"
                topics = dict(line.split("\t", 1) for line in download("topics/" + name).decode().splitlines())
                labels = {}
                for line in download("qrels/" + name).decode().splitlines():
                    query_id, _, document, relevance = line.split()
                    labels.setdefault(query_id, {})[document] = int(relevance)
                # Sample identities are fixed before any model result is read.
                offset = test_offset if split == "test" else 0
                selected = sorted(topics, key=lambda key: digest((language + ":" + key).encode()))[offset:offset + (count if subset == "relevant" else 4)]
                for query_id in selected:
                    judged = labels[query_id]
                    wanted.update(judged)
                    language_samples.append({"id": language + ":" + query_id, "language": language,
                        "split": split, "subset": subset, "query": topics[query_id],
                        "labels": {language + ":" + key: label for key, label in judged.items()}})
        for line in gzip.decompress(download("corpus.jsonl.gz")).splitlines():
            row = json.loads(line)
            if row["docid"] in wanted:
                key = language + ":" + row["docid"]
                corpus[key] = {"id": key, "title": row["title"], "statement": "", "quote": row["text"][:2400]}
        assert all(key in corpus for sample in language_samples for key in sample["labels"])
        samples.extend(language_samples)
        print(language, len(language_samples), len(wanted), flush=True)
    assert len({sample["id"] for sample in samples}) == len(samples), "Overlapping query splits"
    write(directory / "input.json", {"samples": samples, "corpus": corpus, "sources": manifest, "test_offset": test_offset})


def encode(directory):
    import torch
    from torch.nn import functional
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(2)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REVISION, trust_remote_code=False)
    model = AutoModel.from_pretrained(MODEL, revision=MODEL_REVISION, trust_remote_code=False,
                                     use_safetensors=True).eval()
    data = json.loads((directory / "input.json").read_text())
    documents, queries = list(data["corpus"].values()), data["samples"]
    measurements = []
    def vectors(texts):
        output = []
        for offset in range(0, len(texts), 16):
            started = time.perf_counter()
            batch = tokenizer(texts[offset:offset + 16], max_length=512, padding=True,
                              truncation=True, return_tensors="pt")
            with torch.inference_mode():
                hidden = model(**batch).last_hidden_state
                masked = hidden.masked_fill(~batch["attention_mask"][..., None].bool(), 0.0)
                vector = masked.sum(dim=1) / batch["attention_mask"].sum(dim=1)[..., None]
                output.extend(functional.normalize(vector, p=2, dim=1).tolist())
            measurements.append({"items": len(texts[offset:offset + 16]),
                                 "ms": round(1000 * (time.perf_counter() - started), 2)})
        return output
    started = time.perf_counter()
    doc_vectors = vectors(["passage: " + item["title"][:300] + "\n" + item["quote"] for item in documents])
    document_ms = 1000 * (time.perf_counter() - started)
    query_vectors = {}
    query_ms = []
    for row in queries:
        started = time.perf_counter()
        query_vectors[row["id"]] = vectors(["query: " + row["query"]])[0]
        query_ms.append(1000 * (time.perf_counter() - started))
    write(directory / "embeddings.json", {"model": MODEL + "@" + MODEL_REVISION,
        "documents": {item["id"]: vector for item, vector in zip(documents, doc_vectors)},
        "queries": query_vectors, "document_ms": round(document_ms, 2),
        "query_ms": query_ms, "batches": measurements})
    print(json.dumps({"documents": len(documents), "queries": len(queries),
        "document_ms": document_ms, "query_mean_ms": statistics.mean(query_ms)}), flush=True)


async def decisions(directory, args):
    from helvetic_lens.config import Settings
    from helvetic_lens.decision_engines import DecisionUnavailable, LayaEngine
    from helvetic_lens.product_evidence_search import (
        INSTRUCTIONS,
        RELEVANCE,
        semantic_state,
    )
    from pydantic import SecretStr

    settings = Settings(laya_base_url=args.laya_url)
    settings.laya_api_key = SecretStr(json.loads(Path(args.credentials_file).read_text())["LAYA_API_KEY"])
    engine = LayaEngine(settings)
    data = json.loads((directory / "input.json").read_text())
    path = directory / "decisions.jsonl"
    completed = {row["id"] for row in map(json.loads, path.read_text().splitlines())} if path.exists() else set()
    with path.open("a") as output:
        for index, sample in enumerate(row for row in data["samples"] if args.split == "all" or row["split"] == args.split):
            for key in sorted(sample["labels"]):
                identifier = sample["id"] + "/" + key
                if identifier in completed:
                    continue
                row = {"id": identifier, "sample": sample["id"], "document": key}
                try:
                    answer = await engine.choose(semantic_state(sample["query"], data["corpus"][key]), INSTRUCTIONS, RELEVANCE)
                    row.update(probability=answer.probabilities["A"], choice=answer.choice,
                               model=answer.model, ms=answer.latency_ms)
                except DecisionUnavailable as error:
                    row["error"] = error.code
                output.write(json.dumps(row) + "\n")
                output.flush()
            print("Laya", index + 1, "/", len(data["samples"]), sample["language"], sample["split"], flush=True)


def report(directory, destination, split="all"):
    from helvetic_lens.decision_search import lexical_order
    from helvetic_lens.product_evidence_search import literal_match

    data = json.loads((directory / "input.json").read_text())
    vectors = json.loads((directory / "embeddings.json").read_text())
    raw = list(map(json.loads, (directory / "decisions.jsonl").read_text().splitlines()))
    expected = {(sample["id"], key) for sample in data["samples"] for key in sample["labels"]}
    raw = [row for row in raw if (row["sample"], row["document"]) in expected]
    answers = {(row["sample"], row["document"]): row for row in raw}
    rows = []
    def fusion(first, second, weight=2):
        score = {key: weight / (60 + index) for index, key in enumerate(first, 1)}
        for index, key in enumerate(second, 1):
            score[key] = score.get(key, 0) + 1 / (60 + index)
        return sorted(score, key=lambda key: (-score[key], key))
    def active(query, keys):
        terms = set(re.findall(r"\w+", query.casefold()))
        return [key for key in keys if terms.intersection(re.findall(r"\w+", (data["corpus"][key]["title"] + " " + data["corpus"][key]["quote"]).casefold()))]
    def metric(order, labels):
        relevant = {key for key, label in labels.items() if label > 0}
        ideal = sum(1 / math.log2(i + 2) for i in range(min(10, len(relevant))))
        return {"ndcg10": sum((1 if key in relevant else 0) / math.log2(i + 2) for i, key in enumerate(order[:10])) / ideal if ideal else None,
                "recall3": len(relevant.intersection(order[:3])) / len(relevant) if relevant else None,
                "recall12": len(relevant.intersection(order[:12])) / len(relevant) if relevant else None,
                "top1": int(bool(order) and order[0] in relevant) if relevant else None}
    for sample in data["samples"]:
        if split != "all" and sample["split"] != split:
            continue
        keys = sorted(sample["labels"])
        dense_scores = {key: sum(a * b for a, b in zip(vectors["queries"][sample["id"]], vector))
                        for key, vector in vectors["documents"].items()}
        dense = sorted(keys, key=lambda key: (-dense_scores[key], key))
        lexical = lexical_order(sample["query"], [{**data["corpus"][key], "summary": data["corpus"][key]["quote"]} for key in keys])
        literal = [key for key in keys if literal_match(sample["query"], data["corpus"][key])]
        decision = sorted([key for key in keys if "probability" in answers[sample["id"], key]],
                          key=lambda key: (-answers[sample["id"], key]["probability"], key))
        all_keys = sorted(dense_scores)
        all_lexical = lexical_order(sample["query"], [{**data["corpus"][key], "summary": data["corpus"][key]["quote"]} for key in all_keys])
        all_dense = sorted(all_keys, key=lambda key: (-dense_scores[key], key))
        row = {key: sample[key] for key in ("id", "language", "split", "subset")}
        row["labels"] = sample["labels"]
        row["rankings"] = {"words": literal, "bm25": lexical, "laya": fusion(decision, literal),
                           "e5": dense, "e5_bm25": fusion(dense, active(sample["query"], lexical))}
        row["metrics"] = {name: metric(order, sample["labels"]) for name, order in row["rankings"].items()}
        row["pool_known_positive_recall12"] = {name: metric(order, sample["labels"])["recall12"] for name, order in {
            "e5": all_dense, "bm25": all_lexical, "e5_bm25": fusion(all_dense, active(sample["query"], all_lexical)),
            "recency12_upper_bound": sorted(all_keys, key=lambda key: digest(key.encode()))[:12]}.items()}
        row["laya_binary_false_negatives"] = sum(label > 0 and answers[sample["id"], key].get("choice") != "A" for key, label in sample["labels"].items())
        row["laya_binary_false_positives"] = sum(label == 0 and answers[sample["id"], key].get("choice") == "A" for key, label in sample["labels"].items())
        rows.append(row)
    groups = {}
    for group_split in (("dev", "test") if split == "all" else (split,)):
        for language in (*LANGUAGES, "all"):
            group = [row for row in rows if row["split"] == group_split and (language == "all" or row["language"] == language)]
            relevant = [row for row in group if row["subset"] == "relevant"]
            groups[group_split + "/" + language] = {"queries": len(group), "answerable_queries": len(relevant),
                "candidate_metrics": {method: {metric: round(statistics.mean(row["metrics"][method][metric] for row in relevant), 5)
                    for metric in ("ndcg10", "recall3", "top1")} for method in ("words", "bm25", "laya", "e5", "e5_bm25")},
                "pool_known_positive_recall12": {method: round(statistics.mean(row["pool_known_positive_recall12"][method] for row in relevant), 5)
                    for method in ("e5", "bm25", "e5_bm25", "recency12_upper_bound")},
                "laya_false_negatives": sum(row["laya_binary_false_negatives"] for row in group),
                "laya_false_positives": sum(row["laya_binary_false_positives"] for row in group)}
    latencies = [row["ms"] for row in raw if "ms" in row]
    result = {"dataset": "miracl/nomiracl", "revision": DATA_REVISION, "sources": data["sources"],
        "model": vectors["model"], "laya_models": sorted({row["model"] for row in raw if "model" in row}),
        "sampling": f"SHA256(language:query_id), first12 dev /20 test relevant +4 non-relevant each; test offset{data.get('test_offset', 0)}; labels unchanged; no fitting. Zero-score BM25 records add no rank signal.",
        "limits": "Judged encyclopedia candidate pools, not full-corpus benchmark or professional quality. Pooled recall covers known positives only; other-query passages are unjudged, not negatives. E5 trained on MIRACL train; project test is untouched for selection, model pretraining contamination is unknown. No Italian/Ukrainian quality claim. Corpus restricted to captured 2400-character prefixes; E5 truncates at512 tokens. Recency ceiling is an artificial deterministic ordering, not real user history.",
        "documents": len(data["corpus"]), "queries": len(rows), "requests": len(raw),
        "failures": sum("error" in row for row in raw), "estimated_cost_usd": None,
        "cost_basis": "Local 2-CPU inference; compute/hosting not metered, unknown not zero. No paid or private-data calls.",
        "latency": {"laya_mean_ms": round(statistics.mean(latencies), 2), "laya_max_ms": max(latencies),
                    "e5_prepare_all_ms": vectors["document_ms"], "e5_query_mean_ms": round(statistics.mean(vectors["query_ms"]), 2)},
        "groups": groups, "rows": rows}
    write(destination, result)
    print(json.dumps({"latency": result["latency"], "groups": groups}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "encode", "decisions", "report"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--test-offset", type=int, default=0)
    parser.add_argument("--split", choices=("dev", "test", "all"), default="all")
    parser.add_argument("--credentials-file")
    parser.add_argument("--laya-url", default="http://127.0.0.1:18761/v1/systemone")
    args = parser.parse_args()
    if args.stage == "prepare":
        prepare(args.directory, args.test_offset)
    elif args.stage == "encode":
        encode(args.directory)
    elif args.stage == "decisions":
        asyncio.run(decisions(args.directory, args))
    else:
        report(args.directory, args.output, args.split)
