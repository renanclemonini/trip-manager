import tempfile

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


class CollectStaticVendorReferencesTests(SimpleTestCase):
    def test_collectstatic_tolerates_missing_vendor_source_map(self):
        """theme.min.css references a .map we do not vendor (strict would fail)."""
        with tempfile.TemporaryDirectory() as static_root:
            with override_settings(
                STATIC_ROOT=static_root,
                STORAGES={
                    'default': {
                        'BACKEND': 'django.core.files.storage.FileSystemStorage'
                    },
                    'staticfiles': {
                        'BACKEND': 'common.storage.StaticFilesStorage'
                    },
                },
            ):
                call_command('collectstatic', interactive=False, verbosity=0)
