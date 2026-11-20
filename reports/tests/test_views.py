from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from trips.models import Trip, TripType


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


class ReportFormViewTests(TestCase):
    def setUp(self):
        self.user = create_user('report-form@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_get_renders_form_with_chart_options(self):
        response = self.client.get(
            reverse('report_generate', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reports/report_form.html')
        self.assertContains(response, 'Barras')
        self.assertContains(response, 'Linha')
        self.assertContains(response, 'Pizza')
        self.assertContains(response, 'Gerar PDF')
        self.assertContains(response, 'checked')

    def test_anonymous_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(
            reverse('report_generate', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_other_user_can_generate_report(self):
        other = create_user('report-other@example.com')
        self.client.force_login(other)
        response = self.client.get(
            reverse('report_generate', args=[self.trip.pk])
        )
        self.assertEqual(response.status_code, 200)


class ReportGenerateViewTests(TestCase):
    def setUp(self):
        self.user = create_user('report-generate@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)
        self.url = reverse('report_generate', args=[self.trip.pk])

    @patch(
        'reports.views.pdf_builder.build_trip_report_pdf',
        return_value=b'%PDF-fake-content',
    )
    def test_post_returns_pdf_attachment(self, build_pdf):
        response = self.client.post(self.url, {'chart_type': 'bar'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(
            f'attachment; filename="relatorio-viagem-{self.trip.pk}.pdf"',
            response['Content-Disposition'],
        )
        self.assertEqual(response.content, b'%PDF-fake-content')
        build_pdf.assert_called_once_with(self.trip, 'bar')

    @patch(
        'reports.views.pdf_builder.build_trip_report_pdf',
        return_value=b'%PDF-fake-content',
    )
    def test_post_without_chart_type_shows_required_error(self, build_pdf):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertIn('chart_type', response.context['form'].errors)
        build_pdf.assert_not_called()

    def test_invalid_chart_type_shows_form_errors(self):
        response = self.client.post(self.url, {'chart_type': 'radar'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reports/report_form.html')
        self.assertIn('chart_type', response.context['form'].errors)


class FinalReportFormViewTests(TestCase):
    def setUp(self):
        self.user = create_user('final-report-form@example.com')
        self.trip = create_trip(self.user, end_datetime=timezone.now() - timedelta(hours=1))
        self.client.force_login(self.user)
        self.url = reverse('report_final', args=[self.trip.pk])

    def test_get_renders_form_for_completed_trip(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reports/final_report_form.html')
        self.assertContains(response, 'Barras')
        self.assertContains(response, 'Linha')
        self.assertContains(response, 'Pizza')
        self.assertContains(response, 'Gerar PDF final')
        self.assertContains(response, 'checked')
        self.assertContains(
            response,
            'O relatório considera apenas lançamentos já sincronizados '
            'com o servidor',
        )

    def test_get_unfinished_trip_returns_404(self):
        self.trip.end_datetime = None
        self.trip.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_future_end_datetime_returns_404(self):
        self.trip.end_datetime = timezone.now() + timedelta(days=1)
        self.trip.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_past_end_datetime_is_allowed(self):
        self.trip.end_datetime = timezone.now() - timedelta(hours=1)
        self.trip.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_anonymous_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_other_user_can_open_form(self):
        other = create_user('final-report-other@example.com')
        self.client.force_login(other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class FinalReportGenerateViewTests(TestCase):
    def setUp(self):
        self.user = create_user('final-report-generate@example.com')
        self.trip = create_trip(self.user, end_datetime=timezone.now() - timedelta(hours=1))
        self.client.force_login(self.user)
        self.url = reverse('report_final', args=[self.trip.pk])

    @patch(
        'reports.views.pdf_builder.build_final_report_pdf',
        return_value=b'%PDF-final-content',
    )
    def test_post_returns_pdf_attachment(self, build_pdf):
        response = self.client.post(self.url, {'chart_type': 'bar'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(
            f'attachment; filename="relatorio-final-viagem-{self.trip.pk}.pdf"',
            response['Content-Disposition'],
        )
        self.assertEqual(response.content, b'%PDF-final-content')
        build_pdf.assert_called_once_with(self.trip, 'bar')

    @patch('reports.views.pdf_builder.build_final_report_pdf')
    def test_post_without_chart_type_shows_required_error(self, build_pdf):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertIn('chart_type', response.context['form'].errors)
        build_pdf.assert_not_called()

    def test_invalid_chart_type_shows_form_errors(self):
        response = self.client.post(self.url, {'chart_type': 'radar'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reports/final_report_form.html')
        self.assertIn('chart_type', response.context['form'].errors)

    @patch('reports.views.pdf_builder.build_final_report_pdf')
    def test_post_uncompleted_trip_returns_404_and_does_not_build(
        self, build_pdf
    ):
        self.trip.end_datetime = None
        self.trip.save()
        response = self.client.post(self.url, {'chart_type': 'pie'})
        self.assertEqual(response.status_code, 404)
        build_pdf.assert_not_called()


class ReportSendViewTests(TestCase):
    def setUp(self):
        self.user = create_user('report-send@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)
        self.url = reverse('report_send', args=[self.trip.pk])

    def test_get_renders_form_with_channels(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reports/report_send.html')
        self.assertContains(response, 'E-mail')
        self.assertContains(response, 'Telegram')
        self.assertContains(response, 'Enviar relatório')

    def test_anonymous_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_other_user_can_open_send_form(self):
        other = create_user('report-send-other@example.com')
        self.client.force_login(other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    @patch(
        'reports.views.pdf_builder.build_trip_report_pdf',
        return_value=b'%PDF-test',
    )
    def test_email_send_succeeds_and_redirects(self, build_pdf):
        response = self.client.post(
            self.url, {'chart_type': 'pie', 'channel': 'email'}
        )
        self.assertRedirects(
            response, reverse('report_generate', args=[self.trip.pk])
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        filename, _, mimetype = mail.outbox[0].attachments[0]
        self.assertEqual(
            filename, f'relatorio-viagem-{self.trip.pk}.pdf'
        )
        self.assertEqual(mimetype, 'application/pdf')
        build_pdf.assert_called_once_with(self.trip, 'pie')

    @override_settings(TELEGRAM_BOT_TOKEN='', TELEGRAM_CHAT_ID='')
    @patch(
        'reports.views.pdf_builder.build_trip_report_pdf',
        return_value=b'%PDF-test',
    )
    def test_telegram_without_credentials_shows_friendly_error(
        self, build_pdf
    ):
        response = self.client.post(
            self.url, {'chart_type': 'pie', 'channel': 'telegram'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Telegram não configurado')

    @override_settings(TELEGRAM_BOT_TOKEN='token', TELEGRAM_CHAT_ID='42')
    @patch(
        'reports.views.telegram_client.send_report_telegram',
        return_value=True,
    )
    @patch(
        'reports.views.pdf_builder.build_trip_report_pdf',
        return_value=b'%PDF-test',
    )
    def test_telegram_send_succeeds_and_redirects(
        self, build_pdf, send_telegram
    ):
        response = self.client.post(
            self.url, {'chart_type': 'bar', 'channel': 'telegram'}
        )
        self.assertRedirects(
            response, reverse('report_generate', args=[self.trip.pk])
        )
        send_telegram.assert_called_once()
        self.assertEqual(
            send_telegram.call_args.kwargs['filename'],
            f'relatorio-viagem-{self.trip.pk}.pdf',
        )

    def test_invalid_channel_shows_form_errors(self):
        response = self.client.post(
            self.url, {'chart_type': 'pie', 'channel': 'sms'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('channel', response.context['form'].errors)
