from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, FormView, ListView

from expenses import services
from expenses.forms import LodgingForm, MealForm, SightseeingForm
from expenses.models import Lodging, Meal, Sightseeing
from trips.mixins import ExpectedTripTypeMixin, TripContextMixin
from trips.models import TripType


class ExpenseListViewMixin:
    model = None

    def get_queryset(self):
        return self.model.objects.filter(trip=self.get_trip())


class ExpenseDetailViewMixin:
    model = None

    def get_object(self, queryset=None):
        return get_object_or_404(
            self.model, trip=self.get_trip(), pk=self.kwargs['pk']
        )


class ExpenseFormViewMixin:
    list_url_name = ''
    page_heading = ''
    success_message = ''
    is_create = False

    def get_success_url(self):
        return reverse(
            self.list_url_name, kwargs={'trip_id': self.kwargs['trip_id']}
        )

    def form_valid(self, form):
        self.save_expense(form)
        messages.success(self.request, self.success_message)
        return redirect(self.get_success_url())


class ExpenseUpdateViewMixin(ExpenseFormViewMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.expense = get_object_or_404(
                self.model, trip=self.get_trip(), pk=kwargs['pk']
            )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.expense
        return kwargs


class LodgingListView(ExpenseListViewMixin, TripContextMixin, ListView):
    model = Lodging
    template_name = 'expenses/lodging_list.html'
    context_object_name = 'lodgings'


class LodgingDetailView(ExpenseDetailViewMixin, TripContextMixin, DetailView):
    model = Lodging
    template_name = 'expenses/lodging_detail.html'
    context_object_name = 'lodging'


class LodgingCreateView(ExpenseFormViewMixin, TripContextMixin, FormView):
    model = Lodging
    form_class = LodgingForm
    template_name = 'expenses/lodging_form.html'
    list_url_name = 'lodging_list'
    page_heading = 'Nova hospedagem'
    success_message = 'Hospedagem registrada com sucesso.'
    is_create = True

    def save_expense(self, form):
        services.save_lodging(self.get_trip(), form.cleaned_data)


class LodgingUpdateView(ExpenseUpdateViewMixin, TripContextMixin, FormView):
    model = Lodging
    form_class = LodgingForm
    template_name = 'expenses/lodging_form.html'
    list_url_name = 'lodging_list'
    page_heading = 'Editar hospedagem'
    success_message = 'Hospedagem atualizada com sucesso.'

    def save_expense(self, form):
        services.save_lodging(
            self.get_trip(), form.cleaned_data, instance=self.expense
        )


class MealListView(ExpenseListViewMixin, TripContextMixin, ListView):
    model = Meal
    template_name = 'expenses/meal_list.html'
    context_object_name = 'meals'


class MealDetailView(ExpenseDetailViewMixin, TripContextMixin, DetailView):
    model = Meal
    template_name = 'expenses/meal_detail.html'
    context_object_name = 'meal'


class MealCreateView(ExpenseFormViewMixin, TripContextMixin, FormView):
    model = Meal
    form_class = MealForm
    template_name = 'expenses/meal_form.html'
    list_url_name = 'meal_list'
    page_heading = 'Nova alimentação'
    success_message = 'Alimentação registrada com sucesso.'
    is_create = True

    def save_expense(self, form):
        services.save_meal(self.get_trip(), form.cleaned_data)


class MealUpdateView(ExpenseUpdateViewMixin, TripContextMixin, FormView):
    model = Meal
    form_class = MealForm
    template_name = 'expenses/meal_form.html'
    list_url_name = 'meal_list'
    page_heading = 'Editar alimentação'
    success_message = 'Alimentação atualizada com sucesso.'

    def save_expense(self, form):
        services.save_meal(
            self.get_trip(), form.cleaned_data, instance=self.expense
        )


class SightseeingListView(
    ExpenseListViewMixin, ExpectedTripTypeMixin, ListView
):
    expected_trip_type = TripType.BUS
    model = Sightseeing
    template_name = 'expenses/sightseeing_list.html'
    context_object_name = 'sightseeings'


class SightseeingDetailView(
    ExpenseDetailViewMixin, ExpectedTripTypeMixin, DetailView
):
    expected_trip_type = TripType.BUS
    model = Sightseeing
    template_name = 'expenses/sightseeing_detail.html'
    context_object_name = 'sightseeing'


class SightseeingCreateView(ExpenseFormViewMixin, ExpectedTripTypeMixin, FormView):
    expected_trip_type = TripType.BUS
    model = Sightseeing
    form_class = SightseeingForm
    template_name = 'expenses/sightseeing_form.html'
    list_url_name = 'sightseeing_list'
    page_heading = 'Novo passeio'
    success_message = 'Passeio registrado com sucesso.'
    is_create = True

    def save_expense(self, form):
        services.save_sightseeing(self.get_trip(), form.cleaned_data)


class SightseeingUpdateView(
    ExpenseUpdateViewMixin, ExpectedTripTypeMixin, FormView
):
    expected_trip_type = TripType.BUS
    model = Sightseeing
    form_class = SightseeingForm
    template_name = 'expenses/sightseeing_form.html'
    list_url_name = 'sightseeing_list'
    page_heading = 'Editar passeio'
    success_message = 'Passeio atualizado com sucesso.'

    def save_expense(self, form):
        services.save_sightseeing(
            self.get_trip(), form.cleaned_data, instance=self.expense
        )
