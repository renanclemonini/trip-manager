import io
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils.timezone import get_current_timezone, make_aware

from accounts.models import User
from tolls.models import Toll, TollSource
from tolls.services import import_service
from tolls.services.errors import TollImportError
from tolls.services.extract_parser import parse_extract_text
from tolls.tests.fixtures import build_extract_text, toll_text
from trips.models import Trip, TripType
from vehicles.models import TripVehicle, Vehicle, VehicleType

TZ = get_current_timezone()

WINDOW_START = make_aware(datetime(2026, 11, 22, 8, 0), TZ)
WINDOW_END = make_aware(datetime(2026, 11, 24, 0, 11), TZ)


def create_user(email='import@example.com'):
    return User.objects.create_user(email=email, password='strong-pass-123')


def create_trip(user, plate='SYN0A01', with_vehicle=True,
                end_datetime=None, start_datetime=None):
    trip = Trip.objects.create(
        created_by=user,
        origin_city='São Paulo',
        origin_state='SP',
        destination_city='Curitiba',
        destination_state='PR',
        trip_type=TripType.CAR,
        start_datetime=start_datetime or WINDOW_START,
        end_datetime=end_datetime,
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


def single_toll_text(passage='23/11/2026 23:40:38', value='6.90'):
    return build_extract_text(
        [
            toll_text(
                launch='23/11/2026 - 23:41:01',
                description=(
                    'CONCESSIONARIA TESTE - PRAÇA ALFA - Cat. 1 - '
                    f'{passage}'
                ),
                value=value,
            )
        ],
        summary_quantity='0 1 0 0',
        summary_total=f'R$ 0.00 -R$ {value} R$ 0.00 R$ 0.00',
    )


def preview_for(trip, user, text=None):
    result = parse_extract_text(text or single_toll_text())
    return import_service.build_preview_from_result(trip, result, user)


class UploadReadLimitsTests(TestCase):
    def test_size_limit_uses_constant(self):
        self.assertEqual(import_service.MAX_IMPORT_FILE_SIZE, 5 * 1024 * 1024)
        self.assertEqual(import_service.MAX_IMPORT_PAGES, 20)
        self.assertEqual(import_service.PREVIEW_MAX_AGE_SECONDS, 3600)

    def test_oversized_file_is_rejected_before_reading(self):
        class FakeFile:
            size = import_service.MAX_IMPORT_FILE_SIZE + 1

            def read(self, *args, **kwargs):
                raise AssertionError('should not read an oversized file')

        with self.assertRaises(TollImportError) as ctx:
            import_service.read_upload(FakeFile())
        self.assertIn('5 MB', str(ctx.exception))

    def test_file_with_lieing_size_reads_at_most_limit_plus_one(self):
        data = b'A' * (import_service.MAX_IMPORT_FILE_SIZE + 50)

        class FakeFile:
            size = len(data)
            chunk = 0

            def read(self, length=-1):
                read = min(length, len(data) - self.chunk)
                result = data[self.chunk:self.chunk + read]
                self.chunk += read
                return result

        with self.assertRaises(TollImportError) as ctx:
            import_service.read_upload(FakeFile())
        self.assertIn('5 MB', str(ctx.exception))


class UploadErrorTests(TestCase):
    def test_non_pdf_bytes_are_rejected(self):
        user = create_user('nonpdf@example.com')
        trip = create_trip(user)
        with self.assertRaises(TollImportError) as ctx:
            import_service.build_preview(trip, b'GIF89a not a pdf', user)
        self.assertIn('PDF', str(ctx.exception))

    def test_pdf_without_text_layer_is_rejected(self):
        user = create_user('notext@example.com')
        trip = create_trip(user)
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buffer = io.BytesIO()
        writer.write(buffer)
        with self.assertRaises(TollImportError) as ctx:
            import_service.build_preview(trip, buffer.getvalue(), user)
        self.assertIn('texto', str(ctx.exception).lower())

    def test_vehicle_without_plate_blocks_import(self):
        user = create_user('noplate@example.com')
        trip = create_trip(user, plate=None)
        with self.assertRaises(TollImportError) as ctx:
            import_service.build_preview_from_result(
                trip, parse_extract_text(single_toll_text()), user
            )
        self.assertIn('placa', str(ctx.exception).lower())

    def test_vehicle_without_trip_vehicle_blocks_import(self):
        user = create_user('novehicle@example.com')
        trip = create_trip(user, with_vehicle=False)
        with self.assertRaises(TollImportError) as ctx:
            import_service.build_preview_from_result(
                trip, parse_extract_text(single_toll_text()), user
            )
        self.assertIn('placa', str(ctx.exception).lower())


class WindowBoundaryTests(TestCase):
    def setUp(self):
        self.user = create_user('window@example.com')
        self.trip = create_trip(self.user, end_datetime=WINDOW_END)

    def _preview(self, passage, user=None):
        text = single_toll_text(passage=passage)
        return preview_for(self.trip, user or self.user, text)

    def test_passage_exactly_at_start_is_inside(self):
        preview = self._preview('22/11/2026 08:00:00')
        self.assertTrue(preview['rows'][0]['checked'])

    def test_passage_exactly_at_end_is_inside(self):
        preview = self._preview('24/11/2026 00:11:00')
        self.assertTrue(preview['rows'][0]['checked'])

    def test_passage_one_minute_before_start_is_outside(self):
        preview = self._preview('22/11/2026 07:59:00')
        self.assertFalse(preview['rows'][0]['checked'])
        self.assertIn('janela', preview['rows'][0]['reason'])

    def test_passage_one_minute_after_end_is_outside(self):
        preview = self._preview('24/11/2026 00:12:00')
        self.assertFalse(preview['rows'][0]['checked'])
        self.assertIn('janela', preview['rows'][0]['reason'])

    def test_ongoing_trip_uses_now_as_end(self):
        trip = create_trip(self.user, end_datetime=None)
        now = make_aware(datetime(2026, 11, 23, 12, 0), TZ)
        with mock.patch(
            'django.utils.timezone.now', return_value=now
        ):
            inside = preview_for(
                trip, self.user, single_toll_text('23/11/2026 11:59:00')
            )
            outside = preview_for(
                trip, self.user, single_toll_text('23/11/2026 12:01:00')
            )
        self.assertTrue(inside['rows'][0]['checked'])
        self.assertFalse(outside['rows'][0]['checked'])


class PlateMatchingTests(TestCase):
    def test_other_plate_is_unchecked_with_reason(self):
        user = create_user('plate@example.com')
        trip = create_trip(user, plate='SYN0A01')
        text = build_extract_text(
            [
                toll_text(
                    plate='OTH-9X88',
                    description=(
                        'CONCESSIONARIA TESTE - PRAÇA OUTRA - Cat. 1 - '
                        '23/11/2026 23:40:38'
                    ),
                )
            ],
            summary_quantity='0 1 0 0',
            summary_total='R$ 0.00 -R$ 6.90 R$ 0.00 R$ 0.00',
        )
        preview = preview_for(trip, user, text)
        self.assertFalse(preview['rows'][0]['checked'])
        self.assertIn('placa', preview['rows'][0]['reason'])

    def test_divergent_filter_plate_warns(self):
        user = create_user('warn@example.com')
        trip = create_trip(user, plate='SYN0A01')
        text = build_extract_text(
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
        ).replace('Placa: SYN-0A01', 'Placa: DIF-1B22')
        preview = preview_for(trip, user, text)
        self.assertTrue(preview['filter_plate_warning'])
        self.assertFalse(preview['rows'][0]['checked'])


class PreviewOrderingTests(TestCase):
    def test_rows_follow_passage_order_even_with_shuffled_input(self):
        user = create_user('order@example.com')
        trip = create_trip(user)
        rows = [
            toll_text(
                launch='21/11/2026 - 10:00:00',
                description=(
                    'CONCESSIONARIA TESTE - PRAÇA DOIS - Cat. 1 - '
                    '21/11/2026 09:00:00'
                ),
                value='2.00',
            ),
            toll_text(
                launch='20/11/2026 - 10:00:00',
                description=(
                    'CONCESSIONARIA TESTE - PRAÇA UM - Cat. 1 - '
                    '20/11/2026 09:00:00'
                ),
                value='1.00',
            ),
        ]
        text = build_extract_text(
            rows, summary_quantity='0 2 0 0',
            summary_total='R$ 0.00 -R$ 3.00 R$ 0.00 R$ 0.00',
        )
        preview = preview_for(trip, user, text)
        times = [row['datetime'] for row in preview['rows']]
        self.assertEqual(
            times,
            ['20/11/2026 09:00', '21/11/2026 09:00'],
        )


class DeduplicationPreviewTests(TestCase):
    def setUp(self):
        self.user = create_user('dedup@example.com')
        self.trip = create_trip(self.user)

    def test_duplicate_row_in_same_file_is_unchecked(self):
        text = build_extract_text(
            [
                toll_text(
                    launch='23/11/2026 - 23:41:01',
                    description=(
                        'CONCESSIONARIA TESTE - PRAÇA ALFA - Cat. 1 - '
                        '23/11/2026 23:40:38'
                    ),
                    value='6.90',
                ),
                toll_text(
                    launch='23/11/2026 - 23:41:01',
                    description=(
                        'CONCESSIONARIA TESTE - PRAÇA ALFA - Cat. 1 - '
                        '23/11/2026 23:40:38'
                    ),
                    value='6.90',
                ),
            ],
            summary_quantity='0 2 0 0',
            summary_total='R$ 0.00 -R$ 13.80 R$ 0.00 R$ 0.00',
        )
        preview = preview_for(self.trip, self.user, text)
        self.assertTrue(preview['rows'][0]['checked'])
        self.assertFalse(preview['rows'][1]['checked'])
        self.assertIn('extrato', preview['rows'][1]['reason'])

    def test_possible_manual_duplicate_is_unchecked(self):
        text = single_toll_text()
        result = parse_extract_text(text)
        toll = result.rows[0]
        Toll.objects.create(
            trip=self.trip,
            location='PRAÇA ALFA',
            amount_spent=Decimal('6.90'),
            datetime=toll.passage_datetime + timedelta(seconds=30),
            source=TollSource.MANUAL,
        )
        preview = import_service.build_preview_from_result(
            self.trip, result, self.user
        )
        self.assertFalse(preview['rows'][0]['checked'])
        self.assertIn('manual', preview['rows'][0]['reason'])

    def test_reimport_marks_all_as_already_imported(self):
        result = parse_extract_text(single_toll_text())
        preview = import_service.build_preview_from_result(
            self.trip, result, self.user
        )
        signed = import_service.sign_preview(preview)
        created = import_service.confirm_import(
            self.trip, self.user, signed, ['0']
        )
        self.assertEqual(created['created'], 1)
        second = import_service.build_preview_from_result(
            self.trip, parse_extract_text(single_toll_text()), self.user
        )
        self.assertFalse(second['rows'][0]['checked'])
        self.assertIn('importado', second['rows'][0]['reason'])

    def test_identical_pair_created_when_both_checked_and_reimport_skips_both(self):
        text = build_extract_text(
            [
                toll_text(
                    launch='23/11/2026 - 23:41:01',
                    description=(
                        'CONCESSIONARIA TESTE - PRAÇA ALFA - Cat. 1 - '
                        '23/11/2026 23:40:38'
                    ),
                    value='6.90',
                ),
                toll_text(
                    launch='23/11/2026 - 23:41:01',
                    description=(
                        'CONCESSIONARIA TESTE - PRAÇA ALFA - Cat. 1 - '
                        '23/11/2026 23:40:38'
                    ),
                    value='6.90',
                ),
            ],
            summary_quantity='0 2 0 0',
            summary_total='R$ 0.00 -R$ 13.80 R$ 0.00 R$ 0.00',
        )
        result = parse_extract_text(text)
        preview = import_service.build_preview_from_result(
            self.trip, result, self.user
        )
        signed = import_service.sign_preview(preview)
        created = import_service.confirm_import(
            self.trip, self.user, signed, ['0', '1']
        )
        self.assertEqual(created['created'], 2)
        self.assertEqual(Toll.objects.filter(trip=self.trip).count(), 2)
        again = import_service.confirm_import(
            self.trip, self.user, signed, ['0', '1']
        )
        self.assertEqual(again['created'], 0)
        self.assertEqual(Toll.objects.filter(trip=self.trip).count(), 2)


class HashCompatibilityTests(TestCase):
    """The import hash keeps the raw description (Fase 44) — reimporting
    an equivalent extract recognizes tolls hashed with the old parser."""

    def setUp(self):
        self.user = create_user('hash@example.com')
        self.trip = create_trip(self.user)

    @staticmethod
    def legacy_hash(plate, passage, description, amount):
        raw = (
            f'{plate}|{passage.isoformat()}|'
            f'{" ".join(description.split())}|{amount}'
        )
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def suffixed_text(self):
        return build_extract_text(
            [
                toll_text(
                    description=(
                        'CONCESSIONARIA TESTE - PRAÇA ALFA, KM 57, '
                        'SP-070 - Cat. 1 - 23/11/2026 23:40:38'
                    )
                )
            ],
            summary_quantity='0 1 0 0',
            summary_total='R$ 0.00 -R$ 6.90 R$ 0.00 R$ 0.00',
        )

    def test_hash_is_computed_over_raw_description(self):
        result = parse_extract_text(self.suffixed_text())
        row = result.rows[0]
        preview = import_service.build_preview_from_result(
            self.trip, result, self.user
        )
        self.assertEqual(
            preview['rows'][0]['hash'],
            self.legacy_hash(
                row.plate, row.passage_datetime, row.raw_description,
                abs(row.amount),
            ),
        )
        self.assertNotEqual(
            preview['rows'][0]['hash'],
            self.legacy_hash(
                row.plate, row.passage_datetime, row.description,
                abs(row.amount),
            ),
        )

    def test_same_extract_yields_same_hash(self):
        first = import_service.build_preview_from_result(
            self.trip, parse_extract_text(self.suffixed_text()), self.user
        )
        second = import_service.build_preview_from_result(
            self.trip, parse_extract_text(self.suffixed_text()), self.user
        )
        self.assertEqual(
            first['rows'][0]['hash'], second['rows'][0]['hash']
        )

    def test_reimport_with_legacy_hash_creates_no_new_toll(self):
        result = parse_extract_text(self.suffixed_text())
        row = result.rows[0]
        legacy = self.legacy_hash(
            row.plate, row.passage_datetime, row.raw_description,
            abs(row.amount),
        )
        Toll.objects.create(
            trip=self.trip,
            location=row.description,
            amount_spent=abs(row.amount),
            datetime=row.passage_datetime,
            source=TollSource.IMPORT,
            import_hash=legacy,
        )
        preview = import_service.build_preview_from_result(
            self.trip, result, self.user
        )
        self.assertFalse(preview['rows'][0]['checked'])
        self.assertIn('importado', preview['rows'][0]['reason'])
        signed = import_service.sign_preview(preview)
        created = import_service.confirm_import(
            self.trip, self.user, signed, ['0']
        )
        self.assertEqual(created['created'], 0)
        self.assertEqual(Toll.objects.filter(trip=self.trip).count(), 1)

    def test_confirmed_import_stores_cleaned_location(self):
        result = parse_extract_text(self.suffixed_text())
        preview = import_service.build_preview_from_result(
            self.trip, result, self.user
        )
        signed = import_service.sign_preview(preview)
        import_service.confirm_import(self.trip, self.user, signed, ['0'])
        toll = Toll.objects.get(trip=self.trip)
        self.assertEqual(
            toll.location,
            'CONCESSIONARIA TESTE - PRAÇA ALFA, KM 57, SP-070',
        )
        self.assertFalse(toll.location.endswith(' -'))


class PreviewPayloadTests(TestCase):
    def setUp(self):
        self.user = create_user('payload@example.com')
        self.trip = create_trip(self.user)
        self.other_user = create_user('payload-other@example.com')
        self.other_trip = create_trip(self.other_user)

    def _signed(self):
        preview = preview_for(self.trip, self.user)
        return import_service.sign_preview(preview)

    def test_tampered_payload_is_rejected_in_pt_br(self):
        signed = self._signed()
        with self.assertRaises(TollImportError) as ctx:
            import_service.load_preview(
                self.trip, self.user, signed[:-1] + 'X'
            )
        self.assertIn('inválida', str(ctx.exception))

    def test_expired_payload_is_rejected_in_pt_br(self):
        import time as time_module

        signed = self._signed()
        base = time_module.time()
        future = base + import_service.PREVIEW_MAX_AGE_SECONDS + 1
        with mock.patch(
            'django.core.signing.time.time', return_value=future
        ):
            with self.assertRaises(TollImportError) as ctx:
                import_service.load_preview(self.trip, self.user, signed)
        self.assertIn('expi', str(ctx.exception).lower())

    def test_payload_from_another_trip_is_rejected(self):
        signed = self._signed()
        with self.assertRaises(TollImportError) as ctx:
            import_service.load_preview(
                self.other_trip, self.user, signed
            )
        self.assertIn('viagem', str(ctx.exception).lower())

    def test_payload_from_another_user_is_rejected(self):
        signed = self._signed()
        with self.assertRaises(TollImportError) as ctx:
            import_service.load_preview(
                self.trip, self.other_user, signed
            )
        self.assertIn('usuário', str(ctx.exception).lower())

    def test_double_confirm_creates_nothing_extra(self):
        preview = preview_for(self.trip, self.user)
        signed = import_service.sign_preview(preview)
        first = import_service.confirm_import(
            self.trip, self.user, signed, ['0']
        )
        second = import_service.confirm_import(
            self.trip, self.user, signed, ['0']
        )
        self.assertEqual(first['created'], 1)
        self.assertEqual(second['created'], 0)
        self.assertEqual(Toll.objects.filter(trip=self.trip).count(), 1)


class ImportedTollAttributesTests(TestCase):
    def test_imported_toll_carries_source_hash_and_batch(self):
        user = create_user('attrs@example.com')
        trip = create_trip(user)
        preview = preview_for(trip, user)
        signed = import_service.sign_preview(preview)
        import_service.confirm_import(trip, user, signed, ['0'])
        toll = Toll.objects.get(trip=trip)
        self.assertEqual(toll.source, TollSource.IMPORT)
        self.assertIsNotNone(toll.import_hash)
        self.assertEqual(len(toll.import_hash), 64)
        self.assertIsNotNone(toll.import_batch_id)


class DashboardReportIntegrationTests(TestCase):
    def test_imported_toll_counts_in_dashboard_and_final_report(self):
        from reports.services.report_data import get_final_report_context
        from trips.services import get_trip_dashboard

        user = create_user('integrated@example.com')
        trip = create_trip(user)
        preview = preview_for(trip, user)
        signed = import_service.sign_preview(preview)
        import_service.confirm_import(trip, user, signed, ['0'])
        dashboard = get_trip_dashboard(trip)
        labels = [category['label'] for category in dashboard['categories']]
        series = dashboard['chart_data']['categories']['series']
        self.assertEqual(labels[-1], 'Pedágio')
        self.assertEqual(series[-1], 6.9)
        self.assertEqual(dashboard['grand_total'], Decimal('6.90'))
        context = get_final_report_context(trip)
        self.assertEqual(list(context['tolls']), [Toll.objects.get(trip=trip)])
