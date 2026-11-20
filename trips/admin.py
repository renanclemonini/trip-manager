from django.contrib import admin

from trips.models import Trip


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    """RF32: só edição de viagens existentes — sem criar nem excluir."""

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
