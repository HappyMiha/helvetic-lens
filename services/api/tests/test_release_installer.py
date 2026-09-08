"""Actual shell/Git/flock/atomic install in disposable Linux directories only."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Requires real Linux flock and installer tools")
ROOT = Path(__file__).resolve().parents[3]
INSTALLER = ROOT / "deploy/install-auto-deploy.sh"
TRUSTED = "https://github.com/HappyMiha/helvetic-lens.git"


def command(*args, cwd=None, env=None):
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=True).stdout.strip()


@pytest.fixture
def installation(tmp_path):
    source, control, state, tools = [tmp_path / name for name in
                                   ("source repo", "control space", "state", "tools")]
    (source / "deploy").mkdir(parents=True)
    control.mkdir()
    tools.mkdir()
    command("git", "init", "--quiet", str(source))
    command("git", "config", "user.email", "fixture@example.invalid", cwd=source)
    command("git", "config", "user.name", "Installer fixture", cwd=source)
    command("git", "remote", "add", "origin", TRUSTED, cwd=source)
    manager = source / "deploy/release_manager.py"
    manager.write_text("# Synthetic reviewed manager\nprint('do not execute during install')\n")
    command("git", "add", "deploy/release_manager.py", cwd=source)
    command("git", "commit", "--quiet", "-m", "Reviewed manager fixture", cwd=source)
    sha = command("git", "rev-parse", "HEAD", cwd=source)
    command("git", "update-ref", "refs/remotes/origin/main", sha, cwd=source)
    installed = control / "release_manager.py"
    installed.write_text("# Previous manager retained for recovery\n")
    installed.chmod(0o750)
    cron_file = tmp_path / "crontab"
    cron_file.write_text("15 * * * * unrelated-command\n")
    # Only cron is replaced: no user's scheduler can be read or modified.
    crontab = tools / "crontab"
    crontab.write_text('#!/bin/sh\nif [ "$1" = -l ]; then cat "$QA_CRONTAB"; else cp "$1" "$QA_CRONTAB"; fi\n')
    crontab.chmod(0o755)
    env = {**os.environ, "HELVETIC_LENS_SOURCE_REPO": str(source),
           "HELVETIC_LENS_DEPLOY_CONTROL_DIR": str(control), "HELVETIC_LENS_DEPLOY_STATE_DIR": str(state),
           "HELVETIC_LENS_EXPECTED_REPOSITORY": TRUSTED, "QA_CRONTAB": str(cron_file),
           "PATH": str(tools) + os.pathsep + os.environ["PATH"]}
    return source, control, state, cron_file, sha, env


def install(value, *args):
    return subprocess.run(["sh", str(INSTALLER), *args], env=value[-1], text=True, capture_output=True, timeout=15)


def test_update_only_installs_exact_commit_atomically_and_preserves_backup(installation):
    source, control, state, cron, sha, _ = installation
    original = (control / "release_manager.py").read_bytes()
    (source / "deploy/release_manager.py").write_text("uncommitted broken python !\n")
    result = install(installation, "--update-only", "--revision", sha)
    assert result.returncode == 0, result.stderr
    installed = control / "release_manager.py"
    assert installed.read_text() == command("git", "show", f"{sha}:deploy/release_manager.py", cwd=source) + "\n"
    assert installed.stat().st_mode & 0o777 == 0o755
    backups = list(control.glob("release_manager.py.backup.*"))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    assert backups[0].stat().st_mode & 0o777 == 0o750
    assert not state.exists() and not (control / "uv-cache").exists()
    assert cron.read_text() == "15 * * * * unrelated-command\n"
    assert not list(control.glob(".release-manager.*"))
    assert "do not execute" not in result.stdout  # Never starts the installed code.
    assert install(installation, "--update-only", "--revision", sha).returncode == 0
    assert len(list(control.glob("release_manager.py.backup.*"))) == 1


def test_same_lock_as_running_manager_refuses_update_without_writing(installation):
    import fcntl
    control, sha = installation[1], installation[4]
    original = (control / "release_manager.py").read_bytes()
    lock = control / "deployment.lock"
    with lock.open("a+") as handle:
        inode = lock.stat().st_ino
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = install(installation, "--update-only", "--revision", sha)
        assert result.returncode == 75 and "deployment is active" in result.stderr
        assert (control / "release_manager.py").read_bytes() == original
        assert not list(control.glob("release_manager.py.backup.*"))
        assert lock.stat().st_ino == inode


@pytest.mark.parametrize("kind", ["untrusted", "not_in_main", "bad_syntax", "symlink"])
def test_unreviewed_or_unsafe_install_preserves_previous_manager(installation, kind):
    source, control, _, _, sha, _ = installation
    installed = control / "release_manager.py"
    original = installed.read_bytes()
    if kind == "untrusted":
        command("git", "remote", "set-url", "origin", "https://example.invalid/other.git", cwd=source)
    elif kind in {"not_in_main", "bad_syntax"}:
        (source / "deploy/release_manager.py").write_text("invalid syntax !\n" if kind == "bad_syntax" else "# New change\n")
        command("git", "commit", "-am", "Candidate", "--quiet", cwd=source)
        sha = command("git", "rev-parse", "HEAD", cwd=source)
        if kind == "bad_syntax":
            command("git", "update-ref", "refs/remotes/origin/main", sha, cwd=source)
    else:
        external = control.parent / "other.py"
        external.write_bytes(original)
        installed.unlink()
        installed.symlink_to(external)
    result = install(installation, "--update-only", "--revision", sha)
    assert result.returncode != 0
    assert {"untrusted": "Origin does not match", "not_in_main": "not in fetched origin/main",
            "bad_syntax": "SyntaxError", "symlink": "symlink manager destination"}[kind] in result.stderr
    assert installed.read_bytes() == original
    assert not list(control.glob("release_manager.py.backup.*"))
    assert not list(control.glob(".release-manager.*"))


@pytest.mark.parametrize("args", [("--unknown",), ("--revision",), ("--revision", "main"),
                                   ("--revision", "0" * 7), ("--revision", "0" * 40)])
def test_invalid_revision_never_changes_installed_code(installation, args):
    original = (installation[1] / "release_manager.py").read_bytes()
    assert install(installation, *args).returncode != 0
    assert (installation[1] / "release_manager.py").read_bytes() == original


def test_regular_install_preserves_other_cron_entries_and_is_idempotent(installation):
    _, control, state, cron, _, _ = installation
    (control / "release_manager.py").unlink()
    for _ in range(2):
        result = install(installation)
        assert result.returncode == 0, result.stderr
    contents = cron.read_text()
    assert contents.count("# helvetic-lens-auto-deploy") == 1
    assert "15 * * * * unrelated-command" in contents
    assert f"'{control}/release_manager.py' --poll" in contents
    assert (state / "logs").is_dir() and (control / "uv-cache").is_dir()


def test_failed_atomic_replacement_keeps_previous_file_and_recovery_copy(installation):
    _, control, _, cron, sha, env = installation
    original = (control / "release_manager.py").read_bytes()
    mover = Path(env["PATH"].split(os.pathsep)[0]) / "mv"
    mover.write_text("#!/bin/sh\necho 'Synthetic atomic replacement failure' >&2\nexit 17\n")
    mover.chmod(0o755)
    result = install(installation, "--update-only", "--revision", sha)
    assert result.returncode == 17 and "Synthetic atomic replacement failure" in result.stderr
    assert (control / "release_manager.py").read_bytes() == original
    assert list(control.glob("release_manager.py.backup.*"))[0].read_bytes() == original
    assert not list(control.glob(".release-manager.*"))
    assert cron.read_text() == "15 * * * * unrelated-command\n"
