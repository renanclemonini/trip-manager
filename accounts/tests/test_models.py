from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User


class AuthUserModelSettingTests(TestCase):
    def test_auth_user_model_points_to_accounts_user(self):
        self.assertEqual(settings.AUTH_USER_MODEL, 'accounts.User')
        self.assertIs(get_user_model(), User)


class UsernameFieldRemovedTests(TestCase):
    def test_user_has_no_username_field(self):
        with self.assertRaises(FieldDoesNotExist):
            User._meta.get_field('username')


class EmailIsUsernameFieldTests(TestCase):
    def test_email_is_the_username_field(self):
        self.assertEqual(User.USERNAME_FIELD, 'email')
        self.assertEqual(User.REQUIRED_FIELDS, [])


class EmailUniquenessTests(TestCase):
    def test_duplicated_email_raises_integrity_error(self):
        User.objects.create_user(
            email='dup@example.com', password='strong-pass-123'
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                email='dup@example.com', password='other-pass-456'
            )


class StrReturnsEmailTests(TestCase):
    def test_str_returns_email(self):
        user = User.objects.create_user(
            email='str@example.com', password='strong-pass-123'
        )
        self.assertEqual(str(user), 'str@example.com')


class TimestampedFieldsTests(TestCase):
    def test_created_at_and_updated_at_are_populated(self):
        user = User.objects.create_user(
            email='stamp@example.com', password='strong-pass-123'
        )
        self.assertIsNotNone(user.created_at)
        self.assertIsNotNone(user.updated_at)

    def test_updated_at_changes_on_second_save(self):
        user = User.objects.create_user(
            email='stamp2@example.com', password='strong-pass-123'
        )
        first_updated_at = user.updated_at
        user.first_name = 'Renan'
        user.save()
        user.refresh_from_db()
        self.assertGreater(user.updated_at, first_updated_at)
