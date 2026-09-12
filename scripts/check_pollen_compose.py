"""Read-only Compose validation for both isolated Pollen deployment channels."""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env.update({
    "HELVETIC_LENS_RELEASE": "pollen-compose-rehearsal",
    "PUBLIC_BASE_URL": "https://pollen.example.invalid",
    "AUTH_EMAIL_MODE": "smtp", "AUTH_EMAIL_FROM": "Pollen <pollen@example.invalid>",
    "AUTH_SMTP_HOST": "smtp.example.invalid", "HELVETIC_LENS_DB_PASSWORD": "isolated-compose-only",
    "HELVETIC_LENS_CREDENTIAL_KEY": "isolated-compose-only-credential-key",
    "HELVETIC_LENS_DOMAIN": "pollen.example.invalid", "CADDY_ACME_EMAIL": "ops@example.invalid",
    "HELVETIC_LENS_BACKUP_DIR": str(ROOT / "test-results/compose-backup"),
    "POLLEN_SOURCE_POLICY": "{}",
})
for instance in ("main", "monitoring-v2"):
    for disabled in (False, True):
        env["HELVETIC_LENS_INSTANCE"] = instance
        env.pop("MONITORING_V2_ROLLOUT", None)
        if disabled:
            env["MONITORING_V2_ROLLOUT"] = '{"enabled":false}'
        args = ["docker", "compose", "--env-file", os.devnull, "-p", "pollen-config-rehearsal",
                "-f", "compose.production.yaml"]
        if instance == "monitoring-v2":
            args += ["-f", "compose.cloudflare-tunnel.yaml", "-f", "compose.monitoring.yaml"]
        result = subprocess.run([*args, "config", "--format", "json"], cwd=ROOT, env=env,
                                capture_output=True, text=True, check=True)
        config = json.loads(result.stdout)
        decoder = config["services"]["pollen-decoder"]
        assert decoder["read_only"] and decoder["cap_drop"] == ["ALL"]
        assert not decoder.get("ports") and not decoder.get("volumes") and not decoder.get("environment")
        assert set(decoder["networks"]) == {"pollen-decode"}
        assert config["networks"]["pollen-decode"]["internal"]
        assert decoder["healthcheck"]["test"][1] == "/opt/conda/bin/python"
        assert {"data", "outbound", "model-control", "pollen-decode"} <= set(config["services"]["worker-cpu"]["networks"])
        for service in ("api", "worker-cpu", "scheduler"):
            values = config["services"][service]["environment"]
            rollout = json.loads(values["MONITORING_V2_ROLLOUT"])
            assert rollout["enabled"] is not disabled
            if not disabled:
                assert rollout["grants"] == [{"workspace_id": "*", "template_id": "pollen-watch",
                                              "template_version": 1, "mode": "enabled"}]
            assert values["POLLEN_SOURCE_POLICY"] == "{}"
            assert values["POLLEN_DECODER_URL"] == "http://pollen-decoder:8093"
        print(f"{instance}: {'kill switch' if disabled else 'general availability'} / private decoder / source gate passed")
