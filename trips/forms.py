from datetime import date

from django import forms

from common.choices import State
from trips.models import Trip, TripType

DATE_WIDGET = forms.DateInput(
    attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'
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
            'start_date',
            'end_date',
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
            'start_date': DATE_WIDGET,
            'end_date': DATE_WIDGET,
        }

    def clean(self):
        cleaned_data = super().clean()
        trip_type = cleaned_data.get('trip_type')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if trip_type == TripType.CAR:
            cleaned_data['end_date'] = None
            return cleaned_data
        if trip_type in (TripType.BUS, TripType.PLANE) and not end_date:
            self.add_error(
                'end_date',
                'A data de fim é obrigatória para viagens de ônibus e avião.',
            )
            return cleaned_data
        if start_date and end_date and end_date < start_date:
            self.add_error(
                'end_date',
                'A data de fim não pode ser anterior à data de início.',
            )
        return cleaned_data


class FinishTripForm(forms.Form):
    end_date = forms.DateField(label='Data de fim', widget=DATE_WIDGET)

    def __init__(self, *args, trip=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.trip = trip
        self.fields['end_date'].initial = date.today()

    def clean_end_date(self):
        end_date = self.cleaned_data['end_date']
        if self.trip and end_date < self.trip.start_date:
            raise forms.ValidationError(
                'A data de fim não pode ser anterior à data de início.'
            )
        return end_date
