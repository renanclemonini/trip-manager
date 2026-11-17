import os
import subprocess
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = BASE_DIR / 'scripts'
DEV_UP_LINK = BASE_DIR / 'dev-up'
DEV_DOWN_LINK = BASE_DIR / 'dev-down'
DEV_UP_SCRIPT = SCRIPTS_DIR / 'dev-up.sh'
DEV_DOWN_SCRIPT = SCRIPTS_DIR / 'dev-down.sh'


class DevScriptsStructureTests(SimpleTestCase):
    def test_root_shortcuts_are_relative_symlinks_to_scripts(self):
        self.assertTrue(DEV_UP_LINK.is_symlink())
        self.assertEqual(os.readlink(DEV_UP_LINK), 'scripts/dev-up.sh')
        self.assertTrue(DEV_DOWN_LINK.is_symlink())
        self.assertEqual(os.readlink(DEV_DOWN_LINK), 'scripts/dev-down.sh')

    def test_scripts_have_execute_bit(self):
        for script in [DEV_UP_SCRIPT, DEV_DOWN_SCRIPT]:
            with self.subTest(script=script):
                self.assertTrue(os.access(script, os.X_OK))

    def test_scripts_pass_bash_syntax_check(self):
        for script in [DEV_UP_SCRIPT, DEV_DOWN_SCRIPT]:
            with self.subTest(script=script):
                result = subprocess.run(
                    ['bash', '-n', str(script)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


class DevScriptsBehaviorTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.stub_dir = Path(tempfile.mkdtemp())
        self.log_path = self.stub_dir / 'docker.log'
        stub = self.stub_dir / 'docker'
        stub.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s|%s\\n' \"$PWD\" \"$*\" >> \"$DOCKER_STUB_LOG\"\n"
        )
        stub.chmod(0o755)

    def run_dev_script(self, link, args):
        env = {
            **os.environ,
            'PATH': f'{self.stub_dir}{os.pathsep}{os.environ["PATH"]}',
            'DOCKER_STUB_LOG': str(self.log_path),
        }
        return subprocess.run(
            [str(link), *args],
            capture_output=True,
            text=True,
            env=env,
            cwd=tempfile.gettempdir(),
        )

    def logged_calls(self):
        if not self.log_path.exists():
            return []
        return [line.split('|', 1) for line in
                self.log_path.read_text().strip().splitlines()]

    def test_dev_up_runs_compose_up_detached_from_project_root(self):
        result = self.run_dev_script(DEV_UP_LINK, [])
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.logged_calls()
        self.assertEqual(len(calls), 1)
        pwd, args = calls[0]
        self.assertEqual(pwd, str(BASE_DIR))
        self.assertEqual(args, 'compose up -d')

    def test_dev_up_forwards_extra_arguments(self):
        result = self.run_dev_script(DEV_UP_LINK, ['--build'])
        self.assertEqual(result.returncode, 0, result.stderr)
        _, args = self.logged_calls()[0]
        self.assertEqual(args, 'compose up -d --build')

    def test_dev_down_runs_compose_down(self):
        result = self.run_dev_script(DEV_DOWN_LINK, [])
        self.assertEqual(result.returncode, 0, result.stderr)
        _, args = self.logged_calls()[0]
        self.assertEqual(args, 'compose down')

    def test_dev_down_forwards_volume_flag(self):
        result = self.run_dev_script(DEV_DOWN_LINK, ['-v'])
        self.assertEqual(result.returncode, 0, result.stderr)
        _, args = self.logged_calls()[0]
        self.assertEqual(args, 'compose down -v')
