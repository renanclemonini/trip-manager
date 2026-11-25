from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum

from tolls.models import Toll
from trips.models import TripType


def validate_toll(trip, data):
    """Structural rules: tolls only make sense on car trips."""
    if trip.trip_type != TripType.CAR:
        raise ValidationError(
            'Pedágio só pode ser registrado em viagem de carro.'
        )


def create_toll(trip, data, pk=None):
    validate_toll(trip, data)
    kwargs = {'trip': trip, **data}
    if pk is not None:
        kwargs['id'] = pk
    return Toll.objects.create(**kwargs)


def update_toll(trip, toll, data):
    validate_toll(trip, data)
    for field, value in data.items():
        setattr(toll, field, value)
    toll.save()
    return toll


def upsert_toll(trip, pk, data):
    """Idempotent write keyed by the client generated UUID (RF22/RNF14)."""
    instance = Toll.objects.filter(pk=pk).first()
    if instance is not None and instance.trip_id != trip.pk:
        raise ValidationError({
            'id': ['Este id pertence a outra viagem.']
        })
    if instance is not None:
        return update_toll(trip, instance, data)
    return create_toll(trip, data, pk=pk)


def get_toll_total(trip):
    total = Toll.objects.filter(trip=trip).aggregate(
        total=Sum('amount_spent')
    )['total']
    return total or Decimal('0.00')
