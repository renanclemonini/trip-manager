from datetime import date

from django.test import TestCase

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
