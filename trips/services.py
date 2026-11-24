from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from expenses import services as expenses_services
from trips.models import Trip, TripType
from vehicles import services as vehicles_services
from vehicles.models import Refueling, TripVehicle

POST_CREATE_URL_NAMES = {
    TripType.CAR: 'vehicle_new',
    TripType.BUS: 'bus_new',
    TripType.PLANE: 'flight_new',
}

DASHBOARD_CATEGORY_LABELS = {
    'transport': 'Transporte',
    'refueling': 'Abastecimento',
    'lodging': 'Hospedagem',
    'meal': 'Alimentação',
    'sightseeing': 'Passeios',
}

DASHBOARD_CATEGORIES_BY_TRIP_TYPE = {
    TripType.CAR: ('refueling', 'lodging', 'meal'),
    TripType.PLANE: ('transport', 'lodging', 'meal'),
    TripType.BUS: ('transport', 'lodging', 'meal', 'sightseeing'),
}


def save_trip(*, form, created_by):
    """Persist the form data assigning the trip creator (audit only)."""
    trip = form.save(commit=False)
    trip.created_by = created_by
    trip.save()
    return trip


def get_trip_post_create_path(trip):
    """Post-create destination per trip type (PRD section 10 routes)."""
    url_name = POST_CREATE_URL_NAMES[trip.trip_type]
    return reverse(url_name, kwargs={'trip_id': trip.pk})


def finish_trip(*, trip, end_datetime, final_mileage):
    """Finish a car trip, only once (RF27), recording the final odometer.

    RF33: the trip's end datetime and the vehicle's final mileage are stored
    atomically across the two tables. The conditional update guards against a
    concurrent second finish attempt that could otherwise overwrite an already
    set end_datetime.
    """
    with transaction.atomic():
        updated = (
            Trip.objects
            .filter(
                pk=trip.pk,
                trip_type=TripType.CAR,
                end_datetime__isnull=True,
            )
            .update(end_datetime=end_datetime, updated_at=timezone.now())
        )
        if updated != 1:
            return False
        vehicles_updated = TripVehicle.objects.filter(
            trip_id=trip.pk
        ).update(
            final_mileage=final_mileage, updated_at=timezone.now()
        )
        if vehicles_updated != 1:
            raise ValidationError(
                'Cadastre o veículo da viagem antes de finalizá-la.'
            )
        return True


def _get_category_total(trip, key):
    if key == 'transport':
        return vehicles_services.get_transport_total(trip)
    if key == 'refueling':
        return vehicles_services.get_refueling_total(trip)
    if key == 'lodging':
        return expenses_services.get_lodging_total(trip)
    if key == 'meal':
        return expenses_services.get_meal_total(trip)
    return expenses_services.get_sightseeing_total(trip)


def _get_consumption_chart(trip):
    labels = []
    series = []
    for refueling in Refueling.objects.filter(trip=trip).order_by(
        'total_mileage'
    ):
        if refueling.km_per_liter is None:
            continue
        labels.append(f'{refueling.total_mileage} km')
        series.append(float(refueling.km_per_liter))
    return {'labels': labels, 'series': series}


def get_trip_dashboard(trip):
    """Compose the trip dashboard consuming each app service (RNF05)."""
    categories = [
        {
            'key': key,
            'label': DASHBOARD_CATEGORY_LABELS[key],
            'total': _get_category_total(trip, key),
        }
        for key in DASHBOARD_CATEGORIES_BY_TRIP_TYPE[trip.trip_type]
    ]
    grand_total = sum(
        (category['total'] for category in categories), Decimal('0.00')
    )
    refueling = None
    consumption_chart = None
    if trip.trip_type == TripType.CAR:
        refueling = {
            **vehicles_services.get_refueling_aggregates(trip),
            **vehicles_services.get_refueling_stats(trip),
        }
        consumption_chart = _get_consumption_chart(trip)
    return {
        'categories': categories,
        'grand_total': grand_total,
        'refueling': refueling,
        'meal_stats': expenses_services.get_meal_stats(trip),
        'chart_data': {
            'categories': {
                'labels': [category['label'] for category in categories],
                'series': [float(category['total']) for category in categories],
            },
            'consumption': consumption_chart,
        },
    }
