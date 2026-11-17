from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import make_aware

from trips.models import Trip, TripType
from vehicles.models import Refueling, TripVehicle, Vehicle, VehicleType


def create_trip(user, **overrides):
    defaults = {
        'origin_city': 'São Paulo',
        'origin_state': 'SP',
        'destination_city': 'Curitiba',
        'destination_state': 'PR',
        'trip_type': TripType.CAR,
        'start_date': date(2026, 10, 1),
    }
    defaults.update(overrides)
    return Trip.objects.create(created_by=user, **defaults)


def create_refueling(trip, total_mileage):
    return Refueling.objects.create(
        trip=trip,
        city='Campinas',
        state='SP',
        liters=Decimal('10.00'),
        amount_spent=Decimal('50.00'),
        total_mileage=total_mileage,
        datetime=make_aware(datetime(2026, 10, 2, 8, 0)),
    )


class TripListAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='owner@example.com', password='strong-pass-123'
        )
        self.other = get_user_model().objects.create_user(
            email='other@example.com', password='strong-pass-123'
        )

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('home'))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('home')}"
        )

    def test_user_sees_all_trips_of_the_system(self):
        own_trip = create_trip(self.user)
        other_trip = create_trip(
            self.other,
            destination_city='Salvador',
            destination_state='BA',
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'trips/trip_list.html')
        self.assertEqual(
            list(response.context['trips']), [other_trip, own_trip]
        )
        self.assertContains(response, 'Salvador')

    def test_empty_state_is_shown_without_trips(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Nenhuma viagem cadastrada ainda')

    def test_list_shows_route_with_city_and_state(self):
        create_trip(self.user)
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'São Paulo/SP → Curitiba/PR')


class TripCreateViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='creator@example.com', password='strong-pass-123'
        )
        self.client.force_login(self.user)

    def _data(self, **overrides):
        data = {
            'origin_city': 'São Paulo',
            'origin_state': 'SP',
            'destination_city': 'Curitiba',
            'destination_state': 'PR',
            'trip_type': TripType.CAR,
            'start_date': '2026-10-01',
        }
        data.update(overrides)
        return data

    def test_get_renders_form(self):
        response = self.client.get(reverse('trip_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'trips/trip_form.html')

    def test_post_valid_creates_trip_with_creator(self):
        response = self.client.post(reverse('trip_create'), self._data())
        trip = Trip.objects.get(origin_city='São Paulo')
        self.assertEqual(trip.created_by, self.user)
        self.assertEqual(trip.origin_state, 'SP')
        self.assertEqual(trip.destination_city, 'Curitiba')
        self.assertEqual(trip.destination_state, 'PR')
        self.assertRedirects(
            response,
            f'/trip/{trip.pk}/vehicle/new/',
            fetch_redirect_response=False,
        )

    def test_post_car_trip_redirects_to_vehicle_registration(self):
        response = self.client.post(reverse('trip_create'), self._data())
        trip = Trip.objects.get(origin_city='São Paulo')
        self.assertEqual(response['Location'], f'/trip/{trip.pk}/vehicle/new/')

    def test_post_bus_trip_redirects_to_bus_registration(self):
        response = self.client.post(
            reverse('trip_create'),
            self._data(
                trip_type=TripType.BUS,
                origin_city='Campinas',
                end_date='2026-11-05',
            ),
        )
        trip = Trip.objects.get(origin_city='Campinas')
        self.assertEqual(response['Location'], f'/trip/{trip.pk}/bus/new/')

    def test_post_plane_trip_redirects_to_flight_registration(self):
        response = self.client.post(
            reverse('trip_create'),
            self._data(
                trip_type=TripType.PLANE,
                origin_city='Santos',
                end_date='2026-12-05',
            ),
        )
        trip = Trip.objects.get(origin_city='Santos')
        self.assertEqual(response['Location'], f'/trip/{trip.pk}/flight/new/')

    def test_post_car_ignores_end_date_sent_by_client(self):
        self.client.post(
            reverse('trip_create'), self._data(end_date='2026-10-05')
        )
        trip = Trip.objects.get(origin_city='São Paulo')
        self.assertIsNone(trip.end_date)

    def test_post_bus_without_end_date_does_not_create_trip(self):
        response = self.client.post(
            reverse('trip_create'),
            self._data(trip_type=TripType.BUS, origin_city='Campinas'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Trip.objects.count(), 0)

    def test_post_plane_without_end_date_does_not_create_trip(self):
        response = self.client.post(
            reverse('trip_create'),
            self._data(trip_type=TripType.PLANE, origin_city='Santos'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Trip.objects.count(), 0)

    def test_post_invalid_does_not_create_trip(self):
        response = self.client.post(
            reverse('trip_create'), self._data(origin_city='')
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Trip.objects.count(), 0)


class TripDetailViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email='owner-detail@example.com', password='strong-pass-123'
        )
        self.other = get_user_model().objects.create_user(
            email='other-detail@example.com', password='strong-pass-123'
        )
        self.trip = create_trip(self.owner)

    def test_owner_sees_trip_detail(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'trips/trip_detail.html')
        self.assertEqual(response.context['trip'], self.trip)

    def test_detail_shows_route_with_city_and_state(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertContains(response, 'São Paulo/SP → Curitiba/PR')

    def test_other_user_can_view_trip_detail(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['trip'], self.trip)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])


class TripDetailTransportSummaryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='summary@example.com', password='strong-pass-123'
        )
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_shows_transport_call_to_action_when_missing(self):
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertContains(
            response, reverse('vehicle_new', args=[self.trip.pk])
        )
        self.assertContains(response, 'Cadastrar veículo')

    def test_shows_summary_and_edit_link_when_registered(self):
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        TripVehicle.objects.create(
            trip=self.trip, vehicle=vehicle, initial_mileage=1000
        )
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertContains(response, 'Fiat Argo')
        self.assertContains(response, '1.000')
        self.assertContains(
            response, reverse('vehicle_edit', args=[self.trip.pk])
        )

    def test_shows_current_mileage_from_last_refueling(self):
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        TripVehicle.objects.create(
            trip=self.trip, vehicle=vehicle, initial_mileage=1000
        )
        create_refueling(self.trip, 1500)
        create_refueling(self.trip, 1800)
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertContains(response, 'Odômetro atual: 1.800 km')

    def test_current_mileage_defaults_to_initial_without_refuelings(self):
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR, brand='Fiat', model='Argo'
        )
        TripVehicle.objects.create(
            trip=self.trip, vehicle=vehicle, initial_mileage=1000
        )
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertContains(response, 'Odômetro atual: 1.000 km')

    def test_plane_trip_shows_flight_call_to_action(self):
        plane_trip = create_trip(
            self.user, trip_type=TripType.PLANE, origin_city='Santos'
        )
        response = self.client.get(
            reverse('trip_detail', args=[plane_trip.pk])
        )
        self.assertContains(
            response, reverse('flight_new', args=[plane_trip.pk])
        )
        self.assertContains(response, 'Cadastrar dados do voo')

    def test_car_trip_without_end_date_shows_finish_call_to_action(self):
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertContains(
            response, reverse('trip_finish', args=[self.trip.pk])
        )
        self.assertContains(response, 'Finalizar viagem')

    def test_car_trip_with_end_date_hides_finish_call_to_action(self):
        self.trip.end_date = date(2026, 10, 10)
        self.trip.save()
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertNotContains(response, 'Finalizar viagem')

    def test_bus_trip_hides_finish_call_to_action(self):
        bus_trip = create_trip(self.user, trip_type=TripType.BUS)
        response = self.client.get(
            reverse('trip_detail', args=[bus_trip.pk])
        )
        self.assertNotContains(response, 'Finalizar viagem')


class FinishTripViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email='finish-owner@example.com', password='strong-pass-123'
        )
        self.other = get_user_model().objects.create_user(
            email='finish-other@example.com', password='strong-pass-123'
        )
        self.trip = create_trip(self.owner)
        self.client.force_login(self.owner)

    def test_get_renders_form_with_today_default(self):
        response = self.client.get(
            reverse('trip_finish', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'trips/trip_finish.html')
        self.assertEqual(
            response.context['form'].fields['end_date'].initial, date.today()
        )

    def test_post_valid_sets_end_date_and_redirects_to_detail(self):
        response = self.client.post(
            reverse('trip_finish', args=[self.trip.pk]),
            {'end_date': '2026-10-15'},
        )
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.end_date, date(2026, 10, 15))
        self.assertRedirects(
            response, reverse('trip_detail', args=[self.trip.pk])
        )

    def test_post_end_date_before_start_is_invalid(self):
        response = self.client.post(
            reverse('trip_finish', args=[self.trip.pk]),
            {'end_date': '2026-09-30'},
        )
        self.assertEqual(response.status_code, 200)
        self.trip.refresh_from_db()
        self.assertIsNone(self.trip.end_date)

    def test_get_after_finished_returns_404(self):
        self.trip.end_date = date(2026, 10, 15)
        self.trip.save()
        response = self.client.get(
            reverse('trip_finish', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_post_after_finished_returns_404_and_keeps_end_date(self):
        self.trip.end_date = date(2026, 10, 15)
        self.trip.save()
        response = self.client.post(
            reverse('trip_finish', args=[self.trip.pk]),
            {'end_date': '2026-10-20'},
        )
        self.assertEqual(response.status_code, 404)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.end_date, date(2026, 10, 15))

    def test_non_car_trip_returns_404(self):
        bus_trip = create_trip(self.owner, trip_type=TripType.BUS)
        response = self.client.get(
            reverse('trip_finish', args=[bus_trip.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_other_user_can_finish_trip(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse('trip_finish', args=[self.trip.pk]),
            {'end_date': '2026-10-15'},
        )
        self.assertRedirects(
            response, reverse('trip_detail', args=[self.trip.pk])
        )
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.end_date, date(2026, 10, 15))

    def test_anonymous_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(
            reverse('trip_finish', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])


class TripDetailDashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='dashboard-view@example.com', password='strong-pass-123'
        )
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_context_has_dashboard_with_zero_totals(self):
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertIn('dashboard', response.context)
        self.assertEqual(
            response.context['dashboard']['grand_total'], Decimal('0.00')
        )

    def test_template_renders_totals_cards_and_chart_containers(self):
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertContains(response, 'Total gasto')
        self.assertContains(response, 'Abastecimento')
        self.assertContains(response, 'id="dashboard-chart-data"')
        self.assertContains(response, 'id="categoryChart"')
        self.assertContains(response, 'id="consumptionChart"')

    def test_charts_are_hidden_below_large_viewports(self):
        response = self.client.get(
            reverse('trip_detail', args=[self.trip.pk])
        )
        self.assertContains(response, 'd-none d-lg-block')


class BaseTemplateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='nav@example.com', password='strong-pass-123'
        )
        self.client.force_login(self.user)

    def test_base_template_is_used_and_navbar_shows_email(self):
        response = self.client.get(reverse('home'))
        self.assertTemplateUsed(response, 'base.html')
        self.assertTemplateUsed(response, 'includes/navbar.html')
        self.assertContains(response, 'nav@example.com')

    def test_navbar_logout_uses_post_form_with_csrf(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, f'action="{reverse("logout")}"')
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertContains(response, 'method="post"')

    def test_sidebar_links_to_home(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Viagens')

    def test_list_page_offers_new_trip_link(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, f'href="{reverse("trip_create")}"')
