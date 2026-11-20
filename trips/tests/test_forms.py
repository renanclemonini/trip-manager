from django.test import TestCase

from trips.forms import TripForm


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
