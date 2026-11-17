from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from accounts.admin import UserAdmin
from accounts.forms import UserChangeForm, UserCreationForm
from accounts.models import User


class UserAdminRegistrationTests(TestCase):
    def test_user_registered_with_custom_user_admin(self):
        model_admin = admin.site._registry[User]
        self.assertIsInstance(model_admin, UserAdmin)
        self.assertIs(model_admin.form, UserChangeForm)
        self.assertIs(model_admin.add_form, UserCreationForm)
        self.assertIn('email', model_admin.list_display)


class AdminCreatesUserWithHashedPasswordTests(TestCase):
    def test_admin_add_form_stores_hashed_password(self):
        superuser = User.objects.create_superuser(
            email='admin@example.com', password='strong-pass-123'
        )
        self.client.force_login(superuser)
        response = self.client.post(
            reverse('admin:accounts_user_add'),
            {
                'email': 'created@example.com',
                'password1': 'strong-pass-123',
                'password2': 'strong-pass-123',
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='created@example.com')
        self.assertTrue(user.check_password('strong-pass-123'))
        self.assertNotEqual(user.password, 'strong-pass-123')
