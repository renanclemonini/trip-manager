from decimal import Decimal
import re

from django import forms
from django.core.exceptions import ValidationError

from common.choices import State
from vehicles import services
from vehicles.models import normalize_plate

DATE_WIDGET = forms.DateInput(
    attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'
)
DATETIME_WIDGET = forms.DateTimeInput(
    attrs={
        'class': 'form-control',
        'type': 'datetime-local',
        'data-now': 'true',
    },
    format='%Y-%m-%dT%H:%M',
)

PLATE_PATTERN = re.compile(r'^[A-Z]{3}[0-9]{4}$|^[A-Z]{3}[0-9][A-Z][0-9]{2}$')


class VehicleTripForm(forms.Form):
    brand = forms.CharField(
        label='Marca',
        max_length=80,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    model = forms.CharField(
        label='Modelo',
        max_length=80,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    initial_mileage = forms.IntegerField(
        label='Odômetro inicial',
        min_value=0,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'data-mask': 'integer',
            'placeholder': '0',
        }),
    )
    plate = forms.CharField(
        label='Placa',
        max_length=8,
        required=False,
        help_text='Necessária para importar o extrato de pedágio.',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'off',
            'placeholder': 'ABC1D23',
        }),
    )

    def clean_plate(self):
        plate = normalize_plate(self.cleaned_data.get('plate'))
        if plate is None:
            return None
        if not PLATE_PATTERN.match(plate):
            raise forms.ValidationError(
                'Informe uma placa válida '
                '(formato antigo ABC1234 ou Mercosul ABC1D23).'
            )
        return plate


class BusTripForm(forms.Form):
    brand = forms.CharField(
        label='Marca do ônibus',
        max_length=80,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    model = forms.CharField(
        label='Modelo do ônibus',
        max_length=80,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    company = forms.CharField(
        label='Empresa prestadora',
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    amount_paid = forms.DecimalField(
        label='Valor custeado',
        max_digits=8,
        decimal_places=2,
        min_value=0,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'inputmode': 'decimal',
            'autocomplete': 'off',
            'data-mask': 'currency',
            'placeholder': 'R$ 0,00',
        }),
    )
    start_date = forms.DateField(label='Data de início', widget=DATE_WIDGET)


class RefuelingForm(forms.Form):
    state = forms.ChoiceField(
        label='Estado',
        choices=[('', '---------')] + State.choices,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'data-ibge-uf': 'true',
        }),
    )
    city = forms.CharField(
        label='Cidade',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'off',
            'data-ibge-city': 'true',
            'list': 'ibge-city-list',
        }),
    )
    liters = forms.DecimalField(
        label='Litros',
        max_digits=6,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'inputmode': 'decimal',
            'autocomplete': 'off',
            'data-mask': 'decimal',
            'placeholder': '0,00',
        }),
    )
    amount_spent = forms.DecimalField(
        label='Valor gasto',
        max_digits=8,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'inputmode': 'decimal',
            'autocomplete': 'off',
            'data-mask': 'currency',
            'placeholder': 'R$ 0,00',
        }),
    )
    total_mileage = forms.IntegerField(
        label='Odômetro total',
        min_value=0,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'data-mask': 'integer',
            'placeholder': '0',
        }),
    )
    datetime = forms.DateTimeField(
        label='Data/hora', widget=DATETIME_WIDGET
    )

    def __init__(self, *args, trip=None, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.trip = trip
        self.instance = instance

    def clean(self):
        cleaned_data = super().clean()
        if self.trip is None or self._errors:
            return cleaned_data
        try:
            services.validate_refueling(
                self.trip, cleaned_data, instance=self.instance
            )
        except ValidationError as exc:
            if hasattr(exc, 'error_dict'):
                for field, errors in exc.error_dict.items():
                    for error in errors:
                        self.add_error(field, error)
            else:
                self.add_error(None, exc)
        return cleaned_data


class FlightTripForm(forms.Form):
    airline = forms.CharField(
        label='Companhia aérea',
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    aircraft_model = forms.CharField(
        label='Modelo do avião',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    ticket_price = forms.DecimalField(
        label='Valor da passagem',
        max_digits=8,
        decimal_places=2,
        min_value=0,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'inputmode': 'decimal',
            'autocomplete': 'off',
            'data-mask': 'currency',
            'placeholder': 'R$ 0,00',
        }),
    )
    departure_datetime = forms.DateTimeField(
        label='Data/hora de ida', widget=DATETIME_WIDGET
    )
    return_datetime = forms.DateTimeField(
        label='Data/hora de volta', required=False, widget=DATETIME_WIDGET
    )

    def clean(self):
        cleaned_data = super().clean()
        departure = cleaned_data.get('departure_datetime')
        return_datetime = cleaned_data.get('return_datetime')
        if departure and return_datetime and return_datetime < departure:
            self.add_error(
                'return_datetime',
                'A volta não pode ser anterior à ida.',
            )
        return cleaned_data
