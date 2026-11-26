from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.utils.timezone import make_aware

from accounts.models import User
from trips.forms import FinishTripForm, TripForm
from trips.models import Trip, TripType
from vehicles.models import Refueling, TripVehicle, Vehicle, VehicleType


class TripFormFieldsTests(TestCase):
    def test_form_exposes_expected_fields_in_order(self):
        form = TripForm()
        self.assertEqual(
            list(form.fields),
            [
                'origin_city',
                'origin_state',
                'destination_city',
                'destination_state',
                'trip_type',
                'start_datetime',
                'end_datetime',
            ],
        )

    def test_city_fields_have_ibge_autocomplete_markup(self):
        form = TripForm()
        expected = {
            'origin_city': 'origin-city-list',
            'destination_city': 'destination-city-list',
        }
        for field_name, list_id in expected.items():
            attrs = form.fields[field_name].widget.attrs
            self.assertEqual(attrs['data-ibge-city'], 'true')
            self.assertEqual(attrs['list'], list_id)
        for field_name in ('origin_state', 'destination_state'):
            attrs = form.fields[field_name].widget.attrs
            self.assertEqual(attrs['data-ibge-uf'], 'true')

    def test_datetime_fields_expose_now_hook(self):
        form = TripForm()
        for field_name in ('start_datetime', 'end_datetime'):
            self.assertEqual(
                form.fields[field_name].widget.attrs['data-now'], 'true'
            )


class TripFormValidationTests(TestCase):
    def _data(self, **overrides):
        data = {
            'origin_city': 'São Paulo',
            'origin_state': 'SP',
            'destination_city': 'Curitiba',
            'destination_state': 'PR',
            'trip_type': 'car',
            'start_datetime': '2026-10-10T10:00',
        }
        data.update(overrides)
        return data

    def test_car_trip_end_datetime_is_optional(self):
        form = TripForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_car_trip_forces_end_datetime_to_none(self):
        form = TripForm(data=self._data(end_datetime='2026-10-12T10:00'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['end_datetime'])

    def test_bus_trip_requires_end_datetime(self):
        form = TripForm(data=self._data(trip_type='bus'))
        self.assertFalse(form.is_valid())
        self.assertIn('end_datetime', form.errors)

    def test_plane_trip_requires_end_datetime(self):
        form = TripForm(data=self._data(trip_type='plane'))
        self.assertFalse(form.is_valid())
        self.assertIn('end_datetime', form.errors)

    def test_bus_trip_accepts_end_datetime(self):
        form = TripForm(
            data=self._data(trip_type='bus', end_datetime='2026-10-12T10:00')
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_end_datetime_before_start_datetime_is_invalid(self):
        form = TripForm(
            data=self._data(trip_type='bus', end_datetime='2026-10-10T09:00')
        )
        self.assertFalse(form.is_valid())
        self.assertIn('end_datetime', form.errors)

    def test_end_datetime_equal_to_start_datetime_is_valid(self):
        form = TripForm(
            data=self._data(trip_type='bus', end_datetime='2026-10-10T10:00')
        )
        self.assertTrue(form.is_valid(), form.errors)


class FinishTripFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='finish-form@example.com', password='strong-pass-123'
        )
        self.trip = Trip.objects.create(
            created_by=self.user,
            origin_city='São Paulo',
            origin_state='SP',
            destination_city='Curitiba',
            destination_state='PR',
            trip_type=TripType.CAR,
            start_datetime=timezone.now() - timedelta(days=1),
        )
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        self.trip_vehicle = TripVehicle.objects.create(
            trip=self.trip, vehicle=vehicle, initial_mileage=1000
        )

    def _data(self, **overrides):
        end = self.trip.start_datetime + timedelta(hours=5)
        data = {
            'end_datetime': end.strftime('%Y-%m-%dT%H:%M'),
            'final_mileage': '2000',
        }
        data.update(overrides)
        return data

    def test_form_exposes_expected_fields_in_order(self):
        form = FinishTripForm(trip=self.trip)
        self.assertEqual(
            list(form.fields), ['end_datetime', 'final_mileage']
        )
        attrs = form.fields['final_mileage'].widget.attrs
        self.assertEqual(attrs['data-mask'], 'integer')

    def test_final_mileage_is_required(self):
        form = FinishTripForm(
            data=self._data(final_mileage=''), trip=self.trip
        )
        self.assertFalse(form.is_valid())
        self.assertIn('final_mileage', form.errors)

    def test_final_mileage_equal_to_current_is_valid(self):
        Refueling.objects.create(
            trip=self.trip,
            city='Campinas',
            state='SP',
            liters=Decimal('30.00'),
            amount_spent=Decimal('150.00'),
            total_mileage=2000,
            datetime=make_aware(datetime(2026, 11, 20, 8, 0)),
        )
        form = FinishTripForm(data=self._data(), trip=self.trip)
        self.assertTrue(form.is_valid(), form.errors)

    def test_final_mileage_below_current_is_invalid(self):
        Refueling.objects.create(
            trip=self.trip,
            city='Campinas',
            state='SP',
            liters=Decimal('30.00'),
            amount_spent=Decimal('150.00'),
            total_mileage=2000,
            datetime=make_aware(datetime(2026, 11, 20, 8, 0)),
        )
        form = FinishTripForm(
            data=self._data(final_mileage='1999'), trip=self.trip
        )
        self.assertFalse(form.is_valid())
        self.assertIn('final_mileage', form.errors)
        self.assertIn(
            'não pode ser menor', form.errors['final_mileage'][0]
        )

    def test_final_mileage_below_initial_without_refueling_is_invalid(self):
        form = FinishTripForm(
            data=self._data(final_mileage='999'), trip=self.trip
        )
        self.assertFalse(form.is_valid())
        self.assertIn('final_mileage', form.errors)
