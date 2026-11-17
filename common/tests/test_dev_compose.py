from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parents[2]
COMPOSE_FILE = BASE_DIR / 'docker-compose.yml'


class DevComposeMigrateContractTests(SimpleTestCase):
    """Contract checks for the dev compose web service startup order.

    The docker-compose.yml is small and stable, so assertions are textual.
    The web service block is isolated first so no match can leak in from
    another service or from a comment elsewhere in the file.
    """

    def setUp(self):
        super().setUp()
        self.compose = COMPOSE_FILE.read_text()

    def web_service_block(self):
        start = self.compose.index('  web:')
        end = self.compose.index('\nvolumes:', start)
        return self.compose[start:end]

    def web_command_line(self):
        block = self.web_service_block()
        for line in block.splitlines():
            if line.strip().startswith('command:'):
                return line
        self.fail('web service has no command')

    def test_web_command_runs_migrate_before_runserver(self):
        command_line = self.web_command_line()
        self.assertIn('python manage.py migrate', command_line)
        migrate_index = command_line.index('python manage.py migrate')
        self.assertIn('runserver', command_line)
        self.assertLess(migrate_index, command_line.index('runserver'))

    def test_migrate_failure_stops_the_server_from_starting(self):
        command_line = self.web_command_line()
        self.assertIn('&&', command_line)
        before, after = command_line.split('&&', 1)
        self.assertTrue(before.strip().endswith('migrate'))
        self.assertIn('exec', after)
        self.assertIn('runserver', after)

    def test_web_waits_for_a_healthy_database(self):
        self.assertIn('condition: service_healthy', self.web_service_block())
