from django import forms
from django.utils import timezone

from common.choices import State
from trips.models import Trip, TripType

DATETIME_WIDGET = forms.DateTimeInput(
    attrs={
        'class': 'form-control',
        'type': 'datetime-local',
        'data-now': 'true',
    },
    format='%Y-%m-%dT%H:%M',
)


class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = (
            'origin_city',
            'origin_state',
            'destination_city',
            'destination_state',
            'trip_type',
            'start_datetime',
            'end_datetime',
        )
        widgets = {
            'origin_city': forms.TextInput(attrs={
                'class': 'form-control',
                'autocomplete': 'off',
                'data-ibge-city': 'true',
                'list': 'origin-city-list',
            }),
            'origin_state': forms.Select(attrs={
                'class': 'form-select',
                'data-ibge-uf': 'true',
            }),
            'destination_city': forms.TextInput(attrs={
                'class': 'form-control',
                'autocomplete': 'off',
                'data-ibge-city': 'true',
                'list': 'destination-city-list',
            }),
            'destination_state': forms.Select(attrs={
                'class': 'form-select',
                'data-ibge-uf': 'true',
            }),
            'trip_type': forms.Select(attrs={'class': 'form-select'}),
            'start_datetime': DATETIME_WIDGET,
            'end_datetime': DATETIME_WIDGET,
        }

    def clean(self):
        cleaned_data = super().clean()
        trip_type = cleaned_data.get('trip_type')
        start_datetime = cleaned_data.get('start_datetime')
        end_datetime = cleaned_data.get('end_datetime')
        if trip_type == TripType.CAR:
            cleaned_data['end_datetime'] = None
            return cleaned_data
        if trip_type in (TripType.BUS, TripType.PLANE) and not end_datetime:
            self.add_error(
                'end_datetime',
                'A data e hora de fim é obrigatória para viagens de '
                'ônibus e avião.',
            )
            return cleaned_data
        if start_datetime and end_datetime and end_datetime < start_datetime:
            self.add_error(
                'end_datetime',
                'A data e hora de fim não pode ser anterior à data e hora '
                'de início.',
            )
        return cleaned_data


class FinishTripForm(forms.Form):
    end_datetime = forms.DateTimeField(
        label='Data e hora de fim', widget=DATETIME_WIDGET
    )
    final_mileage = forms.IntegerField(
        label='Odômetro final',
        min_value=0,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'data-mask': 'integer',
            'placeholder': '0',
        }),
    )

    def __init__(self, *args, trip=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.trip = trip
        self.fields['end_datetime'].initial = timezone.localtime()

    def clean_end_datetime(self):
        end_datetime = self.cleaned_data['end_datetime']
        if self.trip and end_datetime < self.trip.start_datetime:
            raise forms.ValidationError(
                'A data e hora de fim não pode ser anterior à data e hora '
                'de início.'
            )
        return end_datetime

    def clean_final_mileage(self):
        final_mileage = self.cleaned_data['final_mileage']
        trip_vehicle = getattr(self.trip, 'tripvehicle', None)
        if trip_vehicle is None:
            return final_mileage
        current_mileage = trip_vehicle.current_mileage
        if final_mileage < current_mileage:
            raise forms.ValidationError(
                f'O odômetro final não pode ser menor que o odômetro '
                f'atual ({current_mileage} km).'
            )
        return final_mileage
