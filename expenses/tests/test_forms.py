from django.test import TestCase

from expenses.forms import LodgingForm, MealForm, SightseeingForm


def lodging_data(**overrides):
    data = {
        'city': 'Curitiba',
        'state': 'PR',
        'amount_spent': '450.00',
        'check_in': '2026-10-02T14:00',
        'check_out': '2026-10-05T11:00',
    }
    data.update(overrides)
    return data


def meal_data(**overrides):
    data = {
        'city': 'Curitiba',
        'state': 'PR',
        'amount_spent': '35.00',
        'datetime': '2026-10-02T12:30',
    }
    data.update(overrides)
    return data


class LodgingFormValidationTests(TestCase):
    def test_valid_data(self):
        form = LodgingForm(data=lodging_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_check_out_before_check_in_is_invalid(self):
        form = LodgingForm(
            data=lodging_data(
                check_in='2026-10-05T14:00', check_out='2026-10-02T11:00'
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn('check_out', form.errors)

    def test_check_out_equal_to_check_in_is_valid(self):
        same_day = '2026-10-02T14:00'
        form = LodgingForm(
            data=lodging_data(check_in=same_day, check_out=same_day)
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_all_fields_are_required(self):
        form = LodgingForm(data={})
        self.assertFalse(form.is_valid())
        for field in (
            'city',
            'state',
            'amount_spent',
            'check_in',
            'check_out',
        ):
            self.assertIn(field, form.errors)

    def test_ibge_markup_is_present(self):
        form = LodgingForm()
        self.assertEqual(
            form.fields['state'].widget.attrs['data-ibge-uf'], 'true'
        )
        city_attrs = form.fields['city'].widget.attrs
        self.assertEqual(city_attrs['data-ibge-city'], 'true')
        self.assertEqual(city_attrs['list'], 'ibge-city-list')


class MealFormValidationTests(TestCase):
    def test_valid_data(self):
        form = MealForm(data=meal_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_all_fields_are_required(self):
        form = MealForm(data={})
        self.assertFalse(form.is_valid())
        for field in ('city', 'state', 'amount_spent', 'datetime'):
            self.assertIn(field, form.errors)

    def test_ibge_markup_is_present(self):
        form = MealForm()
        self.assertEqual(
            form.fields['state'].widget.attrs['data-ibge-uf'], 'true'
        )
        self.assertEqual(
            form.fields['city'].widget.attrs['data-ibge-city'], 'true'
        )


class LodgingFormInteractionMarkupTests(TestCase):
    def test_state_comes_before_city(self):
        self.assertEqual(list(LodgingForm().fields)[:2], ['state', 'city'])

    def test_amount_uses_currency_mask(self):
        widget = LodgingForm().fields['amount_spent'].widget
        self.assertEqual(widget.input_type, 'text')
        self.assertEqual(widget.attrs['data-mask'], 'currency')
        self.assertEqual(widget.attrs['inputmode'], 'decimal')
        self.assertEqual(widget.attrs['autocomplete'], 'off')
        self.assertEqual(widget.attrs['placeholder'], 'R$ 0,00')

    def test_datetime_fields_expose_now_hook(self):
        form = LodgingForm()
        for field_name in ('check_in', 'check_out'):
            self.assertEqual(
                form.fields[field_name].widget.attrs['data-now'], 'true'
            )


class MealFormInteractionMarkupTests(TestCase):
    def test_state_comes_before_city(self):
        self.assertEqual(list(MealForm().fields)[:2], ['state', 'city'])

    def test_amount_uses_currency_mask(self):
        widget = MealForm().fields['amount_spent'].widget
        self.assertEqual(widget.input_type, 'text')
        self.assertEqual(widget.attrs['data-mask'], 'currency')
        self.assertEqual(widget.attrs['placeholder'], 'R$ 0,00')

    def test_datetime_field_exposes_now_hook(self):
        widget = MealForm().fields['datetime'].widget
        self.assertEqual(widget.attrs['data-now'], 'true')


class SightseeingFormInteractionMarkupTests(TestCase):
    def test_amount_uses_currency_mask(self):
        widget = SightseeingForm().fields['amount_spent'].widget
        self.assertEqual(widget.input_type, 'text')
        self.assertEqual(widget.attrs['data-mask'], 'currency')
        self.assertEqual(widget.attrs['placeholder'], 'R$ 0,00')


class SightseeingFormValidationTests(TestCase):
    def test_valid_data_with_description(self):
        form = SightseeingForm(
            data={'amount_spent': '80.00', 'description': 'Museu'}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_description_is_optional(self):
        form = SightseeingForm(data={'amount_spent': '80.00', 'description': ''})
        self.assertTrue(form.is_valid(), form.errors)

    def test_amount_spent_is_required(self):
        form = SightseeingForm(data={'amount_spent': '', 'description': 'X'})
        self.assertFalse(form.is_valid())
        self.assertIn('amount_spent', form.errors)
