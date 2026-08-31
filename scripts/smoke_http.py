"""Exercise real HTTP ingestion and persistence using explicitly synthetic public fixtures.

Run against a disposable local workspace, not a shared user's watchlist.
No model doubles are used. A configured model may be called by the normal scan pipeline.
"""

import argparse
import json
import time
from pathlib import Path

import httpx

FIXTURES = "https://raw.githubusercontent.com/HappyMiha/apertus-regwatch/main/demo/"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--record", type=Path)
    parser.add_argument("--verify-record", type=Path)
    args = parser.parse_args()
    client = httpx.Client(
        base_url=args.api.rstrip("/") + "/api", timeout=120, trust_env=False
    )

    def request(method, path, **kwargs):
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def scan(law_id, baseline=None):
        result = request(
            "POST",
            "/scans",
            json={"law_ids": [law_id], "baseline_version_id": baseline},
        )
        deadline = time.monotonic() + 180
        while result["status"] in {"queued", "running"}:
            if time.monotonic() > deadline:
                raise AssertionError(
                    "The scan did not finish within the smoke-check limit."
                )
            time.sleep(0.25)
            result = request("GET", "/scans/" + result["id"])
        return result

    try:
        health = request("GET", "/health")
        if args.verify_record:
            record = json.loads(args.verify_record.read_text(encoding="utf-8"))
            policy = request("GET", "/laws/" + record["law_id"])
            practice = request("GET", "/laws/" + record["practice_id"])
            assert policy["current_version_id"] == record["current_version_id"]
            assert len(policy["versions"]) == record["version_count"]
            assert len(policy["observations"]) == record["observation_count"]
            assert not practice["active"]
            assert any(
                source["id"] == record["source_id"]
                for source in request("GET", "/sources")
            )
            assert (
                request("GET", "/scans/" + record["scan_id"])["status"]
                == record["scan_status"]
            )
            assert request("GET", "/versions/" + record["old_version_id"])["synthetic"]
            artifact = client.get("/versions/" + record["old_version_id"] + "/artifact")
            assert artifact.status_code == 200 and b"30 days" in artifact.content
            if "model_settings" in record:
                assert request("GET", "/settings/apertus") == record["model_settings"]
            print(
                json.dumps(
                    {"restart_persistence": "passed", "database": health["database"]}
                )
            )
            return

        listing = FIXTURES + "index.html"
        source = next(
            (
                source
                for source in request("GET", "/sources")
                if source["url"] == listing
            ),
            None,
        )
        if not source:
            source = request(
                "POST",
                "/sources",
                json={"name": "Synthetic HTTP smoke source", "url": listing},
            )
        discovered = request("POST", "/sources/" + source["id"] + "/discover")
        assert len(discovered["candidates"]) == 2
        assert discovered["inspected_count"] == discovered["verified_count"] == 2
        assert discovered["error_count"] == 0
        policy_url, practice_url = (
            FIXTURES + "policy-current.html",
            FIXTURES + "practice.txt",
        )
        assert policy_url in {
            candidate["url"] for candidate in discovered["candidates"]
        }
        preview = request("POST", "/preview", json={"url": policy_url})
        assert "60 days" in preview["excerpt"]
        laws = request("GET", "/laws")
        policy = next((law for law in laws if law["url"] == policy_url), None)
        if not policy:
            policy = request(
                "POST",
                "/laws",
                json={"url": policy_url, "source_id": source["id"], "synthetic": True},
            )
        practice = next((law for law in laws if law["url"] == practice_url), None)
        if not practice:
            practice = request(
                "POST", "/laws", json={"url": practice_url, "synthetic": True}
            )
        request("PATCH", "/laws/" + policy["id"], json={"active": True})
        current_id = policy["current_version_id"]
        earlier = (
            Path(__file__).resolve().parents[1] / "demo" / "policy-previous.txt"
        ).read_bytes()
        imported = request(
            "POST",
            "/laws/" + policy["id"] + "/import",
            files={"file": ("policy-previous.txt", earlier, "text/plain")},
            data={"synthetic": "true", "declared_date": "2025-01-01"},
        )
        old_id = imported["version"]["id"]
        pair_ids = []
        for _ in range(2):
            result = scan(policy["id"], old_id)
            item = result["items"][0]
            assert (
                item["result"] == "historical_comparison"
                and item["live_result"] == "unchanged"
            )
            pair_ids.append(item["comparison_id"])
            comparison = request("GET", "/comparisons/" + item["comparison_id"])
            assert comparison["old_version"]["id"] == old_id
            assert comparison["new_version"]["id"] == current_id
            counts = comparison["diff"]["counts"]
            assert (
                counts["modified"] == 2
                and counts["removed"] == 1
                and counts["added"] == 2
            )
            assert any(
                item["old"]
                and "30 days" in item["old"]["text"]
                and item["new"]
                and "60 days" in item["new"]["text"]
                for item in comparison["diff"]["items"]
            )
        assert pair_ids[0] == pair_ids[1]
        ordinary = scan(policy["id"])
        assert ordinary["items"][0]["result"] == "unchanged"
        assert (
            request("GET", "/laws/" + policy["id"])["current_version_id"] == current_id
        )
        saved = request(
            "POST",
            "/comparisons",
            json={"old_version_id": old_id, "new_version_id": current_id},
        )
        assert saved["mode"] == "saved_versions"
        evidence = request("GET", "/versions/" + old_id)
        assert evidence["origin"] == "uploaded" and evidence["synthetic"]
        assert any("30 days" in passage["text"] for passage in evidence["passages"])
        request("PATCH", "/laws/" + practice["id"], json={"active": False})
        detail = request("GET", "/laws/" + policy["id"])
        assert len(detail["versions"]) == 2
        record = {
            "core_workflow": "passed",
            "database": health["database"],
            "model_configured": health["apertus"]["configured"],
            "live_model_acceptance": "not established by this core check",
            "source_id": source["id"],
            "law_id": policy["id"],
            "practice_id": practice["id"],
            "current_version_id": current_id,
            "old_version_id": old_id,
            "comparison_id": pair_ids[0],
            "version_count": len(detail["versions"]),
            "observation_count": len(detail["observations"]),
            "scan_id": ordinary["id"],
            "scan_status": ordinary["status"],
            "diff_counts": counts,
            "model_settings": request("GET", "/settings/apertus"),
        }
        if args.record:
            args.record.write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8"
            )
        print(json.dumps(record, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
