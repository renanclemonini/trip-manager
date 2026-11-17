from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import make_aware

from accounts.models import User
from trips import services as trips_services
from trips.models import Trip, TripType
from vehicles import services
from vehicles.models import BusTrip, FlightTrip, TripVehicle, VehicleType


def create_user(email='services-vehicles@example.com'):
    return User.objects.create_user(email=email, password='strong-pass-123')


def create_trip(user, trip_type=TripType.CAR):
    return Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=trip_type,
        start_date=date(2026, 10, 1),
    )


class CarTransportValidationTests(TestCase):
    def test_rejects_trip_that_is_not_car(self):
        trip = create_trip(create_user(), TripType.BUS)
        with self.assertRaises(ValidationError):
            services.create_car_transport(
                trip,
                {'brand': 'Fiat', 'model': 'Argo', 'initial_mileage': 1000},
            )

    def test_update_rejects_trip_that_is_not_car(self):
        trip = create_trip(create_user(), TripType.PLANE)
        with self.assertRaises(ValidationError):
            services.update_car_transport(
                trip,
                {'brand': 'Fiat', 'model': 'Argo', 'initial_mileage': 1000},
            )


class CarTransportCreationTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user('car-create@example.com'))

    def test_creates_car_vehicle_and_trip_vehicle(self):
        trip_vehicle = services.create_car_transport(
            self.trip,
            {'brand': 'Fiat', 'model': 'Argo', 'initial_mileage': 1000},
        )
        self.assertEqual(trip_vehicle.trip, self.trip)
        self.assertEqual(trip_vehicle.initial_mileage, 1000)
        self.assertEqual(trip_vehicle.vehicle.vehicle_type, VehicleType.CAR)
        self.assertEqual(str(trip_vehicle.vehicle), 'Fiat Argo')

    def test_update_changes_vehicle_and_mileage(self):
        services.create_car_transport(
            self.trip,
            {'brand': 'Fiat', 'model': 'Argo', 'initial_mileage': 1000},
        )
        trip_vehicle = services.update_car_transport(
            self.trip,
            {'brand': 'VW', 'model': 'Gol', 'initial_mileage': 2500},
        )
        trip_vehicle.refresh_from_db()
        self.assertEqual(trip_vehicle.initial_mileage, 2500)
        self.assertEqual(trip_vehicle.vehicle.brand, 'VW')
        self.assertEqual(trip_vehicle.vehicle.model, 'Gol')


class BusTransportValidationTests(TestCase):
    def test_rejects_trip_that_is_not_bus(self):
        trip = create_trip(create_user(), TripType.CAR)
        with self.assertRaises(ValidationError):
            services.create_bus_transport(trip, self._data())

    def _data(self):
        return {
            'brand': 'Cometa',
            'model': 'Scania',
            'company': 'Viação Cometa',
            'amount_paid': Decimal('150.50'),
            'start_date': date(2026, 11, 1),
        }


class BusTransportCreationTests(TestCase):
    def setUp(self):
        self.trip = create_trip(
            create_user('bus-create@example.com'), TripType.BUS
        )

    def _data(self, **overrides):
        data = {
            'brand': 'Cometa',
            'model': 'Scania',
            'company': 'Viação Cometa',
            'amount_paid': Decimal('150.50'),
            'start_date': date(2026, 11, 1),
        }
        data.update(overrides)
        return data

    def test_creates_bus_vehicle_and_bus_trip(self):
        bus_trip = services.create_bus_transport(self.trip, self._data())
        self.assertEqual(bus_trip.trip, self.trip)
        self.assertEqual(bus_trip.vehicle.vehicle_type, VehicleType.BUS)
        self.assertEqual(str(bus_trip.amount_paid), '150.50')
        self.assertEqual(bus_trip.company, 'Viação Cometa')

    def test_update_changes_company_and_amount(self):
        services.create_bus_transport(self.trip, self._data())
        bus_trip = services.update_bus_transport(
            self.trip, self._data(company='Águia Branca', amount_paid=Decimal('200.00'))
        )
        bus_trip.refresh_from_db()
        self.assertEqual(bus_trip.company, 'Águia Branca')
        self.assertEqual(str(bus_trip.amount_paid), '200.00')
        self.assertEqual(bus_trip.vehicle.brand, 'Cometa')


class FlightTransportValidationTests(TestCase):
    def test_rejects_trip_that_is_not_plane(self):
        trip = create_trip(create_user(), TripType.BUS)
        with self.assertRaises(ValidationError):
            services.create_flight_transport(trip, self._data())

    def _data(self):
        return {
            'airline': 'LATAM',
            'aircraft_model': '',
            'ticket_price': Decimal('1234.56'),
            'departure_datetime': make_aware(datetime(2026, 11, 1, 10, 30)),
            'return_datetime': None,
        }


class FlightTransportCreationTests(TestCase):
    def setUp(self):
        self.trip = create_trip(
            create_user('flight-create@example.com'), TripType.PLANE
        )

    def _data(self, **overrides):
        data = {
            'airline': 'LATAM',
            'aircraft_model': '',
            'ticket_price': Decimal('1234.56'),
            'departure_datetime': make_aware(datetime(2026, 11, 1, 10, 30)),
            'return_datetime': None,
        }
        data.update(overrides)
        return data

    def test_creates_flight_trip(self):
        flight_trip = services.create_flight_transport(self.trip, self._data())
        self.assertEqual(flight_trip.trip, self.trip)
        self.assertEqual(flight_trip.airline, 'LATAM')
        self.assertIsNone(flight_trip.aircraft_model)
        self.assertEqual(str(flight_trip.ticket_price), '1234.56')

    def test_update_changes_airline_and_return(self):
        services.create_flight_transport(self.trip, self._data())
        flight_trip = services.update_flight_transport(
            self.trip,
            self._data(
                airline='GOL',
                aircraft_model='Boeing 737',
                return_datetime=make_aware(datetime(2026, 11, 10, 18, 0)),
            ),
        )
        flight_trip.refresh_from_db()
        self.assertEqual(flight_trip.airline, 'GOL')
        self.assertEqual(flight_trip.aircraft_model, 'Boeing 737')
        self.assertEqual(
            flight_trip.return_datetime,
            make_aware(datetime(2026, 11, 10, 18, 0)),
        )


class PostCreatePathUsesReverseTests(TestCase):
    def test_paths_match_real_urls(self):
        user = create_user('paths@example.com')
        cases = [
            (TripType.CAR, 'vehicle_new'),
            (TripType.BUS, 'bus_new'),
            (TripType.PLANE, 'flight_new'),
        ]
        for trip_type, url_name in cases:
            trip = create_trip(user, trip_type)
            with self.subTest(trip_type=trip_type):
                self.assertEqual(
                    trips_services.get_trip_post_create_path(trip),
                    reverse(url_name, kwargs={'trip_id': trip.pk}),
                )
