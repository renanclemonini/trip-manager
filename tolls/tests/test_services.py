from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from django.utils.timezone import make_aware

from accounts.models import User
from tolls import services
from tolls.models import Toll
from trips.models import Trip, TripType


TOLL_DATETIME = make_aware(datetime(2026, 10, 2, 8, 0))


def create_trip(trip_type=TripType.CAR):
    user = User.objects.create_user(
        email=f'toll-services-{uuid4().hex[:8]}@example.com',
        password='strong-pass-123',
    )
    return Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=trip_type,
        start_datetime=timezone.now() - timedelta(days=1),
    )


def toll_data(**overrides):
    data = {
        'location': 'Praça ABC',
        'amount_spent': Decimal('25.00'),
        'datetime': TOLL_DATETIME,
    }
    data.update(overrides)
    return data


class TollValidationTests(TestCase):
    def test_bus_trip_is_rejected(self):
        trip = create_trip(TripType.BUS)
        with self.assertRaises(ValidationError):
            services.validate_toll(trip, toll_data())

    def test_plane_trip_is_rejected(self):
        trip = create_trip(TripType.PLANE)
        with self.assertRaises(ValidationError):
            services.validate_toll(trip, toll_data())


class TollCreateUpdateTests(TestCase):
    def setUp(self):
        self.trip = create_trip()

    def test_create_persists_toll(self):
        toll = services.create_toll(self.trip, toll_data())
        self.assertEqual(toll.trip, self.trip)
        self.assertEqual(toll.location, 'Praça ABC')
        self.assertEqual(toll.amount_spent, Decimal('25.00'))
        self.assertEqual(toll.datetime, TOLL_DATETIME)

    def test_create_accepts_car_trip_without_trip_vehicle(self):
        toll = services.create_toll(self.trip, toll_data())
        self.assertEqual(Toll.objects.count(), 1)
        self.assertEqual(toll.source, 'manual')

    def test_create_with_pk_uses_client_generated_uuid(self):
        toll = services.create_toll(
            self.trip,
            toll_data(),
            pk='11111111-1111-4111-8111-111111111111',
        )
        self.assertEqual(str(toll.pk), '11111111-1111-4111-8111-111111111111')

    def test_update_changes_fields(self):
        toll = services.create_toll(self.trip, toll_data())
        updated = services.update_toll(
            self.trip,
            toll,
            toll_data(location='Praça XYZ', amount_spent=Decimal('30.00')),
        )
        self.assertEqual(updated.location, 'Praça XYZ')
        self.assertEqual(updated.amount_spent, Decimal('30.00'))


class TollUpsertTests(TestCase):
    def setUp(self):
        self.trip = create_trip()
        self.other_trip = create_trip()

    def test_upsert_creates_when_missing(self):
        toll = services.upsert_toll(
            self.trip, '11111111-1111-4111-8111-111111111111', toll_data()
        )
        self.assertEqual(Toll.objects.count(), 1)
        self.assertEqual(toll.pk, '11111111-1111-4111-8111-111111111111')

    def test_upsert_updates_existing_without_duplicating(self):
        services.upsert_toll(
            self.trip, '11111111-1111-4111-8111-111111111111', toll_data()
        )
        toll = services.upsert_toll(
            self.trip,
            '11111111-1111-4111-8111-111111111111',
            toll_data(location='Praça XYZ'),
        )
        self.assertEqual(Toll.objects.count(), 1)
        self.assertEqual(toll.location, 'Praça XYZ')

    def test_upsert_rejects_uuid_from_another_trip(self):
        services.upsert_toll(
            self.trip, '11111111-1111-4111-8111-111111111111', toll_data()
        )
        with self.assertRaises(ValidationError):
            services.upsert_toll(
                self.other_trip,
                '11111111-1111-4111-8111-111111111111',
                toll_data(),
            )


class TollTotalTests(TestCase):
    def test_total_is_zero_without_tolls(self):
        self.assertEqual(services.get_toll_total(create_trip()), Decimal('0.00'))

    def test_total_sums_amounts(self):
        trip = create_trip()
        services.create_toll(trip, toll_data())
        services.create_toll(trip, toll_data(amount_spent=Decimal('40.00')))
        self.assertEqual(services.get_toll_total(trip), Decimal('65.00'))
