from django.contrib import admin

from tolls.models import Toll


@admin.register(Toll)
class TollAdmin(admin.ModelAdmin):
    """Minimal RF25 exception: expose the import batch to locate and undo
    a wrong import (justified by the toll module requirements)."""

    list_filter = ('source', 'import_batch_id')
