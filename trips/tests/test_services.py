from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from django.utils.timezone import make_aware

from accounts.models import User
from expenses.models import Lodging, Meal, Sightseeing
from trips import services
from trips.forms import TripForm
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
CHECK_IN = make_aware(datetime(2026, 10, 2, 14, 0))
CHECK_OUT = make_aware(datetime(2026, 10, 5, 11, 0))
MEAL_DATETIME = make_aware(datetime(2026, 10, 2, 12, 30))


class GetTripPostCreatePathTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='service@example.com', password='strong-pass-123'
        )

    def _create_trip(self, trip_type):
        return Trip.objects.create(
            created_by=self.user,
            origin_city='São Paulo',
            origin_state='SP',
            destination_city='Curitiba',
            destination_state='PR',
            trip_type=trip_type,
            start_datetime=timezone.now() - timedelta(days=1),
        )

    def test_car_trip_redirects_to_vehicle_registration(self):
        trip = self._create_trip(TripType.CAR)
        self.assertEqual(
            services.get_trip_post_create_path(trip),
            f'/trip/{trip.pk}/vehicle/new/',
        )

    def test_bus_trip_redirects_to_bus_registration(self):
        trip = self._create_trip(TripType.BUS)
        self.assertEqual(
            services.get_trip_post_create_path(trip),
            f'/trip/{trip.pk}/bus/new/',
        )

    def test_plane_trip_redirects_to_flight_registration(self):
        trip = self._create_trip(TripType.PLANE)
        self.assertEqual(
            services.get_trip_post_create_path(trip),
            f'/trip/{trip.pk}/flight/new/',
        )


class SaveTripAssignsCreatedByTests(TestCase):
    def test_save_trip_assigns_created_by_and_persists(self):
        user = User.objects.create_user(
            email='save-trip@example.com', password='strong-pass-123'
        )
        form = TripForm(data={
            'origin_city': 'São Paulo',
            'origin_state': 'SP',
            'destination_city': 'Curitiba',
            'destination_state': 'PR',
            'trip_type': TripType.CAR,
            'start_datetime': '2026-10-01T10:00',
        })
        self.assertTrue(form.is_valid(), form.errors)
        trip = services.save_trip(form=form, created_by=user)
        self.assertEqual(trip.created_by, user)
        self.assertTrue(
            Trip.objects.filter(pk=trip.pk, created_by=user).exists()
        )


def create_user(email='dashboard-trips@example.com'):
    return User.objects.create_user(email=email, password='strong-pass-123')


def create_trip(user, trip_type=TripType.CAR, initial_mileage=1000):
    trip = Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=trip_type,
        start_datetime=timezone.now() - timedelta(days=1),
    )
    if trip_type == TripType.CAR:
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        TripVehicle.objects.create(
            trip=trip, vehicle=vehicle, initial_mileage=initial_mileage
        )
    return trip


def fill_car_data(trip):
    Refueling.objects.create(
        trip=trip,
        city='Campinas',
        state='SP',
        liters=Decimal('30.00'),
        amount_spent=Decimal('150.00'),
        total_mileage=1500,
        datetime=REFUELING_DATETIME,
    )
    Refueling.objects.create(
        trip=trip,
        city='Curitiba',
        state='PR',
        liters=Decimal('40.00'),
        amount_spent=Decimal('200.00'),
        total_mileage=2000,
        datetime=REFUELING_DATETIME,
    )


def fill_common_expenses(trip):
    Lodging.objects.create(
        trip=trip,
        city='Curitiba',
        state='PR',
        amount_spent=Decimal('450.00'),
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
    )
    Meal.objects.create(
        trip=trip,
        city='Curitiba',
        state='PR',
        amount_spent=Decimal('35.00'),
        datetime=MEAL_DATETIME,
    )


def fill_flight(trip, ticket_price=Decimal('1234.56')):
    FlightTrip.objects.create(
        trip=trip,
        airline='LATAM',
        ticket_price=ticket_price,
        departure_datetime=REFUELING_DATETIME,
    )


def fill_bus(trip, amount_paid=Decimal('150.50')):
    vehicle = Vehicle.objects.create(
        vehicle_type=VehicleType.BUS, brand='Cometa', model='Scania'
    )
    BusTrip.objects.create(
        trip=trip,
        vehicle=vehicle,
        company='Viação Cometa',
        amount_paid=amount_paid,
        start_date=date(2026, 11, 1),
    )
    Sightseeing.objects.create(
        trip=trip, amount_spent=Decimal('80.00'), description='Elevador'
    )


class FinishTripServiceTests(TestCase):
    def setUp(self):
        self.user = create_user('finish-service@example.com')
        self.trip = create_trip(self.user)

    def test_finish_sets_end_datetime_and_final_mileage(self):
        end_datetime = timezone.now()
        trip_updated_at = self.trip.updated_at
        result = services.finish_trip(
            trip=self.trip,
            end_datetime=end_datetime,
            final_mileage=2100,
        )
        self.assertTrue(result)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.end_datetime, end_datetime)
        self.assertGreater(self.trip.updated_at, trip_updated_at)
        trip_vehicle = self.trip.tripvehicle
        trip_vehicle.refresh_from_db()
        self.assertEqual(trip_vehicle.final_mileage, 2100)

    def test_finish_is_rejected_when_already_finished(self):
        finished_at = timezone.now()
        self.trip.end_datetime = finished_at
        self.trip.save()
        trip_vehicle = self.trip.tripvehicle
        trip_vehicle.final_mileage = 1800
        trip_vehicle.save()
        result = services.finish_trip(
            trip=self.trip,
            end_datetime=timezone.now() + timedelta(days=1),
            final_mileage=2100,
        )
        self.assertFalse(result)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.end_datetime, finished_at)
        trip_vehicle.refresh_from_db()
        self.assertEqual(trip_vehicle.final_mileage, 1800)

    def test_finish_is_rejected_for_non_car_trip(self):
        bus_trip = create_trip(
            create_user('finish-service-bus@example.com'), TripType.BUS
        )
        result = services.finish_trip(
            trip=bus_trip,
            end_datetime=timezone.now(),
            final_mileage=2100,
        )
        self.assertFalse(result)
        bus_trip.refresh_from_db()
        self.assertIsNone(bus_trip.end_datetime)

    def test_finish_without_trip_vehicle_rolls_back(self):
        trip = Trip.objects.create(
            created_by=self.user,
            origin_city='São Paulo',
            origin_state='SP',
            destination_city='Curitiba',
            destination_state='PR',
            trip_type=TripType.CAR,
            start_datetime=timezone.now() - timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            services.finish_trip(
                trip=trip,
                end_datetime=timezone.now(),
                final_mileage=2100,
            )
        trip.refresh_from_db()
        self.assertIsNone(trip.end_datetime)


class TripDashboardCarTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user())
        fill_car_data(self.trip)
        fill_common_expenses(self.trip)

    def test_categories_exclude_transport(self):
        dashboard = services.get_trip_dashboard(self.trip)
        keys = [category['key'] for category in dashboard['categories']]
        self.assertEqual(keys, ['refueling', 'lodging', 'meal'])
        labels = [category['label'] for category in dashboard['categories']]
        self.assertEqual(
            labels, ['Abastecimento', 'Hospedagem', 'Alimentação']
        )

    def test_grand_total_sums_categories(self):
        dashboard = services.get_trip_dashboard(self.trip)
        self.assertEqual(dashboard['grand_total'], Decimal('835.00'))

    def test_refueling_aggregates_and_stats_are_included(self):
        dashboard = services.get_trip_dashboard(self.trip)
        self.assertEqual(
            dashboard['refueling']['total_distance'], 1000
        )
        self.assertEqual(
            dashboard['refueling']['average_km_per_liter'],
            Decimal('14.29'),
        )
        self.assertEqual(
            dashboard['refueling']['weighted_average_price'],
            Decimal('5.00'),
        )

    def test_meal_stats_are_included(self):
        dashboard = services.get_trip_dashboard(self.trip)
        self.assertEqual(
            dashboard['meal_stats']['average_amount'], Decimal('35.00')
        )


class TripDashboardPlaneTests(TestCase):
    def setUp(self):
        self.trip = create_trip(
            create_user('plane-dashboard@example.com'), TripType.PLANE
        )
        fill_flight(self.trip)
        fill_common_expenses(self.trip)

    def test_categories_include_transport_and_exclude_refueling(self):
        dashboard = services.get_trip_dashboard(self.trip)
        keys = [category['key'] for category in dashboard['categories']]
        self.assertEqual(keys, ['transport', 'lodging', 'meal'])
        self.assertIsNone(dashboard['refueling'])

    def test_grand_total_includes_ticket(self):
        dashboard = services.get_trip_dashboard(self.trip)
        self.assertEqual(dashboard['grand_total'], Decimal('1719.56'))


class TripDashboardBusTests(TestCase):
    def setUp(self):
        self.trip = create_trip(
            create_user('bus-dashboard@example.com'), TripType.BUS
        )
        fill_bus(self.trip)
        fill_common_expenses(self.trip)

    def test_categories_include_transport_and_sightseeing(self):
        dashboard = services.get_trip_dashboard(self.trip)
        keys = [category['key'] for category in dashboard['categories']]
        self.assertEqual(
            keys, ['transport', 'lodging', 'meal', 'sightseeing']
        )

    def test_grand_total_sums_all_categories(self):
        dashboard = services.get_trip_dashboard(self.trip)
        self.assertEqual(dashboard['grand_total'], Decimal('715.50'))


class TripDashboardEmptyTests(TestCase):
    def test_empty_car_trip_has_zero_totals(self):
        dashboard = services.get_trip_dashboard(
            create_trip(create_user('empty-dashboard@example.com'))
        )
        self.assertEqual(dashboard['grand_total'], Decimal('0.00'))
        totals = [
            category['total'] for category in dashboard['categories']
        ]
        self.assertEqual(totals, [Decimal('0.00')] * 3)
        self.assertEqual(
            dashboard['chart_data']['categories']['series'], [0.0, 0.0, 0.0]
        )


class TripDashboardChartDataTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user('charts@example.com'))
        fill_car_data(self.trip)
        fill_common_expenses(self.trip)

    def test_category_chart_matches_categories(self):
        dashboard = services.get_trip_dashboard(self.trip)
        chart = dashboard['chart_data']['categories']
        self.assertEqual(
            chart['labels'], ['Abastecimento', 'Hospedagem', 'Alimentação']
        )
        self.assertEqual(chart['series'], [350.0, 450.0, 35.0])

    def test_consumption_chart_lists_km_per_liter_by_odometer(self):
        dashboard = services.get_trip_dashboard(self.trip)
        chart = dashboard['chart_data']['consumption']
        self.assertEqual(chart['series'], [16.67, 12.5])
        self.assertEqual(chart['labels'], ['1500 km', '2000 km'])

    def test_plane_trip_has_no_consumption_chart(self):
        trip = create_trip(
            create_user('plane-charts@example.com'), TripType.PLANE
        )
        fill_flight(trip)
        dashboard = services.get_trip_dashboard(trip)
        self.assertIsNone(dashboard['chart_data']['consumption'])
