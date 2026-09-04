import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "release_manager", ROOT / "deploy" / "release_manager.py"
)
assert SPEC and SPEC.loader
release_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_manager)


def test_release_prefix_accepts_exact_and_named_git_releases():
    assert release_manager.release_prefix("git-0123456789ab") == "0123456789ab"
    assert release_manager.release_prefix("6d781e8-brand-auth1") == "6d781e8"
    assert release_manager.release_prefix("latest") is None


def test_remote_normalization_is_exact_but_ignores_git_suffix():
    assert release_manager.normalize_remote("https://github.com/example/repo.git") == (
        "https://github.com/example/repo"
    )
    assert release_manager.normalize_remote("https://github.com/example/repo/") == (
        "https://github.com/example/repo"
    )


def test_release_update_preserves_secrets_and_file_permissions(tmp_path):
    environment = tmp_path / ".env.production"
    environment.write_text(
        "HELVETIC_LENS_RELEASE=old\nAUTH_SMTP_PASSWORD=do-not-change\n",
        encoding="utf-8",
    )
    environment.chmod(0o600)

    release_manager.atomic_update_release(environment, "git-0123456789ab")

    assert environment.read_text(encoding="utf-8") == (
        "HELVETIC_LENS_RELEASE=git-0123456789ab\n"
        "AUTH_SMTP_PASSWORD=do-not-change\n"
    )
    assert environment.stat().st_mode & 0o777 == 0o600


def test_backup_id_comes_from_the_successful_container_output():
    assert release_manager.ReleaseManager._backup_id(
        "Container ready\nBackup 20260904T112145Z completed.\n"
    ) == "20260904T112145Z"


def test_only_a_live_allowlisted_model_is_preserved_for_a_release():
    manager = release_manager.ReleaseManager

    assert manager._active_model_id({"model_id": "apertus-8b-q4km", "state": "ready"}) == (
        "apertus-8b-q4km"
    )
    assert manager._active_model_id({"model_id": "apertus-8b-q4km", "state": "stopped"}) is None
    assert manager._active_model_id({"model_id": "../../secret", "state": "ready"}) is None
