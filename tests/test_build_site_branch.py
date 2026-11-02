"""The generated site is kept on the `site` branch as current + previous only."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/site_branch.sh'


def git(*args, cwd):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class SiteBranchTests(unittest.TestCase):
    def test_keeps_only_current_and_previous_version_and_never_touches_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            remote = tmp / 'remote.git'
            git('init', '-q', '--bare', str(remote), cwd=tmp)
            work = tmp / 'work'
            git('init', '-q', str(work), cwd=tmp)
            git('remote', 'add', 'origin', str(remote), cwd=work)
            git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'code', cwd=work)
            git('push', '-q', 'origin', 'HEAD:refs/heads/main', cwd=work)

            def run(*args):
                return subprocess.run([str(SCRIPT), *args], cwd=work, check=True, capture_output=True, text=True).stdout

            self.assertIn('No site branch yet', run('fetch', str(tmp / 'prev0')))
            for version in range(1, 5):
                previous, out = tmp / f'prev{version}', tmp / f'out{version}'
                run('fetch', str(previous))
                (out / f'2026-11-0{version}').mkdir(parents=True)
                for folder in previous.glob('2026-*'):       # archive carries forward
                    (out / folder.name).mkdir(exist_ok=True)
                    (out / folder.name / 'index.html').write_text((folder / 'index.html').read_text())
                (out / f'2026-11-0{version}' / 'index.html').write_text(f'day {version}')
                (out / 'index.html').write_text(f'version {version}')
                run('save', str(out))

            log = git('--git-dir', str(remote), 'log', '--format=%s', 'site', cwd=tmp).splitlines()
            self.assertEqual(len(log), 2)
            self.assertEqual(git('--git-dir', str(remote), 'show', 'site:index.html', cwd=tmp), 'version 4')
            self.assertEqual(git('--git-dir', str(remote), 'show', 'site~1:index.html', cwd=tmp), 'version 3')
            files = git('--git-dir', str(remote), 'ls-tree', '-r', '--name-only', 'site', cwd=tmp).splitlines()
            self.assertEqual(sorted(files), ['2026-11-01/index.html', '2026-11-02/index.html',
                                             '2026-11-03/index.html', '2026-11-04/index.html', 'index.html'])
            self.assertEqual(git('--git-dir', str(remote), 'log', '--format=%s', 'main', cwd=tmp), 'code')

    def test_workflow_publishes_from_site_branch_without_committing_to_main(self):
        workflow = (ROOT / '.github/workflows/daily-edition.yml').read_text()
        self.assertIn('scripts/site_branch.sh fetch', workflow)
        self.assertIn('scripts/site_branch.sh save', workflow)
        self.assertIn('--history-root "$HISTORY"', workflow)
        self.assertIn('path: ${{ runner.temp }}/news-edition', workflow)
        self.assertNotIn('HEAD:main', workflow)
        self.assertNotIn('git commit', workflow)


if __name__ == '__main__':
    unittest.main()
