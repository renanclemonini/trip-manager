from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import make_aware

from expenses.models import Lodging, Meal, Sightseeing
from trips.models import Trip, TripType
from vehicles.models import Refueling, TripVehicle, Vehicle, VehicleType

DATETIME = make_aware(datetime(2026, 10, 2, 8, 0))
CHECK_IN = make_aware(datetime(2026, 10, 2, 14, 0))
CHECK_OUT = make_aware(datetime(2026, 10, 5, 11, 0))


def create_user(email='offline-markup@example.com'):
    return get_user_model().objects.create_user(
        email=email, password='strong-pass-123'
    )


def create_trip(user, trip_type=TripType.CAR):
    trip = Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=trip_type,
        start_date=date(2026, 10, 1),
    )
    if trip_type == TripType.CAR:
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        TripVehicle.objects.create(
            trip=trip, vehicle=vehicle, initial_mileage=1000
        )
    return trip


def create_record(trip, sync_form_type):
    if sync_form_type == 'refueling':
        return Refueling.objects.create(
            trip=trip,
            city='Campinas',
            state='SP',
            liters=Decimal('30.00'),
            amount_spent=Decimal('150.00'),
            total_mileage=1500,
            datetime=DATETIME,
        )
    if sync_form_type == 'lodging':
        return Lodging.objects.create(
            trip=trip,
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('450.00'),
            check_in=CHECK_IN,
            check_out=CHECK_OUT,
        )
    if sync_form_type == 'meal':
        return Meal.objects.create(
            trip=trip,
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('35.00'),
            datetime=DATETIME,
        )
    return Sightseeing.objects.create(
        trip=trip, amount_spent=Decimal('80.00'), description='Museu'
    )


class OfflineSyncMarkupMixin:
    list_url_name = ''
    create_url_name = ''
    edit_url_name = ''
    sync_url_name = ''
    sync_form_type = ''
    trip_type = TripType.CAR

    def setUp(self):
        self.user = create_user(f'{self.sync_form_type}@example.com')
        self.trip = create_trip(self.user, self.trip_type)
        self.client.force_login(self.user)

    def test_list_page_includes_offline_panel_and_scripts(self):
        response = self.client.get(
            reverse(self.list_url_name, args=[self.trip.pk])
        )
        self.assertContains(response, 'id="offline-sync-panel"')
        self.assertContains(response, 'id="offline-sync-now"')
        self.assertContains(response, 'd-lg-none')
        self.assertContains(response, 'js/offline_db.js')
        self.assertContains(response, 'js/sync_client.js')

    def test_create_form_is_marked_for_offline_sync(self):
        response = self.client.get(
            reverse(self.create_url_name, args=[self.trip.pk])
        )
        self.assertContains(
            response, f'data-sync-form="{self.sync_form_type}"'
        )
        self.assertContains(response, reverse(self.sync_url_name))
        self.assertContains(response, f'data-sync-trip="{self.trip.pk}"')

    def test_edit_form_is_not_marked_for_offline_sync(self):
        record = create_record(self.trip, self.sync_form_type)
        response = self.client.get(
            reverse(self.edit_url_name, args=[self.trip.pk, record.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-sync-form')


class RefuelingOfflineMarkupTests(OfflineSyncMarkupMixin, TestCase):
    list_url_name = 'refueling_list'
    create_url_name = 'refueling_create'
    edit_url_name = 'refueling_edit'
    sync_url_name = 'sync_refueling'
    sync_form_type = 'refueling'


class LodgingOfflineMarkupTests(OfflineSyncMarkupMixin, TestCase):
    list_url_name = 'lodging_list'
    create_url_name = 'lodging_create'
    edit_url_name = 'lodging_edit'
    sync_url_name = 'sync_lodging'
    sync_form_type = 'lodging'


class MealOfflineMarkupTests(OfflineSyncMarkupMixin, TestCase):
    list_url_name = 'meal_list'
    create_url_name = 'meal_create'
    edit_url_name = 'meal_edit'
    sync_url_name = 'sync_meal'
    sync_form_type = 'meal'


class SightseeingOfflineMarkupTests(OfflineSyncMarkupMixin, TestCase):
    list_url_name = 'sightseeing_list'
    create_url_name = 'sightseeing_create'
    edit_url_name = 'sightseeing_edit'
    sync_url_name = 'sync_sightseeing'
    sync_form_type = 'sightseeing'
    trip_type = TripType.BUS
