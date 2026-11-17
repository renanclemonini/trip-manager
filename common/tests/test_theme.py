from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class ThemeCssRulesTests(TestCase):
    def _theme_css(self):
        path = settings.BASE_DIR / 'static' / 'css' / 'theme.css'
        return path.read_text()

    def test_dark_skin_styles_options(self):
        css = self._theme_css()
        self.assertIn('html.app-skin-dark option', css)
        self.assertIn('background-color: #0f172a', css)
        self.assertIn('color: #fff', css)

    def test_theme_css_rules_are_dark_scoped(self):
        css = self._theme_css()
        selectors = []
        depth = 0
        current = []
        for char in css:
            if char == '{':
                if depth == 0:
                    selectors.append(''.join(current).strip())
                depth += 1
            elif char == '}':
                depth = max(0, depth - 1)
                if depth == 0:
                    current = []
            elif depth == 0 and char != '\n':
                current.append(char)
        for selector in selectors:
            self.assertIn('app-skin-dark', selector)


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
