from django.forms.models import model_to_dict
from django.test import TestCase

from accounts.forms import UserChangeForm, UserCreationForm
from accounts.models import User


class UserCreationFormEmailTests(TestCase):
    def test_valid_form_creates_user_with_hashed_password(self):
        form = UserCreationForm(data={
            'email': 'new@example.com',
            'password1': 'strong-pass-123',
            'password2': 'strong-pass-123',
        })
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.email, 'new@example.com')
        self.assertTrue(user.check_password('strong-pass-123'))

    def test_email_is_required(self):
        form = UserCreationForm(data={
            'email': '',
            'password1': 'strong-pass-123',
            'password2': 'strong-pass-123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class UserChangeFormEmailTests(TestCase):
    def test_form_exposes_email_and_hides_username(self):
        form = UserChangeForm()
        self.assertIn('email', form.fields)
        self.assertNotIn('username', form.fields)

    def test_updates_email(self):
        user = User.objects.create_user(
            email='old@example.com', password='strong-pass-123'
        )
        data = model_to_dict(user)
        data['email'] = 'new@example.com'
        form = UserChangeForm(data=data, instance=user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        user.refresh_from_db()
        self.assertEqual(user.email, 'new@example.com')
