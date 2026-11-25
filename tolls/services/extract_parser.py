import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils.timezone import get_current_timezone, make_aware

from tolls.services.errors import TollImportError

TZ = get_current_timezone()

ROW_MARKER = re.compile(
    r'(\d{2})\s*/\s*(\d{2})\s*/\s*(\d{4})\s*-\s*(\d{2}:\d{2}:\d{2})'
)
SIGNATURE = re.compile(
    r'Cat\.\s*\d+\s*-\s*(\d{2})\s*/\s*(\d{2})\s*/\s*(\d{4})\s*'
    r'(\d{2}:\d{2}:\d{2})'
)
PLATE = re.compile(r'([A-Z]{3})\s*-\s*(\d[A-Z]\d{2})')
AMOUNT = re.compile(r'(-?)R\$\s*([\d.,]+)')
FILTER_PLATE = re.compile(r'Placa:\s*([A-Z]{3})\s*-\s*(\d[A-Z]\d{2})')

COLUMN_HEADER = (
    'Data do lançamento Veículo Descrição da transação '
    'Crédito Débito Saldo'
)


@dataclass(frozen=True)
class ParsedRow:
    plate: str
    launch_datetime: datetime
    description: str
    raw_description: str
    amount: Decimal
    passage_datetime: datetime | None


@dataclass(frozen=True)
class ExtractResult:
    filter_plate: str | None
    summary_toll_count: int | None
    summary_toll_total: Decimal | None
    rows: list[ParsedRow]


def _parse_aware(text, date_format):
    return make_aware(datetime.strptime(text, date_format), TZ)


def _clean_description(description):
    """Display cleanup only — hashing keeps the raw description.

    The provider prints the description followed by ' - ' before the
    'Cat. n' signature; the trailing hyphen is an artifact. When the PDF
    line breaks inside a road code ('SP-070'), flattening joins the
    fragments with a space ('SP- 070'); the hyphen is glued to the
    preceding letter, so only that shape is rejoined — spaced roads
    ('SP - 088') stay verbatim.
    """
    cleaned = re.sub(r'\s*-\s*$', '', description)
    return re.sub(r'(?<=\w)-\s+(?=\d)', '-', cleaned)


def _parse_amount(token):
    negative = token.startswith('-')
    cleaned = token.replace('R$', '').replace('-', '').replace(' ', '')
    cleaned = cleaned.replace(',', '')
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise TollImportError(
            'Não foi possível reconhecer o layout do extrato.'
        ) from exc
    return -value if negative else value


def _parse_summary(block):
    """Pedágio is the second column of the summary (index 1)."""
    quantities = []
    for chunk in re.findall(r'Quantidade:\s*([\d\s]+)', block):
        quantities.extend(
            int(number) for number in chunk.split() if number.isdigit()
        )
    totals = []
    for chunk in re.findall(r'Total:\s*(.*?)(?=Quantidade:|\Z)', block):
        totals.extend(
            _parse_amount(sign + 'R$ ' + value)
            for sign, value in AMOUNT.findall(chunk)
        )
    return quantities, totals


def parse_extract_text(text):
    """Interpret the plain text layer into classified transactions.

    The extractor output is flattened first, so wrapped cells from any
    generator (pypdf plain content order) are reassembled from contiguous
    tokens. Raises TollImportError (pt-br, numbers only) for unknown
    layouts and for summary mismatches — reconciliation with the Resumo
    is the safety net that blocks partial imports.
    """
    flat = re.sub(r'\s+', ' ', text)
    resumo_marker = 'Resumo de Transações'
    resumo_index = flat.find(resumo_marker)
    transactions_index = flat.find(
        'Transações', resumo_index + len(resumo_marker)
    )
    if transactions_index == -1:
        raise TollImportError(
            'Não foi possível reconhecer o layout do extrato.'
        )
    block = (
        flat[resumo_index + len(resumo_marker):transactions_index]
        if resumo_index != -1 else ''
    )
    quantities, totals = _parse_summary(block)
    if len(quantities) < 4 or len(totals) < 4:
        raise TollImportError(
            'Não foi possível localizar o resumo de transações no extrato.'
        )
    summary_toll_count = quantities[1]
    summary_toll_total = abs(totals[1])

    filter_plate_match = FILTER_PLATE.search(flat)
    filter_plate = None
    if filter_plate_match:
        filter_plate = (
            filter_plate_match.group(1) + filter_plate_match.group(2)
        ).upper()

    section = flat[transactions_index + len('Transações'):]
    section = section.split('Valor aproximado')[0].strip()
    if section.startswith(COLUMN_HEADER):
        section = section[len(COLUMN_HEADER):].strip()
    if not ROW_MARKER.match(section):
        raise TollImportError(
            'Não foi possível reconhecer o layout do extrato.'
        )

    markers = list(ROW_MARKER.finditer(section))
    row_blocks = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(section)
        row_blocks.append((marker, section[marker.end():end]))

    rows = []
    for marker, span in row_blocks:
        launch = _parse_aware(
            f'{marker.group(1)}/{marker.group(2)}/{marker.group(3)} - '
            f'{marker.group(4)}',
            '%d/%m/%Y - %H:%M:%S',
        )
        plate_match = PLATE.search(span)
        signature = SIGNATURE.search(span)
        amounts = list(AMOUNT.finditer(span))
        if plate_match is None or not amounts:
            raise TollImportError(
                'Não foi possível reconhecer o layout do extrato.'
            )
        plate = (plate_match.group(1) + plate_match.group(2)).upper()
        first_amount = amounts[0]
        amount = _parse_amount(
            first_amount.group(1) + 'R$ ' + first_amount.group(2)
        )
        description_end = (
            signature.start() if signature else first_amount.start()
        )
        description = span[plate_match.end():description_end].strip()
        if not description:
            raise TollImportError(
                'Não foi possível reconhecer o layout do extrato.'
            )
        passage = None
        if signature is not None:
            passage = _parse_aware(
                f'{signature.group(1)}/{signature.group(2)}/'
                f'{signature.group(3)} {signature.group(4)}',
                '%d/%m/%Y %H:%M:%S',
            )
        rows.append(ParsedRow(
            plate=plate,
            launch_datetime=launch,
            description=_clean_description(description),
            raw_description=description,
            amount=amount,
            passage_datetime=passage,
        ))

    tolls = [row for row in rows if row.passage_datetime is not None]
    if len(tolls) != summary_toll_count:
        raise TollImportError(
            'O extrato não confere: o resumo indica '
            f'{summary_toll_count} pedágio(s) e foram identificados '
            f'{len(tolls)}.'
        )
    computed_total = sum(
        (abs(row.amount) for row in tolls), Decimal('0.00')
    )
    if computed_total != summary_toll_total:
        raise TollImportError(
            'O extrato não confere: o resumo indica '
            f'R$ {summary_toll_total:.2f} em pedágios e o total '
            f'identificado foi R$ {computed_total:.2f}.'
        )
    return ExtractResult(
        filter_plate=filter_plate,
        summary_toll_count=summary_toll_count,
        summary_toll_total=summary_toll_total,
        rows=rows,
    )
