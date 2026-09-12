"""Exercise main-only safeguards using disposable local Git repositories."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(os.environ.get('WORKFLOW_CANDIDATE', Path(__file__).resolve().parents[1]))


class WorkflowTests(unittest.TestCase):
    def command(self, cwd, *args, ok=True, input_text=None):
        env = os.environ.copy()
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=40, input=input_text)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return (result.stdout + result.stderr).strip()

    def git(self, cwd, *args, **kwargs):
        return self.command(cwd, 'git', *args, **kwargs)

    def setup(self, cwd, *args, **kwargs):
        return self.command(cwd, 'sh', 'scripts/setup-git-workflow.sh', *args, **kwargs)

    def setUp(self):
        parent = REPO / '.tmp'
        parent.mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix='git-workflow-', dir=parent)
        self.root = Path(temp.name).resolve()
        assert self.root.parent == parent.resolve()
        self.addCleanup(temp.cleanup)
        self.remote = self.root / 'origin.git'
        self.dev = self.root / 'development'
        self.upstream = self.root / 'remote-race-fixture'
        self.git(self.root, 'init', '--bare', '--initial-branch=main', str(self.remote))
        self.git(self.root, 'clone', str(self.remote), str(self.dev))
        self.identity(self.dev)
        shutil.copytree(REPO / '.githooks', self.dev / '.githooks')
        (self.dev / 'scripts').mkdir()
        shutil.copy(REPO / 'scripts/setup-git-workflow.sh', self.dev / 'scripts')
        self.git(self.dev, 'add', '.')
        self.git(self.dev, 'commit', '-m', 'Initial workflow')
        self.git(self.dev, 'push', '-u', 'origin', 'main')
        self.base = self.git(self.dev, 'rev-parse', 'HEAD')
        self.git(self.root, 'clone', str(self.remote), str(self.upstream))
        self.identity(self.upstream)
        self.setup(self.dev)

    def identity(self, repo):
        self.git(repo, 'config', 'user.name', 'Workflow test')
        self.git(repo, 'config', 'user.email', 'workflow@example.invalid')

    def change(self, repo, name='change.txt'):
        (repo / name).write_text(name, encoding='utf-8')
        self.git(repo, 'add', name)
        self.git(repo, 'commit', '-m', 'Complete feature')
        return self.git(repo, 'rev-parse', 'HEAD')

    def test_main_commit_and_push_without_host_trailer(self):
        self.git(self.dev, 'config', 'helvetic.host', 'HistoricalHost')
        self.setup(self.dev)
        self.git(self.dev, 'config', '--get', 'helvetic.host', ok=False)
        sha = self.change(self.dev)
        self.assertNotIn('Development-Host:', self.git(self.dev, 'log', '-1', '--format=%B'))
        self.git(self.dev, 'push', 'origin', 'main')
        self.assertEqual(self.git(self.remote, 'rev-parse', 'main'), sha)

    def test_other_branch_and_detached_commits_rejected(self):
        self.git(self.dev, 'switch', '-c', 'historical-task')
        self.git(self.dev, 'commit', '--allow-empty', '-m', 'Wrong branch', ok=False)
        self.git(self.dev, 'switch', '--detach', self.base)
        self.git(self.dev, 'commit', '--allow-empty', '-m', 'Detached', ok=False)

    def test_main_deletion_rejected(self):
        self.git(self.remote, 'config', 'receive.denyDeleteCurrent', 'ignore')
        self.assertIn('Deleting main', self.git(self.dev, 'push', 'origin', ':main', ok=False))
        self.assertEqual(self.git(self.remote, 'rev-parse', 'main'), self.base)

    def test_force_cannot_replace_history(self):
        self.change(self.dev)
        self.git(self.dev, 'push', 'origin', 'main')
        self.git(self.dev, 'push', '--force', 'origin', self.base + ':main', ok=False)

    def test_remote_race_checked_even_with_stale_advertised_sha(self):
        local = self.change(self.dev)
        self.change(self.upstream, 'upstream.txt')
        self.git(self.upstream, 'push', 'origin', 'main')
        result = self.command(self.dev, 'sh', '.githooks/pre-push', 'origin', str(self.remote),
                              input_text=f'refs/heads/main {local} refs/heads/main {self.base}\n', ok=False)
        self.assertIn('missing changes', result)

    def test_unreachable_remote_blocks_publication(self):
        result = self.command(self.dev, 'sh', '.githooks/pre-push', 'origin', str(self.root / 'missing.git'),
                              input_text=f'refs/heads/main {self.base} refs/heads/main {self.base}\n', ok=False)
        self.assertIn('Cannot refresh', result)

    def test_new_tag_allowed_but_replacement_and_deletion_blocked(self):
        self.git(self.dev, 'tag', 'frozen-reference')
        self.git(self.dev, 'push', 'origin', 'refs/tags/frozen-reference')
        self.change(self.dev)
        self.git(self.dev, 'tag', '-f', 'frozen-reference')
        self.git(self.dev, 'push', '--force', 'origin', 'refs/tags/frozen-reference', ok=False)
        self.git(self.dev, 'push', 'origin', ':refs/tags/frozen-reference', ok=False)
        self.assertEqual(self.git(self.remote, 'rev-parse', 'frozen-reference'), self.base)

    def test_other_branch_destination_rejected_atomically(self):
        self.change(self.dev)
        self.git(self.dev, 'push', '--atomic', 'origin', 'main', 'HEAD:historical-task', ok=False)
        self.assertEqual(self.git(self.remote, 'rev-parse', 'main'), self.base)

    def test_production_checkout_guarded(self):
        self.setup(self.dev, '--production')
        self.git(self.dev, 'commit', '--allow-empty', '-m', 'Accidental production edit', ok=False)

    def test_unrelated_hooks_preserved(self):
        self.git(self.dev, 'config', 'core.hooksPath', 'custom-hooks')
        self.setup(self.dev, ok=False)
        self.assertEqual(self.git(self.dev, 'config', 'core.hooksPath'), 'custom-hooks')

    def test_default_existing_hook_preserved(self):
        self.git(self.dev, 'config', '--unset', 'core.hooksPath')
        hook = self.dev / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 1\n', encoding='utf-8')
        self.setup(self.dev, ok=False)
        self.assertIn('exit 1', hook.read_text())

    def test_commit_from_subdirectory(self):
        self.git(self.dev / 'scripts', 'commit', '--allow-empty', '-m', 'Subdirectory feature')


if __name__ == '__main__':
    unittest.main()
