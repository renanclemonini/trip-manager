from django.conf import settings
from django.core.mail import EmailMessage

from reports.services import ReportDeliveryError


def send_report_email(*, pdf_bytes, filename, subject, body, to):
    """Send the report PDF as an e-mail attachment (RF16/RF17)."""
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
    )
    message.attach(filename, pdf_bytes, 'application/pdf')
    try:
        message.send(fail_silently=False)
    except Exception as exc:
        raise ReportDeliveryError(
            f'Falha ao enviar e-mail: {exc}'
        ) from exc
    return True
