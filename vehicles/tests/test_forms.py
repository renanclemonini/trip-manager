from datetime import date, datetime

from django.test import TestCase
from django.utils.timezone import make_aware

from trips.models import Trip, TripType
from vehicles.forms import BusTripForm, FlightTripForm, VehicleTripForm


class VehicleTripFormTests(TestCase):
    def _data(self, **overrides):
        data = {'brand': 'Fiat', 'model': 'Argo', 'initial_mileage': '1000'}
        data.update(overrides)
        return data

    def test_valid_data(self):
        form = VehicleTripForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_required_fields(self):
        form = VehicleTripForm(data=self._data(brand='', model=''))
        self.assertFalse(form.is_valid())
        self.assertIn('brand', form.errors)
        self.assertIn('model', form.errors)

    def test_initial_mileage_must_be_non_negative(self):
        form = VehicleTripForm(data=self._data(initial_mileage='-1'))
        self.assertFalse(form.is_valid())
        self.assertIn('initial_mileage', form.errors)


class VehicleTripFormInteractionMarkupTests(TestCase):
    def test_initial_mileage_uses_integer_mask(self):
        widget = VehicleTripForm().fields['initial_mileage'].widget
        self.assertEqual(widget.input_type, 'text')
        self.assertEqual(widget.attrs['data-mask'], 'integer')
        self.assertEqual(widget.attrs['inputmode'], 'numeric')
        self.assertEqual(widget.attrs['placeholder'], '0')


class BusTripFormTests(TestCase):
    def _data(self, **overrides):
        data = {
            'brand': 'Cometa',
            'model': 'Scania',
            'company': 'Viação Cometa',
            'amount_paid': '150.50',
            'start_date': '2026-11-01',
        }
        data.update(overrides)
        return data

    def test_valid_data(self):
        form = BusTripForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(str(form.cleaned_data['amount_paid']), '150.50')
        self.assertEqual(form.cleaned_data['start_date'], date(2026, 11, 1))

    def test_amount_paid_must_be_decimal(self):
        form = BusTripForm(data=self._data(amount_paid='abc'))
        self.assertFalse(form.is_valid())
        self.assertIn('amount_paid', form.errors)

    def test_all_fields_are_required(self):
        form = BusTripForm(data={})
        self.assertFalse(form.is_valid())
        for field in ('brand', 'model', 'company', 'amount_paid', 'start_date'):
            self.assertIn(field, form.errors)


class BusTripFormInteractionMarkupTests(TestCase):
    def test_amount_paid_uses_currency_mask(self):
        widget = BusTripForm().fields['amount_paid'].widget
        self.assertEqual(widget.input_type, 'text')
        self.assertEqual(widget.attrs['data-mask'], 'currency')
        self.assertEqual(widget.attrs['placeholder'], 'R$ 0,00')


class FlightTripFormTests(TestCase):
    def _data(self, **overrides):
        data = {
            'airline': 'LATAM',
            'aircraft_model': '',
            'ticket_price': '1234.56',
            'departure_datetime': '2026-11-01T10:30',
            'return_datetime': '',
        }
        data.update(overrides)
        return data

    def test_valid_data_with_optional_fields_empty(self):
        form = FlightTripForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data['departure_datetime'],
            make_aware(datetime(2026, 11, 1, 10, 30)),
        )

    def test_return_before_departure_is_invalid(self):
        form = FlightTripForm(data=self._data(
            return_datetime='2026-11-01T09:00'
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('return_datetime', form.errors)

    def test_return_equal_to_departure_is_valid(self):
        form = FlightTripForm(data=self._data(
            return_datetime='2026-11-01T10:30'
        ))
        self.assertTrue(form.is_valid(), form.errors)


class FlightTripFormInteractionMarkupTests(TestCase):
    def test_ticket_price_uses_currency_mask(self):
        widget = FlightTripForm().fields['ticket_price'].widget
        self.assertEqual(widget.input_type, 'text')
        self.assertEqual(widget.attrs['data-mask'], 'currency')
        self.assertEqual(widget.attrs['placeholder'], 'R$ 0,00')

    def test_datetime_fields_expose_now_hook(self):
        form = FlightTripForm()
        for field_name in ('departure_datetime', 'return_datetime'):
            self.assertEqual(
                form.fields[field_name].widget.attrs['data-now'], 'true'
            )
