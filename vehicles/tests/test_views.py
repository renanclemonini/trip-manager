from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from trips.models import Trip, TripType
from vehicles.models import BusTrip, FlightTrip, TripVehicle, Vehicle, VehicleType


def create_user(email):
    return get_user_model().objects.create_user(
        email=email, password='strong-pass-123'
    )


def create_trip(user, trip_type=TripType.CAR):
    return Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=trip_type,
        start_date=date(2026, 10, 1),
    )


class TransportAccessTests(TestCase):
    def setUp(self):
        self.owner = create_user('owner-transport@example.com')
        self.other = create_user('other-transport@example.com')
        self.car_trip = create_trip(self.owner)
        self.bus_trip = create_trip(self.owner, TripType.BUS)
        self.plane_trip = create_trip(self.owner, TripType.PLANE)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(
            reverse('vehicle_new', args=[self.car_trip.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_other_user_can_access_vehicle_form(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse('vehicle_new', args=[self.car_trip.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_wrong_trip_type_gets_404(self):
        self.client.force_login(self.owner)
        cases = [
            ('vehicle_new', self.bus_trip.pk),
            ('vehicle_edit', self.bus_trip.pk),
            ('bus_new', self.car_trip.pk),
            ('bus_edit', self.car_trip.pk),
            ('flight_new', self.bus_trip.pk),
            ('flight_edit', self.plane_trip.pk),
        ]
        for url_name, trip_id in cases:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name, args=[trip_id]))
                self.assertEqual(response.status_code, 404)


class VehicleTransportViewTests(TestCase):
    def setUp(self):
        self.user = create_user('vehicle-view@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def _data(self, **overrides):
        data = {'brand': 'Fiat', 'model': 'Argo', 'initial_mileage': '1000'}
        data.update(overrides)
        return data

    def test_get_renders_form(self):
        response = self.client.get(reverse('vehicle_new', args=[self.trip.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vehicles/vehicle_form.html')
        self.assertContains(response, 'data-mask="integer"')
        self.assertContains(response, 'js/form_masks.js')

    def test_post_valid_creates_and_redirects_to_trip_detail(self):
        response = self.client.post(
            reverse('vehicle_new', args=[self.trip.pk]), self._data()
        )
        self.assertRedirects(
            response, reverse('trip_detail', args=[self.trip.pk])
        )
        trip_vehicle = TripVehicle.objects.get(trip=self.trip)
        self.assertEqual(trip_vehicle.initial_mileage, 1000)
        self.assertEqual(trip_vehicle.vehicle.brand, 'Fiat')

    def test_new_redirects_to_edit_when_already_registered(self):
        self.client.post(
            reverse('vehicle_new', args=[self.trip.pk]), self._data()
        )
        response = self.client.get(
            reverse('vehicle_new', args=[self.trip.pk])
        )
        self.assertRedirects(
            response, reverse('vehicle_edit', args=[self.trip.pk])
        )

    def test_edit_without_registration_gets_404(self):
        response = self.client.get(
            reverse('vehicle_edit', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_get_edit_prefills_existing_data(self):
        self.client.post(
            reverse('vehicle_new', args=[self.trip.pk]), self._data()
        )
        response = self.client.get(
            reverse('vehicle_edit', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial['brand'], 'Fiat')
        self.assertEqual(response.context['form'].initial['model'], 'Argo')

    def test_post_edit_updates_and_redirects(self):
        self.client.post(
            reverse('vehicle_new', args=[self.trip.pk]), self._data()
        )
        response = self.client.post(
            reverse('vehicle_edit', args=[self.trip.pk]),
            self._data(brand='VW', model='Gol', initial_mileage='2500'),
        )
        self.assertRedirects(
            response, reverse('trip_detail', args=[self.trip.pk])
        )
        trip_vehicle = TripVehicle.objects.get(trip=self.trip)
        self.assertEqual(trip_vehicle.initial_mileage, 2500)
        self.assertEqual(trip_vehicle.vehicle.brand, 'VW')


class BusTransportViewTests(TestCase):
    def setUp(self):
        self.user = create_user('bus-view@example.com')
        self.trip = create_trip(self.user, TripType.BUS)
        self.client.force_login(self.user)

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

    def test_get_renders_form(self):
        response = self.client.get(reverse('bus_new', args=[self.trip.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vehicles/bus_trip_form.html')
        self.assertContains(response, 'data-mask="currency"')
        self.assertContains(response, 'js/form_masks.js')

    def test_post_valid_creates_and_redirects_to_trip_detail(self):
        response = self.client.post(
            reverse('bus_new', args=[self.trip.pk]), self._data()
        )
        self.assertRedirects(
            response, reverse('trip_detail', args=[self.trip.pk])
        )
        bus_trip = BusTrip.objects.get(trip=self.trip)
        self.assertEqual(bus_trip.company, 'Viação Cometa')
        self.assertEqual(bus_trip.vehicle.vehicle_type, VehicleType.BUS)

    def test_new_redirects_to_edit_when_already_registered(self):
        self.client.post(reverse('bus_new', args=[self.trip.pk]), self._data())
        response = self.client.get(reverse('bus_new', args=[self.trip.pk]))
        self.assertRedirects(
            response, reverse('bus_edit', args=[self.trip.pk])
        )

    def test_edit_without_registration_gets_404(self):
        response = self.client.get(reverse('bus_edit', args=[self.trip.pk]))
        self.assertEqual(response.status_code, 404)

    def test_post_edit_updates_and_redirects(self):
        self.client.post(reverse('bus_new', args=[self.trip.pk]), self._data())
        response = self.client.post(
            reverse('bus_edit', args=[self.trip.pk]),
            self._data(company='Águia Branca', amount_paid='200.00'),
        )
        self.assertRedirects(
            response, reverse('trip_detail', args=[self.trip.pk])
        )
        bus_trip = BusTrip.objects.get(trip=self.trip)
        self.assertEqual(bus_trip.company, 'Águia Branca')
        self.assertEqual(str(bus_trip.amount_paid), '200.00')


class FlightTransportViewTests(TestCase):
    def setUp(self):
        self.user = create_user('flight-view@example.com')
        self.trip = create_trip(self.user, TripType.PLANE)
        self.client.force_login(self.user)

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

    def test_get_renders_form(self):
        response = self.client.get(reverse('flight_new', args=[self.trip.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vehicles/flight_trip_form.html')
        self.assertContains(response, 'data-mask="currency"')
        self.assertContains(response, 'data-now="true"')
        self.assertContains(response, 'js/form_masks.js')

    def test_post_valid_creates_and_redirects_to_trip_detail(self):
        response = self.client.post(
            reverse('flight_new', args=[self.trip.pk]), self._data()
        )
        self.assertRedirects(
            response, reverse('trip_detail', args=[self.trip.pk])
        )
        flight_trip = FlightTrip.objects.get(trip=self.trip)
        self.assertEqual(flight_trip.airline, 'LATAM')
        self.assertEqual(str(flight_trip.ticket_price), '1234.56')

    def test_new_redirects_to_edit_when_already_registered(self):
        self.client.post(
            reverse('flight_new', args=[self.trip.pk]), self._data()
        )
        response = self.client.get(
            reverse('flight_new', args=[self.trip.pk])
        )
        self.assertRedirects(
            response, reverse('flight_edit', args=[self.trip.pk])
        )

    def test_edit_without_registration_gets_404(self):
        response = self.client.get(
            reverse('flight_edit', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_post_invalid_does_not_create(self):
        response = self.client.post(
            reverse('flight_new', args=[self.trip.pk]),
            self._data(return_datetime='2026-11-01T09:00'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FlightTrip.objects.count(), 0)

    def test_post_edit_updates_and_redirects(self):
        self.client.post(
            reverse('flight_new', args=[self.trip.pk]), self._data()
        )
        response = self.client.post(
            reverse('flight_edit', args=[self.trip.pk]),
            self._data(airline='GOL', aircraft_model='Boeing 737'),
        )
        self.assertRedirects(
            response, reverse('trip_detail', args=[self.trip.pk])
        )
        flight_trip = FlightTrip.objects.get(trip=self.trip)
        self.assertEqual(flight_trip.airline, 'GOL')
        self.assertEqual(flight_trip.aircraft_model, 'Boeing 737')


class AdminRegistrationTests(TestCase):
    def test_vehicle_models_are_registered(self):
        from django.contrib import admin

        for model in (Vehicle, TripVehicle, BusTrip, FlightTrip):
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)
