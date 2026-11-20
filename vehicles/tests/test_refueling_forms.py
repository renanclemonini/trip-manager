from datetime import date, datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.utils.timezone import make_aware

from accounts.models import User
from trips.models import Trip, TripType
from vehicles.forms import RefuelingForm
from vehicles.models import Refueling, TripVehicle, Vehicle, VehicleType

REFUELING_DATETIME = make_aware(datetime(2026, 10, 2, 8, 0))


def create_car_trip(initial_mileage=1000):
    user = User.objects.create_user(
        email='refueling-forms@example.com', password='strong-pass-123'
    )
    trip = Trip.objects.create(
        created_by=user,
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
    TripVehicle.objects.create(
        trip=trip, vehicle=vehicle, initial_mileage=initial_mileage
    )
    return trip


def form_data(**overrides):
    data = {
        'city': 'Campinas',
        'state': 'SP',
        'liters': '30.00',
        'amount_spent': '150.00',
        'total_mileage': '1500',
        'datetime': '2026-10-02T08:00',
    }
    data.update(overrides)
    return data


class RefuelingFormValidTests(TestCase):
    def setUp(self):
        self.trip = create_car_trip()

    def test_valid_data(self):
        form = RefuelingForm(data=form_data(), trip=self.trip)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['amount_spent'], Decimal('150.00'))

    def test_liters_must_be_greater_than_zero(self):
        form = RefuelingForm(data=form_data(liters='0.00'), trip=self.trip)
        self.assertFalse(form.is_valid())
        self.assertIn('liters', form.errors)

    def test_state_must_be_a_valid_uf(self):
        form = RefuelingForm(data=form_data(state='XX'), trip=self.trip)
        self.assertFalse(form.is_valid())
        self.assertIn('state', form.errors)

    def test_all_fields_are_required(self):
        form = RefuelingForm(data={}, trip=self.trip)
        self.assertFalse(form.is_valid())
        for field in (
            'city',
            'state',
            'liters',
            'amount_spent',
            'total_mileage',
            'datetime',
        ):
            self.assertIn(field, form.errors)


class RefuelingFormOdometerValidationTests(TestCase):
    def setUp(self):
        self.trip = create_car_trip(initial_mileage=1000)

    def test_mileage_below_initial_is_invalid(self):
        form = RefuelingForm(data=form_data(total_mileage='900'), trip=self.trip)
        self.assertFalse(form.is_valid())
        self.assertIn('total_mileage', form.errors)

    def test_duplicated_mileage_is_invalid(self):
        Refueling.objects.create(
            trip=self.trip,
            city='Campinas',
            state='SP',
            liters=Decimal('30.00'),
            amount_spent=Decimal('150.00'),
            total_mileage=1500,
            datetime=REFUELING_DATETIME,
        )
        form = RefuelingForm(data=form_data(total_mileage='1500'), trip=self.trip)
        self.assertFalse(form.is_valid())
        self.assertIn('total_mileage', form.errors)

    def test_own_instance_mileage_is_allowed_on_update(self):
        refueling = Refueling.objects.create(
            trip=self.trip,
            city='Campinas',
            state='SP',
            liters=Decimal('30.00'),
            amount_spent=Decimal('150.00'),
            total_mileage=1500,
            datetime=REFUELING_DATETIME,
        )
        form = RefuelingForm(
            data=form_data(total_mileage='1500', city='Jundiaí'),
            trip=self.trip,
            instance=refueling,
        )
        self.assertTrue(form.is_valid(), form.errors)


class RefuelingFormIbgEMarkupTests(TestCase):
    def setUp(self):
        self.trip = create_car_trip()

    def test_state_select_is_marked_for_autocomplete(self):
        form = RefuelingForm(trip=self.trip)
        attrs = form.fields['state'].widget.attrs
        self.assertEqual(attrs['data-ibge-uf'], 'true')
        self.assertEqual(len(form.fields['state'].choices), 28)

    def test_state_has_blank_first_choice(self):
        form = RefuelingForm(trip=self.trip)
        self.assertEqual(form.fields['state'].choices[0][0], '')

    def test_city_input_is_marked_for_autocomplete(self):
        form = RefuelingForm(trip=self.trip)
        attrs = form.fields['city'].widget.attrs
        self.assertEqual(attrs['data-ibge-city'], 'true')
        self.assertEqual(attrs['list'], 'ibge-city-list')
        self.assertEqual(attrs['autocomplete'], 'off')


class RefuelingFormInteractionMarkupTests(TestCase):
    def setUp(self):
        self.trip = create_car_trip()
        self.form = RefuelingForm(trip=self.trip)

    def test_state_comes_before_city(self):
        self.assertEqual(
            list(self.form.fields),
            [
                'state',
                'city',
                'liters',
                'amount_spent',
                'total_mileage',
                'datetime',
            ],
        )

    def test_liters_uses_decimal_mask(self):
        widget = self.form.fields['liters'].widget
        self.assertEqual(widget.input_type, 'text')
        self.assertEqual(widget.attrs['data-mask'], 'decimal')
        self.assertEqual(widget.attrs['inputmode'], 'decimal')
        self.assertEqual(widget.attrs['placeholder'], '0,00')

    def test_amount_uses_currency_mask(self):
        widget = self.form.fields['amount_spent'].widget
        self.assertEqual(widget.input_type, 'text')
        self.assertEqual(widget.attrs['data-mask'], 'currency')
        self.assertEqual(widget.attrs['placeholder'], 'R$ 0,00')

    def test_total_mileage_uses_integer_mask(self):
        widget = self.form.fields['total_mileage'].widget
        self.assertEqual(widget.input_type, 'text')
        self.assertEqual(widget.attrs['data-mask'], 'integer')
        self.assertEqual(widget.attrs['inputmode'], 'numeric')
        self.assertEqual(widget.attrs['placeholder'], '0')

    def test_datetime_exposes_now_hook(self):
        widget = self.form.fields['datetime'].widget
        self.assertEqual(widget.attrs['data-now'], 'true')
