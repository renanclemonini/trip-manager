import uuid
from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase
from django.utils.timezone import make_aware

from accounts.models import User
from trips.models import Trip, TripType
from vehicles.models import Refueling, TripVehicle, Vehicle, VehicleType

DEFAULT_DATETIME = make_aware(datetime(2026, 10, 2, 8, 0))


def create_user(email='refueling@example.com'):
    return User.objects.create_user(email=email, password='strong-pass-123')


def create_car_trip(user, initial_mileage=1000, with_vehicle=True):
    trip = Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=TripType.CAR,
        start_date=date(2026, 10, 1),
    )
    if with_vehicle:
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        TripVehicle.objects.create(
            trip=trip, vehicle=vehicle, initial_mileage=initial_mileage
        )
    return trip


def create_refueling(
    trip,
    total_mileage,
    liters='10.00',
    amount_spent='50.00',
    when=None,
):
    return Refueling.objects.create(
        trip=trip,
        city='Campinas',
        state='SP',
        liters=Decimal(liters),
        amount_spent=Decimal(amount_spent),
        total_mileage=total_mileage,
        datetime=when or DEFAULT_DATETIME,
    )


class RefuelingIdIsUuidTests(TestCase):
    def test_id_is_uuid_generated_by_default(self):
        trip = create_car_trip(create_user())
        refueling = create_refueling(trip, 1500)
        self.assertIsInstance(refueling.id, uuid.UUID)


class RefuelingStrTests(TestCase):
    def test_str_returns_city_state_and_mileage(self):
        trip = create_car_trip(create_user())
        refueling = create_refueling(trip, 1500)
        self.assertEqual(str(refueling), 'Campinas/SP — 1500 km')


class RefuelingDefaultOrderingTests(TestCase):
    def test_highest_mileage_comes_first(self):
        trip = create_car_trip(create_user())
        lower = create_refueling(trip, 1200)
        higher = create_refueling(trip, 1800)
        self.assertEqual(list(Refueling.objects.all()), [higher, lower])


class PreviousRefuelingTests(TestCase):
    def setUp(self):
        self.trip = create_car_trip(create_user())

    def test_first_refueling_has_no_previous(self):
        refueling = create_refueling(self.trip, 1500)
        self.assertIsNone(refueling.previous_refueling)

    def test_previous_is_the_nearest_lower_mileage(self):
        first = create_refueling(self.trip, 1200)
        create_refueling(self.trip, 1800)
        middle = create_refueling(self.trip, 1500)
        self.assertEqual(middle.previous_refueling, first)

    def test_sequence_is_defined_by_mileage_not_datetime(self):
        later = make_aware(datetime(2026, 10, 5, 8, 0))
        earlier = make_aware(datetime(2026, 10, 1, 8, 0))
        higher = create_refueling(self.trip, 1500, when=later)
        lower = create_refueling(self.trip, 1200, when=earlier)
        self.assertEqual(higher.previous_refueling, lower)


class PreviousMileageTests(TestCase):
    def test_first_refueling_uses_initial_mileage(self):
        trip = create_car_trip(create_user(), initial_mileage=900)
        refueling = create_refueling(trip, 1500)
        self.assertEqual(refueling.previous_mileage, 900)

    def test_without_trip_vehicle_returns_none(self):
        trip = create_car_trip(create_user(), with_vehicle=False)
        refueling = create_refueling(trip, 1500)
        self.assertIsNone(refueling.previous_mileage)


class DistanceTraveledTests(TestCase):
    def setUp(self):
        self.trip = create_car_trip(create_user(), initial_mileage=1000)

    def test_uses_previous_refueling_when_exists(self):
        create_refueling(self.trip, 1200)
        current = create_refueling(self.trip, 1500)
        self.assertEqual(current.distance_traveled, 300)

    def test_uses_initial_mileage_for_first_refueling(self):
        first = create_refueling(self.trip, 1500)
        self.assertEqual(first.distance_traveled, 500)

    def test_none_without_any_base(self):
        trip = create_car_trip(create_user('nobase@example.com'), with_vehicle=False)
        refueling = create_refueling(trip, 1500)
        self.assertIsNone(refueling.distance_traveled)


class KmPerLiterTests(TestCase):
    def setUp(self):
        self.trip = create_car_trip(create_user(), initial_mileage=1000)

    def test_rounded_to_two_decimals(self):
        refueling = create_refueling(
            self.trip, 1500, liters='30.00', amount_spent='100.00'
        )
        self.assertEqual(refueling.km_per_liter, Decimal('16.67'))

    def test_none_with_zero_liters(self):
        refueling = create_refueling(
            self.trip, 1500, liters='0.00', amount_spent='100.00'
        )
        self.assertIsNone(refueling.km_per_liter)

    def test_none_without_distance(self):
        refueling = create_refueling(self.trip, 1000, liters='30.00')
        self.assertIsNone(refueling.km_per_liter)


class CostPerKmTests(TestCase):
    def setUp(self):
        self.trip = create_car_trip(create_user(), initial_mileage=1000)

    def test_rounded_to_two_decimals(self):
        refueling = create_refueling(
            self.trip, 1500, liters='30.00', amount_spent='150.00'
        )
        self.assertEqual(refueling.cost_per_km, Decimal('0.30'))

    def test_none_without_distance(self):
        refueling = create_refueling(self.trip, 1000, liters='30.00')
        self.assertIsNone(refueling.cost_per_km)
