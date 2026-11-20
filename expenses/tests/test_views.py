from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from django.utils.timezone import localdate, make_aware

from expenses.models import Lodging, Meal, Sightseeing
from trips.models import Trip, TripType

CHECK_IN = make_aware(datetime(2026, 10, 2, 14, 0))
CHECK_OUT = make_aware(datetime(2026, 10, 5, 11, 0))
MEAL_DATETIME = make_aware(datetime(2026, 10, 2, 12, 30))


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


def create_lodging(trip, check_in=CHECK_IN, amount='450.00'):
    return Lodging.objects.create(
        trip=trip,
        city='Curitiba',
        state='PR',
        amount_spent=Decimal(amount),
        check_in=check_in,
        check_out=CHECK_OUT,
    )


def create_meal(trip, when=MEAL_DATETIME, amount='35.00'):
    return Meal.objects.create(
        trip=trip,
        city='Curitiba',
        state='PR',
        amount_spent=Decimal(amount),
        datetime=when,
    )


def create_sightseeing(trip, amount='80.00', description='Museu'):
    return Sightseeing.objects.create(
        trip=trip, amount_spent=Decimal(amount), description=description
    )


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


class ExpenseAccessTests(TestCase):
    def setUp(self):
        self.owner = create_user('owner-expenses@example.com')
        self.other = create_user('other-expenses@example.com')
        self.car_trip = create_trip(self.owner)
        self.plane_trip = create_trip(self.owner, TripType.PLANE)
        self.bus_trip = create_trip(self.owner, TripType.BUS)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(
            reverse('lodging_list', args=[self.car_trip.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_other_user_can_access_lodging_list(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse('lodging_list', args=[self.car_trip.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_sightseeing_on_car_trip_gets_404(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('sightseeing_list', args=[self.car_trip.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_sightseeing_on_plane_trip_gets_404(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('sightseeing_list', args=[self.plane_trip.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_sightseeing_on_bus_trip_is_allowed(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('sightseeing_list', args=[self.bus_trip.pk])
        )
        self.assertEqual(response.status_code, 200)


class LodgingViewTests(TestCase):
    def setUp(self):
        self.user = create_user('lodging-view@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_list_renders_template_with_newest_first(self):
        earlier = create_lodging(
            self.trip, check_in=make_aware(datetime(2026, 10, 1, 14, 0))
        )
        later = create_lodging(
            self.trip, check_in=make_aware(datetime(2026, 10, 4, 14, 0))
        )
        response = self.client.get(
            reverse('lodging_list', args=[self.trip.pk])
        )
        self.assertTemplateUsed(response, 'expenses/lodging_list.html')
        self.assertEqual(list(response.context['lodgings']), [later, earlier])
        self.assertContains(
            response, f'href="{reverse("trip_detail", args=[self.trip.pk])}"'
        )
        self.assertContains(response, 'Voltar para a viagem')

    def test_list_rows_link_to_detail_without_detail_column(self):
        lodging = create_lodging(self.trip)
        response = self.client.get(reverse('lodging_list', args=[self.trip.pk]))
        self.assertContains(
            response,
            f'href="{reverse("lodging_detail", args=[self.trip.pk, lodging.pk])}"',
        )
        self.assertContains(response, 'stretched-link')
        self.assertContains(response, 'position-relative')
        self.assertNotContains(response, 'Detalhe')
        self.assertNotIn('<th></th>', response.content.decode())

    def test_create_get_renders_form(self):
        response = self.client.get(
            reverse('lodging_create', args=[self.trip.pk])
        )
        self.assertTemplateUsed(response, 'expenses/lodging_form.html')

    def test_create_form_has_masks_now_hook_and_state_first(self):
        response = self.client.get(
            reverse('lodging_create', args=[self.trip.pk])
        )
        content = response.content.decode()
        self.assertContains(response, 'data-ibge-pair')
        self.assertContains(response, 'data-mask="currency"')
        self.assertContains(response, 'data-now="true"')
        self.assertContains(response, 'js/form_masks.js')
        self.assertLess(
            content.index('name="state"'), content.index('name="city"')
        )

    def test_create_post_redirects_to_list(self):
        response = self.client.post(
            reverse('lodging_create', args=[self.trip.pk]), lodging_data()
        )
        self.assertRedirects(
            response, reverse('lodging_list', args=[self.trip.pk])
        )
        lodging = Lodging.objects.get(trip=self.trip)
        self.assertEqual(str(lodging.amount_spent), '450.00')

    def test_detail_shows_nights_and_edit_link(self):
        lodging = create_lodging(self.trip)
        response = self.client.get(
            reverse('lodging_detail', args=[self.trip.pk, lodging.pk])
        )
        self.assertEqual(response.context['lodging'], lodging)
        self.assertContains(response, '3')
        self.assertContains(
            response,
            reverse('lodging_edit', args=[self.trip.pk, lodging.pk]),
        )

    def test_edit_updates_lodging(self):
        lodging = create_lodging(self.trip)
        response = self.client.post(
            reverse('lodging_edit', args=[self.trip.pk, lodging.pk]),
            lodging_data(amount_spent='500.00'),
        )
        self.assertRedirects(
            response, reverse('lodging_list', args=[self.trip.pk])
        )
        lodging.refresh_from_db()
        self.assertEqual(str(lodging.amount_spent), '500.00')


class MealViewTests(TestCase):
    def setUp(self):
        self.user = create_user('meal-view@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_list_renders_template_with_newest_first(self):
        earlier = create_meal(
            self.trip, when=make_aware(datetime(2026, 10, 2, 12, 0))
        )
        later = create_meal(
            self.trip, when=make_aware(datetime(2026, 10, 3, 20, 0))
        )
        response = self.client.get(reverse('meal_list', args=[self.trip.pk]))
        self.assertTemplateUsed(response, 'expenses/meal_list.html')
        self.assertEqual(list(response.context['meals']), [later, earlier])
        self.assertContains(
            response, f'href="{reverse("trip_detail", args=[self.trip.pk])}"'
        )
        self.assertContains(response, 'Voltar para a viagem')

    def test_list_rows_link_to_detail_without_detail_column(self):
        meal = create_meal(self.trip)
        response = self.client.get(reverse('meal_list', args=[self.trip.pk]))
        self.assertContains(
            response,
            f'href="{reverse("meal_detail", args=[self.trip.pk, meal.pk])}"',
        )
        self.assertContains(response, 'stretched-link')
        self.assertContains(response, 'position-relative')
        self.assertNotContains(response, 'Detalhe')
        self.assertNotIn('<th></th>', response.content.decode())

    def test_create_form_has_masks_now_hook_and_state_first(self):
        response = self.client.get(
            reverse('meal_create', args=[self.trip.pk])
        )
        content = response.content.decode()
        self.assertContains(response, 'data-ibge-pair')
        self.assertContains(response, 'data-mask="currency"')
        self.assertContains(response, 'data-now="true"')
        self.assertContains(response, 'js/form_masks.js')
        self.assertLess(
            content.index('name="state"'), content.index('name="city"')
        )

    def test_create_post_redirects_to_list(self):
        response = self.client.post(
            reverse('meal_create', args=[self.trip.pk]), meal_data()
        )
        self.assertRedirects(
            response, reverse('meal_list', args=[self.trip.pk])
        )
        self.assertEqual(Meal.objects.filter(trip=self.trip).count(), 1)

    def test_detail_and_edit(self):
        meal = create_meal(self.trip)
        detail = self.client.get(
            reverse('meal_detail', args=[self.trip.pk, meal.pk])
        )
        self.assertEqual(detail.context['meal'], meal)
        response = self.client.post(
            reverse('meal_edit', args=[self.trip.pk, meal.pk]),
            meal_data(city='Jundiaí'),
        )
        self.assertRedirects(
            response, reverse('meal_list', args=[self.trip.pk])
        )
        meal.refresh_from_db()
        self.assertEqual(meal.city, 'Jundiaí')


class SightseeingViewTests(TestCase):
    def setUp(self):
        self.user = create_user('sightseeing-view@example.com')
        self.trip = create_trip(self.user, TripType.BUS)
        self.client.force_login(self.user)

    def test_list_renders_template(self):
        sightseeing = create_sightseeing(self.trip)
        response = self.client.get(
            reverse('sightseeing_list', args=[self.trip.pk])
        )
        self.assertTemplateUsed(
            response, 'expenses/sightseeing_list.html'
        )
        self.assertEqual(list(response.context['sightseeings']), [sightseeing])
        self.assertContains(
            response, f'href="{reverse("trip_detail", args=[self.trip.pk])}"'
        )
        self.assertContains(response, 'Voltar para a viagem')

    def test_list_rows_link_to_detail_without_detail_column(self):
        sightseeing = create_sightseeing(self.trip)
        response = self.client.get(
            reverse('sightseeing_list', args=[self.trip.pk])
        )
        self.assertContains(
            response,
            f'href="{reverse("sightseeing_detail", args=[self.trip.pk, sightseeing.pk])}"',
        )
        self.assertContains(response, 'stretched-link')
        self.assertContains(response, 'position-relative')
        self.assertNotContains(response, 'Detalhe')
        self.assertNotIn('<th></th>', response.content.decode())

    def test_create_form_has_currency_mask_and_script(self):
        response = self.client.get(
            reverse('sightseeing_create', args=[self.trip.pk])
        )
        self.assertContains(response, 'data-mask="currency"')
        self.assertContains(response, 'js/form_masks.js')

    def test_create_post_redirects_to_list(self):
        response = self.client.post(
            reverse('sightseeing_create', args=[self.trip.pk]),
            {'amount_spent': '80.00', 'description': 'Museu'},
        )
        self.assertRedirects(
            response, reverse('sightseeing_list', args=[self.trip.pk])
        )
        self.assertEqual(Sightseeing.objects.filter(trip=self.trip).count(), 1)

    def test_detail_and_edit(self):
        sightseeing = create_sightseeing(self.trip)
        detail = self.client.get(
            reverse('sightseeing_detail', args=[self.trip.pk, sightseeing.pk])
        )
        self.assertEqual(detail.context['sightseeing'], sightseeing)
        response = self.client.post(
            reverse('sightseeing_edit', args=[self.trip.pk, sightseeing.pk]),
            {'amount_spent': '95.00', 'description': 'Parque'},
        )
        self.assertRedirects(
            response, reverse('sightseeing_list', args=[self.trip.pk])
        )
        sightseeing.refresh_from_db()
        self.assertEqual(sightseeing.description, 'Parque')


class LodgingListCompletedTripTests(TestCase):
    def setUp(self):
        self.user = create_user('completed-lodging@example.com')
        self.client.force_login(self.user)

    def test_completed_trip_hides_create_button(self):
        trip = create_trip(self.user, end_datetime=timezone.now() - timedelta(hours=1))
        create_lodging(trip)
        response = self.client.get(reverse('lodging_list', args=[trip.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response, f'href="{reverse("lodging_create", args=[trip.pk])}"'
        )
        self.assertNotContains(response, 'Nova hospedagem')
        self.assertContains(response, 'id="offline-sync-panel"')

    def test_in_progress_trip_keeps_create_button(self):
        trip = create_trip(self.user)
        response = self.client.get(reverse('lodging_list', args=[trip.pk]))
        self.assertContains(
            response, f'href="{reverse("lodging_create", args=[trip.pk])}"'
        )
        self.assertContains(response, 'Nova hospedagem')


class MealListCompletedTripTests(TestCase):
    def setUp(self):
        self.user = create_user('completed-meal@example.com')
        self.client.force_login(self.user)

    def test_completed_trip_hides_create_button(self):
        trip = create_trip(self.user, end_datetime=timezone.now() - timedelta(hours=1))
        create_meal(trip)
        response = self.client.get(reverse('meal_list', args=[trip.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response, f'href="{reverse("meal_create", args=[trip.pk])}"'
        )
        self.assertNotContains(response, 'Nova alimentação')
        self.assertContains(response, 'id="offline-sync-panel"')

    def test_in_progress_trip_keeps_create_button(self):
        trip = create_trip(self.user)
        response = self.client.get(reverse('meal_list', args=[trip.pk]))
        self.assertContains(
            response, f'href="{reverse("meal_create", args=[trip.pk])}"'
        )
        self.assertContains(response, 'Nova alimentação')


class SightseeingListCompletedTripTests(TestCase):
    def setUp(self):
        self.user = create_user('completed-sightseeing@example.com')
        self.client.force_login(self.user)

    def test_completed_trip_hides_create_button(self):
        trip = create_trip(self.user, TripType.BUS, end_datetime=timezone.now() - timedelta(hours=1))
        create_sightseeing(trip)
        response = self.client.get(
            reverse('sightseeing_list', args=[trip.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            f'href="{reverse("sightseeing_create", args=[trip.pk])}"',
        )
        self.assertNotContains(response, 'Novo passeio')
        self.assertContains(response, 'id="offline-sync-panel"')

    def test_in_progress_trip_keeps_create_button(self):
        trip = create_trip(
            self.user,
            TripType.BUS,
            end_datetime=timezone.now() + timedelta(days=1),
        )
        response = self.client.get(
            reverse('sightseeing_list', args=[trip.pk])
        )
        self.assertContains(
            response,
            f'href="{reverse("sightseeing_create", args=[trip.pk])}"',
        )
        self.assertContains(response, 'Novo passeio')


class TripDetailLaunchLinksTests(TestCase):
    def setUp(self):
        self.user = create_user('links@example.com')
        self.client.force_login(self.user)

    def _detail(self, trip):
        return self.client.get(reverse('trip_detail', args=[trip.pk]))

    def test_car_trip_shows_only_compatible_categories(self):
        trip = create_trip(self.user)
        response = self._detail(trip)
        self.assertContains(response, reverse('refueling_list', args=[trip.pk]))
        self.assertContains(response, reverse('lodging_list', args=[trip.pk]))
        self.assertContains(response, reverse('meal_list', args=[trip.pk]))
        self.assertNotContains(
            response, reverse('sightseeing_list', args=[trip.pk])
        )

    def test_plane_trip_shows_only_compatible_categories(self):
        trip = create_trip(self.user, TripType.PLANE)
        response = self._detail(trip)
        self.assertContains(response, reverse('lodging_list', args=[trip.pk]))
        self.assertContains(response, reverse('meal_list', args=[trip.pk]))
        self.assertNotContains(
            response, reverse('refueling_list', args=[trip.pk])
        )
        self.assertNotContains(
            response, reverse('sightseeing_list', args=[trip.pk])
        )

    def test_bus_trip_shows_only_compatible_categories(self):
        trip = create_trip(self.user, TripType.BUS)
        response = self._detail(trip)
        self.assertContains(response, reverse('lodging_list', args=[trip.pk]))
        self.assertContains(response, reverse('meal_list', args=[trip.pk]))
        self.assertContains(
            response, reverse('sightseeing_list', args=[trip.pk])
        )
        self.assertNotContains(
            response, reverse('refueling_list', args=[trip.pk])
        )
