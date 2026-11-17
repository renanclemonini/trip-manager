from django.urls import path

from reports.views import (
    FinalReportGenerateView,
    ReportGenerateView,
    ReportSendView,
)

urlpatterns = [
    path(
        'trip/<int:trip_id>/report/',
        ReportGenerateView.as_view(),
        name='report_generate',
    ),
    path(
        'trip/<int:trip_id>/report/final/',
        FinalReportGenerateView.as_view(),
        name='report_final',
    ),
    path(
        'trip/<int:trip_id>/report/send/',
        ReportSendView.as_view(),
        name='report_send',
    ),
]
