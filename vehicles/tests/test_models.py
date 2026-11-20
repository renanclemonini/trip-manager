from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone
from django.utils.timezone import make_aware

from accounts.models import User
from trips.models import Trip, TripType
from vehicles.models import (
    BusTrip,
    FlightTrip,
    Refueling,
    TripVehicle,
    Vehicle,
    VehicleType,
)

REFUELING_DATETIME = make_aware(datetime(2026, 10, 2, 8, 0))


def create_user(email='vehicles@example.com'):
    return User.objects.create_user(email=email, password='strong-pass-123')


def create_trip(user, trip_type=TripType.CAR):
    return Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=trip_type,
        start_datetime=timezone.now() - timedelta(days=1),
    )


def create_refueling(trip, total_mileage, when=None):
    return Refueling.objects.create(
        trip=trip,
        city='Campinas',
        state='SP',
        liters=Decimal('10.00'),
        amount_spent=Decimal('50.00'),
        total_mileage=total_mileage,
        datetime=when or REFUELING_DATETIME,
    )


class VehicleTypeChoicesTests(TestCase):
    def test_choices_cover_car_and_bus(self):
        self.assertEqual(
            [(kind.value, kind.label) for kind in VehicleType],
            [('car', 'Carro'), ('bus', 'Ônibus')],
        )


class VehicleStrTests(TestCase):
    def test_str_returns_brand_and_model(self):
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        self.assertEqual(str(vehicle), 'Fiat Argo')


class TripVehicleRelationTests(TestCase):
    def test_deleting_vehicle_with_trip_vehicle_is_protected(self):
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        TripVehicle.objects.create(
            trip=create_trip(create_user()), vehicle=vehicle, initial_mileage=1000
        )
        with self.assertRaises(ProtectedError):
            vehicle.delete()


class TripRelationsAreOneToOneTests(TestCase):
    def test_second_trip_vehicle_for_same_trip_is_rejected(self):
        user = create_user()
        trip = create_trip(user)
        first = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        second = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='VW', model='Gol'
        )
        TripVehicle.objects.create(
            trip=trip, vehicle=first, initial_mileage=1000
        )
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError), transaction.atomic():
            TripVehicle.objects.create(
                trip=trip, vehicle=second, initial_mileage=2000
            )


class TripVehicleCurrentMileageTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user())
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        self.trip_vehicle = TripVehicle.objects.create(
            trip=self.trip, vehicle=vehicle, initial_mileage=1000
        )

    def test_without_refuelings_returns_initial_mileage(self):
        self.assertEqual(self.trip_vehicle.current_mileage, 1000)

    def test_returns_highest_mileage_not_last_inserted(self):
        create_refueling(self.trip, 1500)
        create_refueling(self.trip, 1800)
        create_refueling(self.trip, 1200)
        self.assertEqual(self.trip_vehicle.current_mileage, 1800)

    def test_highest_mileage_wins_regardless_of_datetime(self):
        later = make_aware(datetime(2026, 10, 5, 8, 0))
        earlier = make_aware(datetime(2026, 10, 1, 8, 0))
        create_refueling(self.trip, 1200, when=later)
        create_refueling(self.trip, 1500, when=earlier)
        self.assertEqual(self.trip_vehicle.current_mileage, 1500)


class BusTripFieldsTests(TestCase):
    def test_bus_trip_persists_decimal_amount(self):
        user = create_user('bustrip@example.com')
        trip = create_trip(user, TripType.BUS)
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.BUS, brand='Cometa', model='Scania'
        )
        bus_trip = BusTrip.objects.create(
            trip=trip,
            vehicle=vehicle,
            company='Viação Cometa',
            amount_paid='150.50',
            start_date=date(2026, 11, 1),
        )
        bus_trip.refresh_from_db()
        self.assertEqual(str(bus_trip.amount_paid), '150.50')


class FlightTripFieldsTests(TestCase):
    def test_aircraft_model_and_return_are_optional(self):
        user = create_user('flight@example.com')
        trip = create_trip(user, TripType.PLANE)
        flight_trip = FlightTrip.objects.create(
            trip=trip,
            airline='LATAM',
            ticket_price='1234.56',
            departure_datetime='2026-11-01T10:30:00-03:00',
        )
        flight_trip.refresh_from_db()
        self.assertIsNone(flight_trip.aircraft_model)
        self.assertIsNone(flight_trip.return_datetime)
        self.assertEqual(str(flight_trip.ticket_price), '1234.56')
