from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, FormView, ListView

from tolls import services
from tolls.forms import TollForm
from tolls.models import Toll
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
