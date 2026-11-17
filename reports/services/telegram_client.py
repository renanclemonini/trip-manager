import requests
from django.conf import settings

from reports.services import ReportDeliveryError

TELEGRAM_API_URL = 'https://api.telegram.org/bot{token}/sendDocument'


def is_telegram_configured():
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def send_report_telegram(*, pdf_bytes, filename, caption=''):
    """Send the report PDF through the Telegram Bot API (RF16/RF17)."""
    if not is_telegram_configured():
        raise ReportDeliveryError(
            'Telegram não configurado: defina TELEGRAM_BOT_TOKEN e '
            'TELEGRAM_CHAT_ID no ambiente.'
        )
    response = requests.post(
        TELEGRAM_API_URL.format(token=settings.TELEGRAM_BOT_TOKEN),
        data={'chat_id': settings.TELEGRAM_CHAT_ID, 'caption': caption},
        files={'document': (filename, pdf_bytes, 'application/pdf')},
        timeout=20,
    )
    if response.status_code != 200:
        raise ReportDeliveryError(
            f'Falha ao enviar pelo Telegram (HTTP {response.status_code}).'
        )
    return True
