from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import make_aware

from trips.models import Trip, TripType
from vehicles.forms import RefuelingForm
from vehicles.models import Refueling, TripVehicle, Vehicle, VehicleType

REFUELING_DATETIME = make_aware(datetime(2026, 10, 2, 8, 0))


def create_user(email):
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
        start_date=date(2026, 10, 1),
    )
    if with_vehicle:
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        TripVehicle.objects.create(
            trip=trip, vehicle=vehicle, initial_mileage=1000
        )
    return trip


def create_refueling(trip, total_mileage=1500, amount_spent='150.00'):
    return Refueling.objects.create(
        trip=trip,
        city='Campinas',
        state='SP',
        liters=Decimal('30.00'),
        amount_spent=Decimal(amount_spent),
        total_mileage=total_mileage,
        datetime=REFUELING_DATETIME,
    )


def refueling_data(**overrides):
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


class RefuelingAccessTests(TestCase):
    def setUp(self):
        self.owner = create_user('owner-refueling@example.com')
        self.other = create_user('other-refueling@example.com')
        self.trip = create_trip(self.owner)
        self.bus_trip = create_trip(self.owner, TripType.BUS)
        self.refueling = create_refueling(self.trip)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('refueling_list', args=[self.trip.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_other_user_can_access_list(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse('refueling_list', args=[self.trip.pk]))
        self.assertEqual(response.status_code, 200)

    def test_other_user_can_access_detail(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse('refueling_detail', args=[self.trip.pk, self.refueling.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_wrong_trip_type_gets_404(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('refueling_list', args=[self.bus_trip.pk])
        )
        self.assertEqual(response.status_code, 404)


class RefuelingListViewTests(TestCase):
    def setUp(self):
        self.user = create_user('list-refueling@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_renders_list_with_modal_form(self):
        response = self.client.get(reverse('refueling_list', args=[self.trip.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vehicles/refueling_list.html')
        self.assertContains(response, 'id="refuelingModal"')
        self.assertContains(
            response, f'action="{reverse("refueling_create", args=[self.trip.pk])}"'
        )
        self.assertContains(response, 'data-bs-toggle="modal"')
        self.assertContains(
            response, f'href="{reverse("trip_detail", args=[self.trip.pk])}"'
        )
        self.assertContains(response, 'Voltar para a viagem')
        self.assertIsInstance(response.context['form'], RefuelingForm)

    def test_modal_shows_current_mileage_from_last_refueling(self):
        create_refueling(self.trip, total_mileage=1500)
        create_refueling(self.trip, total_mileage=1800)
        response = self.client.get(reverse('refueling_list', args=[self.trip.pk]))
        self.assertContains(response, 'odômetro atual')
        self.assertContains(response, '1.800 km')

    def test_modal_shows_initial_mileage_without_refuelings(self):
        response = self.client.get(reverse('refueling_list', args=[self.trip.pk]))
        self.assertContains(response, '1.000 km')

    def test_modal_omits_mileage_without_trip_vehicle(self):
        trip = create_trip(self.user, with_vehicle=False)
        response = self.client.get(reverse('refueling_list', args=[trip.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'odômetro atual')

    def test_modal_form_has_masks_now_hook_and_state_first(self):
        response = self.client.get(reverse('refueling_list', args=[self.trip.pk]))
        content = response.content.decode()
        self.assertContains(response, 'data-ibge-pair')
        self.assertContains(response, 'data-mask="currency"')
        self.assertContains(response, 'data-now="true"')
        self.assertContains(response, 'js/form_masks.js')
        self.assertLess(
            content.index('name="state"'), content.index('name="city"')
        )

    def test_row_links_to_detail_without_detail_column(self):
        refueling = create_refueling(self.trip)
        response = self.client.get(reverse('refueling_list', args=[self.trip.pk]))
        self.assertContains(
            response,
            f'href="{reverse("refueling_detail", args=[self.trip.pk, refueling.pk])}"',
        )
        self.assertContains(response, 'stretched-link')
        self.assertContains(response, 'position-relative')
        self.assertNotContains(response, 'Detalhe')
        self.assertNotIn('<th></th>', response.content.decode())

    def test_shows_distance_traveled_column_instead_of_odometer(self):
        create_refueling(self.trip, total_mileage=1500)
        response = self.client.get(reverse('refueling_list', args=[self.trip.pk]))
        self.assertContains(response, '<th>Distância percorrida</th>', html=True)
        self.assertNotContains(response, '<th>Odômetro</th>', html=True)
        self.assertContains(response, '500 km')

    def test_distance_traveled_uses_previous_refueling(self):
        create_refueling(self.trip, total_mileage=1200)
        create_refueling(self.trip, total_mileage=1800)
        response = self.client.get(reverse('refueling_list', args=[self.trip.pk]))
        self.assertContains(response, '600 km')
        self.assertContains(response, '200 km')

    def test_distance_traveled_shows_dash_without_trip_vehicle(self):
        trip = create_trip(self.user, with_vehicle=False)
        create_refueling(trip)
        response = self.client.get(reverse('refueling_list', args=[trip.pk]))
        self.assertContains(response, '— km')

    def test_lists_highest_mileage_first(self):
        lower = create_refueling(self.trip, total_mileage=1200)
        higher = create_refueling(self.trip, total_mileage=1800)
        response = self.client.get(reverse('refueling_list', args=[self.trip.pk]))
        self.assertEqual(
            list(response.context['refuelings']), [higher, lower]
        )

    def test_empty_state_is_shown_without_refuelings(self):
        response = self.client.get(reverse('refueling_list', args=[self.trip.pk]))
        self.assertContains(response, 'Nenhum abastecimento')


class RefuelingCreateViewTests(TestCase):
    def setUp(self):
        self.user = create_user('create-refueling@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_get_renders_full_form(self):
        response = self.client.get(
            reverse('refueling_create', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vehicles/refueling_form.html')

    def test_post_valid_creates_and_redirects_to_list(self):
        response = self.client.post(
            reverse('refueling_create', args=[self.trip.pk]), refueling_data()
        )
        self.assertRedirects(
            response, reverse('refueling_list', args=[self.trip.pk])
        )
        refueling = Refueling.objects.get(trip=self.trip)
        self.assertEqual(refueling.total_mileage, 1500)

    def test_post_invalid_shows_errors_and_does_not_create(self):
        response = self.client.post(
            reverse('refueling_create', args=[self.trip.pk]),
            refueling_data(total_mileage='900'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Refueling.objects.count(), 0)
        self.assertFormError(
            response.context['form'], 'total_mileage', 'Informe um odômetro maior ou igual ao inicial da viagem.'
        )


class RefuelingDetailViewTests(TestCase):
    def setUp(self):
        self.user = create_user('detail-refueling@example.com')
        self.trip = create_trip(self.user)
        self.refueling = create_refueling(self.trip)
        self.client.force_login(self.user)

    def test_shows_calculated_values(self):
        response = self.client.get(
            reverse('refueling_detail', args=[self.trip.pk, self.refueling.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['refueling'], self.refueling)
        self.assertContains(response, 'Campinas/SP')
        self.assertContains(response, '16,67')
        self.assertContains(response, '0,30')

    def test_offers_edit_link(self):
        response = self.client.get(
            reverse('refueling_detail', args=[self.trip.pk, self.refueling.pk])
        )
        self.assertContains(
            response,
            reverse('refueling_edit', args=[self.trip.pk, self.refueling.pk]),
        )


class RefuelingUpdateViewTests(TestCase):
    def setUp(self):
        self.user = create_user('update-refueling@example.com')
        self.trip = create_trip(self.user)
        self.refueling = create_refueling(self.trip)
        self.client.force_login(self.user)

    def test_get_prefills_existing_data(self):
        response = self.client.get(
            reverse('refueling_edit', args=[self.trip.pk, self.refueling.pk])
        )
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.initial['city'], 'Campinas')
        self.assertEqual(form.initial['total_mileage'], 1500)

    def test_post_updates_and_redirects_to_list(self):
        response = self.client.post(
            reverse('refueling_edit', args=[self.trip.pk, self.refueling.pk]),
            refueling_data(city='Jundiaí', total_mileage='1600'),
        )
        self.assertRedirects(
            response, reverse('refueling_list', args=[self.trip.pk])
        )
        self.refueling.refresh_from_db()
        self.assertEqual(self.refueling.city, 'Jundiaí')
        self.assertEqual(self.refueling.total_mileage, 1600)

    def test_missing_refueling_gets_404(self):
        missing = create_refueling(self.trip, total_mileage=1800)
        missing_pk = missing.pk
        missing.delete()
        response = self.client.get(
            reverse('refueling_edit', args=[self.trip.pk, missing_pk])
        )
        self.assertEqual(response.status_code, 404)
