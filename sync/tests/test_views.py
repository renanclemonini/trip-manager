import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone
from django.urls import reverse
from django.utils.timezone import make_aware

from expenses.models import Lodging, Meal, Sightseeing
from trips.models import Trip, TripType
from vehicles.models import Refueling, TripVehicle, Vehicle, VehicleType

REFUELING_DATETIME = make_aware(datetime(2026, 10, 2, 8, 0))
CHECK_IN = make_aware(datetime(2026, 10, 2, 14, 0))
CHECK_OUT = make_aware(datetime(2026, 10, 5, 11, 0))


def create_user(email='sync@example.com'):
    return get_user_model().objects.create_user(
        email=email, password='strong-pass-123'
    )


def create_trip(user, trip_type=TripType.CAR, with_vehicle=True):
    trip = Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=trip_type,
        start_datetime=timezone.now() - timedelta(days=1),
    )
    if with_vehicle and trip_type == TripType.CAR:
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        TripVehicle.objects.create(
            trip=trip, vehicle=vehicle, initial_mileage=1000
        )
    return trip


def post_json(client, url, payload, **extra):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type='application/json',
        **extra,
    )


def refueling_payload(trip, **overrides):
    payload = {
        'id': str(uuid4()),
        'trip': trip.pk,
        'city': 'Campinas',
        'state': 'SP',
        'liters': '30.00',
        'amount_spent': '150.00',
        'total_mileage': 1500,
        'datetime': '2026-10-02T08:00',
    }
    payload.update(overrides)
    return payload


def lodging_payload(trip, **overrides):
    payload = {
        'id': str(uuid4()),
        'trip': trip.pk,
        'city': 'Curitiba',
        'state': 'PR',
        'amount_spent': '450.00',
        'check_in': '2026-10-02T14:00',
        'check_out': '2026-10-05T11:00',
    }
    payload.update(overrides)
    return payload


def meal_payload(trip, **overrides):
    payload = {
        'id': str(uuid4()),
        'trip': trip.pk,
        'city': 'Curitiba',
        'state': 'PR',
        'amount_spent': '35.00',
        'datetime': '2026-10-02T12:30',
    }
    payload.update(overrides)
    return payload


def sightseeing_payload(trip, **overrides):
    payload = {
        'id': str(uuid4()),
        'trip': trip.pk,
        'amount_spent': '80.00',
        'description': 'Museu',
    }
    payload.update(overrides)
    return payload


class SyncAuthTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user())

    def test_anonymous_gets_json_403(self):
        response = post_json(
            self.client, reverse('sync_refueling'), refueling_payload(self.trip)
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['status'], 'error')

    def test_get_is_not_allowed(self):
        self.client.force_login(self.trip.created_by)
        response = self.client.get(reverse('sync_refueling'))
        self.assertEqual(response.status_code, 405)


class SyncCsrfTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user('csrf@example.com'))
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.trip.created_by)
        self.client.get(reverse('home'))

    def test_post_without_csrf_token_is_rejected(self):
        response = post_json(
            self.client, reverse('sync_refueling'), refueling_payload(self.trip)
        )
        self.assertEqual(response.status_code, 403)

    def test_post_with_csrf_header_is_accepted(self):
        token = self.client.cookies['csrftoken'].value
        response = post_json(
            self.client,
            reverse('sync_refueling'),
            refueling_payload(self.trip),
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201)


class RefuelingSyncCreateTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user('create-sync@example.com'))
        self.client.force_login(self.trip.created_by)

    def test_creates_record_with_client_uuid(self):
        payload = refueling_payload(self.trip)
        response = post_json(
            self.client, reverse('sync_refueling'), payload
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(), {'status': 'ok', 'id': payload['id']}
        )
        refueling = Refueling.objects.get(pk=payload['id'])
        self.assertEqual(refueling.trip, self.trip)
        self.assertEqual(str(refueling.liters), '30.00')
        self.assertEqual(refueling.datetime, REFUELING_DATETIME)


class RefuelingSyncIdempotencyTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user('idempotent@example.com'))
        self.client.force_login(self.trip.created_by)

    def test_resend_updates_same_record(self):
        payload = refueling_payload(self.trip)
        first = post_json(self.client, reverse('sync_refueling'), payload)
        second = post_json(
            self.client,
            reverse('sync_refueling'),
            payload | {'liters': '40.00'},
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Refueling.objects.count(), 1)
        refueling = Refueling.objects.get(pk=payload['id'])
        self.assertEqual(str(refueling.liters), '40.00')


class RefuelingSyncValidationTests(TestCase):
    def setUp(self):
        self.user = create_user('validation-sync@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_mileage_below_initial_returns_400(self):
        response = post_json(
            self.client,
            reverse('sync_refueling'),
            refueling_payload(self.trip, total_mileage=900),
        )
        self.assertEqual(response.status_code, 400)
        errors = response.json()['errors']
        self.assertIn('total_mileage', errors)

    def test_duplicated_mileage_returns_400(self):
        Refueling.objects.create(
            trip=self.trip,
            city='Campinas',
            state='SP',
            liters=Decimal('30.00'),
            amount_spent=Decimal('150.00'),
            total_mileage=1500,
            datetime=REFUELING_DATETIME,
        )
        response = post_json(
            self.client,
            reverse('sync_refueling'),
            refueling_payload(self.trip, total_mileage=1500),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('total_mileage', response.json()['errors'])

    def test_non_car_trip_returns_400(self):
        bus_trip = create_trip(self.user, TripType.BUS)
        response = post_json(
            self.client,
            reverse('sync_refueling'),
            refueling_payload(bus_trip),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('__all__', response.json()['errors'])

    def test_other_user_trip_is_allowed(self):
        other_trip = create_trip(create_user('other-sync@example.com'))
        payload = refueling_payload(other_trip)
        response = post_json(
            self.client,
            reverse('sync_refueling'),
            payload,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Refueling.objects.filter(pk=payload['id']).exists())


class SyncUuidConflictTests(TestCase):
    def setUp(self):
        self.user = create_user('conflict@example.com')
        self.first_trip = create_trip(self.user)
        self.second_trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_uuid_from_another_trip_returns_400(self):
        existing = Refueling.objects.create(
            trip=self.first_trip,
            city='Campinas',
            state='SP',
            liters=Decimal('30.00'),
            amount_spent=Decimal('150.00'),
            total_mileage=1500,
            datetime=REFUELING_DATETIME,
        )
        response = post_json(
            self.client,
            reverse('sync_refueling'),
            refueling_payload(self.second_trip, id=str(existing.pk)),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('id', response.json()['errors'])


class SyncPayloadTests(TestCase):
    def setUp(self):
        self.trip = create_trip(create_user('payload@example.com'))
        self.client.force_login(self.trip.created_by)

    def test_malformed_json_returns_400(self):
        response = self.client.post(
            reverse('sync_refueling'),
            data='{invalid',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_id_returns_400(self):
        payload = refueling_payload(self.trip)
        del payload['id']
        response = post_json(
            self.client, reverse('sync_refueling'), payload
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('id', response.json()['errors'])

    def test_missing_trip_returns_400(self):
        payload = refueling_payload(self.trip)
        del payload['trip']
        response = post_json(
            self.client, reverse('sync_refueling'), payload
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('trip', response.json()['errors'])

    def test_invalid_uuid_returns_400(self):
        response = post_json(
            self.client,
            reverse('sync_refueling'),
            refueling_payload(self.trip, id='not-a-uuid'),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('id', response.json()['errors'])


class LodgingSyncTests(TestCase):
    def setUp(self):
        self.user = create_user('lodging-sync@example.com')
        self.trip = create_trip(self.user, TripType.PLANE, with_vehicle=False)
        self.client.force_login(self.user)

    def test_creates_and_is_idempotent(self):
        payload = lodging_payload(self.trip)
        first = post_json(self.client, reverse('sync_lodging'), payload)
        second = post_json(
            self.client,
            reverse('sync_lodging'),
            payload | {'amount_spent': '500.00'},
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Lodging.objects.count(), 1)
        lodging = Lodging.objects.get(pk=payload['id'])
        self.assertEqual(str(lodging.amount_spent), '500.00')

    def test_check_out_before_check_in_returns_400(self):
        response = post_json(
            self.client,
            reverse('sync_lodging'),
            lodging_payload(
                self.trip,
                check_in='2026-10-05T14:00',
                check_out='2026-10-02T11:00',
            ),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('check_out', response.json()['errors'])


class MealSyncTests(TestCase):
    def setUp(self):
        self.user = create_user('meal-sync@example.com')
        self.trip = create_trip(self.user, TripType.PLANE, with_vehicle=False)
        self.client.force_login(self.user)

    def test_creates_meal(self):
        payload = meal_payload(self.trip)
        response = post_json(self.client, reverse('sync_meal'), payload)
        self.assertEqual(response.status_code, 201)
        meal = Meal.objects.get(pk=payload['id'])
        self.assertEqual(meal.trip, self.trip)
        self.assertEqual(str(meal.amount_spent), '35.00')


class SightseeingSyncTests(TestCase):
    def setUp(self):
        self.user = create_user('sightseeing-sync@example.com')
        self.client.force_login(self.user)

    def test_creates_on_bus_trip(self):
        bus_trip = create_trip(self.user, TripType.BUS, with_vehicle=False)
        payload = sightseeing_payload(bus_trip)
        response = post_json(
            self.client, reverse('sync_sightseeing'), payload
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Sightseeing.objects.filter(pk=payload['id']).exists())

    def test_car_trip_returns_400(self):
        car_trip = create_trip(self.user)
        response = post_json(
            self.client,
            reverse('sync_sightseeing'),
            sightseeing_payload(car_trip),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.json()['errors'])
