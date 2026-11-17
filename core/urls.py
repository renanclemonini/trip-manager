from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('trips.urls')),
    path('', include('vehicles.urls')),
    path('', include('expenses.urls')),
    path('', include('reports.urls')),
    path('', include('sync.urls')),
    path('', include('accounts.urls')),
]
