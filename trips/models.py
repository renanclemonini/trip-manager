from django.conf import settings
from django.db import models

from common.choices import State
from common.models import TimestampedModel


class TripType(models.TextChoices):
    CAR = 'car', 'Carro'
    PLANE = 'plane', 'Avião'
    BUS = 'bus', 'Ônibus'


class Trip(TimestampedModel):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_trips',
        verbose_name='Criado por',
    )
    origin_city = models.CharField('Cidade de origem', max_length=100)
    origin_state = models.CharField(
        'Estado de origem', max_length=2, choices=State.choices
    )
    destination_city = models.CharField('Cidade de destino', max_length=100)
    destination_state = models.CharField(
        'Estado de destino', max_length=2, choices=State.choices
    )
    trip_type = models.CharField(
        'Tipo de viagem', max_length=10, choices=TripType.choices
    )
    start_date = models.DateField('Data de início')
    end_date = models.DateField('Data de fim', null=True, blank=True)

    class Meta:
        verbose_name = 'Viagem'
        verbose_name_plural = 'Viagens'
        ordering = ['-start_date', '-id']

    def __str__(self):
        return (
            f'{self.origin_city}/{self.origin_state} → '
            f'{self.destination_city}/{self.destination_state}'
        )
