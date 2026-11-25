from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from tolls import services
from tolls.forms import TollForm, TollImportForm
from tolls.models import Toll
from tolls.services.errors import TollImportError
from trips.mixins import ExpectedTripTypeMixin
from trips.models import TripType


class TollFormViewMixin(ExpectedTripTypeMixin):
    expected_trip_type = TripType.CAR
    form_class = TollForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['trip'] = self.get_trip()
        toll = getattr(self, 'toll', None)
        if toll is not None:
            kwargs['instance'] = toll
        return kwargs


class TollListView(ExpectedTripTypeMixin, ListView):
    expected_trip_type = TripType.CAR
    model = Toll
    template_name = 'tolls/toll_list.html'
    context_object_name = 'tolls'

    def get_queryset(self):
        return Toll.objects.filter(trip=self.get_trip())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = TollForm(trip=self.get_trip())
        return context


class TollCreateView(TollFormViewMixin, FormView):
    template_name = 'tolls/toll_form.html'
    page_heading = 'Novo pedágio'
    is_create = True

    def form_valid(self, form):
        services.create_toll(self.get_trip(), form.cleaned_data)
        messages.success(self.request, 'Pedágio registrado com sucesso.')
        return redirect('toll_list', trip_id=self.kwargs['trip_id'])


class TollUpdateView(TollFormViewMixin, FormView):
    template_name = 'tolls/toll_form.html'
    page_heading = 'Editar pedágio'
    is_create = False

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.toll = get_object_or_404(
                Toll, trip=self.get_trip(), pk=kwargs['pk']
            )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {
            'location': self.toll.location,
            'amount_spent': self.toll.amount_spent,
            'datetime': self.toll.datetime,
        }

    def form_valid(self, form):
        services.update_toll(self.get_trip(), self.toll, form.cleaned_data)
        messages.success(self.request, 'Pedágio atualizado com sucesso.')
        return redirect('toll_list', trip_id=self.kwargs['trip_id'])


class TollDetailView(ExpectedTripTypeMixin, DetailView):
    expected_trip_type = TripType.CAR
    model = Toll
    template_name = 'tolls/toll_detail.html'
    context_object_name = 'toll'

    def get_object(self, queryset=None):
        return get_object_or_404(
            Toll, trip=self.get_trip(), pk=self.kwargs['pk']
        )


class TollImportView(ExpectedTripTypeMixin, FormView):
    """Upload the statement and render the preview in the same POST.

    The file is processed in memory only; nothing is written to disk or
    the database before the confirmation. Reloading the page (F5/back)
    merely resubmits the upload — harmless, since no import happened.
    """

    expected_trip_type = TripType.CAR
    form_class = TollImportForm
    template_name = 'tolls/toll_import_form.html'

    def form_valid(self, form):
        upload = form.cleaned_data['file']
        try:
            file_bytes = services.read_upload(upload)
            preview = services.build_preview(
                self.get_trip(), file_bytes, self.request.user
            )
        except TollImportError as exc:
            form.add_error('file', str(exc))
            return self.form_invalid(form)
        context = self.get_context_data(form=form)
        context['preview'] = preview
        context['signed_payload'] = services.sign_preview(preview)
        return TemplateResponse(
            self.request, 'tolls/toll_import_preview.html', context
        )


class TollImportConfirmView(ExpectedTripTypeMixin, View):
    """Create the selected tolls atomically, revalidating the preview."""

    expected_trip_type = TripType.CAR
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        trip = self.get_trip()
        payload = request.POST.get('payload', '')
        selected = request.POST.getlist('selected')
        try:
            result = services.confirm_import(
                trip, request.user, payload, selected
            )
        except TollImportError as exc:
            messages.error(request, str(exc))
            return redirect('toll_import', trip_id=trip.pk)
        created = result['created']
        skipped = result['skipped']
        if created:
            message = f'{created} pedágio(s) importado(s) com sucesso.'
            if skipped:
                message += f' {skipped} já haviam sido importado(s).'
            messages.success(request, message)
        else:
            messages.info(
                request, 'Nenhum pedágio novo para importar.'
            )
        return redirect('toll_list', trip_id=trip.pk)
