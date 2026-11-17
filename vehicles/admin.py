from django.contrib import admin

from vehicles.models import BusTrip, FlightTrip, TripVehicle, Vehicle

admin.site.register(Vehicle)
admin.site.register(TripVehicle)
admin.site.register(BusTrip)
admin.site.register(FlightTrip)
