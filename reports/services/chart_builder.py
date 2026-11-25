import io
import re

import matplotlib

matplotlib.use('Agg')

from matplotlib import pyplot as plt  # noqa: E402

CHART_TYPES = {
    'bar': 'Barras',
    'line': 'Linha',
    'pie': 'Pizza',
}


def _figure_to_png(figure):
    buffer = io.BytesIO()
    figure.savefig(buffer, format='png', bbox_inches='tight')
    plt.close(figure)
    return buffer.getvalue()


def _empty_chart(figure, axes):
    axes.text(
        0.5, 0.5, 'Sem dados', ha='center', va='center', fontsize=12
    )
    axes.set_axis_off()


def build_category_chart(labels, series, chart_type):
    """Category spending chart (RF20): bar, line or pie."""
    figure, axes = plt.subplots(figsize=(7, 3.5), dpi=150)
    if not labels or not series:
        _empty_chart(figure, axes)
        return _figure_to_png(figure)
    if chart_type == 'pie':
        axes.pie(series, labels=labels, autopct='%1.1f%%')
        axes.set_aspect('equal')
    elif chart_type == 'line':
        axes.plot(labels, series, marker='o')
        axes.set_ylabel('R$')
    else:
        axes.bar(labels, series)
        axes.set_ylabel('R$')
    return _figure_to_png(figure)


def format_mileage_label(label):
    """Group digits with Brazilian thousands separator (no locale)."""
    return re.sub(
        r'\d+',
        lambda match: f'{int(match.group()):,}'.replace(',', '.'),
        label,
    )


def build_consumption_chart(labels, series):
    """Fuel consumption evolution (line only — RF11 data)."""
    figure, axes = plt.subplots(figsize=(7, 3.5), dpi=150)
    if not labels or not series:
        _empty_chart(figure, axes)
        return _figure_to_png(figure)
    axes.plot(
        [format_mileage_label(label) for label in labels],
        series,
        marker='o',
    )
    axes.set_ylabel('km/l')
    return _figure_to_png(figure)
