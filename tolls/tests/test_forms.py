from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from tolls.forms import TollForm
from trips.models import Trip, TripType


def create_trip(trip_type=TripType.CAR):
    user = User.objects.create_user(
        email='toll-form@example.com', password='strong-pass-123'
    )
    return Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=trip_type,
        start_datetime=timezone.now() - timedelta(days=1),
    )


def toll_data(**overrides):
    data = {
        'location': 'Praça ABC',
        'amount_spent': '25.00',
        'datetime': '2026-10-02T08:00',
    }
    data.update(overrides)
    return data


class TollFormTests(TestCase):
    def test_valid_data(self):
        form = TollForm(data=toll_data(), trip=create_trip())
        self.assertTrue(form.is_valid(), form.errors)

    def test_required_fields(self):
        form = TollForm(data={}, trip=create_trip())
        self.assertFalse(form.is_valid())
        for field in ('location', 'amount_spent', 'datetime'):
            self.assertIn(field, form.errors)

    def test_amount_spent_must_be_positive(self):
        form = TollForm(
            data=toll_data(amount_spent='0.00'), trip=create_trip()
        )
        self.assertFalse(form.is_valid())
        self.assertIn('amount_spent', form.errors)

    def test_amount_spent_must_be_decimal(self):
        form = TollForm(
            data=toll_data(amount_spent='abc'), trip=create_trip()
        )
        self.assertFalse(form.is_valid())
        self.assertIn('amount_spent', form.errors)

    def test_bus_trip_is_rejected(self):
        form = TollForm(
            data=toll_data(), trip=create_trip(TripType.BUS)
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            'Pedágio só pode ser registrado em viagem de carro.',
            form.errors['__all__'],
        )

    def test_plane_trip_is_rejected(self):
        form = TollForm(
            data=toll_data(), trip=create_trip(TripType.PLANE)
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            'Pedágio só pode ser registrado em viagem de carro.',
            form.errors['__all__'],
        )


class TollFormMarkupTests(TestCase):
    def test_amount_spent_uses_currency_mask(self):
        widget = TollForm(trip=create_trip()).fields['amount_spent'].widget
        self.assertEqual(widget.input_type, 'text')
        self.assertEqual(widget.attrs['data-mask'], 'currency')
        self.assertEqual(widget.attrs['placeholder'], 'R$ 0,00')

    def test_datetime_exposes_now_hook(self):
        widget = TollForm(trip=create_trip()).fields['datetime'].widget
        self.assertEqual(widget.attrs['data-now'], 'true')
