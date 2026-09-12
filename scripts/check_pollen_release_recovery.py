"""Explicit, disposable Docker rehearsal. Never reads production env or volumes."""

import argparse
import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path
from uuid import uuid4

import yaml

ROOT = Path(__file__).resolve().parents[1]
POSTGRES = "postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
BACKUP = "20260912T020000Z"


def run(args, *, data=None, ok=True):
    result = subprocess.run(args, input=data, capture_output=True, timeout=180, check=False)
    if ok and result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace")[-3000:])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decoder-image", required=True, help="Locally built candidate image")
    options = parser.parse_args()
    project = "pollen-recovery-" + uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix=project, dir=ROOT.parent) as temporary:
        scratch = Path(temporary)
        backups, documents = scratch / "backups", scratch / "documents"
        snapshot = backups / BACKUP
        snapshot.mkdir(parents=True)
        documents.mkdir()
        production = yaml.safe_load((ROOT / "compose.production.yaml").read_text())
        decoder = production["services"]["pollen-decoder"]
        decoder = {key: value for key, value in decoder.items() if key not in {"build", "networks", "restart"}}
        decoder["image"] = options.decoder_image
        # Same health command and default image entrypoint/CMD as production.
        decoder["healthcheck"] = {**decoder["healthcheck"], "interval": "1s", "retries": 30}
        manifest = {
            "services": {
                "decoder": decoder,
                "db": {"image": POSTGRES, "environment": {"POSTGRES_USER": "recovery_test",
                    "POSTGRES_PASSWORD": "isolated-recovery-only", "POSTGRES_DB": "recovery_test"},
                    "tmpfs": ["/var/lib/postgresql/data"],
                    "healthcheck": {"test": ["CMD", "pg_isready", "-U", "recovery_test"], "interval": "1s", "retries": 30}},
            },
            "networks": {"default": {"internal": True}},
        }
        compose_path = scratch / "compose.yaml"
        compose_path.write_text(yaml.safe_dump(manifest))
        compose = ["docker", "compose", "-p", project, "-f", str(compose_path)]
        sql = [*compose, "exec", "-T", "db", "psql", "-U", "recovery_test", "-d", "recovery_test", "-At", "-v", "ON_ERROR_STOP=1", "-c"]
        def query(value):
            return run([*sql, value]).stdout.decode().strip()
        def checksums():
            (snapshot / "SHA256SUMS").write_text("".join(
                hashlib.sha256((snapshot / name).read_bytes()).hexdigest() + "  " + name + "\n"
                for name in ["database.dump", "documents.tar.gz", "environment", "Caddyfile", "METADATA"]), newline="\n")
        def restore(*, script=None, wrapper=False):
            args = ["docker", "run", "--rm", "--network", project + "_default",
                "--label", "purpose=pollen-release-recovery-test",
                "--mount", f"type=bind,source={backups},target=/backups,readonly",
                "--mount", f"type=bind,source={documents},target=/documents",
                "--mount", f"type=bind,source={script or ROOT / 'deploy/restore.sh'},target=/operations/restore.sh,readonly"]
            for key, value in {"POSTGRES_HOST": "db", "POSTGRES_USER": "recovery_test", "POSTGRES_DB": "recovery_test",
                "POSTGRES_PASSWORD": "isolated-recovery-only", "BACKUP_ID": BACKUP, "CONFIRM_RESTORE": BACKUP}.items():
                args += ["-e", key + "=" + value]
            if wrapper:
                args += ["--mount", f"type=bind,source={scratch / 'inject.sh'},target=/qa/inject.sh,readonly",
                         "--entrypoint", "/bin/sh", POSTGRES, "/qa/inject.sh"]
            else:
                args += ["--entrypoint", "/bin/sh", POSTGRES, "/operations/restore.sh"]
            return run(args, ok=False)
        try:
            run([*compose, "up", "-d", "--wait", "--wait-timeout", "100"])
            query("CREATE TABLE users(id text PRIMARY KEY, value text); INSERT INTO users VALUES ('owner','original');")
            dump = run([*compose, "exec", "-T", "db", "pg_dump", "-U", "recovery_test", "-d", "recovery_test",
                        "--format=custom", "--no-owner", "--no-privileges"]).stdout
            (snapshot / "database.dump").write_bytes(dump)
            with tarfile.open(snapshot / "documents.tar.gz", "w:gz") as archive:
                body = b"original document"
                info = tarfile.TarInfo("original.txt")
                info.size = len(body)
                archive.addfile(info, io.BytesIO(body))
            for name in ("environment", "Caddyfile", "METADATA"):
                (snapshot / name).write_text("synthetic isolated fixture\n")
            checksums()
            query("CREATE TABLE monitoring_deliveries(owner_id text REFERENCES users(id)); UPDATE users SET value='changed'; INSERT INTO monitoring_deliveries VALUES ('owner');")
            (documents / "changed.txt").write_text("changed document")
            old_script = scratch / "old-restore.sh"
            old_script.write_bytes(run(["git", "-C", str(ROOT), "show",
                "0ec41a916b4fdba62ae59651c2f9c623aedca294:deploy/restore.sh"]).stdout)
            old = restore(script=old_script)
            assert old.returncode and b"depend" in old.stderr, old.stderr.decode()
            fixed = restore()
            assert fixed.returncode == 0, fixed.stderr.decode()
            assert query("SELECT value FROM users") == "original"
            assert query("SELECT to_regclass('public.monitoring_deliveries') IS NULL") == "t"
            assert (documents / "original.txt").read_bytes() == b"original document"
            assert not (documents / "changed.txt").exists()
            assert restore().returncode == 0

            # Introduce a SQL failure after reset/replay, inside the same actual
            # psql transaction. Injection exists only in this disposable client.
            (scratch / "inject.sh").write_text("""#!/bin/sh
set -eu
mkdir /tmp/qa-bin
cat > /tmp/qa-bin/pg_restore <<'WRAPPER'
#!/bin/sh
/usr/local/bin/pg_restore "$@"
for arg in "$@"; do case "$arg" in --file=*) printf '\\nSELECT 1/0;\\n' >> "${arg#--file=}" ;; esac; done
WRAPPER
chmod +x /tmp/qa-bin/pg_restore
PATH=/tmp/qa-bin:$PATH exec /bin/sh /operations/restore.sh
""", newline="\n")
            query("UPDATE users SET value='must survive SQL failure'")
            (documents / "original.txt").write_text("must survive SQL failure")
            failed = restore(wrapper=True)
            assert failed.returncode and b"division by zero" in failed.stderr, failed.stderr.decode()
            assert query("SELECT value FROM users") == "must survive SQL failure"
            assert (documents / "original.txt").read_text() == "must survive SQL failure"
            query("CREATE SCHEMA unrelated")
            denied = restore()
            assert denied.returncode and b"dedicated application database" in denied.stderr
            assert query("SELECT value FROM users") == "must survive SQL failure"
            query("DROP SCHEMA unrelated")
            (snapshot / "database.dump").write_bytes(b"not a PostgreSQL archive")
            checksums()  # Invalid archive, even with a valid checksum, fails before reset.
            assert restore().returncode != 0
            assert query("SELECT value FROM users") == "must survive SQL failure"
            print(json.dumps({"decoder_default_start_and_exact_health": "passed", "old_restore_failure_reproduced": True,
                "older_snapshot_after_new_foreign_keys": "passed", "repeat_restore": "passed",
                "sql_error_preserves_database_and_documents": "passed", "unrelated_schema_refused": "passed",
                "invalid_archive_refused_before_reset": "passed", "production_access": False}, indent=2))
        finally:
            run([*compose, "down", "--volumes", "--remove-orphans"], ok=False)


if __name__ == "__main__":
    main()
