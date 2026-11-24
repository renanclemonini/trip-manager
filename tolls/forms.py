from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from tolls import services

DATETIME_WIDGET = forms.DateTimeInput(
    attrs={
        'class': 'form-control',
        'type': 'datetime-local',
        'data-now': 'true',
    },
    format='%Y-%m-%dT%H:%M',
)


class TollForm(forms.Form):
    location = forms.CharField(
        label='Local/Praça',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'off',
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
            services.validate_toll(self.trip, cleaned_data)
        except ValidationError as exc:
            if hasattr(exc, 'error_dict'):
                for field, errors in exc.error_dict.items():
                    for error in errors:
                        self.add_error(field, error)
            else:
                self.add_error(None, exc)
        return cleaned_data
