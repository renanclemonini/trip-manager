from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    Max,
    Min,
    Sum,
)

from trips.models import TripType
from vehicles.models import (
    BusTrip,
    FlightTrip,
    Refueling,
    TripVehicle,
    Vehicle,
    VehicleType,
)


def _assert_trip_type(trip, expected, transport_label):
    if trip.trip_type != expected:
        raise ValidationError(
            f'{transport_label} só pode ser cadastrado em viagem compatível.'
        )


def create_car_transport(trip, data):
    _assert_trip_type(trip, TripType.CAR, 'Veículo')
    with transaction.atomic():
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR,
            brand=data['brand'],
            model=data['model'],
        )
        return TripVehicle.objects.create(
            trip=trip,
            vehicle=vehicle,
            initial_mileage=data['initial_mileage'],
        )


def update_car_transport(trip, data):
    _assert_trip_type(trip, TripType.CAR, 'Veículo')
    with transaction.atomic():
        trip_vehicle = TripVehicle.objects.get(trip=trip)
        vehicle = trip_vehicle.vehicle
        vehicle.brand = data['brand']
        vehicle.model = data['model']
        vehicle.save()
        trip_vehicle.initial_mileage = data['initial_mileage']
        trip_vehicle.save()
        return trip_vehicle


def create_bus_transport(trip, data):
    _assert_trip_type(trip, TripType.BUS, 'Dados do ônibus')
    with transaction.atomic():
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.BUS,
            brand=data['brand'],
            model=data['model'],
        )
        return BusTrip.objects.create(
            trip=trip,
            vehicle=vehicle,
            company=data['company'],
            amount_paid=data['amount_paid'],
            start_date=data['start_date'],
        )


def update_bus_transport(trip, data):
    _assert_trip_type(trip, TripType.BUS, 'Dados do ônibus')
    with transaction.atomic():
        bus_trip = BusTrip.objects.get(trip=trip)
        vehicle = bus_trip.vehicle
        vehicle.brand = data['brand']
        vehicle.model = data['model']
        vehicle.save()
        bus_trip.company = data['company']
        bus_trip.amount_paid = data['amount_paid']
        bus_trip.start_date = data['start_date']
        bus_trip.save()
        return bus_trip


def create_flight_transport(trip, data):
    _assert_trip_type(trip, TripType.PLANE, 'Dados do voo')
    return FlightTrip.objects.create(
        trip=trip,
        airline=data['airline'],
        aircraft_model=data['aircraft_model'] or None,
        ticket_price=data['ticket_price'],
        departure_datetime=data['departure_datetime'],
        return_datetime=data['return_datetime'],
    )


def update_flight_transport(trip, data):
    _assert_trip_type(trip, TripType.PLANE, 'Dados do voo')
    flight_trip = FlightTrip.objects.get(trip=trip)
    flight_trip.airline = data['airline']
    flight_trip.aircraft_model = data['aircraft_model'] or None
    flight_trip.ticket_price = data['ticket_price']
    flight_trip.departure_datetime = data['departure_datetime']
    flight_trip.return_datetime = data['return_datetime']
    flight_trip.save()
    return flight_trip


def _assert_refueling_allowed(trip):
    if trip.trip_type != TripType.CAR:
        raise ValidationError(
            'Abastecimento só pode ser registrado em viagem de carro.'
        )
    if not TripVehicle.objects.filter(trip=trip).exists():
        raise ValidationError(
            'Cadastre o veículo da viagem antes dos abastecimentos.'
        )


def validate_refueling(trip, data, instance=None):
    """Structural rules: car trip with vehicle, odometer range and uniqueness."""
    _assert_refueling_allowed(trip)
    trip_vehicle = trip.tripvehicle
    total_mileage = data['total_mileage']
    if total_mileage < trip_vehicle.initial_mileage:
        raise ValidationError({
            'total_mileage': [
                'Informe um odômetro maior ou igual ao inicial da viagem.'
            ]
        })
    duplicates = Refueling.objects.filter(
        trip=trip, total_mileage=total_mileage
    )
    if instance is not None:
        duplicates = duplicates.exclude(pk=instance.pk)
    if duplicates.exists():
        raise ValidationError({
            'total_mileage': [
                'Já existe um abastecimento com este odômetro nesta viagem.'
            ]
        })


def create_refueling(trip, data, pk=None):
    validate_refueling(trip, data)
    kwargs = {'trip': trip, **data}
    if pk is not None:
        kwargs['id'] = pk
    return Refueling.objects.create(**kwargs)


def update_refueling(trip, refueling, data):
    validate_refueling(trip, data, instance=refueling)
    for field, value in data.items():
        setattr(refueling, field, value)
    refueling.save()
    return refueling


def upsert_refueling(trip, pk, data):
    """Idempotent write keyed by the client generated UUID (RF22/RNF14)."""
    instance = Refueling.objects.filter(pk=pk).first()
    if instance is not None and instance.trip_id != trip.pk:
        raise ValidationError({
            'id': ['Este id pertence a outra viagem.']
        })
    if instance is not None:
        return update_refueling(trip, instance, data)
    return create_refueling(trip, data, pk=pk)


def get_refueling_stats(trip):
    """Price per liter metrics (RF11): weighted average, min and max."""
    refuelings = Refueling.objects.filter(trip=trip, liters__gt=0)
    totals = refuelings.aggregate(
        total_amount=Sum('amount_spent'), total_liters=Sum('liters')
    )
    if not totals['total_liters']:
        return {
            'weighted_average_price': None,
            'min_price': None,
            'max_price': None,
        }
    unit_price = ExpressionWrapper(
        F('amount_spent') / F('liters'),
        output_field=DecimalField(max_digits=12, decimal_places=4),
    )
    prices = refuelings.annotate(unit_price=unit_price).aggregate(
        min_price=Min('unit_price'), max_price=Max('unit_price')
    )
    return {
        'weighted_average_price': round(
            totals['total_amount'] / totals['total_liters'], 2
        ),
        'min_price': round(prices['min_price'], 2),
        'max_price': round(prices['max_price'], 2),
    }


def get_refueling_total(trip):
    total = Refueling.objects.filter(trip=trip).aggregate(
        total=Sum('amount_spent')
    )['total']
    return total or Decimal('0.00')


def get_transport_total(trip):
    """Transport category (decision C): flight ticket or bus amount paid."""
    if trip.trip_type == TripType.PLANE:
        flight_trip = getattr(trip, 'flighttrip', None)
        return flight_trip.ticket_price if flight_trip else Decimal('0.00')
    if trip.trip_type == TripType.BUS:
        bus_trip = getattr(trip, 'bustrip', None)
        return bus_trip.amount_paid if bus_trip else Decimal('0.00')
    return Decimal('0.00')


def get_refueling_aggregates(trip):
    """Trip level consumption (RF11): distance, liters and weighted averages."""
    refuelings = Refueling.objects.filter(trip=trip)
    totals = refuelings.aggregate(
        total_amount=Sum('amount_spent'), total_liters=Sum('liters')
    )
    trip_vehicle = getattr(trip, 'tripvehicle', None)
    last_refueling = trip_vehicle.last_refueling if trip_vehicle else None
    total_distance = None
    if last_refueling:
        total_distance = (
            last_refueling.total_mileage - trip_vehicle.initial_mileage
        )
    total_liters = totals['total_liters']
    total_amount = totals['total_amount']
    return {
        'total_distance': total_distance,
        'total_liters': total_liters,
        'total_amount': total_amount,
        'average_km_per_liter': (
            round(total_distance / total_liters, 2)
            if total_distance and total_liters
            else None
        ),
        'average_cost_per_km': (
            round(total_amount / total_distance, 2)
            if total_distance and total_amount
            else None
        ),
    }
