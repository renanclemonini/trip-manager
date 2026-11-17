import base64
import subprocess

from django.template.loader import render_to_string
from django.utils import timezone

from reports.services import chart_builder, report_data
from trips.services import get_trip_dashboard


def _png_data_uri(image_bytes):
    encoded = base64.b64encode(image_bytes).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def _render_pdf(html):
    """Convert the rendered HTML to PDF with wkhtmltopdf (stdin/stdout)."""
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


def _build_chart_images(dashboard, chart_type):
    """Chart PNGs embedded as data URIs (category + consumption)."""
    charts = dashboard['chart_data']
    consumption_chart = None
    if charts['consumption']:
        consumption_chart = _png_data_uri(
            chart_builder.build_consumption_chart(
                charts['consumption']['labels'],
                charts['consumption']['series'],
            )
        )
    return {
        'category_chart': _png_data_uri(
            chart_builder.build_category_chart(
                charts['categories']['labels'],
                charts['categories']['series'],
                chart_type,
            )
        ),
        'consumption_chart': consumption_chart,
    }


def build_trip_report_pdf(trip, chart_type):
    """Render the summary report template and convert it to PDF."""
    dashboard = get_trip_dashboard(trip)
    context = {
        'trip': trip,
        'dashboard': dashboard,
        'chart_type_label': chart_builder.CHART_TYPES.get(chart_type, ''),
        'generated_at': timezone.localtime(),
    }
    context.update(_build_chart_images(dashboard, chart_type))
    html = render_to_string('reports/trip_report.html', context)
    return _render_pdf(html)


def build_final_report_pdf(trip, chart_type):
    """Render the final report template and convert it to PDF."""
    context = report_data.get_final_report_context(trip)
    context['chart_type_label'] = chart_builder.CHART_TYPES.get(
        chart_type, ''
    )
    context.update(_build_chart_images(context['dashboard'], chart_type))
    context['generated_at'] = timezone.localtime()
    html = render_to_string('reports/trip_final_report.html', context)
    return _render_pdf(html)
