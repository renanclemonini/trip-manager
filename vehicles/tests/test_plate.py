from django.test import TestCase

from accounts.models import User
from trips.models import Trip, TripType
from vehicles import services
from vehicles.forms import VehicleTripForm
from vehicles.models import Vehicle, VehicleType


def create_vehicle(**kwargs):
    defaults = {
        'vehicle_type': VehicleType.CAR,
        'brand': 'Fiat',
        'model': 'Argo',
    }
    defaults.update(kwargs)
    return Vehicle.objects.create(**defaults)


def create_trip():
    user = User.objects.create_user(
        email='plate@example.com', password='strong-pass-123'
    )
    return Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=TripType.CAR,
        start_datetime='2026-11-01T08:00:00-03:00',
    )


class VehiclePlateNormalizationTests(TestCase):
    def test_uppercases_and_removes_hyphen(self):
        vehicle = create_vehicle(plate='abc-1d23')
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.plate, 'ABC1D23')

    def test_removes_spaces(self):
        vehicle = create_vehicle(plate='ABC 1234')
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.plate, 'ABC1234')

    def test_empty_string_becomes_none(self):
        vehicle = create_vehicle(plate='')
        vehicle.refresh_from_db()
        self.assertIsNone(vehicle.plate)

    def test_legacy_vehicle_without_plate_keeps_none(self):
        vehicle = create_vehicle()
        self.assertIsNone(vehicle.plate)


class VehicleTripFormPlateTests(TestCase):
    def _data(self, **overrides):
        data = {
            'brand': 'Fiat',
            'model': 'Argo',
            'initial_mileage': '1000',
            'plate': '',
        }
        data.update(overrides)
        return data

    def test_plate_is_optional(self):
        form = VehicleTripForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['plate'])

    def test_accepts_old_format_with_hyphen(self):
        form = VehicleTripForm(data=self._data(plate='abc-1234'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['plate'], 'ABC1234')

    def test_accepts_mercosul_format_with_hyphen(self):
        form = VehicleTripForm(data=self._data(plate='abc-1d23'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['plate'], 'ABC1D23')

    def test_rejects_invalid_format(self):
        form = VehicleTripForm(data=self._data(plate='AB1234'))
        self.assertFalse(form.is_valid())
        self.assertIn('plate', form.errors)
        self.assertIn('placa válida', form.errors['plate'][0])

    def test_rejects_old_format_with_extra_digit(self):
        form = VehicleTripForm(data=self._data(plate='ABC12345'))
        self.assertFalse(form.is_valid())
        self.assertIn('plate', form.errors)


class VehicleTripFormPlateMarkupTests(TestCase):
    def test_plate_help_text_present(self):
        self.assertEqual(
            VehicleTripForm().fields['plate'].help_text,
            'Necessária para importar o extrato de pedágio.',
        )


class CarTransportPlateServiceTests(TestCase):
    def setUp(self):
        self.trip = create_trip()

    def test_create_persists_plate(self):
        trip_vehicle = services.create_car_transport(
            self.trip,
            {
                'brand': 'Fiat',
                'model': 'Argo',
                'initial_mileage': 1000,
                'plate': 'abc-1d23',
            },
        )
        self.assertEqual(trip_vehicle.vehicle.plate, 'ABC1D23')

    def test_create_without_plate_key_keeps_none(self):
        trip_vehicle = services.create_car_transport(
            self.trip,
            {'brand': 'Fiat', 'model': 'Argo', 'initial_mileage': 1000},
        )
        self.assertIsNone(trip_vehicle.vehicle.plate)

    def test_update_changes_plate(self):
        services.create_car_transport(
            self.trip,
            {
                'brand': 'Fiat',
                'model': 'Argo',
                'initial_mileage': 1000,
                'plate': 'abc-1234',
            },
        )
        trip_vehicle = services.update_car_transport(
            self.trip,
            {
                'brand': 'Fiat',
                'model': 'Argo',
                'initial_mileage': 1000,
                'plate': 'abc-1d23',
            },
        )
        self.assertEqual(trip_vehicle.vehicle.plate, 'ABC1D23')
