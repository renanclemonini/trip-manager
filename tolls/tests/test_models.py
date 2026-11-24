from datetime import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils.timezone import make_aware

from accounts.models import User
from tolls.models import Toll, TollSource
from trips.models import Trip, TripType


TOLL_DATETIME = make_aware(datetime(2026, 10, 2, 8, 0))


def create_toll(trip, amount_spent='25.00', when=None):
    return Toll.objects.create(
        trip=trip,
        location='Praça ABC',
        amount_spent=Decimal(amount_spent),
        datetime=when or TOLL_DATETIME,
    )


class TollSourceChoicesTests(TestCase):
    def test_choices_cover_manual_and_import(self):
        self.assertEqual(
            [(kind.value, kind.label) for kind in TollSource],
            [('manual', 'Manual'), ('import', 'Importado')],
        )


class TollStrTests(TestCase):
    def test_str_returns_location_and_amount(self):
        user = User.objects.create_user(
            email='toll-str@example.com', password='strong-pass-123'
        )
        trip = Trip.objects.create(
            created_by=user,
            origin_city='São Paulo',
            origin_state='SP',
            destination_city='Curitiba',
            destination_state='PR',
            trip_type=TripType.CAR,
            start_datetime=TOLL_DATETIME,
        )
        toll = create_toll(trip)
        self.assertEqual(str(toll), 'Praça ABC — R$ 25.00')


class TollDefaultsTests(TestCase):
    def test_source_defaults_to_manual(self):
        user = User.objects.create_user(
            email='toll-default@example.com', password='strong-pass-123'
        )
        trip = Trip.objects.create(
            created_by=user,
            origin_city='São Paulo',
            origin_state='SP',
            destination_city='Curitiba',
            destination_state='PR',
            trip_type=TripType.CAR,
            start_datetime=TOLL_DATETIME,
        )
        toll = create_toll(trip)
        self.assertEqual(toll.source, TollSource.MANUAL)
        self.assertIsNone(toll.import_hash)
        self.assertIsNone(toll.import_batch_id)


class TollOrderingTests(TestCase):
    def test_lists_most_recent_first(self):
        user = User.objects.create_user(
            email='toll-order@example.com', password='strong-pass-123'
        )
        trip = Trip.objects.create(
            created_by=user,
            origin_city='São Paulo',
            origin_state='SP',
            destination_city='Curitiba',
            destination_state='PR',
            trip_type=TripType.CAR,
            start_datetime=TOLL_DATETIME,
        )
        earlier = create_toll(
            trip, when=make_aware(datetime(2026, 10, 2, 8, 0))
        )
        later = create_toll(
            trip, when=make_aware(datetime(2026, 10, 2, 9, 0))
        )
        self.assertEqual(list(Toll.objects.filter(trip=trip)), [later, earlier])
