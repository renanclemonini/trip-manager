from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.generic import FormView

from reports.forms import ReportChartForm, ReportSendForm
from reports.services import (
    ReportDeliveryError,
    email_client,
    pdf_builder,
    telegram_client,
)
from trips.mixins import TripContextMixin
from trips.services import get_trip_dashboard


class ReportGenerateView(TripContextMixin, FormView):
    form_class = ReportChartForm
    template_name = 'reports/report_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        trip = self.get_trip()
        context['dashboard'] = get_trip_dashboard(trip)
        context['download_filename'] = f'relatorio-viagem-{trip.pk}.pdf'
        return context

    def form_valid(self, form):
        trip = self.get_trip()
        pdf_content = pdf_builder.build_trip_report_pdf(
            trip, form.cleaned_data['chart_type']
        )
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="relatorio-viagem-{trip.pk}.pdf"'
        )
        return response


class ReportSendView(TripContextMixin, FormView):
    form_class = ReportSendForm
    template_name = 'reports/report_send.html'

    def form_valid(self, form):
        trip = self.get_trip()
        filename = f'relatorio-viagem-{trip.pk}.pdf'
        pdf_content = pdf_builder.build_trip_report_pdf(
            trip, form.cleaned_data['chart_type']
        )
        channel = form.cleaned_data['channel']
        try:
            if channel == 'email':
                email_client.send_report_email(
                    pdf_bytes=pdf_content,
                    filename=filename,
                    subject=f'Relatório da viagem {trip}',
                    body='Segue em anexo o relatório da viagem.',
                    to=self.request.user.email,
                )
            else:
                telegram_client.send_report_telegram(
                    pdf_bytes=pdf_content,
                    filename=filename,
                    caption=f'Relatório da viagem {trip}',
                )
        except ReportDeliveryError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, 'Relatório enviado com sucesso.')
        return redirect('report_generate', trip_id=trip.pk)
