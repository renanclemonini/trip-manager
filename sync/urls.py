from django.urls import path

from sync.views import (
    LodgingSyncView,
    MealSyncView,
    RefuelingSyncView,
    SightseeingSyncView,
    TollSyncView,
)

urlpatterns = [
    path('sync/refuelings/', RefuelingSyncView.as_view(), name='sync_refueling'),
    path('sync/lodgings/', LodgingSyncView.as_view(), name='sync_lodging'),
    path('sync/meals/', MealSyncView.as_view(), name='sync_meal'),
    path(
        'sync/sightseeings/',
        SightseeingSyncView.as_view(),
        name='sync_sightseeing',
    ),
    path('sync/tolls/', TollSyncView.as_view(), name='sync_toll'),
]
