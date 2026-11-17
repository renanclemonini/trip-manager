from django.urls import path

from reports.views import ReportGenerateView, ReportSendView

urlpatterns = [
    path(
        'trip/<int:trip_id>/report/',
        ReportGenerateView.as_view(),
        name='report_generate',
    ),
    path(
        'trip/<int:trip_id>/report/send/',
        ReportSendView.as_view(),
        name='report_send',
    ),
]
