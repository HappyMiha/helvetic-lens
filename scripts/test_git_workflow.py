"""Exercise real Git hooks against disposable local remotes and two clones."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def run_command(self, cwd, *args, ok=True, input_text=None):
        env = os.environ.copy()
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        result = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=40,
            check=False,
            input=input_text,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def git(self, cwd, *args, ok=True):
        return self.run_command(cwd, "git", *args, ok=ok).strip()

    def setup_clone(self, path, host, *args, ok=True):
        return self.run_command(
            path,
            "sh",
            "scripts/setup-git-workflow.sh",
            host,
            *args,
            ok=ok,
        )

    def setUp(self):
        parent = REPO / ".tmp"
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="git-workflow-", dir=parent)
        self.root = Path(self.temp.name).resolve()
        # All repositories (and later recursive cleanup) stay in this test workspace.
        assert self.root.parent == parent.resolve()
        self.addCleanup(self.temp.cleanup)
        self.remote = self.root / "origin.git"
        self.ducky = self.root / "ducky"
        self.snowman = self.root / "snowman"
        self.git(self.root, "init", "--bare", "--initial-branch=main", str(self.remote))
        self.git(self.root, "clone", str(self.remote), str(self.ducky))
        self.git(self.ducky, "config", "user.name", "Test developer")
        self.git(self.ducky, "config", "user.email", "test@example.invalid")
        shutil.copytree(REPO / ".githooks", self.ducky / ".githooks")
        (self.ducky / "scripts").mkdir()
        shutil.copy(REPO / "scripts/setup-git-workflow.sh", self.ducky / "scripts")
        shutil.copy(REPO / ".gitattributes", self.ducky)
        self.git(self.ducky, "add", ".")
        self.git(
            self.ducky,
            "update-index",
            "--chmod=+x",
            ".githooks/pre-commit",
            ".githooks/prepare-commit-msg",
            ".githooks/pre-push",
        )
        self.git(self.ducky, "commit", "-m", "Initial shared workflow")
        self.git(self.ducky, "push", "-u", "origin", "main")
        self.base = self.git(self.ducky, "rev-parse", "HEAD")
        self.git(self.root, "clone", str(self.remote), str(self.snowman))
        self.git(self.snowman, "config", "user.name", "Test developer")
        self.git(self.snowman, "config", "user.email", "test@example.invalid")
        self.setup_clone(self.ducky, "HappyDucky02")
        self.setup_clone(self.snowman, "HappySnowman")
        self.git(self.ducky, "switch", "-c", "codex/HappyDucky02/task-a")
        self.git(self.snowman, "switch", "-c", "codex/HappySnowman/task-b")

    def change(self, repo, name):
        (repo / name).write_text(name + "\n", encoding="utf-8")
        self.git(repo, "add", name)
        self.git(repo, "commit", "-m", "Add " + name)
        return self.git(repo, "rev-parse", "HEAD")

    def test_host_trailer_and_normal_branch_push(self):
        self.change(self.ducky, "a.txt")
        message = self.git(self.ducky, "log", "-1", "--format=%B")
        self.assertIn("Development-Host: HappyDucky02", message)
        self.git(self.ducky, "push", "-u", "origin", "HEAD")
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), self.base)

    def test_main_and_wrong_host_commits_blocked(self):
        for branch in ("main", "codex/HappySnowman/wrong"):
            if branch == "main":
                self.git(self.ducky, "switch", branch)
            else:
                self.git(self.ducky, "switch", "-c", branch)
            output = self.git(
                self.ducky, "commit", "--allow-empty", "-m", "No", ok=False
            )
            self.assertIn("Commit on a unique", output)

    def test_missing_host_blocks_commit(self):
        self.git(self.ducky, "config", "--unset", "helvetic.host")
        self.assertIn(
            "Set this clone up",
            self.git(
                self.ducky,
                "commit",
                "--allow-empty",
                "-m",
                "No",
                ok=False,
            ),
        )

    def test_detached_head_blocks_commit(self):
        self.git(self.ducky, "switch", "--detach")
        self.assertIn(
            "Commit on a unique",
            self.git(
                self.ducky,
                "commit",
                "--allow-empty",
                "-m",
                "No",
                ok=False,
            ),
        )

    def test_two_hosts_merge_without_losing_either_task(self):
        first = self.change(self.ducky, "a.txt")
        self.change(self.snowman, "b.txt")
        self.git(self.ducky, "push", "origin", "HEAD:main")
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), first)
        # Even --force cannot bypass the local ancestry guard.
        output = self.git(
            self.snowman, "push", "--force", "origin", "HEAD:main", ok=False
        )
        self.assertIn("Remote main has changes missing", output)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), first)
        self.git(self.snowman, "fetch", "origin")
        self.git(self.snowman, "merge", "--no-edit", "origin/main")
        self.git(self.snowman, "push", "origin", "HEAD:main")
        self.assertEqual(self.git(self.remote, "show", "main:a.txt"), "a.txt")
        self.assertEqual(self.git(self.remote, "show", "main:b.txt"), "b.txt")

    def test_wrong_host_branch_push_blocked(self):
        self.change(self.ducky, "a.txt")
        output = self.git(
            self.ducky, "push", "origin", "HEAD:codex/HappySnowman/task-b", ok=False
        )
        self.assertIn("do not write another host", output)

    def test_main_deletion_blocked(self):
        self.assertIn(
            "Deleting main is prohibited",
            self.git(
                self.ducky,
                "push",
                "origin",
                ":main",
                ok=False,
            ),
        )
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), self.base)

    def test_task_branch_rewrite_blocked(self):
        self.change(self.ducky, "a.txt")
        self.git(self.ducky, "push", "-u", "origin", "HEAD")
        output = self.git(
            self.ducky,
            "push",
            "--force",
            "origin",
            self.base + ":refs/heads/codex/HappyDucky02/task-a",
            ok=False,
        )
        self.assertIn("replace published history", output)

    def test_worktree_inherits_host_but_production_cannot_write(self):
        self.setup_clone(self.snowman, "HappySnowman", "--production")
        output = self.git(self.snowman, "commit", "--allow-empty", "-m", "No", ok=False)
        self.assertIn("production checkout", output)
        self.assertIn(
            "production checkout",
            self.git(
                self.snowman,
                "push",
                "origin",
                "HEAD:main",
                ok=False,
            ),
        )
        sibling = self.root / "development worktree"
        self.git(
            self.snowman,
            "worktree",
            "add",
            "-b",
            "codex/HappySnowman/worktree",
            str(sibling),
        )
        self.change(sibling, "worktree.txt")
        self.git(sibling, "push", "-u", "origin", "HEAD")
        self.assertIn("HappySnowman", self.git(sibling, "log", "-1", "--format=%B"))

    def test_setup_refuses_existing_hooks_or_host_change(self):
        output = self.setup_clone(self.ducky, "HappySnowman", ok=False)
        self.assertIn("refusing to silently relabel", output)
        self.git(self.ducky, "config", "core.hooksPath", "custom-hooks")
        self.assertIn(
            "Existing core.hooksPath",
            self.setup_clone(self.ducky, "HappyDucky02", ok=False),
        )
        self.git(self.ducky, "config", "--unset", "core.hooksPath")
        (self.ducky / ".git/hooks/pre-commit").write_text("#!/bin/sh\nexit 0\n")
        self.assertIn(
            "refusing to disable",
            self.setup_clone(self.ducky, "HappyDucky02", ok=False),
        )

    def test_trailer_is_not_duplicated_on_amend(self):
        self.change(self.ducky, "a.txt")
        self.git(self.ducky, "commit", "--amend", "--no-edit")
        message = self.git(self.ducky, "log", "-1", "--format=%B")
        self.assertEqual(message.count("Development-Host:"), 1)

    def test_commit_from_subdirectory(self):
        self.git(
            self.ducky / "scripts", "commit", "--allow-empty", "-m", "Subdirectory"
        )
        self.assertIn("HappyDucky02", self.git(self.ducky, "log", "-1", "--format=%B"))

    def test_main_refresh_failure_blocks_hook(self):
        tip = self.change(self.ducky, "a.txt")
        output = self.run_command(
            self.ducky,
            "sh",
            ".githooks/pre-push",
            "origin",
            str(self.root / "missing.git"),
            input_text=f"HEAD {tip} refs/heads/main {self.base}\n",
            ok=False,
        )
        self.assertIn("Cannot refresh remote main", output)

    def test_refresh_catches_main_newer_than_advertised_oid(self):
        tip = self.change(self.ducky, "a.txt")
        other = self.change(self.snowman, "b.txt")
        self.git(self.snowman, "push", "origin", "HEAD:main")
        output = self.run_command(
            self.ducky,
            "sh",
            ".githooks/pre-push",
            "origin",
            str(self.remote),
            input_text=f"HEAD {tip} refs/heads/main {self.base}\n",
            ok=False,
        )
        self.assertIn("Remote main has changes missing", output)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), other)

    def test_invalid_second_ref_blocks_entire_push(self):
        self.change(self.ducky, "a.txt")
        self.git(
            self.ducky,
            "push",
            "origin",
            "HEAD:main",
            "HEAD:codex/HappySnowman/wrong",
            ok=False,
        )
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), self.base)


if __name__ == "__main__":
    unittest.main(verbosity=2)
