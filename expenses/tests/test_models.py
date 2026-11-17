import uuid
from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase
from django.utils.timezone import make_aware

from accounts.models import User
from expenses.models import Lodging, Meal, Sightseeing
from trips.models import Trip, TripType

CHECK_IN = make_aware(datetime(2026, 10, 2, 14, 0))
CHECK_OUT = make_aware(datetime(2026, 10, 5, 11, 0))
MEAL_DATETIME = make_aware(datetime(2026, 10, 2, 12, 30))


def create_user(email='expenses@example.com'):
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


class MealMetaLabelTests(TestCase):
    def test_verbose_name_follows_prd_section_9_1(self):
        self.assertEqual(Meal._meta.verbose_name, 'Alimentação')
        self.assertEqual(Meal._meta.verbose_name_plural, 'Alimentações')


class ExpenseIdIsUuidTests(TestCase):
    def test_all_expense_models_use_uuid_ids(self):
        trip = create_trip(create_user())
        lodging = Lodging.objects.create(
            trip=trip,
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('450.00'),
            check_in=CHECK_IN,
            check_out=CHECK_OUT,
        )
        meal = Meal.objects.create(
            trip=trip,
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('35.00'),
            datetime=MEAL_DATETIME,
        )
        sightseeing = Sightseeing.objects.create(
            trip=trip, amount_spent=Decimal('80.00')
        )
        for expense in (lodging, meal, sightseeing):
            with self.subTest(model=type(expense).__name__):
                self.assertIsInstance(expense.id, uuid.UUID)


class LodgingNightsTests(TestCase):
    def test_nights_counts_difference_in_days(self):
        lodging = Lodging.objects.create(
            trip=create_trip(create_user()),
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('450.00'),
            check_in=CHECK_IN,
            check_out=CHECK_OUT,
        )
        self.assertEqual(lodging.nights, 3)

    def test_same_day_check_out_has_zero_nights(self):
        lodging = Lodging.objects.create(
            trip=create_trip(create_user('sameday@example.com')),
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('80.00'),
            check_in=CHECK_IN,
            check_out=CHECK_IN,
        )
        self.assertEqual(lodging.nights, 0)


class LodgingDefaultOrderingTests(TestCase):
    def test_newest_check_in_comes_first(self):
        trip = create_trip(create_user())
        earlier = Lodging.objects.create(
            trip=trip,
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('100.00'),
            check_in=make_aware(datetime(2026, 10, 1, 14, 0)),
            check_out=make_aware(datetime(2026, 10, 2, 11, 0)),
        )
        later = Lodging.objects.create(
            trip=trip,
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('200.00'),
            check_in=make_aware(datetime(2026, 10, 4, 14, 0)),
            check_out=make_aware(datetime(2026, 10, 5, 11, 0)),
        )
        self.assertEqual(list(Lodging.objects.all()), [later, earlier])


class MealDefaultOrderingTests(TestCase):
    def test_newest_datetime_comes_first(self):
        trip = create_trip(create_user())
        earlier = Meal.objects.create(
            trip=trip,
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('20.00'),
            datetime=make_aware(datetime(2026, 10, 2, 12, 0)),
        )
        later = Meal.objects.create(
            trip=trip,
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('40.00'),
            datetime=make_aware(datetime(2026, 10, 3, 20, 0)),
        )
        self.assertEqual(list(Meal.objects.all()), [later, earlier])


class SightseeingDefaultOrderingTests(TestCase):
    def test_newest_created_at_comes_first(self):
        trip = create_trip(create_user(), TripType.BUS)
        first = Sightseeing.objects.create(
            trip=trip, amount_spent=Decimal('50.00'), description='Museu'
        )
        second = Sightseeing.objects.create(
            trip=trip, amount_spent=Decimal('70.00'), description='Parque'
        )
        self.assertEqual(list(Sightseeing.objects.all()), [second, first])


class SightseeingDescriptionTests(TestCase):
    def test_description_is_optional(self):
        sightseeing = Sightseeing.objects.create(
            trip=create_trip(create_user(), TripType.BUS),
            amount_spent=Decimal('90.00'),
        )
        self.assertEqual(sightseeing.description, '')
