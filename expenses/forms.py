from django import forms

from expenses.models import Lodging, Meal, Sightseeing

CITY_WIDGET = forms.TextInput(attrs={
    'class': 'form-control',
    'autocomplete': 'off',
    'data-ibge-city': 'true',
    'list': 'ibge-city-list',
})
STATE_WIDGET = forms.Select(attrs={
    'class': 'form-select',
    'data-ibge-uf': 'true',
})
AMOUNT_WIDGET = forms.TextInput(attrs={
    'class': 'form-control',
    'inputmode': 'decimal',
    'autocomplete': 'off',
    'data-mask': 'currency',
    'placeholder': 'R$ 0,00',
})
DATETIME_WIDGET = forms.DateTimeInput(
    attrs={
        'class': 'form-control',
        'type': 'datetime-local',
        'data-now': 'true',
    },
    format='%Y-%m-%dT%H:%M',
)


class LodgingForm(forms.ModelForm):
    class Meta:
        model = Lodging
        fields = ('state', 'city', 'amount_spent', 'check_in', 'check_out')
        widgets = {
            'city': CITY_WIDGET,
            'state': STATE_WIDGET,
            'amount_spent': AMOUNT_WIDGET,
            'check_in': DATETIME_WIDGET,
            'check_out': DATETIME_WIDGET,
        }

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')
        if check_in and check_out and check_out < check_in:
            self.add_error(
                'check_out',
                'A saída não pode ser anterior à entrada.',
            )
        return cleaned_data


class MealForm(forms.ModelForm):
    class Meta:
        model = Meal
        fields = ('state', 'city', 'amount_spent', 'datetime')
        widgets = {
            'city': CITY_WIDGET,
            'state': STATE_WIDGET,
            'amount_spent': AMOUNT_WIDGET,
            'datetime': DATETIME_WIDGET,
        }


class SightseeingForm(forms.ModelForm):
    class Meta:
        model = Sightseeing
        fields = ('amount_spent', 'description')
        widgets = {
            'amount_spent': AMOUNT_WIDGET,
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }
