import uuid

from django.db import models

from common.models import TimestampedModel
from trips.models import Trip


class TollSource(models.TextChoices):
    MANUAL = 'manual', 'Manual'
    IMPORT = 'import', 'Importado'


class Toll(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='tolls',
        verbose_name='Viagem',
    )
    location = models.CharField('Local/Praça', max_length=255)
    amount_spent = models.DecimalField(
        'Valor gasto', max_digits=8, decimal_places=2
    )
    datetime = models.DateTimeField('Data/hora')
    source = models.CharField(
        'Origem',
        max_length=10,
        choices=TollSource.choices,
        default=TollSource.MANUAL,
    )
    import_hash = models.CharField(
        'Chave da importação', max_length=64, null=True, blank=True
    )
    import_batch_id = models.UUIDField(
        'Lote da importação', null=True, blank=True
    )

    class Meta:
        verbose_name = 'Pedágio'
        verbose_name_plural = 'Pedágios'
        ordering = ['-datetime']

    def __str__(self):
        return f'{self.location} — R$ {self.amount_spent}'
