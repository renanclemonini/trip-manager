import uuid

from django.db import models
from django.utils.formats import number_format

from common.choices import State
from common.models import TimestampedModel
from trips.models import Trip


class VehicleType(models.TextChoices):
    CAR = "car", "Carro"
    BUS = "bus", "Ônibus"


def normalize_plate(value):
    """Uppercase plate without hyphen/spaces; empty input becomes None."""
    if value is None:
        return None
    normalized = value.upper().replace("-", "").replace(" ", "")
    return normalized or None


class Vehicle(TimestampedModel):
    vehicle_type = models.CharField("Tipo", max_length=10, choices=VehicleType.choices)
    brand = models.CharField("Marca", max_length=80)
    model = models.CharField("Modelo", max_length=80)
    plate = models.CharField("Placa", max_length=7, null=True, blank=True)

    class Meta:
        verbose_name = "Veículo"
        verbose_name_plural = "Veículos"

    def save(self, *args, **kwargs):
        self.plate = normalize_plate(self.plate)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.brand} {self.model}"


class TripVehicle(TimestampedModel):
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, verbose_name="Viagem")
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, verbose_name="Veículo"
    )
    initial_mileage = models.PositiveIntegerField("Odômetro inicial")
    final_mileage = models.PositiveIntegerField(
        "Odômetro final", null=True, blank=True
    )

    class Meta:
        verbose_name = "Veículo da viagem"
        verbose_name_plural = "Veículos da viagem"

    @property
    def last_refueling(self):
        """Latest record by odometer — highest total_mileage of the trip."""
        return self.trip.refuelings.order_by("-total_mileage").first()

    @property
    def effective_mileage(self):
        """Highest known odometer: initial, last refueling and final (RF33)."""
        known = [self.initial_mileage]
        if self.final_mileage is not None:
            known.append(self.final_mileage)
        last_refueling = self.last_refueling
        if last_refueling:
            known.append(last_refueling.total_mileage)
        return max(known)

    @property
    def current_mileage(self):
        return self.effective_mileage

    def __str__(self):
        current_mileage = number_format(self.current_mileage, force_grouping=True)
        return f"{self.trip}: {self.vehicle.brand} {self.vehicle.model} ({current_mileage} km)"


class Refueling(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="refuelings",
        verbose_name="Viagem",
    )
    city = models.CharField("Cidade", max_length=100)
    state = models.CharField("Estado", max_length=2, choices=State.choices)
    liters = models.DecimalField("Litros", max_digits=6, decimal_places=2)
    amount_spent = models.DecimalField("Valor gasto", max_digits=8, decimal_places=2)
    total_mileage = models.PositiveIntegerField("Odômetro total")
    datetime = models.DateTimeField("Data/hora")

    class Meta:
        verbose_name = "Abastecimento"
        verbose_name_plural = "Abastecimentos"
        ordering = ["-total_mileage"]

    def __str__(self):
        return f"{self.city}/{self.state} — {self.total_mileage} km"

    @property
    def previous_refueling(self):
        """Previous record by odometer — insertion/sync order is irrelevant."""
        return (
            Refueling.objects.filter(
                trip_id=self.trip_id, total_mileage__lt=self.total_mileage
            )
            .order_by("-total_mileage")
            .first()
        )

    @property
    def previous_mileage(self):
        previous = self.previous_refueling
        if previous:
            return previous.total_mileage
        trip_vehicle = getattr(self.trip, "tripvehicle", None)
        return trip_vehicle.initial_mileage if trip_vehicle else None

    @property
    def distance_traveled(self):
        base = self.previous_mileage
        return None if base is None else self.total_mileage - base

    @property
    def km_per_liter(self):
        km = self.distance_traveled
        return round(km / self.liters, 2) if km and self.liters else None

    @property
    def cost_per_km(self):
        km = self.distance_traveled
        return round(self.amount_spent / km, 2) if km else None


class BusTrip(TimestampedModel):
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, verbose_name="Viagem")
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, verbose_name="Veículo"
    )
    company = models.CharField("Empresa prestadora", max_length=150)
    amount_paid = models.DecimalField("Valor custeado", max_digits=8, decimal_places=2)
    start_date = models.DateField("Data de início")

    class Meta:
        verbose_name = "Viagem de ônibus"
        verbose_name_plural = "Viagens de ônibus"


class FlightTrip(TimestampedModel):
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, verbose_name="Viagem")
    airline = models.CharField("Companhia aérea", max_length=150)
    aircraft_model = models.CharField(
        "Modelo do avião", max_length=100, null=True, blank=True
    )
    ticket_price = models.DecimalField(
        "Valor da passagem", max_digits=8, decimal_places=2
    )
    departure_datetime = models.DateTimeField("Data/hora de ida")
    return_datetime = models.DateTimeField("Data/hora de volta", null=True, blank=True)

    class Meta:
        verbose_name = "Viagem de avião"
        verbose_name_plural = "Viagens de avião"
