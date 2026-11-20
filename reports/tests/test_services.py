import shutil
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from django.utils.timezone import make_aware

from accounts.models import User
from reports.services import ReportDeliveryError, email_client, telegram_client
from reports.services import chart_builder, pdf_builder, report_data
from trips.models import Trip, TripType
from expenses.models import Lodging, Meal, Sightseeing
from vehicles import services as vehicles_services
from vehicles.models import (
    BusTrip,
    FlightTrip,
    Refueling,
    TripVehicle,
    Vehicle,
    VehicleType,
)

REFUELING_DATETIME = make_aware(datetime(2026, 10, 2, 8, 0))
WKWEBTOPDF_AVAILABLE = shutil.which('wkhtmltopdf') is not None


class CategoryChartTests(SimpleTestCase):
    def test_returns_png_bytes(self):
        data = chart_builder.build_category_chart(
            ['A', 'B'], [1.0, 2.0], 'bar'
        )
        self.assertTrue(data.startswith(b'\x89PNG'))

    def test_each_chart_type_returns_png_bytes(self):
        for chart_type in ('bar', 'line', 'pie'):
            with self.subTest(chart_type=chart_type):
                data = chart_builder.build_category_chart(
                    ['Abastecimento', 'Hospedagem'], [350.0, 450.0], chart_type
                )
                self.assertTrue(data.startswith(b'\x89PNG'))

    def test_chart_types_produce_distinct_images(self):
        images = {
            chart_type: chart_builder.build_category_chart(
                ['A', 'B'], [1.0, 2.0], chart_type
            )
            for chart_type in ('bar', 'line', 'pie')
        }
        self.assertEqual(len(set(images.values())), 3)

    def test_empty_series_is_safe(self):
        data = chart_builder.build_category_chart([], [], 'bar')
        self.assertTrue(data.startswith(b'\x89PNG'))


class ConsumptionChartTests(SimpleTestCase):
    def test_returns_png_bytes(self):
        data = chart_builder.build_consumption_chart(
            ['1500 km', '2000 km'], [16.67, 12.5]
        )
        self.assertTrue(data.startswith(b'\x89PNG'))

    def test_empty_series_is_safe(self):
        data = chart_builder.build_consumption_chart([], [])
        self.assertTrue(data.startswith(b'\x89PNG'))


def create_user(email='reports@example.com'):
    return User.objects.create_user(email=email, password='strong-pass-123')


def create_car_trip(user):
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
        trip=trip, vehicle=vehicle, initial_mileage=1000
    )
    Refueling.objects.create(
        trip=trip,
        city='Campinas',
        state='SP',
        liters=Decimal('30.00'),
        amount_spent=Decimal('150.00'),
        total_mileage=1500,
        datetime=REFUELING_DATETIME,
    )
    Meal.objects.create(
        trip=trip,
        city='Curitiba',
        state='PR',
        amount_spent=Decimal('35.00'),
        datetime=REFUELING_DATETIME,
    )
    return trip


def create_car_trip_without_refueling(user):
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
        trip=trip, vehicle=vehicle, initial_mileage=1000
    )
    return trip


def create_bus_trip(user):
    trip = Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Foz do Iguaçu',
        destination_state='PR',
        trip_type=TripType.BUS,
        start_datetime=timezone.now() - timedelta(days=30),
        end_datetime=timezone.now() - timedelta(hours=1),
    )
    vehicle = Vehicle.objects.create(
        vehicle_type=VehicleType.BUS, brand='Marcopolo', model='Paradiso'
    )
    BusTrip.objects.create(
        trip=trip,
        vehicle=vehicle,
        company='Viação Cometa',
        amount_paid=Decimal('250.00'),
        start_date=date(2026, 9, 1),
    )
    return trip


def create_plane_trip(user, **flight_overrides):
    trip = Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Recife',
        destination_state='PE',
        trip_type=TripType.PLANE,
        start_datetime=timezone.now() - timedelta(days=30),
        end_datetime=timezone.now() - timedelta(hours=1),
    )
    flight_data = {
        'airline': 'Azul',
        'aircraft_model': 'Airbus A320',
        'ticket_price': Decimal('500.00'),
        'departure_datetime': make_aware(datetime(2026, 10, 1, 9, 30)),
        'return_datetime': make_aware(datetime(2026, 10, 5, 18, 0)),
    }
    flight_data.update(flight_overrides)
    FlightTrip.objects.create(trip=trip, **flight_data)
    return trip


class TransportDetailsTests(TestCase):
    def test_car_trip_with_refueling_returns_final_mileage(self):
        trip = create_car_trip(create_user('details-car@example.com'))
        details = vehicles_services.get_transport_details(trip)
        self.assertEqual(details['vehicle'], 'Fiat Argo')
        self.assertEqual(details['initial_mileage'], 1000)
        self.assertEqual(details['final_mileage'], 1500)

    def test_car_trip_without_refueling_has_no_final_mileage(self):
        trip = create_car_trip_without_refueling(
            create_user('details-no-refuel@example.com')
        )
        details = vehicles_services.get_transport_details(trip)
        self.assertEqual(details['initial_mileage'], 1000)
        self.assertNotIn('final_mileage', details)

    def test_car_trip_without_vehicle_returns_none(self):
        user = create_user('details-no-vehicle@example.com')
        trip = Trip.objects.create(
            created_by=user,
            origin_city='São Paulo',
            origin_state='SP',
            destination_city='Curitiba',
            destination_state='PR',
            trip_type=TripType.CAR,
            start_datetime=timezone.now() - timedelta(days=1),
        )
        self.assertIsNone(vehicles_services.get_transport_details(trip))

    def test_bus_trip_returns_bus_details(self):
        trip = create_bus_trip(create_user('details-bus@example.com'))
        details = vehicles_services.get_transport_details(trip)
        self.assertEqual(details['company'], 'Viação Cometa')
        self.assertEqual(details['vehicle'], 'Marcopolo Paradiso')
        self.assertEqual(details['amount_paid'], Decimal('250.00'))
        self.assertEqual(details['start_date'], date(2026, 9, 1))

    def test_flight_trip_without_optional_fields(self):
        trip = create_plane_trip(
            create_user('details-plane@example.com'),
            aircraft_model=None,
            return_datetime=None,
        )
        details = vehicles_services.get_transport_details(trip)
        self.assertEqual(details['airline'], 'Azul')
        self.assertIsNone(details['aircraft_model'])
        self.assertEqual(details['ticket_price'], Decimal('500.00'))
        self.assertIsNone(details['return_datetime'])

    def test_flight_trip_with_optional_fields(self):
        trip = create_plane_trip(create_user('details-plane-full@example.com'))
        details = vehicles_services.get_transport_details(trip)
        self.assertEqual(details['aircraft_model'], 'Airbus A320')
        self.assertIsNotNone(details['return_datetime'])


class FinalReportContextTests(TestCase):
    def test_car_context_lists_items_in_narrative_order(self):
        user = create_user('ctx-car@example.com')
        trip = create_car_trip(user)
        Refueling.objects.create(
            trip=trip,
            city='São Paulo',
            state='SP',
            liters=Decimal('20.00'),
            amount_spent=Decimal('100.00'),
            total_mileage=1200,
            datetime=make_aware(datetime(2026, 10, 1, 9, 0)),
        )
        Lodging.objects.create(
            trip=trip,
            city='Curitiba',
            state='PR',
            amount_spent=Decimal('200.00'),
            check_in=make_aware(datetime(2026, 10, 3, 14, 0)),
            check_out=make_aware(datetime(2026, 10, 4, 11, 0)),
        )
        context = report_data.get_final_report_context(trip)
        self.assertEqual(
            list(
                context['refuelings'].values_list('total_mileage', flat=True)
            ),
            [1200, 1500],
        )
        self.assertEqual(
            [category['key'] for category in context['dashboard']['categories']],
            ['refueling', 'lodging', 'meal'],
        )
        self.assertEqual(context['transport']['final_mileage'], 1500)
        self.assertEqual(list(context['sightseeings']), [])

    def test_bus_context_includes_transport_total_and_sightseeings(self):
        user = create_user('ctx-bus@example.com')
        trip = create_bus_trip(user)
        first = Sightseeing.objects.create(
            trip=trip,
            amount_spent=Decimal('80.00'),
            description='Cataratas',
        )
        second = Sightseeing.objects.create(
            trip=trip,
            amount_spent=Decimal('60.00'),
            description='Itaipu',
        )
        context = report_data.get_final_report_context(trip)
        self.assertEqual(
            [category['key'] for category in context['dashboard']['categories']],
            ['transport', 'lodging', 'meal', 'sightseeing'],
        )
        self.assertEqual(
            context['dashboard']['categories'][0]['total'],
            Decimal('250.00'),
        )
        self.assertEqual(list(context['sightseeings']), [first, second])
        self.assertEqual(context['transport']['company'], 'Viação Cometa')

    def test_plane_context_transport_total_is_ticket_price(self):
        user = create_user('ctx-plane@example.com')
        trip = create_plane_trip(user)
        context = report_data.get_final_report_context(trip)
        self.assertEqual(
            [category['key'] for category in context['dashboard']['categories']],
            ['transport', 'lodging', 'meal'],
        )
        self.assertEqual(
            context['dashboard']['categories'][0]['total'],
            Decimal('500.00'),
        )
        self.assertEqual(context['transport']['airline'], 'Azul')
        self.assertEqual(list(context['refuelings']), [])


@skipUnless(WKWEBTOPDF_AVAILABLE, 'wkhtmltopdf não disponível neste ambiente')
class PdfBuilderTests(TestCase):
    def test_car_report_starts_with_pdf_magic(self):
        trip = create_car_trip(create_user())
        pdf = pdf_builder.build_trip_report_pdf(trip, 'pie')
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 1024)

    def test_plane_report_without_consumption_chart(self):
        user = create_user('plane-reports@example.com')
        trip = Trip.objects.create(
            created_by=user,
            origin_city='Santos',
            origin_state='SP',
            destination_city='Brasília',
            destination_state='DF',
            trip_type=TripType.PLANE,
            start_datetime=timezone.now() - timedelta(days=1),
        )
        pdf = pdf_builder.build_trip_report_pdf(trip, 'bar')
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_final_car_report_starts_with_pdf_magic(self):
        trip = create_car_trip(create_user('final-pdf-car@example.com'))
        trip.end_datetime = timezone.now() - timedelta(hours=1)
        trip.save()
        pdf = pdf_builder.build_final_report_pdf(trip, 'pie')
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 1024)

    def test_final_bus_report_starts_with_pdf_magic(self):
        trip = create_bus_trip(create_user('final-pdf-bus@example.com'))
        pdf = pdf_builder.build_final_report_pdf(trip, 'bar')
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_final_plane_report_starts_with_pdf_magic(self):
        trip = create_plane_trip(create_user('final-pdf-plane@example.com'))
        pdf = pdf_builder.build_final_report_pdf(trip, 'line')
        self.assertTrue(pdf.startswith(b'%PDF'))


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
)
class EmailClientTests(TestCase):
    def test_sends_email_with_pdf_attachment(self):
        email_client.send_report_email(
            pdf_bytes=b'%PDF-test-content',
            filename='relatorio-viagem-1.pdf',
            subject='Relatório da viagem',
            body='Segue em anexo.',
            to='user@example.com',
        )
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['user@example.com'])
        self.assertEqual(len(message.attachments), 1)
        filename, content, mimetype = message.attachments[0]
        self.assertEqual(filename, 'relatorio-viagem-1.pdf')
        self.assertEqual(content, b'%PDF-test-content')
        self.assertEqual(mimetype, 'application/pdf')

    def test_backend_failure_raises_delivery_error(self):
        with patch(
            'reports.services.email_client.EmailMessage.send',
            side_effect=Exception('smtp fora do ar'),
        ):
            with self.assertRaises(ReportDeliveryError):
                email_client.send_report_email(
                    pdf_bytes=b'%PDF',
                    filename='relatorio-viagem-1.pdf',
                    subject='s',
                    body='b',
                    to='user@example.com',
                )


class TelegramClientTests(TestCase):
    @override_settings(TELEGRAM_BOT_TOKEN='', TELEGRAM_CHAT_ID='')
    def test_unconfigured_raises_friendly_error(self):
        with self.assertRaisesMessage(
            ReportDeliveryError, 'Telegram não configurado'
        ):
            telegram_client.send_report_telegram(
                pdf_bytes=b'%PDF', filename='r.pdf'
            )

    @override_settings(TELEGRAM_BOT_TOKEN='123:abc', TELEGRAM_CHAT_ID='42')
    @patch('reports.services.telegram_client.requests.post')
    def test_posts_document_to_telegram_api(self, post):
        post.return_value = Mock(status_code=200)
        telegram_client.send_report_telegram(
            pdf_bytes=b'%PDF-content',
            filename='relatorio-viagem-1.pdf',
            caption='Relatório',
        )
        args, kwargs = post.call_args
        self.assertEqual(
            args[0], 'https://api.telegram.org/bot123:abc/sendDocument'
        )
        self.assertEqual(kwargs['data']['chat_id'], '42')
        self.assertEqual(kwargs['data']['caption'], 'Relatório')
        filename, content, mimetype = kwargs['files']['document']
        self.assertEqual(filename, 'relatorio-viagem-1.pdf')
        self.assertEqual(content, b'%PDF-content')
        self.assertEqual(mimetype, 'application/pdf')

    @override_settings(TELEGRAM_BOT_TOKEN='123:abc', TELEGRAM_CHAT_ID='42')
    @patch('reports.services.telegram_client.requests.post')
    def test_api_failure_raises_delivery_error(self, post):
        post.return_value = Mock(status_code=400)
        with self.assertRaisesMessage(
            ReportDeliveryError, 'Falha ao enviar pelo Telegram'
        ):
            telegram_client.send_report_telegram(
                pdf_bytes=b'%PDF', filename='r.pdf'
            )
