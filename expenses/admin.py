from django.contrib import admin

from expenses.models import Lodging, Meal, Sightseeing

admin.site.register(Lodging)
admin.site.register(Meal)
admin.site.register(Sightseeing)
