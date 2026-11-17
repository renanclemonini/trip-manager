from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404

from trips.models import Trip


class TripContextMixin(LoginRequiredMixin):
    """Resolve the trip by id and expose it to the view context."""

    trip = None

    def get_trip(self):
        if self.trip is None:
            self.trip = get_object_or_404(Trip, pk=self.kwargs['trip_id'])
        return self.trip

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['trip'] = self.get_trip()
        return context


class ExpectedTripTypeMixin(TripContextMixin):
    """Reject the view with 404 when the trip type does not match."""

    expected_trip_type = None

    def get_trip(self):
        trip = super().get_trip()
        if trip.trip_type != self.expected_trip_type:
            raise Http404
        return trip
