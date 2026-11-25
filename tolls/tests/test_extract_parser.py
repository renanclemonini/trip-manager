from datetime import datetime
from decimal import Decimal

from django.test import SimpleTestCase
from django.utils.timezone import get_current_timezone, make_aware

from tolls.services.errors import TollImportError
from tolls.services.extract_parser import parse_extract_text
from tolls.tests.fixtures import (
    FILTER_PLATE,
    build_extract_text,
    plan_fee_text,
    recarga_text,
    toll_text,
)

TZ = get_current_timezone()


def aware(day, hour, minute, second=0):
    return make_aware(datetime(2026, 11, day, hour, minute, second), TZ)


class TollSignatureVariantTests(SimpleTestCase):
    def test_signature_with_space_before_value(self):
        result = parse_extract_text(
            build_extract_text(
                [toll_text()],
                summary_quantity='0 1 0 0',
                summary_total='R$ 0.00 -R$ 6.90 R$ 0.00 R$ 0.00',
            )
        )
        tolls = [row for row in result.rows if row.passage_datetime]
        self.assertEqual(len(tolls), 1)
        self.assertEqual(tolls[0].passage_datetime, aware(23, 23, 40, 38))
        self.assertEqual(tolls[0].amount, Decimal('-6.90'))

    def test_signature_glued_to_value(self):
        result = parse_extract_text(
            build_extract_text(
                [toll_text(glued_value=True)],
                summary_quantity='0 1 0 0',
                summary_total='R$ 0.00 -R$ 6.90 R$ 0.00 R$ 0.00',
            )
        )
        tolls = [row for row in result.rows if row.passage_datetime]
        self.assertEqual(len(tolls), 1)
        self.assertEqual(tolls[0].passage_datetime, aware(23, 23, 40, 38))
        self.assertEqual(tolls[0].amount, Decimal('-6.90'))

    def test_signature_date_glued_to_time(self):
        result = parse_extract_text(
            build_extract_text(
                [toll_text(glued_datetime=True)],
                summary_quantity='0 1 0 0',
                summary_total='R$ 0.00 -R$ 6.90 R$ 0.00 R$ 0.00',
            )
        )
        tolls = [row for row in result.rows if row.passage_datetime]
        self.assertEqual(len(tolls), 1)
        self.assertEqual(tolls[0].passage_datetime, aware(23, 23, 40, 38))


class TollDescriptionReassemblyTests(SimpleTestCase):
    def test_multiline_description_is_reassembled(self):
        text = build_extract_text(
            [
                '23/11/2026 - 23:03:50 SYN-0A01 FREEFLOW - CONCESSIONARIA '
                'TESTE -\n'
                'P02 PRAÇA BETA SUL, 40+800, SP - 088 - Cat. 1 - '
                '23/11/2026 22:45:17\n'
                '-R$ 1.97 R$ 48.36\n'
            ],
            summary_quantity='0 1 0 0',
            summary_total='R$ 0.00 -R$ 1.97 R$ 0.00 R$ 0.00',
        )
        tolls = [row for row in parse_extract_text(text).rows
                 if row.passage_datetime]
        self.assertEqual(len(tolls), 1)
        self.assertEqual(tolls[0].passage_datetime, aware(23, 22, 45, 17))
        self.assertIn('PRAÇA BETA SUL', tolls[0].description)

    def test_description_without_hyphen_in_road_kept_verbatim(self):
        text = build_extract_text(
            [
                '23/11/2026 - 22:20:18 SYN-0A01 ECOPISTAS - 22 PRAÇA GAMA, '
                'KM 92, SP070 - Cat. 1 - 23/11/2026 22:20:08 -R$ 5.70 '
                'R$ 56.03\n'
            ],
            summary_quantity='0 1 0 0',
            summary_total='R$ 0.00 -R$ 5.70 R$ 0.00 R$ 0.00',
        )
        tolls = [row for row in parse_extract_text(text).rows
                 if row.passage_datetime]
        self.assertEqual(len(tolls), 1)
        self.assertIn('SP070', tolls[0].description)


class TollDescriptionCleanupTests(SimpleTestCase):
    DESCRIPTION = (
        'CONCESSIONARIA TESTE - PRAÇA ALFA, KM 57, SP-070 - '
        'Cat. 1 - 23/11/2026 23:40:38'
    )
    CLEAN = 'CONCESSIONARIA TESTE - PRAÇA ALFA, KM 57, SP-070'
    RAW = 'CONCESSIONARIA TESTE - PRAÇA ALFA, KM 57, SP-070 -'

    def _parse(self, rows):
        return parse_extract_text(
            build_extract_text(
                rows,
                summary_quantity='0 1 0 0',
                summary_total='R$ 0.00 -R$ 6.90 R$ 0.00 R$ 0.00',
            )
        )

    def test_trailing_hyphen_removed_in_each_signature_variant(self):
        variants = (
            toll_text(description=self.DESCRIPTION),
            toll_text(description=self.DESCRIPTION, glued_value=True),
            toll_text(description=self.DESCRIPTION, glued_datetime=True),
        )
        for text in variants:
            with self.subTest(text=text):
                tolls = [row for row in self._parse([text]).rows
                         if row.passage_datetime]
                self.assertEqual(tolls[0].description, self.CLEAN)

    def test_broken_road_code_is_rejoined(self):
        description = (
            'CONCESSIONARIA TESTE - PRAÇA ALFA, KM 57, SP-\n070 - '
            'Cat. 1 - 23/11/2026 23:40:38'
        )
        tolls = [row for row in
                 self._parse([toll_text(description=description)]).rows
                 if row.passage_datetime]
        self.assertEqual(tolls[0].description, self.CLEAN)

    def test_spaced_road_kept_verbatim(self):
        description = (
            'ECOPISTAS - 22 PRAÇA GAMA, KM 92, SP - 088 - '
            'Cat. 1 - 23/11/2026 23:40:38'
        )
        tolls = [row for row in
                 self._parse([toll_text(description=description)]).rows
                 if row.passage_datetime]
        self.assertEqual(
            tolls[0].description,
            'ECOPISTAS - 22 PRAÇA GAMA, KM 92, SP - 088',
        )

    def test_raw_description_preserves_original_text(self):
        tolls = [row for row in
                 self._parse([toll_text(description=self.DESCRIPTION)]).rows
                 if row.passage_datetime]
        self.assertEqual(tolls[0].raw_description, self.RAW)

    def test_fifteen_report_style_descriptions_change_only_trailing_hyphen(self):
        descriptions = [
            'CONCESSIONARIA TESTE - PRAÇA 01, KM 57, SP - 088',
            'P02 PRAÇA BETA SUL, 40+800, SP - 088',
            'FREEFLOW - CONCESSIONARIA TESTE - P02 PRAÇA BETA SUL, '
            '40+800, SP - 088',
            'ECOPISTAS - 22 PRAÇA GAMA, KM 92, SP070',
            'VIA RAPIDA - PRAÇA DELTA NORTE, KM 114+300, BR - 116',
            'CONCESSIONARIA ALPHA - 01 PRAÇA EPSILON, KM 12, SP - 270',
            'P03 PRAÇA ZETA OESTE, 15+900, SP - 099',
            'NOVO PEDAGIO - PRAÇA ETA SUL, KM 34+500, RJ - 104',
            'CONCESSIONARIA BETA - PRAÇA TETA, KM 2, SP - 021',
            'PEDAGIO LESTE - 40+800 PRAÇA IOTA, SP - 088',
            'CONCESSIONARIA GAMA - PRAÇA CAPA NORTE, KM 333, BR - 381',
            'FREEFLOW - PRAÇA LAMBDA, KM 8+200, SP - 010',
            'CONCESSIONARIA DELTA - PRAÇA MI, KM 45, SP - 065',
            'PEDAGIO SUL - PRAÇA NI OESTE, 12+300, SP - 040',
            'CONCESSIONARIA EPSILON - PRAÇA XI, KM 540+100, BR - 040',
        ]
        rows = [
            toll_text(
                launch=f'20/11/2026 - 10:00:{day:02d}',
                description=(
                    f'{description} - Cat. 1 - 20/11/2026 09:00:{day:02d}'
                ),
                value='6.90',
            )
            for day, description in enumerate(descriptions)
        ]
        result = parse_extract_text(
            build_extract_text(
                rows,
                summary_quantity='0 15 0 0',
                summary_total='R$ 0.00 -R$ 103.50 R$ 0.00 R$ 0.00',
            )
        )
        tolls = [row for row in result.rows if row.passage_datetime]
        self.assertEqual(len(tolls), 15)
        for toll, description in zip(tolls, descriptions):
            self.assertEqual(toll.description, description)
            self.assertEqual(toll.raw_description, f'{description} -')


class NonTollClassificationTests(SimpleTestCase):
    def _parse(self, rows, quantity='0 1 0 1', total='R$ 0.00 -R$ 6.90 R$ 0.00 -R$ 9.90'):
        return parse_extract_text(
            build_extract_text(rows, summary_quantity=quantity,
                               summary_total=total)
        )

    def test_recarga_is_not_a_toll(self):
        result = self._parse([toll_text(), recarga_text()])
        self.assertEqual(len([r for r in result.rows if r.passage_datetime]), 1)
        non_tolls = [r for r in result.rows if r.passage_datetime is None]
        self.assertEqual(len(non_tolls), 1)
        self.assertIn('Recarga', non_tolls[0].description)
        self.assertEqual(non_tolls[0].amount, Decimal('50.00'))

    def test_plan_fee_debit_is_not_a_toll(self):
        result = self._parse([toll_text(), plan_fee_text()])
        non_tolls = [r for r in result.rows if r.passage_datetime is None]
        self.assertEqual(len(non_tolls), 1)
        self.assertIn('Plano Completo', non_tolls[0].description)
        self.assertEqual(non_tolls[0].amount, Decimal('-9.90'))

    def test_unknown_credit_is_not_a_toll(self):
        result = self._parse([
            toll_text(),
            '20/11/2026 - 09:00:00 SYN-0A01 Estorno de cobrança '
            'R$ 3.00 R$ 12.00\n',
        ])
        non_tolls = [r for r in result.rows if r.passage_datetime is None]
        self.assertEqual(len(non_tolls), 1)
        self.assertEqual(non_tolls[0].amount, Decimal('3.00'))

    def test_balance_column_is_ignored(self):
        result = self._parse([toll_text()])
        tolls = [r for r in result.rows if r.passage_datetime]
        self.assertEqual(tolls[0].amount, Decimal('-6.90'))


class TollSummaryReconciliationTests(SimpleTestCase):
    def test_sixteen_tolls_match_summary(self):
        rows = []
        for day in range(15):
            rows.append(toll_text(
                launch=f'20/11/2026 - 10:00:{day:02d}',
                description=(
                    f'CONCESSIONARIA TESTE - PRAÇA {day:02d}, KM 57, '
                    f'SP-070 - Cat. 1 - 20/11/2026 09:00:{day:02d}'
                ),
                value='9.00',
                balance='R$ 99.00',
            ))
        rows.append(toll_text(
            launch='20/11/2026 - 10:15:00',
            description=(
                'CONCESSIONARIA TESTE - PRAÇA EXTRA, KM 92, SP-070 - '
                'Cat. 1 - 20/11/2026 09:14:02'
            ),
            value='15.84',
            balance='R$ 99.00',
        ))
        result = parse_extract_text(build_extract_text(rows))
        tolls = [row for row in result.rows if row.passage_datetime]
        self.assertEqual(len(tolls), 16)
        total = sum((abs(row.amount) for row in tolls), Decimal('0.00'))
        self.assertEqual(total, Decimal('150.84'))

    def test_count_mismatch_blocks_with_numbers_only(self):
        rows = [toll_text(), toll_text()]
        text = build_extract_text(
            rows, summary_quantity='0 3 0 0',
            summary_total='R$ 0.00 -R$ 150.84 R$ 0.00 R$ 0.00',
        )
        with self.assertRaises(TollImportError) as ctx:
            parse_extract_text(text)
        message = str(ctx.exception)
        self.assertIn('3', message)
        self.assertIn('2', message)
        self.assertNotIn('PRAÇA', message)
        self.assertNotIn('CONCESSIONARIA', message)

    def test_total_mismatch_blocks_with_numbers_only(self):
        rows = [toll_text(value='6.90'), toll_text(value='5.70')]
        text = build_extract_text(
            rows, summary_quantity='0 2 0 0',
            summary_total='R$ 0.00 -R$ 200.00 R$ 0.00 R$ 0.00',
        )
        with self.assertRaises(TollImportError) as ctx:
            parse_extract_text(text)
        message = str(ctx.exception)
        self.assertIn('200.00', message)
        self.assertIn('12.60', message)
        self.assertNotIn('PRAÇA', message)

    def test_missing_summary_is_unknown_layout(self):
        text = build_extract_text(
            [toll_text()], summary_quantity=None, summary_total=None
        )
        with self.assertRaises(TollImportError) as ctx:
            parse_extract_text(text)
        self.assertIn('resumo', str(ctx.exception).lower())


class RowOrderIndependenceTests(SimpleTestCase):
    def test_shuffled_rows_parse_to_same_transactions(self):
        rows = [
            toll_text(
                launch='20/11/2026 - 10:00:00',
                description=(
                    'CONCESSIONARIA TESTE - PRAÇA UM - Cat. 1 - '
                    '20/11/2026 09:00:00'
                ),
                value='1.00',
            ),
            toll_text(
                launch='21/11/2026 - 10:00:00',
                description=(
                    'CONCESSIONARIA TESTE - PRAÇA DOIS - Cat. 1 - '
                    '21/11/2026 09:00:00'
                ),
                value='2.00',
            ),
        ]
        summary_total = 'R$ 0.00 -R$ 3.00 R$ 0.00 R$ 0.00'
        forward = parse_extract_text(
            build_extract_text(rows, summary_quantity='0 2 0 0',
                               summary_total=summary_total)
        )
        shuffled = parse_extract_text(
            build_extract_text(list(reversed(rows)),
                               summary_quantity='0 2 0 0',
                               summary_total=summary_total)
        )
        forward_times = sorted(
            r.passage_datetime for r in forward.rows if r.passage_datetime
        )
        shuffled_times = sorted(
            r.passage_datetime for r in shuffled.rows if r.passage_datetime
        )
        self.assertEqual(forward_times, shuffled_times)

    def test_orphan_fragment_is_unknown_layout_and_imports_nothing(self):
        text = build_extract_text([
            'PRAÇA ORFÃ - Cat. 1 - 20/11/2026 09:00:00 -R$ 4.00 R$ 9.00\n',
            toll_text(),
        ])
        with self.assertRaises(TollImportError) as ctx:
            parse_extract_text(text)
        self.assertIn('layout', str(ctx.exception).lower())
        self.assertNotIn('PRAÇA ORFÃ', str(ctx.exception))
