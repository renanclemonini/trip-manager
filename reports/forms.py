from django import forms

from reports.services.chart_builder import CHART_TYPES

REPORT_CHANNELS = [
    ('email', 'E-mail'),
    ('telegram', 'Telegram'),
]


class ReportChartForm(forms.Form):
    chart_type = forms.ChoiceField(
        label='Tipo de gráfico',
        choices=CHART_TYPES,
        initial='pie',
        widget=forms.RadioSelect,
    )


class ReportSendForm(ReportChartForm):
    channel = forms.ChoiceField(
        label='Canal de envio',
        choices=REPORT_CHANNELS,
        widget=forms.RadioSelect,
    )
