import uuid

from django.db import models

from common.choices import State
from common.models import TimestampedModel
from trips.models import Trip


class Lodging(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='lodgings',
        verbose_name='Viagem',
    )
    city = models.CharField('Cidade', max_length=100)
    state = models.CharField('Estado', max_length=2, choices=State.choices)
    amount_spent = models.DecimalField(
        'Valor gasto', max_digits=8, decimal_places=2
    )
    check_in = models.DateTimeField('Entrada')
    check_out = models.DateTimeField('Saída')

    class Meta:
        verbose_name = 'Hospedagem'
        verbose_name_plural = 'Hospedagens'
        ordering = ['-check_in']

    @property
    def nights(self):
        if not self.check_in or not self.check_out:
            return None
        return (self.check_out.date() - self.check_in.date()).days

    def __str__(self):
        return f'{self.city} - {self.state} ({self.check_in.date()} a {self.check_out.date()})'


class Meal(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='meals',
        verbose_name='Viagem',
    )
    city = models.CharField('Cidade', max_length=100)
    state = models.CharField('Estado', max_length=2, choices=State.choices)
    amount_spent = models.DecimalField(
        'Valor gasto', max_digits=8, decimal_places=2
    )
    datetime = models.DateTimeField('Data/hora')

    class Meta:
        verbose_name = 'Refeição'
        verbose_name_plural = 'Refeições'
        ordering = ['-datetime']

    def __str__(self):
        formatted_datetime = self.datetime.strftime('%d/%m/%Y às %H:%M')
        return f'{formatted_datetime} em {self.city}/{self.state}: R$ {self.amount_spent}'


class Sightseeing(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='sightseeings',
        verbose_name='Viagem',
    )
    amount_spent = models.DecimalField(
        'Valor gasto', max_digits=8, decimal_places=2
    )
    description = models.CharField('Descrição', max_length=150, blank=True)

    class Meta:
        verbose_name = 'Passeio'
        verbose_name_plural = 'Passeios'
        ordering = ['-created_at']
