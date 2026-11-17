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
                'start_date',
                'end_date',
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


class TripFormValidationTests(TestCase):
    def _data(self, **overrides):
        data = {
            'origin_city': 'São Paulo',
            'origin_state': 'SP',
            'destination_city': 'Curitiba',
            'destination_state': 'PR',
            'trip_type': 'car',
            'start_date': '2026-10-10',
        }
        data.update(overrides)
        return data

    def test_car_trip_end_date_is_optional(self):
        form = TripForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_car_trip_forces_end_date_to_none(self):
        form = TripForm(data=self._data(end_date='2026-10-12'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['end_date'])

    def test_bus_trip_requires_end_date(self):
        form = TripForm(data=self._data(trip_type='bus'))
        self.assertFalse(form.is_valid())
        self.assertIn('end_date', form.errors)

    def test_plane_trip_requires_end_date(self):
        form = TripForm(data=self._data(trip_type='plane'))
        self.assertFalse(form.is_valid())
        self.assertIn('end_date', form.errors)

    def test_bus_trip_accepts_end_date(self):
        form = TripForm(
            data=self._data(trip_type='bus', end_date='2026-10-12')
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_end_date_before_start_date_is_invalid(self):
        form = TripForm(
            data=self._data(trip_type='bus', end_date='2026-10-01')
        )
        self.assertFalse(form.is_valid())
        self.assertIn('end_date', form.errors)

    def test_end_date_equal_to_start_date_is_valid(self):
        form = TripForm(
            data=self._data(trip_type='bus', end_date='2026-10-10')
        )
        self.assertTrue(form.is_valid(), form.errors)
