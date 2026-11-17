from django.test import TestCase

from accounts.models import User


class CreateUserPersistsAndHashesPasswordTests(TestCase):
    def test_creates_user_with_hashed_password(self):
        user = User.objects.create_user(
            email='rider@example.com', password='strong-pass-123'
        )
        self.assertEqual(user.email, 'rider@example.com')
        self.assertTrue(user.check_password('strong-pass-123'))
        self.assertNotEqual(user.password, 'strong-pass-123')
        self.assertTrue(User.objects.filter(email='rider@example.com').exists())


class CreateUserRequiresEmailTests(TestCase):
    def test_raises_value_error_without_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='strong-pass-123')


class CreateSuperuserFlagsTests(TestCase):
    def test_superuser_gets_staff_and_superuser_flags(self):
        user = User.objects.create_superuser(
            email='boss@example.com', password='strong-pass-123'
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
