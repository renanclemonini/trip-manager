"""Synthetic extract text builders — mirror the real provider layout.

The real PDF, read by pypdf in plain mode, emits each transaction as a
marker line (date and time), the plate and the description (which may wrap
into several lines), followed by the value and the balance appended right
after the signature. These builders reproduce that shape with fictional
data.
"""

from decimal import Decimal

FILTER_PLATE = 'SYN-0A01'

EXTRACT_HEADER = (
    'Conectcar Teste\n'
    'Filtro de transações -\n'
    'Data inicial: 25/10/2026 às 00:00 Data final: 24/11/2026 às 23:59 '
    f'Placa: {FILTER_PLATE}\n'
    'Resumo de Transações\n'
    'Tipo de serviço: Recarga Pedágio Estacionamento Outros\n'
    'Quantidade: 3 16 0 1\n'
    'Total: R$ 150.00 -R$ 150.84 R$ 0.00 -R$ 9.90\n'
    'Transações\n'
    'Data do lançamento Veículo Descrição da transação Crédito Débito Saldo\n'
)

TRAILER = 'Valor aproximado dos tributos na prestação de serviço.\n'


def toll_text(
    *,
    launch='23/11/2026 - 23:41:01',
    plate=FILTER_PLATE,
    description=(
        'CONCESSIONARIA TESTE - PRAÇA ALFA SUL, 92+740, SP - 098 - '
        'Cat. 1 - 23/11/2026 23:40:38'
    ),
    value='6.90',
    balance='R$ 48.36',
    glued_value=False,
    glued_datetime=False,
):
    """Toll transaction text with its three tolerated signature variants."""
    if glued_value:
        suffix = f'-R$ {value} {balance}'
    else:
        suffix = f' -R$ {value} {balance}'
    if glued_datetime:
        description = description.replace('2026 ', '2026')
    return f'{launch} {plate} {description}{suffix}\n'


def recarga_text(
    *,
    launch='23/11/2026 - 21:54:58',
    plate=FILTER_PLATE,
    value='50.00',
    balance='R$ 67.53',
):
    return (
        f'{launch} {plate} Recarga Automatica cartao de credito final 9999 '
        f'R$ {value} {balance}\n'
    )


def plan_fee_text(
    *,
    launch='19/11/2026 - 18:10:29',
    plate=FILTER_PLATE,
    value='9.90',
    balance='R$ 42.30',
):
    return (
        f'{launch} {plate} Plano Completo - Quantidade de Veículos '
        f'11/2026 - 1 -R$ {value} {balance}\n'
    )


def build_extract_text(
    rows,
    *,
    summary_quantity='3 16 0 1',
    summary_total='R$ 150.00 -R$ 150.84 R$ 0.00 -R$ 9.90',
    trailer=TRAILER,
):
    header = EXTRACT_HEADER
    if summary_quantity is not None:
        header = header.replace(
            'Quantidade: 3 16 0 1', f'Quantidade: {summary_quantity}'
        )
    if summary_total is not None:
        header = header.replace(
            'Total: R$ 150.00 -R$ 150.84 R$ 0.00 -R$ 9.90',
            f'Total: {summary_total}',
        )
    body = ''.join(rows)
    return header + body + (trailer or '')


def toll_sum(rows):
    total = Decimal('0.00')
    for row in rows:
        marker = '-R$ '
        value = row[row.index(marker) + len(marker):].split()[0]
        total += Decimal(value)
    return total
