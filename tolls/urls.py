from django.urls import path

from tolls.views import (
    TollCreateView,
    TollDetailView,
    TollImportConfirmView,
    TollImportView,
    TollListView,
    TollUpdateView,
)

urlpatterns = [
    path(
        'trip/<int:trip_id>/tolls/',
        TollListView.as_view(),
        name='toll_list',
    ),
    path(
        'trip/<int:trip_id>/tolls/new/',
        TollCreateView.as_view(),
        name='toll_create',
    ),
    path(
        'trip/<int:trip_id>/tolls/import/',
        TollImportView.as_view(),
        name='toll_import',
    ),
    path(
        'trip/<int:trip_id>/tolls/import/confirm/',
        TollImportConfirmView.as_view(),
        name='toll_import_confirm',
    ),
    path(
        'trip/<int:trip_id>/tolls/<uuid:pk>/',
        TollDetailView.as_view(),
        name='toll_detail',
    ),
    path(
        'trip/<int:trip_id>/tolls/<uuid:pk>/edit/',
        TollUpdateView.as_view(),
        name='toll_edit',
    ),
]
