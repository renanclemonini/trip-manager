from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from django.utils.timezone import make_aware

from accounts.models import User
from expenses import services
from expenses.models import Lodging, Meal, Sightseeing
from trips.models import Trip, TripType

CHECK_IN = make_aware(datetime(2026, 10, 2, 14, 0))
CHECK_OUT = make_aware(datetime(2026, 10, 5, 11, 0))
MEAL_DATETIME = make_aware(datetime(2026, 10, 2, 12, 30))


def create_user(email='expenses-services@example.com'):
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


def lodging_data(**overrides):
    data = {
        'city': 'Curitiba',
        'state': 'PR',
        'amount_spent': Decimal('450.00'),
        'check_in': CHECK_IN,
        'check_out': CHECK_OUT,
    }
    data.update(overrides)
    return data


def meal_data(**overrides):
    data = {
        'city': 'Curitiba',
        'state': 'PR',
        'amount_spent': Decimal('35.00'),
        'datetime': MEAL_DATETIME,
    }
    data.update(overrides)
    return data


def sightseeing_data(**overrides):
    data = {'amount_spent': Decimal('80.00'), 'description': 'Museu'}
    data.update(overrides)
    return data


class LodgingCompatibilityTests(TestCase):
    def test_lodging_is_allowed_on_every_trip_type(self):
        user = create_user()
        for trip_type in (TripType.CAR, TripType.PLANE, TripType.BUS):
            with self.subTest(trip_type=trip_type):
                trip = create_trip(user, trip_type)
                lodging = services.save_lodging(trip, lodging_data())
                self.assertEqual(lodging.trip, trip)
                self.assertTrue(Lodging.objects.filter(pk=lodging.pk).exists())


class MealCompatibilityTests(TestCase):
    def test_meal_is_allowed_on_every_trip_type(self):
        user = create_user()
        for trip_type in (TripType.CAR, TripType.PLANE, TripType.BUS):
            with self.subTest(trip_type=trip_type):
                trip = create_trip(user, trip_type)
                meal = services.save_meal(trip, meal_data())
                self.assertEqual(meal.trip, trip)


class SightseeingCompatibilityTests(TestCase):
    def test_rejects_car_trip(self):
        trip = create_trip(create_user(), TripType.CAR)
        with self.assertRaises(ValidationError):
            services.save_sightseeing(trip, sightseeing_data())

    def test_rejects_plane_trip(self):
        trip = create_trip(create_user(), TripType.PLANE)
        with self.assertRaises(ValidationError):
            services.save_sightseeing(trip, sightseeing_data())

    def test_allows_bus_trip(self):
        trip = create_trip(create_user(), TripType.BUS)
        sightseeing = services.save_sightseeing(trip, sightseeing_data())
        self.assertEqual(sightseeing.trip, trip)
        self.assertEqual(str(sightseeing.amount_spent), '80.00')


class ExpenseUpdateTests(TestCase):
    def test_update_lodging_changes_amount(self):
        trip = create_trip(create_user())
        lodging = services.save_lodging(trip, lodging_data())
        updated = services.save_lodging(
            trip, lodging_data(amount_spent=Decimal('500.00')), instance=lodging
        )
        updated.refresh_from_db()
        self.assertEqual(str(updated.amount_spent), '500.00')

    def test_update_meal_changes_city(self):
        trip = create_trip(create_user())
        meal = services.save_meal(trip, meal_data())
        updated = services.save_meal(
            trip, meal_data(city='Jundiaí'), instance=meal
        )
        updated.refresh_from_db()
        self.assertEqual(updated.city, 'Jundiaí')

    def test_update_sightseeing_changes_description(self):
        trip = create_trip(create_user(), TripType.BUS)
        sightseeing = services.save_sightseeing(trip, sightseeing_data())
        updated = services.save_sightseeing(
            trip,
            sightseeing_data(description='Parque'),
            instance=sightseeing,
        )
        updated.refresh_from_db()
        self.assertEqual(updated.description, 'Parque')


class ExpenseTotalsTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user())

    def test_empty_trip_returns_zero_for_all_categories(self):
        self.assertEqual(
            services.get_lodging_total(self.trip), Decimal('0.00')
        )
        self.assertEqual(services.get_meal_total(self.trip), Decimal('0.00'))
        self.assertEqual(
            services.get_sightseeing_total(self.trip), Decimal('0.00')
        )

    def test_sums_each_category(self):
        Lodging.objects.create(
            trip=self.trip,
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('450.00'),
            check_in=CHECK_IN,
            check_out=CHECK_OUT,
        )
        Meal.objects.create(
            trip=self.trip,
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('35.00'),
            datetime=MEAL_DATETIME,
        )
        Sightseeing.objects.create(
            trip=self.trip, amount_spent=Decimal('80.00')
        )
        self.assertEqual(
            services.get_lodging_total(self.trip), Decimal('450.00')
        )
        self.assertEqual(services.get_meal_total(self.trip), Decimal('35.00'))
        self.assertEqual(
            services.get_sightseeing_total(self.trip), Decimal('80.00')
        )


class MealStatsTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user())

    def _create(self, amount):
        return Meal.objects.create(
            trip=self.trip,
            city='Curitiba',
            state='PR',
            amount_spent=Decimal(amount),
            datetime=MEAL_DATETIME,
        )

    def test_empty_trip_returns_none_values(self):
        stats = services.get_meal_stats(self.trip)
        self.assertIsNone(stats['average_amount'])
        self.assertIsNone(stats['min_amount'])
        self.assertIsNone(stats['max_amount'])

    def test_average_min_and_max(self):
        self._create('11.11')
        self._create('22.23')
        self._create('40.00')
        stats = services.get_meal_stats(self.trip)
        self.assertEqual(stats['average_amount'], Decimal('24.45'))
        self.assertEqual(stats['min_amount'], Decimal('11.11'))
        self.assertEqual(stats['max_amount'], Decimal('40.00'))
