from django.contrib.staticfiles import finders
from django.test import SimpleTestCase

VENDOR_ASSETS = [
    'vendor/duralux/css/bootstrap.min.css',
    'vendor/duralux/css/vendors.min.css',
    'vendor/duralux/css/theme.min.css',
    'vendor/duralux/js/vendors.min.js',
    'vendor/duralux/js/common-init.min.js',
    'vendor/duralux/images/favicon.ico',
    'vendor/apexcharts.min.js',
]


class VendorAssetsTests(SimpleTestCase):
    def test_vendor_assets_are_found_by_staticfiles(self):
        for asset in VENDOR_ASSETS:
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))


class ProjectAssetsTests(SimpleTestCase):
    def test_project_assets_are_found_by_staticfiles(self):
        for asset in [
            'js/form_masks.js',
            'js/ibge_city_autocomplete.js',
            'js/offline_db.js',
            'js/sync_client.js',
            'trips/js/dashboard_charts.js',
            'reports/js/report_download.js',
        ]:
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))
