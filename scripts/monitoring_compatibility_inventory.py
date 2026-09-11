"""Read-only MV2-001 inventory from an exact Git revision (no app/database startup)."""

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

BASELINE = "7109a2891f9c99e53572008cc7c1a86001792a57"
MVP_TAG_OBJECT = "c33f3094e51019bfe1083bec71a53858eef1917c"


def git(*args):
    return subprocess.check_output(["git", *args])


def inventory(revision):
    sha = git("rev-parse", revision + "^{commit}").decode().strip()
    files = git("ls-tree", "-r", "--name-only", sha).decode().splitlines()
    result = {"revision": sha, "api_routes": [], "web_routes": [], "models": {},
              "job_types": [], "migrations": {}, "contract_file_hashes": {}}
    for path in files:
        if path.startswith("apps/web/app/") and path.endswith("/page.tsx"):
            result["web_routes"].append(path)
        if not path.startswith("services/api/") or not path.endswith(".py"):
            continue
        if "/alembic/versions/" in path:
            result["migrations"][path] = hashlib.sha256(git("show", f"{sha}:{path}")).hexdigest()
            continue
        if not path.startswith("services/api/helvetic_lens/"):
            continue
        raw = git("show", f"{sha}:{path}")
        tree = ast.parse(raw)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                            and decorator.func.attr in {"get", "post", "put", "patch", "delete"}
                            and decorator.args and isinstance(decorator.args[0], ast.Constant)
                            and isinstance(decorator.args[0].value, str)
                            and decorator.args[0].value.startswith("/")):
                        result["api_routes"].append({"method": decorator.func.attr.upper(),
                                                    "path": decorator.args[0].value, "file": path})
            if path.endswith("/models.py") and isinstance(node, ast.ClassDef):
                result["models"][node.name] = ast.unparse(node)
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "job_type":
                for value in ast.walk(node):
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        result["job_types"].append(value.value)
        if path.rsplit("/", 1)[-1] in {"models.py", "schemas.py", "main.py", "db.py", "service.py", "jobs.py", "connectors.py"}:
            result["contract_file_hashes"][path] = hashlib.sha256(raw).hexdigest()
    result["job_types"] = sorted(set(result["job_types"]))
    # Dynamic dispatch is visible in these additional source contracts.
    result["job_dispatch_reference"] = "services/api/helvetic_lens/service.py:run_job and interest_policy.py"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert git("rev-parse", "v1.0.0-hackathon-mvp").decode().strip() == MVP_TAG_OBJECT
    assert git("rev-parse", "v1.0.0-hackathon-mvp^{commit}").decode().strip() == BASELINE
    baseline, current = inventory(BASELINE), inventory(args.revision)
    old_rows = git("show", BASELINE + ":BACKLOG.md").decode()
    open_ids = {line.split("[", 1)[1].split("]", 1)[0] for line in old_rows.splitlines()
                if line.startswith("| [HL-") and line.split("|")[3].strip() != "DONE"}
    disposition = Path("docs/monitoring-v2/LEGACY_DISPOSITION.md").read_text(encoding="utf-8")
    mapped_ids = {line.split("[", 1)[1].split("]", 1)[0] for line in disposition.splitlines()
                  if line.startswith("| [HL-")}
    assert len(open_ids) == 35 and open_ids == mapped_ids, (open_ids - mapped_ids, mapped_ids - open_ids)
    report = {"baseline": baseline, "current": current, "mvp_tag_object": MVP_TAG_OBJECT,
              "legacy_disposition_ids": sorted(mapped_ids),
              "removed_api_routes": [r for r in baseline["api_routes"] if r not in current["api_routes"]],
              "removed_web_routes": sorted(set(baseline["web_routes"]) - set(current["web_routes"])),
              "changed_models": [name for name, body in baseline["models"].items()
                                 if current["models"].get(name) != body]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"baseline": BASELINE, "current": current["revision"],
                      "legacy_items": len(mapped_ids), "api_routes": len(current["api_routes"]),
                      "web_routes": len(current["web_routes"]), "models": len(current["models"]),
                      "removed_api_routes": len(report["removed_api_routes"]),
                      "removed_web_routes": report["removed_web_routes"],
                      "changed_models": report["changed_models"]}))


if __name__ == "__main__":
    main()
