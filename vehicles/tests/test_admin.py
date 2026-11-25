from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from trips.models import Trip, TripType
from vehicles.models import Refueling, TripVehicle, Vehicle, VehicleType


class TripVehicleAdminValidationTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            email='admin@example.com', password='strong-pass-123'
        )
        self.client.force_login(self.superuser)
        self.trip = Trip.objects.create(
            created_by=self.superuser,
            origin_city='São Paulo',
            origin_state='SP',
            destination_city='Curitiba',
            destination_state='PR',
            trip_type=TripType.CAR,
            start_datetime=timezone.now() - timedelta(days=1),
        )
        self.vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        self.trip_vehicle = TripVehicle.objects.create(
            trip=self.trip, vehicle=self.vehicle, initial_mileage=1000
        )
        self.url = reverse(
            'admin:vehicles_tripvehicle_change', args=[self.trip_vehicle.pk]
        )

    def post(self, final_mileage):
        return self.client.post(self.url, {
            'trip': self.trip.pk,
            'vehicle': self.vehicle.pk,
            'initial_mileage': '1000',
            'final_mileage': final_mileage,
        })

    def add_refueling(self, total_mileage):
        Refueling.objects.create(
            trip=self.trip,
            city='Campinas',
            state='SP',
            liters=Decimal('10.00'),
            amount_spent=Decimal('50.00'),
            total_mileage=total_mileage,
            datetime=timezone.now(),
        )

    def assert_change_failed(self, response):
        errors = (
            response.context['adminform'].form.errors
            if response.context and 'adminform' in response.context
            else None
        )
        self.assertEqual(response.status_code, 200, errors)

    def test_final_mileage_below_initial_is_rejected(self):
        response = self.post('900')
        self.assert_change_failed(response)
        self.assertContains(response, 'não pode ser menor')
        self.trip_vehicle.refresh_from_db()
        self.assertIsNone(self.trip_vehicle.final_mileage)

    def test_final_mileage_below_last_refueling_is_rejected(self):
        self.add_refueling(1500)
        response = self.post('1400')
        self.assert_change_failed(response)
        self.assertContains(response, 'não pode ser menor')
        self.trip_vehicle.refresh_from_db()
        self.assertIsNone(self.trip_vehicle.final_mileage)

    def test_final_mileage_equal_to_initial_is_accepted(self):
        response = self.post('1000')
        errors = (
            response.context['adminform'].form.errors
            if response.context and 'adminform' in response.context
            else None
        )
        self.assertEqual(response.status_code, 302, errors)
        self.trip_vehicle.refresh_from_db()
        self.assertEqual(self.trip_vehicle.final_mileage, 1000)

    def test_final_mileage_equal_to_last_refueling_is_accepted(self):
        self.add_refueling(1500)
        response = self.post('1500')
        errors = (
            response.context['adminform'].form.errors
            if response.context and 'adminform' in response.context
            else None
        )
        self.assertEqual(response.status_code, 302, errors)
        self.trip_vehicle.refresh_from_db()
        self.assertEqual(self.trip_vehicle.final_mileage, 1500)

    def test_null_final_mileage_is_accepted(self):
        response = self.post('')
        self.assertEqual(response.status_code, 302)
        self.trip_vehicle.refresh_from_db()
        self.assertIsNone(self.trip_vehicle.final_mileage)

    def test_add_with_final_mileage_below_initial_is_rejected(self):
        trip = Trip.objects.create(
            created_by=self.superuser,
            origin_city='São Paulo',
            origin_state='SP',
            destination_city='Curitiba',
            destination_state='PR',
            trip_type=TripType.CAR,
            start_datetime=timezone.now() - timedelta(days=1),
        )
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='VW', model='Gol'
        )
        response = self.client.post(
            reverse('admin:vehicles_tripvehicle_add'),
            {
                'trip': trip.pk,
                'vehicle': vehicle.pk,
                'initial_mileage': '1000',
                'final_mileage': '900',
            },
        )
        self.assert_change_failed(response)
        self.assertContains(response, 'não pode ser menor')
        self.assertFalse(
            TripVehicle.objects.filter(trip=trip, vehicle=vehicle).exists()
        )

    def test_late_synced_refueling_blocks_edit_until_final_is_fixed(self):
        self.trip_vehicle.final_mileage = 2200
        self.trip_vehicle.save()
        self.add_refueling(2400)
        response = self.post('2200')
        self.assert_change_failed(response)
        self.assertContains(response, 'não pode ser menor')
        self.assertContains(response, '2400')
