import os
import subprocess
import sys
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

STRONG_SECRET_KEY = (
    'test-only-0123456789abcdefghijklmnopqrstuvwxyz-ABCDEFGHIJKLMNOPQRSTUVWXYZ'
)

DEPLOY_SETTINGS = {
    'DEBUG': False,
    'SECRET_KEY': STRONG_SECRET_KEY,
    'ALLOWED_HOSTS': ['trip.example.com'],
    'CSRF_TRUSTED_ORIGINS': ['https://trip.example.com'],
    'SECURE_SSL_REDIRECT': True,
    'SESSION_COOKIE_SECURE': True,
    'CSRF_COOKIE_SECURE': True,
    'SECURE_HSTS_SECONDS': 31536000,
    'SECURE_HSTS_INCLUDE_SUBDOMAINS': True,
    'SECURE_HSTS_PRELOAD': True,
    'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'),
    'EMAIL_HOST': 'smtp.example.com',
}

PROD_PROBE_CODE = """
import django
django.setup()
from django.conf import settings
print('|'.join([
    str(settings.SECURE_SSL_REDIRECT),
    str(settings.SESSION_COOKIE_SECURE),
    str(settings.CSRF_COOKIE_SECURE),
    str(settings.SECURE_HSTS_SECONDS),
    settings.STORAGES['staticfiles']['BACKEND'],
    ','.join(settings.CSRF_TRUSTED_ORIGINS),
    '|'.join(settings.ALLOWED_HOSTS),
]))
"""


class DeployCheckTests(SimpleTestCase):
    @override_settings(**DEPLOY_SETTINGS)
    def test_deploy_check_has_no_errors_or_warnings(self):
        output = StringIO()
        try:
            call_command('check', deploy=True, stdout=output)
        except Exception as exc:  # SystemCheckError em caso de erro
            self.fail(f'check --deploy falhou: {exc}')
        text = output.getvalue()
        self.assertNotIn('ERRORS', text)
        self.assertNotIn('WARNINGS', text)


class ProdSettingsTests(SimpleTestCase):
    def _run_prod_setup(self, extra_env, code=PROD_PROBE_CODE):
        env = os.environ.copy()
        env.update({
            'DJANGO_SETTINGS_MODULE': 'core.settings.prod',
            'DJANGO_SECRET_KEY': STRONG_SECRET_KEY,
            'DJANGO_ALLOWED_HOSTS': 'trip.example.com',
        })
        env.pop('EMAIL_HOST', None)
        env.update(extra_env)
        return subprocess.run(
            [sys.executable, '-c', code],
            cwd=str(settings.BASE_DIR),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_missing_email_host_fails_fast(self):
        result = self._run_prod_setup({})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('EMAIL_HOST', result.stderr)

    def test_complete_environment_uses_secure_defaults(self):
        result = self._run_prod_setup({
            'EMAIL_HOST': 'smtp.example.com',
            'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://trip.example.com',
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        values = result.stdout.strip().split('|')
        self.assertEqual(values[0], 'True')
        self.assertEqual(values[1], 'True')
        self.assertEqual(values[2], 'True')
        self.assertEqual(values[3], '31536000')
        self.assertEqual(
            values[4], 'common.storage.StaticFilesStorage'
        )
        self.assertEqual(values[5], 'https://trip.example.com')
        self.assertEqual(values[6], 'trip.example.com')

    def test_ssl_redirect_can_be_disabled_by_env(self):
        result = self._run_prod_setup({
            'EMAIL_HOST': 'smtp.example.com',
            'DJANGO_SECURE_SSL_REDIRECT': 'false',
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        values = result.stdout.strip().split('|')
        self.assertEqual(values[0], 'False')
        self.assertEqual(values[1], 'False')
        self.assertEqual(values[2], 'False')
        self.assertEqual(values[3], '0')
