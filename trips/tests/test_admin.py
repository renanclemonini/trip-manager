from datetime import datetime

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import make_aware

from trips.models import Trip, TripType


def create_trip(**overrides):
    defaults = {
        'origin_city': 'São Paulo',
        'origin_state': 'SP',
        'destination_city': 'Curitiba',
        'destination_state': 'PR',
        'trip_type': TripType.CAR,
        'start_datetime': make_aware(datetime(2026, 11, 20)),
    }
    defaults.update(overrides)
    return Trip.objects.create(**defaults)


class TripAdminRegistrationTests(TestCase):
    """RF32: Trip registrado no admin para edição de viagens existentes."""

    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            email='admin@example.com', password='strong-pass-123'
        )
        self.client.force_login(self.superuser)

    def test_trip_registered_in_admin(self):
        self.assertIn(Trip, admin.site._registry)

    def test_changelist_ok_for_superuser(self):
        response = self.client.get(reverse('admin:trips_trip_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'delete_selected')

    def test_change_form_ok_for_superuser(self):
        trip = create_trip()
        response = self.client.get(
            reverse('admin:trips_trip_change', args=[trip.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_change_saves_local_time_as_utc(self):
        trip = create_trip(
            start_datetime=make_aware(datetime(2026, 11, 20)),
        )
        response = self.client.post(
            reverse('admin:trips_trip_change', args=[trip.pk]),
            {
                'origin_city': 'São Paulo',
                'origin_state': 'SP',
                'destination_city': 'Curitiba',
                'destination_state': 'PR',
                'trip_type': TripType.CAR,
                'start_datetime_0': '20/11/2026',
                'start_datetime_1': '08:30:00',
            },
        )
        errors = (
            response.context['adminform'].form.errors
            if response.context and 'adminform' in response.context
            else None
        )
        self.assertEqual(response.status_code, 302, errors)
        trip.refresh_from_db()
        self.assertEqual(
            trip.start_datetime,
            make_aware(datetime(2026, 11, 20, 8, 30)),
        )

    def test_add_view_forbidden(self):
        response = self.client.get(reverse('admin:trips_trip_add'))
        self.assertEqual(response.status_code, 403)

    def test_delete_view_forbidden(self):
        trip = create_trip()
        response = self.client.get(
            reverse('admin:trips_trip_delete', args=[trip.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_delete_selected_post_does_not_delete(self):
        trip = create_trip()
        response = self.client.post(
            reverse('admin:trips_trip_changelist'),
            {
                'action': 'delete_selected',
                '_selected_action': [trip.pk],
                'post': 'yes',
            },
        )
        self.assertTrue(Trip.objects.filter(pk=trip.pk).exists())
        self.assertNotContains(
            response, 'Tem certeza de que deseja remover'
        )
