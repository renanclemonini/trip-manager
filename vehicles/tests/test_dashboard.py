from datetime import date, datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.utils.timezone import make_aware

from accounts.models import User
from trips.models import Trip, TripType
from vehicles import services
from vehicles.models import BusTrip, FlightTrip, Refueling, Vehicle, VehicleType
from vehicles.models import TripVehicle

REFUELING_DATETIME = make_aware(datetime(2026, 10, 2, 8, 0))


def create_user(email='dashboard-vehicles@example.com'):
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


def create_refueling(trip, total_mileage, liters, amount_spent):
    return Refueling.objects.create(
        trip=trip,
        city='Campinas',
        state='SP',
        liters=Decimal(liters),
        amount_spent=Decimal(amount_spent),
        total_mileage=total_mileage,
        datetime=REFUELING_DATETIME,
    )


class RefuelingAggregatesTests(TestCase):
    def test_empty_trip_returns_none_values(self):
        trip = create_trip(create_user())
        aggregates = services.get_refueling_aggregates(trip)
        self.assertIsNone(aggregates['total_distance'])
        self.assertIsNone(aggregates['total_liters'])
        self.assertIsNone(aggregates['total_amount'])
        self.assertIsNone(aggregates['average_km_per_liter'])
        self.assertIsNone(aggregates['average_cost_per_km'])

    def test_totals_and_averages(self):
        trip = create_trip(create_user(), initial_mileage=1000)
        create_refueling(trip, 1500, '30.00', '150.00')
        create_refueling(trip, 2000, '40.00', '200.00')
        aggregates = services.get_refueling_aggregates(trip)
        self.assertEqual(aggregates['total_distance'], 1000)
        self.assertEqual(aggregates['total_liters'], Decimal('70.00'))
        self.assertEqual(aggregates['total_amount'], Decimal('350.00'))
        self.assertEqual(
            aggregates['average_km_per_liter'], Decimal('14.29')
        )
        self.assertEqual(
            aggregates['average_cost_per_km'], Decimal('0.35')
        )

    def test_without_trip_vehicle_distance_is_none(self):
        trip = create_trip(create_user(), with_vehicle=False)
        create_refueling(trip, 1500, '30.00', '150.00')
        aggregates = services.get_refueling_aggregates(trip)
        self.assertIsNone(aggregates['total_distance'])
        self.assertIsNone(aggregates['average_km_per_liter'])


class RefuelingTotalTests(TestCase):
    def test_empty_trip_returns_zero(self):
        trip = create_trip(create_user())
        self.assertEqual(
            services.get_refueling_total(trip), Decimal('0.00')
        )

    def test_sums_amount_spent(self):
        trip = create_trip(create_user())
        create_refueling(trip, 1500, '30.00', '150.00')
        create_refueling(trip, 2000, '40.00', '200.00')
        self.assertEqual(
            services.get_refueling_total(trip), Decimal('350.00')
        )


class TransportTotalTests(TestCase):
    def test_car_trip_has_no_transport_total(self):
        trip = create_trip(create_user())
        self.assertEqual(
            services.get_transport_total(trip), Decimal('0.00')
        )

    def test_plane_trip_uses_ticket_price(self):
        trip = create_trip(create_user(), TripType.PLANE)
        FlightTrip.objects.create(
            trip=trip,
            airline='LATAM',
            ticket_price=Decimal('1234.56'),
            departure_datetime='2026-11-01T10:30:00-03:00',
        )
        self.assertEqual(
            services.get_transport_total(trip), Decimal('1234.56')
        )

    def test_plane_trip_without_flight_data_returns_zero(self):
        trip = create_trip(create_user(), TripType.PLANE)
        self.assertEqual(
            services.get_transport_total(trip), Decimal('0.00')
        )

    def test_bus_trip_uses_amount_paid(self):
        trip = create_trip(create_user(), TripType.BUS)
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.BUS, brand='Cometa', model='Scania'
        )
        BusTrip.objects.create(
            trip=trip,
            vehicle=vehicle,
            company='Viação Cometa',
            amount_paid=Decimal('150.50'),
            start_date=date(2026, 11, 1),
        )
        self.assertEqual(
            services.get_transport_total(trip), Decimal('150.50')
        )
