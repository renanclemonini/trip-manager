from django.test import TestCase

from reports.forms import ReportChartForm, ReportSendForm
from reports.services.chart_builder import CHART_TYPES


class ReportChartFormTests(TestCase):
    def test_choices_are_bar_line_pie(self):
        form = ReportChartForm()
        self.assertEqual(
            list(form.fields['chart_type'].choices),
            [('bar', 'Barras'), ('line', 'Linha'), ('pie', 'Pizza')],
        )

    def test_default_chart_type_is_pie(self):
        form = ReportChartForm()
        self.assertEqual(form.fields['chart_type'].initial, 'pie')

    def test_invalid_chart_type_is_rejected(self):
        form = ReportChartForm(data={'chart_type': 'radar'})
        self.assertFalse(form.is_valid())
        self.assertIn('chart_type', form.errors)

    def test_every_chart_type_is_valid(self):
        for chart_type in CHART_TYPES:
            with self.subTest(chart_type=chart_type):
                form = ReportChartForm(data={'chart_type': chart_type})
                self.assertTrue(form.is_valid(), form.errors)


class ReportSendFormTests(TestCase):
    def test_channel_choices_are_email_and_telegram(self):
        form = ReportSendForm()
        self.assertEqual(
            list(form.fields['channel'].choices),
            [('email', 'E-mail'), ('telegram', 'Telegram')],
        )

    def test_chart_type_is_reused_from_report_form(self):
        form = ReportSendForm()
        self.assertEqual(form.fields['chart_type'].initial, 'pie')

    def test_valid_email_submission(self):
        form = ReportSendForm(
            data={'chart_type': 'bar', 'channel': 'email'}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_channel_is_rejected(self):
        form = ReportSendForm(
            data={'chart_type': 'bar', 'channel': 'sms'}
        )
        self.assertFalse(form.is_valid())
        self.assertIn('channel', form.errors)

    def test_channel_is_required(self):
        form = ReportSendForm(data={'chart_type': 'bar'})
        self.assertFalse(form.is_valid())
        self.assertIn('channel', form.errors)
