from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from django.utils.timezone import make_aware

from accounts.models import User
from trips.models import Trip, TripType
from vehicles import services
from vehicles.models import Refueling, TripVehicle, Vehicle, VehicleType

REFUELING_DATETIME = make_aware(datetime(2026, 10, 2, 8, 0))


def create_user(email='refueling-services@example.com'):
    return User.objects.create_user(email=email, password='strong-pass-123')


def create_trip(user, trip_type=TripType.CAR, with_vehicle=True, initial_mileage=1000):
    trip = Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=trip_type,
        start_datetime=timezone.now() - timedelta(days=1),
    )
    if with_vehicle:
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        TripVehicle.objects.create(
            trip=trip, vehicle=vehicle, initial_mileage=initial_mileage
        )
    return trip


def refueling_data(**overrides):
    data = {
        'city': 'Campinas',
        'state': 'SP',
        'liters': Decimal('30.00'),
        'amount_spent': Decimal('150.00'),
        'total_mileage': 1500,
        'datetime': REFUELING_DATETIME,
    }
    data.update(overrides)
    return data


class ValidateRefuelingTests(TestCase):
    def test_rejects_non_car_trip(self):
        trip = create_trip(create_user(), TripType.BUS)
        with self.assertRaises(ValidationError):
            services.validate_refueling(trip, refueling_data())

    def test_rejects_car_trip_without_trip_vehicle(self):
        trip = create_trip(create_user(), with_vehicle=False)
        with self.assertRaises(ValidationError):
            services.validate_refueling(trip, refueling_data())

    def test_rejects_mileage_below_initial_mileage(self):
        trip = create_trip(create_user(), initial_mileage=1000)
        with self.assertRaises(ValidationError) as context:
            services.validate_refueling(
                trip, refueling_data(total_mileage=900)
            )
        self.assertIn('total_mileage', context.exception.error_dict)

    def test_rejects_duplicated_mileage_on_same_trip(self):
        trip = create_trip(create_user())
        Refueling.objects.create(
            trip=trip,
            city='Campinas',
            state='SP',
            liters=Decimal('30.00'),
            amount_spent=Decimal('150.00'),
            total_mileage=1500,
            datetime=REFUELING_DATETIME,
        )
        with self.assertRaises(ValidationError) as context:
            services.validate_refueling(trip, refueling_data(total_mileage=1500))
        self.assertIn('total_mileage', context.exception.error_dict)

    def test_allows_own_instance_on_update(self):
        trip = create_trip(create_user())
        refueling = Refueling.objects.create(
            trip=trip,
            city='Campinas',
            state='SP',
            liters=Decimal('30.00'),
            amount_spent=Decimal('150.00'),
            total_mileage=1500,
            datetime=REFUELING_DATETIME,
        )
        services.validate_refueling(
            trip, refueling_data(total_mileage=1500), instance=refueling
        )

    def test_same_mileage_on_another_trip_is_allowed(self):
        user = create_user()
        first_trip = create_trip(user)
        second_trip = create_trip(user)
        Refueling.objects.create(
            trip=first_trip,
            city='Campinas',
            state='SP',
            liters=Decimal('30.00'),
            amount_spent=Decimal('150.00'),
            total_mileage=1500,
            datetime=REFUELING_DATETIME,
        )
        services.validate_refueling(second_trip, refueling_data(total_mileage=1500))


class RefuelingPersistenceTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user())

    def test_create_refueling_persists(self):
        refueling = services.create_refueling(self.trip, refueling_data())
        self.assertEqual(refueling.trip, self.trip)
        self.assertEqual(refueling.total_mileage, 1500)
        self.assertEqual(str(refueling.liters), '30.00')

    def test_update_refueling_changes_fields(self):
        refueling = services.create_refueling(self.trip, refueling_data())
        updated = services.update_refueling(
            self.trip, refueling, refueling_data(city='Jundiaí', total_mileage=1600)
        )
        updated.refresh_from_db()
        self.assertEqual(updated.city, 'Jundiaí')
        self.assertEqual(updated.total_mileage, 1600)


class RefuelingStatsTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user())

    def _create(self, total_mileage, liters, amount_spent):
        return Refueling.objects.create(
            trip=self.trip,
            city='Campinas',
            state='SP',
            liters=Decimal(liters),
            amount_spent=Decimal(amount_spent),
            total_mileage=total_mileage,
            datetime=REFUELING_DATETIME,
        )

    def test_empty_trip_returns_none_values(self):
        stats = services.get_refueling_stats(self.trip)
        self.assertIsNone(stats['weighted_average_price'])
        self.assertIsNone(stats['min_price'])
        self.assertIsNone(stats['max_price'])

    def test_weighted_average_uses_total_amount_over_total_liters(self):
        self._create(1200, '25.00', '100.00')
        self._create(1800, '50.00', '210.00')
        stats = services.get_refueling_stats(self.trip)
        self.assertEqual(stats['weighted_average_price'], Decimal('4.13'))
        self.assertEqual(stats['min_price'], Decimal('4.00'))
        self.assertEqual(stats['max_price'], Decimal('4.20'))

    def test_zero_liter_entries_do_not_break_price_metrics(self):
        self._create(1200, '0.00', '100.00')
        self._create(1800, '50.00', '200.00')
        stats = services.get_refueling_stats(self.trip)
        self.assertEqual(stats['weighted_average_price'], Decimal('4.00'))
        self.assertEqual(stats['min_price'], Decimal('4.00'))
        self.assertEqual(stats['max_price'], Decimal('4.00'))
