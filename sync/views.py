import json
from uuid import UUID

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.views import View

from expenses import services as expenses_services
from expenses.forms import LodgingForm, MealForm, SightseeingForm
from expenses.models import Lodging, Meal, Sightseeing
from trips.models import Trip
from vehicles import services as vehicles_services
from vehicles.forms import RefuelingForm
from vehicles.models import Refueling


class BaseSyncView(LoginRequiredMixin, View):
    """JSON sync endpoint: login + CSRF, payload validation via app forms."""

    http_method_names = ['post']

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return super().handle_no_permission()
        return JsonResponse(
            {
                'status': 'error',
                'errors': {'detail': ['Autenticação necessária.']},
            },
            status=403,
        )

    def post(self, request, *args, **kwargs):
        payload = self._parse_payload(request)
        if isinstance(payload, JsonResponse):
            return payload
        trip = self._resolve_trip(request, payload)
        if isinstance(trip, JsonResponse):
            return trip
        record_id = self._parse_record_id(payload)
        if isinstance(record_id, JsonResponse):
            return record_id
        return self.handle_sync(trip, record_id, payload)

    def _parse_payload(self, request):
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self.error_response(
                {'detail': ['JSON inválido.']}
            )
        if not isinstance(payload, dict):
            return self.error_response(
                {'detail': ['O payload deve ser um objeto JSON.']}
            )
        return payload

    def _resolve_trip(self, request, payload):
        trip_id = payload.get('trip')
        if trip_id is None:
            return self.error_response({'trip': ['Campo obrigatório.']})
        trip = Trip.objects.filter(pk=trip_id).first()
        if trip is None:
            raise Http404
        return trip

    def _parse_record_id(self, payload):
        raw_id = payload.get('id')
        if not raw_id:
            return self.error_response({'id': ['Campo obrigatório.']})
        try:
            return UUID(str(raw_id))
        except ValueError:
            return self.error_response({'id': ['UUID inválido.']})

    def error_response(self, errors, status=400):
        return JsonResponse({'status': 'error', 'errors': errors}, status=status)

    def validation_error_response(self, exc):
        if hasattr(exc, 'error_dict'):
            errors = {
                field: [str(message) for message in messages]
                for field, messages in exc.error_dict.items()
            }
        else:
            errors = {'detail': [str(message) for message in exc.messages]}
        return self.error_response(errors)

    def success_response(self, instance, created):
        return JsonResponse(
            {'status': 'ok', 'id': str(instance.pk)},
            status=201 if created else 200,
        )

    def handle_sync(self, trip, record_id, payload):
        raise NotImplementedError


class RefuelingSyncView(BaseSyncView):
    def handle_sync(self, trip, record_id, payload):
        instance = Refueling.objects.filter(pk=record_id, trip=trip).first()
        form = RefuelingForm(data=payload, trip=trip, instance=instance)
        if not form.is_valid():
            return self.error_response(form.errors.get_json_data())
        try:
            refueling = vehicles_services.upsert_refueling(
                trip, record_id, form.cleaned_data
            )
        except ValidationError as exc:
            return self.validation_error_response(exc)
        return self.success_response(refueling, created=instance is None)


class LodgingSyncView(BaseSyncView):
    def handle_sync(self, trip, record_id, payload):
        instance = Lodging.objects.filter(pk=record_id, trip=trip).first()
        form = LodgingForm(data=payload, instance=instance)
        if not form.is_valid():
            return self.error_response(form.errors.get_json_data())
        try:
            lodging = expenses_services.upsert_lodging(
                trip, record_id, form.cleaned_data
            )
        except ValidationError as exc:
            return self.validation_error_response(exc)
        return self.success_response(lodging, created=instance is None)


class MealSyncView(BaseSyncView):
    def handle_sync(self, trip, record_id, payload):
        instance = Meal.objects.filter(pk=record_id, trip=trip).first()
        form = MealForm(data=payload, instance=instance)
        if not form.is_valid():
            return self.error_response(form.errors.get_json_data())
        try:
            meal = expenses_services.upsert_meal(
                trip, record_id, form.cleaned_data
            )
        except ValidationError as exc:
            return self.validation_error_response(exc)
        return self.success_response(meal, created=instance is None)


class SightseeingSyncView(BaseSyncView):
    def handle_sync(self, trip, record_id, payload):
        instance = Sightseeing.objects.filter(pk=record_id, trip=trip).first()
        form = SightseeingForm(data=payload, instance=instance)
        if not form.is_valid():
            return self.error_response(form.errors.get_json_data())
        try:
            sightseeing = expenses_services.upsert_sightseeing(
                trip, record_id, form.cleaned_data
            )
        except ValidationError as exc:
            return self.validation_error_response(exc)
        return self.success_response(sightseeing, created=instance is None)
