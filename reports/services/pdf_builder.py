import base64
import subprocess

from django.template.loader import render_to_string
from django.utils import timezone

from reports.services import chart_builder
from trips.services import get_trip_dashboard


def _png_data_uri(image_bytes):
    encoded = base64.b64encode(image_bytes).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def build_trip_report_pdf(trip, chart_type):
    """Render the report template and convert it to PDF with wkhtmltopdf."""
    dashboard = get_trip_dashboard(trip)
    charts = dashboard['chart_data']
    consumption_chart = None
    if charts['consumption']:
        consumption_chart = _png_data_uri(
            chart_builder.build_consumption_chart(
                charts['consumption']['labels'],
                charts['consumption']['series'],
            )
        )
    context = {
        'trip': trip,
        'dashboard': dashboard,
        'chart_type_label': chart_builder.CHART_TYPES.get(chart_type, ''),
        'category_chart': _png_data_uri(
            chart_builder.build_category_chart(
                charts['categories']['labels'],
                charts['categories']['series'],
                chart_type,
            )
        ),
        'consumption_chart': consumption_chart,
        'generated_at': timezone.localtime(),
    }
    html = render_to_string('reports/trip_report.html', context)
    result = subprocess.run(
        ['wkhtmltopdf', '--quiet', '--encoding', 'utf-8', '-', '-'],
        input=html.encode('utf-8'),
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            'wkhtmltopdf falhou: '
            f'{result.stderr.decode("utf-8", "replace")}'
        )
    return result.stdout
