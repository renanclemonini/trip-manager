import shutil
from datetime import date, datetime
from decimal import Decimal
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils.timezone import make_aware

from accounts.models import User
from reports.services import ReportDeliveryError, email_client, telegram_client
from reports.services import chart_builder, pdf_builder
from trips.models import Trip, TripType
from expenses.models import Meal
from vehicles.models import Refueling, TripVehicle, Vehicle, VehicleType

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
        start_date=date(2026, 10, 1),
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
            start_date=date(2026, 12, 1),
        )
        pdf = pdf_builder.build_trip_report_pdf(trip, 'bar')
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
