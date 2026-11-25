import hashlib
import uuid
from datetime import datetime
from decimal import Decimal

from django.core import signing
from django.db import transaction
from django.utils import timezone

from tolls.models import Toll, TollSource
from tolls.services.constants import (
    MAX_IMPORT_FILE_SIZE,
    MAX_IMPORT_PAGES,
    PREVIEW_MAX_AGE_SECONDS,
)
from tolls.services.errors import TollImportError
from tolls.services.extract_parser import parse_extract_text
from tolls.services.pdf_extractor import extract_text

PREVIEW_SALT = 'tolls.import.preview'


def read_upload(file_obj):
    """Enforce the size limit before/while reading — untrusted input."""
    if file_obj.size > MAX_IMPORT_FILE_SIZE:
        raise TollImportError('O arquivo excede o limite de 5 MB.')
    data = file_obj.read(MAX_IMPORT_FILE_SIZE + 1)
    if len(data) > MAX_IMPORT_FILE_SIZE:
        raise TollImportError('O arquivo excede o limite de 5 MB.')
    return data


def build_preview(trip, file_bytes, user):
    text = extract_text(file_bytes)
    result = parse_extract_text(text)
    return build_preview_from_result(trip, result, user)


def _trip_vehicle_plate(trip):
    trip_vehicle = getattr(trip, 'tripvehicle', None)
    plate = trip_vehicle.vehicle.plate if trip_vehicle else None
    if not plate:
        raise TollImportError(
            'Cadastre a placa do veículo da viagem antes de '
            'importar o extrato.'
        )
    return plate


def _window(trip):
    return trip.start_datetime, trip.end_datetime or timezone.now()


def _normalize_description(description):
    return ' '.join(description.split())


def _row_hash(plate, passage, description, amount):
    raw = (
        f'{plate}|{passage.isoformat()}|'
        f'{_normalize_description(description)}|{amount}'
    )
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def build_preview_from_result(trip, result, user):
    plate = _trip_vehicle_plate(trip)
    start, end = _window(trip)
    warning = bool(
        result.filter_plate and result.filter_plate != plate
    )
    existing_hashes = set(
        Toll.objects.filter(trip=trip, import_hash__isnull=False)
        .values_list('import_hash', flat=True)
    )
    manual_tolls = list(
        Toll.objects.filter(
            trip=trip, source=TollSource.MANUAL, import_hash__isnull=True
        )
    )
    tolls = sorted(
        (row for row in result.rows if row.passage_datetime is not None),
        key=lambda row: row.passage_datetime,
    )
    non_tolls = [
        row for row in result.rows if row.passage_datetime is None
    ]
    rows = []
    ignored = []
    seen_hashes = set()
    checked_total = Decimal('0.00')
    for index, row in enumerate(tolls):
        in_window = start <= row.passage_datetime <= end
        digest = _row_hash(
            row.plate, row.passage_datetime, row.description,
            abs(row.amount),
        )
        reason = None
        checked = True
        if row.plate != plate:
            reason = 'placa diferente da viagem'
            checked = False
        elif warning:
            reason = 'placa do extrato difere do veículo'
            checked = False
        elif not in_window:
            reason = 'fora da janela da viagem'
            checked = False
        elif digest in existing_hashes:
            reason = 'já importado'
            checked = False
        elif digest in seen_hashes:
            reason = 'duplicado no extrato'
            checked = False
        seen_hashes.add(digest)
        if checked and any(
            abs((toll.datetime - row.passage_datetime).total_seconds()) <= 60
            and toll.amount_spent == abs(row.amount)
            for toll in manual_tolls
        ):
            reason = 'possível duplicado registrado manualmente'
            checked = False
        if checked:
            checked_total += abs(row.amount)
        rows.append({
            'index': str(index),
            'plate': row.plate,
            'datetime': timezone.localtime(row.passage_datetime).strftime(
                '%d/%m/%Y %H:%M'
            ),
            'passage': row.passage_datetime.isoformat(),
            'description': row.description,
            'amount': f'{abs(row.amount):.2f}',
            'hash': digest,
            'checked': checked,
            'reason': reason,
        })
    for row in non_tolls:
        if 'Recarga' in row.description:
            reason = 'recarga (não é pedágio)'
        elif row.amount < 0:
            reason = 'débito sem assinatura de pedágio'
        else:
            reason = 'crédito não reconhecido'
        ignored.append({
            'description': row.description,
            'amount': f'{abs(row.amount):.2f}',
            'reason': reason,
        })
    return {
        'trip_id': trip.pk,
        'user_id': user.pk,
        'filter_plate': result.filter_plate,
        'summary_toll_count': result.summary_toll_count,
        'summary_toll_total': f'{result.summary_toll_total:.2f}',
        'filter_plate_warning': warning,
        'rows': rows,
        'ignored': ignored,
        'checked_total': f'{checked_total:.2f}',
        'checked_count': sum(1 for row in rows if row['checked']),
    }


def sign_preview(preview):
    return signing.dumps(preview, salt=PREVIEW_SALT, compress=True)


def load_preview(trip, user, signed_payload):
    try:
        preview = signing.loads(
            signed_payload, salt=PREVIEW_SALT,
            max_age=PREVIEW_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired:
        raise TollImportError(
            'A prévia expirou. Importe o extrato novamente.'
        )
    except signing.BadSignature:
        raise TollImportError(
            'A prévia é inválida. Importe o extrato novamente.'
        )
    if preview.get('trip_id') != trip.pk:
        raise TollImportError('A prévia não pertence a esta viagem.')
    if preview.get('user_id') != user.pk:
        raise TollImportError('A prévia pertence a outro usuário.')
    return preview


def confirm_import(trip, user, signed_payload, selected_indexes):
    """Create the selected tolls atomically, revalidating everything.

    The import hash is the anti-reimport key: rows whose hash already
    exists in the database are skipped, never duplicated. Identical rows
    inside the same batch may be created (the field has no unique
    constraint); a future reimport skips them all — the check uses
    existence, not counting.
    """
    preview = load_preview(trip, user, signed_payload)
    plate = _trip_vehicle_plate(trip)
    start, end = _window(trip)
    batch_id = uuid.uuid4()
    selected = set(selected_indexes)
    existing_hashes = set(
        Toll.objects.filter(trip=trip, import_hash__isnull=False)
        .values_list('import_hash', flat=True)
    )
    created = 0
    skipped = 0
    with transaction.atomic():
        for row in preview['rows']:
            if row['index'] not in selected:
                continue
            passage = datetime.fromisoformat(row['passage'])
            if row['plate'] != plate or not (start <= passage <= end):
                continue
            digest = row['hash']
            if digest in existing_hashes:
                skipped += 1
                continue
            Toll.objects.create(
                trip=trip,
                location=row['description'],
                amount_spent=Decimal(row['amount']),
                datetime=passage,
                source=TollSource.IMPORT,
                import_hash=digest,
                import_batch_id=batch_id,
            )
            created += 1
    return {'created': created, 'skipped': skipped}
