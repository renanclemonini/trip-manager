from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class ThemeMarkupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='theme@example.com', password='strong-pass-123'
        )
        self.client.force_login(self.user)

    def test_home_has_pre_paint_script_before_stylesheets(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode()
        init_pos = content.index('data-theme-init')
        first_css_pos = content.index('rel="stylesheet"')
        self.assertLess(init_pos, first_css_pos)

    def test_home_renders_theme_assets_and_toggle(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'static/css/theme.css')
        self.assertContains(response, 'static/js/theme.js')
        self.assertContains(response, 'data-theme-toggle')
        self.assertContains(response, 'type="button"')
        self.assertContains(response, 'aria-label="Ativar tema escuro"')
        self.assertContains(response, 'title="Ativar tema escuro"')

    def test_html_has_no_dark_skin_by_default(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, '<html lang="pt-br">')


class LoginThemeMarkupTests(TestCase):
    def test_login_renders_theme_toggle(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'data-theme-init')
        self.assertContains(response, 'static/css/theme.css')
        self.assertContains(response, 'data-theme-toggle')
        self.assertContains(response, 'aria-label="Ativar tema escuro"')
        self.assertNotContains(response, 'nxl-navigation')
