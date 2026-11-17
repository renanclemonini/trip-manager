from django.urls import path

from trips.views import (
    FinishTripView,
    TripCreateView,
    TripDetailView,
    TripListView,
)

urlpatterns = [
    path('', TripListView.as_view(), name='home'),
    path('trip/new/', TripCreateView.as_view(), name='trip_create'),
    path(
        'trip/<int:trip_id>/',
        TripDetailView.as_view(),
        name='trip_detail',
    ),
    path(
        'trip/<int:trip_id>/finish/',
        FinishTripView.as_view(),
        name='trip_finish',
    ),
]
