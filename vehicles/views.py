from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, FormView, ListView

from trips.mixins import ExpectedTripTypeMixin
from trips.models import TripType
from vehicles import services
from vehicles.forms import (
    BusTripForm,
    FlightTripForm,
    RefuelingForm,
    VehicleTripForm,
)
from vehicles.models import BusTrip, FlightTrip, Refueling, TripVehicle


class TransportFormViewMixin(ExpectedTripTypeMixin, FormView):
    """Common create/update flow for a trip transport form."""

    success_message = ''

    def get_success_url(self):
        return reverse(
            'trip_detail', kwargs={'trip_id': self.kwargs['trip_id']}
        )

    def form_valid(self, form):
        self.save_transport(form)
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


class VehicleCreateView(TransportFormViewMixin):
    expected_trip_type = TripType.CAR
    template_name = 'vehicles/vehicle_form.html'
    form_class = VehicleTripForm
    success_message = 'Veículo da viagem cadastrado com sucesso.'

    def get(self, request, *args, **kwargs):
        if hasattr(self.get_trip(), 'tripvehicle'):
            return redirect('vehicle_edit', trip_id=self.get_trip().pk)
        return super().get(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['trip'] = self.get_trip()
        return kwargs

    def save_transport(self, form):
        services.create_car_transport(self.get_trip(), form.cleaned_data)


class VehicleUpdateView(TransportFormViewMixin):
    expected_trip_type = TripType.CAR
    template_name = 'vehicles/vehicle_form.html'
    form_class = VehicleTripForm
    success_message = 'Veículo da viagem atualizado com sucesso.'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.get_trip_vehicle()
        return super().dispatch(request, *args, **kwargs)

    def get_trip_vehicle(self):
        return get_object_or_404(TripVehicle, trip=self.get_trip())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['trip'] = self.get_trip()
        return kwargs

    def get_initial(self):
        trip_vehicle = self.get_trip_vehicle()
        return {
            'brand': trip_vehicle.vehicle.brand,
            'model': trip_vehicle.vehicle.model,
            'initial_mileage': trip_vehicle.initial_mileage,
            'plate': trip_vehicle.vehicle.plate,
        }

    def save_transport(self, form):
        services.update_car_transport(self.get_trip(), form.cleaned_data)


class RefuelingFormViewMixin(ExpectedTripTypeMixin):
    expected_trip_type = TripType.CAR
    form_class = RefuelingForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['trip'] = self.get_trip()
        refueling = getattr(self, 'refueling', None)
        if refueling is not None:
            kwargs['instance'] = refueling
        return kwargs


class RefuelingListView(ExpectedTripTypeMixin, ListView):
    expected_trip_type = TripType.CAR
    model = Refueling
    template_name = 'vehicles/refueling_list.html'
    context_object_name = 'refuelings'

    def get_queryset(self):
        return Refueling.objects.filter(trip=self.get_trip())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = RefuelingForm(trip=self.get_trip())
        return context


class RefuelingCreateView(RefuelingFormViewMixin, FormView):
    template_name = 'vehicles/refueling_form.html'
    page_heading = 'Novo abastecimento'
    is_create = True

    def form_valid(self, form):
        services.create_refueling(self.get_trip(), form.cleaned_data)
        messages.success(self.request, 'Abastecimento registrado com sucesso.')
        return redirect('refueling_list', trip_id=self.kwargs['trip_id'])


class RefuelingUpdateView(RefuelingFormViewMixin, FormView):
    template_name = 'vehicles/refueling_form.html'
    page_heading = 'Editar abastecimento'
    is_create = False

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.refueling = get_object_or_404(
                Refueling, trip=self.get_trip(), pk=kwargs['pk']
            )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {
            'city': self.refueling.city,
            'state': self.refueling.state,
            'liters': self.refueling.liters,
            'amount_spent': self.refueling.amount_spent,
            'total_mileage': self.refueling.total_mileage,
            'datetime': self.refueling.datetime,
        }

    def form_valid(self, form):
        services.update_refueling(
            self.get_trip(), self.refueling, form.cleaned_data
        )
        messages.success(self.request, 'Abastecimento atualizado com sucesso.')
        return redirect('refueling_list', trip_id=self.kwargs['trip_id'])


class RefuelingDetailView(ExpectedTripTypeMixin, DetailView):
    expected_trip_type = TripType.CAR
    model = Refueling
    template_name = 'vehicles/refueling_detail.html'
    context_object_name = 'refueling'

    def get_object(self, queryset=None):
        return get_object_or_404(
            Refueling, trip=self.get_trip(), pk=self.kwargs['pk']
        )


class BusTripCreateView(TransportFormViewMixin):
    expected_trip_type = TripType.BUS
    template_name = 'vehicles/bus_trip_form.html'
    form_class = BusTripForm
    success_message = 'Dados do ônibus cadastrados com sucesso.'

    def get(self, request, *args, **kwargs):
        if hasattr(self.get_trip(), 'bustrip'):
            return redirect('bus_edit', trip_id=self.get_trip().pk)
        return super().get(request, *args, **kwargs)

    def save_transport(self, form):
        services.create_bus_transport(self.get_trip(), form.cleaned_data)


class BusTripUpdateView(TransportFormViewMixin):
    expected_trip_type = TripType.BUS
    template_name = 'vehicles/bus_trip_form.html'
    form_class = BusTripForm
    success_message = 'Dados do ônibus atualizados com sucesso.'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.get_bus_trip()
        return super().dispatch(request, *args, **kwargs)

    def get_bus_trip(self):
        return get_object_or_404(BusTrip, trip=self.get_trip())

    def get_initial(self):
        bus_trip = self.get_bus_trip()
        return {
            'brand': bus_trip.vehicle.brand,
            'model': bus_trip.vehicle.model,
            'company': bus_trip.company,
            'amount_paid': bus_trip.amount_paid,
            'start_date': bus_trip.start_date,
        }

    def save_transport(self, form):
        services.update_bus_transport(self.get_trip(), form.cleaned_data)


class FlightTripCreateView(TransportFormViewMixin):
    expected_trip_type = TripType.PLANE
    template_name = 'vehicles/flight_trip_form.html'
    form_class = FlightTripForm
    success_message = 'Dados do voo cadastrados com sucesso.'

    def get(self, request, *args, **kwargs):
        if hasattr(self.get_trip(), 'flighttrip'):
            return redirect('flight_edit', trip_id=self.get_trip().pk)
        return super().get(request, *args, **kwargs)

    def save_transport(self, form):
        services.create_flight_transport(self.get_trip(), form.cleaned_data)


class FlightTripUpdateView(TransportFormViewMixin):
    expected_trip_type = TripType.PLANE
    template_name = 'vehicles/flight_trip_form.html'
    form_class = FlightTripForm
    success_message = 'Dados do voo atualizados com sucesso.'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.get_flight_trip()
        return super().dispatch(request, *args, **kwargs)

    def get_flight_trip(self):
        return get_object_or_404(FlightTrip, trip=self.get_trip())

    def get_initial(self):
        flight_trip = self.get_flight_trip()
        return {
            'airline': flight_trip.airline,
            'aircraft_model': flight_trip.aircraft_model,
            'ticket_price': flight_trip.ticket_price,
            'departure_datetime': flight_trip.departure_datetime,
            'return_datetime': flight_trip.return_datetime,
        }

    def save_transport(self, form):
        services.update_flight_transport(self.get_trip(), form.cleaned_data)
