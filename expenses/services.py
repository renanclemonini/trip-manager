from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Avg, Max, Min, Sum

from trips.models import TripType
from expenses.models import Lodging, Meal, Sightseeing


def _save(model, trip, data, instance=None, pk=None):
    if instance is not None:
        obj = instance
    else:
        obj = model(trip=trip)
        if pk is not None:
            obj.pk = pk
    for field, value in data.items():
        setattr(obj, field, value)
    obj.save()
    return obj


def _get_conflicting(model, trip, pk):
    instance = model.objects.filter(pk=pk).first()
    if instance is not None and instance.trip_id != trip.pk:
        raise ValidationError({
            'id': ['Este id pertence a outra viagem.']
        })
    return instance


def save_lodging(trip, data, instance=None):
    return _save(Lodging, trip, data, instance)


def save_meal(trip, data, instance=None):
    return _save(Meal, trip, data, instance)


def _assert_sightseeing_allowed(trip):
    if trip.trip_type != TripType.BUS:
        raise ValidationError(
            'Passeio só pode ser registrado em viagem de ônibus.'
        )


def save_sightseeing(trip, data, instance=None):
    _assert_sightseeing_allowed(trip)
    return _save(Sightseeing, trip, data, instance)


def get_meal_stats(trip):
    """Meal statistics (RF12): arithmetic average, min and max."""
    stats = Meal.objects.filter(trip=trip).aggregate(
        average_amount=Avg('amount_spent'),
        min_amount=Min('amount_spent'),
        max_amount=Max('amount_spent'),
    )
    if stats['average_amount'] is not None:
        stats['average_amount'] = round(stats['average_amount'], 2)
    return stats


def _get_total(model, trip):
    total = model.objects.filter(trip=trip).aggregate(
        total=Sum('amount_spent')
    )['total']
    return total or Decimal('0.00')


def get_lodging_total(trip):
    return _get_total(Lodging, trip)


def get_meal_total(trip):
    return _get_total(Meal, trip)


def get_sightseeing_total(trip):
    return _get_total(Sightseeing, trip)


def upsert_lodging(trip, pk, data):
    """Idempotent write keyed by the client generated UUID (RF22/RNF14)."""
    return _save(
        Lodging,
        trip,
        data,
        instance=_get_conflicting(Lodging, trip, pk),
        pk=pk,
    )


def upsert_meal(trip, pk, data):
    return _save(
        Meal,
        trip,
        data,
        instance=_get_conflicting(Meal, trip, pk),
        pk=pk,
    )


def upsert_sightseeing(trip, pk, data):
    _assert_sightseeing_allowed(trip)
    return _save(
        Sightseeing,
        trip,
        data,
        instance=_get_conflicting(Sightseeing, trip, pk),
        pk=pk,
    )
