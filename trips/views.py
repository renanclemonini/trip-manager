from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import CreateView, DetailView, FormView, ListView

from trips import services
from trips.forms import FinishTripForm, TripForm
from trips.mixins import ExpectedTripTypeMixin, TripContextMixin
from trips.models import Trip, TripType


class TripListView(LoginRequiredMixin, ListView):
    model = Trip
    template_name = 'trips/trip_list.html'
    context_object_name = 'trips'

    def get_queryset(self):
        return Trip.objects.all()


class TripCreateView(LoginRequiredMixin, CreateView):
    model = Trip
    form_class = TripForm
    template_name = 'trips/trip_form.html'

    def form_valid(self, form):
        self.object = services.save_trip(
            form=form, created_by=self.request.user
        )
        messages.success(self.request, 'Viagem criada com sucesso.')
        return redirect(self.get_success_url())

    def get_success_url(self):
        return services.get_trip_post_create_path(self.object)


class TripDetailView(TripContextMixin, DetailView):
    model = Trip
    template_name = 'trips/trip_detail.html'
    context_object_name = 'trip'

    def get_object(self, queryset=None):
        return self.get_trip()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dashboard'] = services.get_trip_dashboard(self.get_trip())
        return context


class FinishTripView(ExpectedTripTypeMixin, FormView):
    """Narrow RF27 exception: set end_datetime for an unfinished car trip.

    RF33: also records the final odometer on the trip vehicle; a car trip
    without a TripVehicle cannot be finished (no known odometer to check the
    minimum against).
    """

    form_class = FinishTripForm
    template_name = 'trips/trip_finish.html'
    expected_trip_type = TripType.CAR

    def get_trip(self):
        trip = super().get_trip()
        if trip.end_datetime is not None:
            raise Http404
        return trip

    def _guard_trip_vehicle(self, trip):
        if getattr(trip, 'tripvehicle', None) is None:
            messages.error(
                self.request,
                'Cadastre o veículo da viagem antes de finalizá-la.',
            )
            return redirect('trip_detail', trip_id=trip.pk)
        return None

    def get(self, request, *args, **kwargs):
        trip = self.get_trip()
        guard = self._guard_trip_vehicle(trip)
        if guard is not None:
            return guard
        return super().get(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['trip'] = self.get_trip()
        return kwargs

    def form_valid(self, form):
        trip = self.get_trip()
        guard = self._guard_trip_vehicle(trip)
        if guard is not None:
            return guard
        finished = services.finish_trip(
            trip=trip,
            end_datetime=form.cleaned_data['end_datetime'],
            final_mileage=form.cleaned_data['final_mileage'],
        )
        if not finished:
            raise Http404
        messages.success(self.request, 'Viagem finalizada com sucesso.')
        return redirect('trip_detail', trip_id=trip.pk)
