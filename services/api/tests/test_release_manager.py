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
