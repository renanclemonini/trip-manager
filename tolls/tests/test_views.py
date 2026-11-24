from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import make_aware

from tolls.forms import TollForm
from tolls.models import Toll
from trips.models import Trip, TripType


TOLL_DATETIME = make_aware(datetime(2026, 10, 2, 8, 0))


def create_user(email):
    return get_user_model().objects.create_user(
        email=email, password='strong-pass-123'
    )


def create_trip(user, trip_type=TripType.CAR, end_datetime=None):
    return Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=trip_type,
        start_datetime=timezone.now() - timedelta(days=1),
        end_datetime=end_datetime,
    )


def create_toll(trip, amount_spent='25.00', when=None):
    return Toll.objects.create(
        trip=trip,
        location='Praça ABC',
        amount_spent=Decimal(amount_spent),
        datetime=when or TOLL_DATETIME,
    )


def toll_data(**overrides):
    data = {
        'location': 'Praça ABC',
        'amount_spent': '25.00',
        'datetime': '2026-10-02T08:00',
    }
    data.update(overrides)
    return data


class TollAccessTests(TestCase):
    def setUp(self):
        self.owner = create_user('owner-toll@example.com')
        self.other = create_user('other-toll@example.com')
        self.trip = create_trip(self.owner)
        self.bus_trip = create_trip(self.owner, TripType.BUS)
        self.toll = create_toll(self.trip)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('toll_list', args=[self.trip.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_other_user_can_access_list(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse('toll_list', args=[self.trip.pk]))
        self.assertEqual(response.status_code, 200)

    def test_other_user_can_access_detail(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse('toll_detail', args=[self.trip.pk, self.toll.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_wrong_trip_type_gets_404(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('toll_list', args=[self.bus_trip.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_plane_trip_gets_404(self):
        plane_trip = create_trip(self.owner, TripType.PLANE)
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('toll_list', args=[plane_trip.pk])
        )
        self.assertEqual(response.status_code, 404)


class TollListViewTests(TestCase):
    def setUp(self):
        self.user = create_user('list-toll@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_renders_list_with_modal_form(self):
        response = self.client.get(reverse('toll_list', args=[self.trip.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tolls/toll_list.html')
        self.assertContains(response, 'id="tollModal"')
        self.assertContains(
            response,
            f'action="{reverse("toll_create", args=[self.trip.pk])}"',
        )
        self.assertContains(response, 'data-bs-toggle="modal"')
        self.assertContains(
            response, f'href="{reverse("trip_detail", args=[self.trip.pk])}"'
        )
        self.assertContains(response, 'Voltar para a viagem')
        self.assertIsInstance(response.context['form'], TollForm)

    def test_modal_form_has_masks_and_now_hook(self):
        response = self.client.get(reverse('toll_list', args=[self.trip.pk]))
        self.assertContains(response, 'data-mask="currency"')
        self.assertContains(response, 'data-now="true"')
        self.assertContains(response, 'js/form_masks.js')

    def test_row_links_to_detail_without_detail_column(self):
        toll = create_toll(self.trip)
        response = self.client.get(reverse('toll_list', args=[self.trip.pk]))
        self.assertContains(
            response,
            f'href="{reverse("toll_detail", args=[self.trip.pk, toll.pk])}"',
        )
        self.assertContains(response, 'stretched-link')
        self.assertContains(response, 'position-relative')
        self.assertNotContains(response, 'Detalhe')

    def test_lists_most_recent_first(self):
        earlier = create_toll(
            self.trip, when=make_aware(datetime(2026, 10, 2, 8, 0))
        )
        later = create_toll(
            self.trip, when=make_aware(datetime(2026, 10, 2, 9, 0))
        )
        response = self.client.get(reverse('toll_list', args=[self.trip.pk]))
        self.assertEqual(list(response.context['tolls']), [later, earlier])

    def test_empty_state_is_shown_without_tolls(self):
        response = self.client.get(reverse('toll_list', args=[self.trip.pk]))
        self.assertContains(response, 'Nenhum pedágio')


class TollListCompletedTripTests(TestCase):
    """RF29 exception: toll creation stays available on completed trips."""

    def setUp(self):
        self.user = create_user('completed-toll@example.com')
        self.client.force_login(self.user)

    def test_completed_trip_keeps_create_button_and_modal(self):
        trip = create_trip(
            self.user, end_datetime=timezone.now() - timedelta(hours=1)
        )
        response = self.client.get(reverse('toll_list', args=[trip.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-bs-toggle="modal"')
        self.assertContains(response, 'id="tollModal"')
        self.assertContains(response, 'Novo pedágio')

    def test_completed_trip_keeps_list_and_offline_sync_panel(self):
        trip = create_trip(
            self.user, end_datetime=timezone.now() - timedelta(hours=1)
        )
        toll = create_toll(trip)
        response = self.client.get(reverse('toll_list', args=[trip.pk]))
        self.assertContains(response, 'id="offline-sync-panel"')
        self.assertContains(
            response,
            f'href="{reverse("toll_detail", args=[trip.pk, toll.pk])}"',
        )

    def test_completed_trip_other_entries_still_hide_creation(self):
        trip = create_trip(
            self.user, end_datetime=timezone.now() - timedelta(hours=1)
        )
        response = self.client.get(reverse('refueling_list', args=[trip.pk]))
        self.assertNotContains(response, 'Novo abastecimento')
        self.assertNotContains(response, 'id="refuelingModal"')
        response = self.client.get(reverse('lodging_list', args=[trip.pk]))
        self.assertNotContains(response, 'Nova hospedagem')
        self.assertNotContains(
            response, reverse('lodging_create', args=[trip.pk])
        )
        response = self.client.get(reverse('meal_list', args=[trip.pk]))
        self.assertNotContains(response, 'Nova alimentação')
        self.assertNotContains(
            response, reverse('meal_create', args=[trip.pk])
        )


class TollCreateViewTests(TestCase):
    def setUp(self):
        self.user = create_user('create-toll@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_get_renders_full_form(self):
        response = self.client.get(
            reverse('toll_create', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tolls/toll_form.html')

    def test_post_valid_creates_and_redirects_to_list(self):
        response = self.client.post(
            reverse('toll_create', args=[self.trip.pk]), toll_data()
        )
        self.assertRedirects(
            response, reverse('toll_list', args=[self.trip.pk])
        )
        toll = Toll.objects.get(trip=self.trip)
        self.assertEqual(toll.location, 'Praça ABC')
        self.assertEqual(toll.amount_spent, Decimal('25.00'))

    def test_post_invalid_shows_errors_and_does_not_create(self):
        response = self.client.post(
            reverse('toll_create', args=[self.trip.pk]),
            toll_data(amount_spent='0.00'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Toll.objects.count(), 0)
        self.assertFormError(
            response.context['form'], 'amount_spent', 'Certifique-se que este valor seja maior ou igual a 0.01.'
        )


class TollDetailViewTests(TestCase):
    def setUp(self):
        self.user = create_user('detail-toll@example.com')
        self.trip = create_trip(self.user)
        self.toll = create_toll(self.trip)
        self.client.force_login(self.user)

    def test_shows_values(self):
        response = self.client.get(
            reverse('toll_detail', args=[self.trip.pk, self.toll.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['toll'], self.toll)
        self.assertContains(response, 'Praça ABC')
        self.assertContains(response, 'R$ 25,00')

    def test_offers_edit_link(self):
        response = self.client.get(
            reverse('toll_detail', args=[self.trip.pk, self.toll.pk])
        )
        self.assertContains(
            response,
            reverse('toll_edit', args=[self.trip.pk, self.toll.pk]),
        )


class TollUpdateViewTests(TestCase):
    def setUp(self):
        self.user = create_user('update-toll@example.com')
        self.trip = create_trip(self.user)
        self.toll = create_toll(self.trip)
        self.client.force_login(self.user)

    def test_get_prefills_existing_data(self):
        response = self.client.get(
            reverse('toll_edit', args=[self.trip.pk, self.toll.pk])
        )
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.initial['location'], 'Praça ABC')
        self.assertEqual(str(form.initial['amount_spent']), '25.00')

    def test_post_updates_and_redirects_to_list(self):
        response = self.client.post(
            reverse('toll_edit', args=[self.trip.pk, self.toll.pk]),
            toll_data(location='Praça XYZ', amount_spent='30.00'),
        )
        self.assertRedirects(
            response, reverse('toll_list', args=[self.trip.pk])
        )
        self.toll.refresh_from_db()
        self.assertEqual(self.toll.location, 'Praça XYZ')
        self.assertEqual(self.toll.amount_spent, Decimal('30.00'))

    def test_missing_toll_gets_404(self):
        missing = create_toll(self.trip)
        missing_pk = missing.pk
        missing.delete()
        response = self.client.get(
            reverse('toll_edit', args=[self.trip.pk, missing_pk])
        )
        self.assertEqual(response.status_code, 404)
