from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class LoginPageTests(TestCase):
    def test_login_page_renders_with_email_field(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')
        self.assertContains(response, 'E-mail')
        self.assertNotContains(response, 'nxl-navigation')


class LoginAuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='auth@example.com', password='strong-pass-123'
        )

    def test_valid_credentials_redirect_to_home(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'auth@example.com', 'password': 'strong-pass-123'},
        )
        self.assertRedirects(response, reverse('home'))

    def test_invalid_credentials_do_not_authenticate(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'auth@example.com', 'password': 'wrong-pass-456'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)


class LoginFormRepopulationTests(TestCase):
    def test_email_is_repopulated_after_failed_login(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'typed@example.com', 'password': 'wrong-pass-456'},
        )
        self.assertContains(response, 'value="typed@example.com"')


class LoginNextRedirectTests(TestCase):
    def test_next_is_respected(self):
        User.objects.create_user(
            email='next@example.com', password='strong-pass-123'
        )
        url = f"{reverse('login')}?next=/trip/new/"
        response = self.client.post(
            url,
            {'username': 'next@example.com', 'password': 'strong-pass-123'},
        )
        self.assertRedirects(response, '/trip/new/', fetch_redirect_response=False)


class LogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='bye@example.com', password='strong-pass-123'
        )
        self.client.force_login(self.user)

    def test_post_logs_out_and_redirects_to_login(self):
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 405)
