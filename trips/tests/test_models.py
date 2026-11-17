from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from trips.models import Trip, TripType


class TripTypeChoicesTests(TestCase):
    def test_choices_cover_car_plane_bus(self):
        self.assertEqual(
            [(trip_type.value, trip_type.label) for trip_type in TripType],
            [('car', 'Carro'), ('plane', 'Avião'), ('bus', 'Ônibus')],
        )


class TripStrTests(TestCase):
    def test_str_returns_city_state_to_city_state(self):
        user = User.objects.create_user(
            email='str-trip@example.com', password='strong-pass-123'
        )
        trip = Trip.objects.create(
            created_by=user,
            origin_city='São Paulo',
            origin_state='SP',
            destination_city='Curitiba',
            destination_state='PR',
            trip_type=TripType.CAR,
            start_date=date(2026, 10, 1),
        )
        self.assertEqual(str(trip), 'São Paulo/SP → Curitiba/PR')


class TripIsCompletedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='completed@example.com', password='strong-pass-123'
        )
        self.base = {
            'created_by': self.user,
            'origin_city': 'São Paulo',
            'origin_state': 'SP',
            'destination_city': 'Curitiba',
            'destination_state': 'PR',
            'trip_type': TripType.CAR,
            'start_date': timezone.localdate() - timedelta(days=10),
        }

    def _create_trip(self, end_date):
        return Trip.objects.create(**self.base, end_date=end_date)

    def test_null_end_date_is_not_completed(self):
        trip = self._create_trip(None)
        self.assertFalse(trip.is_completed)

    def test_past_end_date_is_completed(self):
        trip = self._create_trip(timezone.localdate() - timedelta(days=1))
        self.assertTrue(trip.is_completed)

    def test_today_end_date_is_completed(self):
        trip = self._create_trip(timezone.localdate())
        self.assertTrue(trip.is_completed)

    def test_future_end_date_is_not_completed(self):
        trip = self._create_trip(timezone.localdate() + timedelta(days=1))
        self.assertFalse(trip.is_completed)


class TripDefaultOrderingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='order@example.com', password='strong-pass-123'
        )

    def _create_trip(self, origin_city, destination_city, start_date):
        return Trip.objects.create(
            created_by=self.user,
            origin_city=origin_city,
            origin_state='SP',
            destination_city=destination_city,
            destination_state='PR',
            trip_type=TripType.CAR,
            start_date=start_date,
        )

    def test_newest_start_date_comes_first(self):
        older = self._create_trip('A', 'B', date(2026, 1, 1))
        newer = self._create_trip('C', 'D', date(2026, 5, 1))
        self.assertEqual(list(Trip.objects.all()), [newer, older])

    def test_same_start_date_breaks_tie_by_newest_id(self):
        first = self._create_trip('A', 'B', date(2026, 5, 1))
        second = self._create_trip('C', 'D', date(2026, 5, 1))
        self.assertEqual(list(Trip.objects.all()), [second, first])
