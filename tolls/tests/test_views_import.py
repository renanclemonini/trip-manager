import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import get_current_timezone, make_aware

from tolls.models import Toll
from tolls.services import import_service
from tolls.services.extract_parser import parse_extract_text
from tolls.tests.fixtures import build_extract_text, toll_text
from trips.models import Trip, TripType
from vehicles.models import TripVehicle, Vehicle, VehicleType

TZ = get_current_timezone()
WKWEBTOPDF_AVAILABLE = shutil.which('wkhtmltopdf') is not None

PDF_HTML = """<!DOCTYPE html>
<html lang="pt-br"><head><meta charset="utf-8">
<style>
body {{ font-family: Helvetica, sans-serif; font-size: 9px; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #ccc; padding: 4px; vertical-align: top; }}
.desc {{ width: 46%; }} .num {{ width: 9%; text-align: right; }}
.date {{ width: 12%; }} .plate {{ width: 9%; }}
</style></head><body>
<h4>Extrato Sintético — Teste</h4>
<p>Filtro de transações — Data inicial: 25/10/2026 às 00:00
Data final: 24/11/2026 às 23:59 Placa: SYN-0A01</p>
<h4>Resumo de Transações</h4>
<table><tr><th>Recarga</th><th>Pedágio</th><th>Estacionamento</th><th>Outros</th></tr>
<tr><td>Quantidade: 0<br>Total: R$ 0.00</td>
<td>Quantidade: 1<br>Total: -R$ 6.90</td>
<td>Quantidade: 0<br>Total: R$ 0.00</td>
<td>Quantidade: 0<br>Total: R$ 0.00</td></tr></table>
<h4>Transações</h4>
<table>
<tr><th class="date">Data do lançamento</th><th class="plate">Veículo</th>
<th class="desc">Descrição da transação</th>
<th class="num">Crédito</th><th class="num">Débito</th><th class="num">Saldo</th></tr>
<tr><td class="date">23/11/2026 - 23:41:01</td><td class="plate">SYN-0A01</td>
<td class="desc">CONCESSIONARIA TESTE - PRAÇA ALFA SUL, 92+740, SP - 098 -
Cat. 1 - 23/11/2026 23:40:38</td>
<td class="num"></td><td class="num">-R$ 6.90</td><td class="num">R$ 48.36</td></tr>
</table>
</body></html>
"""


def build_pdf_bytes(html=PDF_HTML):
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / 'extrato.html'
        pdf_path = Path(tmp) / 'extrato.pdf'
        html_path.write_text(html, encoding='utf-8')
        subprocess.run(
            ['wkhtmltopdf', '-q', str(html_path), str(pdf_path)],
            check=True,
            capture_output=True,
        )
        return pdf_path.read_bytes()


def create_user(email='views-import@example.com'):
    return get_user_model().objects.create_user(
        email=email, password='strong-pass-123'
    )


def create_trip(user, trip_type=TripType.CAR, plate='SYN0A01',
                with_vehicle=True):
    trip = Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=trip_type,
        start_datetime=make_aware(datetime(2026, 11, 22, 8, 0), TZ),
    )
    if with_vehicle:
        vehicle = Vehicle.objects.create(
            vehicle_type=VehicleType.CAR,
            brand='Fiat',
            model='Argo',
            plate=plate,
        )
        TripVehicle.objects.create(
            trip=trip, vehicle=vehicle, initial_mileage=1000
        )
    return trip


def signed_payload(trip, user):
    result = parse_extract_text(
        build_extract_text(
            [
                toll_text(
                    description=(
                        'CONCESSIONARIA TESTE - PRAÇA ALFA - Cat. 1 - '
                        '23/11/2026 23:40:38'
                    )
                )
            ],
            summary_quantity='0 1 0 0',
            summary_total='R$ 0.00 -R$ 6.90 R$ 0.00 R$ 0.00',
        )
    )
    preview = import_service.build_preview_from_result(trip, result, user)
    return import_service.sign_preview(preview)


class TollImportViewAccessTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.bus_trip = create_trip(self.user, TripType.BUS)
        self.client.force_login(self.user)

    def test_get_renders_upload_form(self):
        trip = create_trip(self.user)
        response = self.client.get(reverse('toll_import', args=[trip.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tolls/toll_import_form.html')

    def test_bus_trip_gets_404(self):
        response = self.client.get(
            reverse('toll_import', args=[self.bus_trip.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_anonymous_is_redirected_to_login(self):
        self.client.logout()
        trip = create_trip(self.user)
        response = self.client.get(reverse('toll_import', args=[trip.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])


class TollImportViewPostTests(TestCase):
    def setUp(self):
        self.user = create_user('post-import@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_non_pdf_upload_shows_error_without_creating(self):
        upload = SimpleUploadedFile(
            'extrato.pdf', b'GIF89a not a pdf', content_type='application/pdf'
        )
        response = self.client.post(
            reverse('toll_import', args=[self.trip.pk]), {'file': upload}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PDF')
        self.assertEqual(Toll.objects.count(), 0)

    @skipUnless(WKWEBTOPDF_AVAILABLE, 'wkhtmltopdf não disponível neste ambiente')
    def test_vehicle_without_plate_blocks_upload(self):
        trip = create_trip(self.user, plate=None)
        upload = SimpleUploadedFile(
            'extrato.pdf', build_pdf_bytes(), content_type='application/pdf'
        )
        response = self.client.post(
            reverse('toll_import', args=[trip.pk]), {'file': upload}
        )
        self.assertContains(response, 'placa')

    @skipUnless(WKWEBTOPDF_AVAILABLE, 'wkhtmltopdf não disponível neste ambiente')
    def test_valid_pdf_renders_preview_with_defaults(self):
        upload = SimpleUploadedFile(
            'extrato.pdf', build_pdf_bytes(), content_type='application/pdf'
        )
        response = self.client.post(
            reverse('toll_import', args=[self.trip.pk]), {'file': upload}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tolls/toll_import_preview.html')
        self.assertContains(response, 'Confirmar importação')
        self.assertContains(response, 'PRAÇA ALFA SUL')
        preview = response.context['preview']
        self.assertEqual(len(preview['rows']), 1)
        self.assertTrue(preview['rows'][0]['checked'])
        self.assertTrue(response.context['signed_payload'])


class TollImportConfirmViewTests(TestCase):
    def setUp(self):
        self.user = create_user('confirm-import@example.com')
        self.trip = create_trip(self.user)
        self.client.force_login(self.user)

    def test_confirm_creates_selected_rows_and_redirects(self):
        payload = signed_payload(self.trip, self.user)
        response = self.client.post(
            reverse('toll_import_confirm', args=[self.trip.pk]),
            {'payload': payload, 'selected': ['0']},
        )
        self.assertRedirects(
            response, reverse('toll_list', args=[self.trip.pk])
        )
        tolls = Toll.objects.filter(trip=self.trip)
        self.assertEqual(tolls.count(), 1)
        self.assertEqual(tolls[0].amount_spent, Decimal('6.90'))
        self.assertEqual(tolls[0].source, 'import')

    def test_double_confirm_creates_nothing_extra(self):
        payload = signed_payload(self.trip, self.user)
        first = self.client.post(
            reverse('toll_import_confirm', args=[self.trip.pk]),
            {'payload': payload, 'selected': ['0']},
        )
        self.assertEqual(first.status_code, 302)
        second = self.client.post(
            reverse('toll_import_confirm', args=[self.trip.pk]),
            {'payload': payload, 'selected': ['0']},
        )
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Toll.objects.filter(trip=self.trip).count(), 1)

    def test_tampered_payload_is_rejected(self):
        payload = signed_payload(self.trip, self.user)
        response = self.client.post(
            reverse('toll_import_confirm', args=[self.trip.pk]),
            {'payload': payload[:-1] + 'X', 'selected': ['0']},
        )
        self.assertRedirects(
            response, reverse('toll_import', args=[self.trip.pk])
        )
        self.assertEqual(Toll.objects.count(), 0)

    def test_bus_trip_gets_404(self):
        bus_trip = create_trip(self.user, TripType.BUS)
        response = self.client.post(
            reverse('toll_import_confirm', args=[bus_trip.pk]),
            {'payload': 'x', 'selected': ['0']},
        )
        self.assertEqual(response.status_code, 404)
